# 远程 MCP 执行协议

## 连接与授权

本分支直接连接 `https://dev.yuanji.studio/api/agent/mcp/v2`，使用标准 Streamable HTTP MCP 与 OAuth。无需本地画布服务、bridge.token 或保持浏览器画布打开。由宿主完成授权发现、浏览器登录、PKCE 和令牌刷新；不索取或复制用户密码、Cookie、Access Token，不使用本地桥接替代授权。

首次连接按宿主提示打开插件配置的站点完成授权，确认账号和空间。后续任务、宿主重启和同一环境插件升级先复用宿主保存的连接，让宿主自动刷新令牌，不把每日 `/mcp`、退出重登、重装或重复添加服务器作为启动步骤。插件不自己保存或刷新用户令牌。通过标准 MCP `tools/list` 获取当前部署的工具及完整 inputSchema；不要调用旧本地适配器独有的 `canvas_status`、`canvas_describe_tools` 或 `canvas_list_projects`。若宿主已发现工具，直接读取其最新定义。使用 `listProjects` 返回的 `authorizationContext` 核对账号和空间；创建项目的回执也包含该字段。

工具不可用、未授权或权限不足时给出实际错误，不能使用过期工具目录冒充连接成功。项目与模型目录通过当前实际工具查询。

连接错误按 [账号连接与续期](../../../docs/oauth-connection.md) 处理：工具未注入不等于授权已失效；403 不要求重新登录；429、5xx、stream timeout 不清除连接。`invalid_client` 优先检查后端客户端注册是否仍存在及认证方法，`invalid_grant` 检查刷新凭据到期、撤销或轮换；向用户说明真实错误，不通过反复授权掩盖服务端异常。401 交给宿主标准刷新/重新连接流程，不读取宿主凭据文件或自行请求令牌。只有确认需要重新连接时才提示用户操作一次；任何请求失败后先核对原操作回执和状态，不能借重新连接重复创建、上传或付费生成。

## 参数与画布状态

标准 v2 工具参数按实时 inputSchema **平铺**传递，不包裹旧版 `payload`，不传本地 `clientId`。projectId/nodeId/elementId/assetId/fileId 原样使用各自读取接口返回的字符串；当前 v2 资源 ID 是十进制字符串，不转成 JavaScript Number，也不自行加密或解密。mentionToken、uploadId、generationRef 等标识原样保留，不从 workbench URL 推算 ID。版本号和其他字段遵循实际 Schema 的类型。

先检查实时 inputSchema：支持 brief 时，用 `getCanvasContext(detail="brief", includeSubjects=false)` 按游标定位节点（仅 ID、名称、类型、状态与关系，不含正文或生成参数，新后端默认最多 500 个/页（正常长度的 485 个节点可一次读完；旧部署可能仍是 100 个，以实时 Schema 为准））；需要正文预览时才用 `getCanvasOutline`。已知 nodeId/externalKey 时直接读对应节点。`getCanvasContext(detail="compact")` 仍含正文，最多 20 个/页；full 最多 5 个/页。`complete=false` 表示还没读完，不能因为当前页没出现目标就判定节点不存在。nextCursor 原样传回，项目、detail、nodeType、includeSubjects 保持一致；版本变化时从第一页重新读。响应上限 256 KiB；新后端 brief 超限时保留完整节点并自动分页，不截断名称。其他详情超限时减小 limit 或改用 getNodes 指定更少 fields，不能截断全文后覆盖原节点。只有需要完整画布快照或主体资产详情时才读取对应 context；保存回执用于同一版本的后续检查，不把大份 JSON 重复回显到对话。读取返回的 scope 必须覆盖修改范围；过滤快照不能当作完整画布。缺少字段不等于空值，不建立另一个可写 Film DSL 副本。

### 按需读取节点

先检查实时 inputSchema 是否已开放下列参数，插件升级不等于后端已发布：

| 本轮要做什么 | getNodes 读取方式 |
| --- | --- |
| 看标题、状态、内容概况、是否已有媒体 | `detail="brief"`，默认 `fields=["summary"]`；最多 20 个节点，正文只预览 60 字 |
| 本批生成门禁 | `detail="full", fields=["details","content","generationParams","subjects","media"]`；只取本批节点及真实依赖，保存回执运行 `--scope batch --nodes`；需要主体素材时补读相关素材节点，不遍历 full 画布 |
| 修改正文或提示词 | `detail="full", fields=["content","writeState"]`，只读目标节点；预览不能覆盖全文 |
| 核对模型、分辨率、音频开关 | `detail="full", fields=["generationSettings"]`，没有提示词和参考列表 |
| 检查或替换垫图 | `detail="full", fields=["generationParams","writeState"]`；需要主体展开素材时再加 subjects，不为查参考图顺带取正文、时间轴 |
| 看真实挂载的文件 | `detail="full", fields=["media"]` |
| 删除节点 | `fields=["deletion"]`，取得目标的删除摘要和影响范围 |

full 每批最多 5 个节点，长提示词通常一次只读 1 个。full 的 generationParams 不重复带 prompt；正文从 content 读。summary 的 directReferenceCount 是直接资源条目数，subjectReferenceCount 是主体绑定数量，都不能当作展开后的全部参考图片数。需要核对实际参考图上限时读取对应 generationParams/subjects。

旧后端没有 detail/summary/generationSettings 时，不发送未开放字段；用旧 fields 精读目标：查状态用 details，改正文用 content/writeState，查参考用 generationParams，需要什么才追加什么。仅在未开放轻量配置字段时使用 generationParams 核对模型。旧显式 fields 且省略 detail 的调用保持原有语义。不要把所有 fields 作为通用读法，也不在每个检查步骤反复取同一份长提示词。

主体读取仍使用 `getCanvasContext`：`subjects.subjectTypes` 是当前可用分类（含已有“其他”分类），`subjects.elements` 是正式主体资产；`detail="full"` 返回 assets、fileRefList、referenceLayout，可传 subjectId 精读或 subjectQuery 搜索。结果最多 100 个主体，缺少目标时精读或搜索，不推断主体不存在。character/environment/product/custom 分组中的 id/subjectNodeId 是画布节点，elementId 才是主体资产 ID；不要互换。

引用优先用读取结果的 mentionToken；返回 mentionId 时按工具说明组成 `[@mentionId]`，重名时不用裸名称。先确认目标已应用到当前画布且关联正式主体。当前已核验的 v2 createNode/updateNode 不接收 `generationParams.elementBindings`：在 content 中写入真实 token，由服务端解析绑定，再回读核验。读取结果里的 elementBindings、referenceMode、selectedAssetIds 不自动等于可写参数；只有实时写入 Schema 明确开放时才能传。需要选素材子集时先查实际能力，不能假称已经选定；不要自行拼接、转换主体 ID 或把 fileId 当成 assetId。

正式主体使用 createSubject 创建；普通 `createNode(type="element")` 只建容器，不据此认定已登记主体库。createSubject 返回 elementId、subjectNodeId、generationNodeIds 和 assetTaskPlans；保存各 ID 的职责，按 [主体创建](subjects.md) 核验关联。建档不扣费，生成仍走 calculateCredits → 已有费用授权核验 → generateNodes。成功图片由服务端归档到主体素材，随后精读主体核验；不要因待生成而重建主体。基础三视图字段为 threeView（triView 是旧别名），不传当前 Schema 未开放的 look 等字段。

写入按实时定义提供 `idempotencyKey`、`expectedNodeStates`、`expectedDeletion`、`expectedSourceFiles` 等所需字段。摘要来自当前快照，不能凭空补造；冲突后先重新读取并检查用户改动。相同操作使用稳定幂等键，参数改变视为新操作。工具失败或超时先查原状态，不自动重复写入或付费生成。

### 参数不可见与失败恢复

- 宿主只展示 `unknown & unknown` 或无字段对象时，不能据此判定远端没有该能力。优先通过宿主提供的工具发现功能读取同一连接的完整 inputSchema；不要假造工具名，也不要用画布写入来试探字段。仍无法取得定义时，保留待执行内容并说明缺少哪个工具的参数定义，本地示例仅作核对线索，不代替实时契约；不为查 Schema 索取令牌或绕到旧接口。
- 调用前检查顶层必填项、枚举与额外字段限制。createSubject 当前必填 projectId、idempotencyKey、kind、label；scene 还必填 sceneDescription。`kind` 当前只接受 character/scene，道具与自定义分类通过 scene 分支的 subjectType/subjectTypeId 选择，不传 kind=prop/custom。
- `invalid_arguments`：记录工具名、请求字段、code、message、traceId（如有），对照实际 Schema 定位缺失或多传字段，再修正；不要随机删模型、参考文件或依次猜 subType。请求明确被拒绝且原因已定位后可修正重试；同类错误修正后仍出现，停止该写入并报告证据，继续无依赖工作。
- “三视图生成需要基础形象”：检查 frontView 计划或真实可复用的演员素材。只有 threeView.content，或在文字里写“沿用已有图”，都不构成图像绑定；具体复用与上传路径见 [主体创建](subjects.md#创建角色结构)。
- “正式主体不存在或已删除”：逐个回读当前提示词引用的节点及主体，核对项目、elementId、主体记录和媒体。关联为空或 0 的 element 容器不是正式主体；不把节点 ID 换名当作主体 ID，也不修改数据库补关联。确需建档时先排除重复，再在授权范围内 createSubject，验证成功后更新受影响引用，保留旧素材。记录完整 traceId，不能把这种错误当作图片生成失败而重新扣费。

## 生成与交付

1. 用户明确要求生成后，读取节点、参考文件及实时模型配置，准备实际生成参数。
2. 未指定时默认 **Creatly Sigma 2.5 Sunburst、2K**。当前模型标识为 `gpt-image-2.5-sunburst`、function 为 `gpt25_sunburst`、modelConfigId 为 `image_gpt25_sunburst`、resolution 为 `2k`；以当前模型目录验证可用性。用户明确指定的模型、分辨率、质量和数量优先。默认模型不可用时说明缺口，不擅自换模型。
3. 节点配置、费用估算和生成请求参数保持一致。每批图片或视频生成前，在当前对话中说明目标节点、模型、数量与预计积分，取得用户明确同意；同一批已确认内容不重复询问。确认后直接调用 `generateNodes`，将用户同意的本批总积分作为 `maxCredits`，无需再打开画布或网页确认费用。报价超过上限、生成范围改变或失败重试时，回到对话重新确认，不擅自增加额度或重复提交。仅提高同一批的费用上限时沿用原幂等键；生成参数或节点范围改变时使用新键。若旧部署仍返回网页费用确认，说明需要更新后端，停止提交，不伪造确认凭据。
4. 提交后查询原任务，回读非空 frameFiles/videoFiles/audioFiles 等实际媒体；受理、生成终态、挂载和视觉验收分别判断。
5. 保留成功结果。用户指定的待处理节点保持原状，不因默认参数改变而重生成。没有像素或音频证据时，不宣称质量验收通过。
6. 使用返回的 `projectUrl` 交付画布链接。精简目录不包含 previewAssemble、浏览器交接或 Film DSL 工具。


## 角色参考图（强制）

凡是画面中出现已建角色的 Frame 或 Video，生成前必须垫该角色的参考图来固定身份，没有例外：

1. 先有角色图：角色主体至少 3 个视角（正视图 + 侧/背视图或三视图）必须已经生成并回读到非空 frameFiles。角色图还没生成时，先生成角色图，不生成依赖它的分镜或视频。用户提供了真人照片或剧照时，先用这些照片垫图生成角色正视图，再用正视图垫分镜。
2. 用主体提及锁定，不连线：凡是涉及主体（角色、场景、色卡等）的 Frame 和 Video，都在提示词里用 `[@主体名]` 提及（画布保存后可能显示为 `[@主体ID]`，两种写法等价），系统据此建立正式 elementBindings 并带入主体素材；只有历史画布主体使用 mentionElementIds。主体不写进 `parentIds`，也不把主体图重复写进 referenceResources。Video 的 referenceResources 只放本镜分镜、补拍图和音频，提示词里原来的【图N】角色行改写成「[@角色名]：锁定的特征」，其余【图N】按新顺序重新编号。
3. 每个出场角色各垫一张：双人或多人镜头要把每个出场角色的正视图都垫上；只露背影、肩膀或手的角色同样要垫，以锁定服装与发型。
4. 提示词写明引用职责：说明每张参考图锁定什么（脸、发型、帽子、服装），并写明参考图不决定构图。
5. 生成前回读核对：对本批目标用 `getNodes(detail="full", fields=["content","subjects"])`（旧部署用已开放的相同 fields）检查提示词都用 `[@角色名]` 提及了全部出场角色；缺任何一个就先补齐，不提交 generateNodes。
6. 改角色图后传播：角色正视图重新生成后，列出所有引用它的分镜和视频，按用户确认的范围重生。

## 视频参考素材（全能参考，强制）

视频默认 **Seedance 2.5、480p、开启音频**。先用实时 `listGenerationModels(scene="video", detail="compact")` 定位模型，再带目标 `modelIds` 精读 full 确认 480p/音频能力；新建视频显式写入 `generationParams.resolution="480p"`、`generationParams.bgm=true`。用户明确选择优先，不覆盖既有已确认配置；不支持默认组合时说明缺口，不擅自换模型或提高分辨率。估价前、生成前只对本批目标用 `getNodes(detail="full", fields=["generationSettings"])` 回读核对模型、分辨率和音频开关（旧部署按上面的兼容方式读取），确保节点、估价和生成参数一致。

视频默认走全能参考（`videoType="referenceImg"`）：只垫资产，镜头关系写进提示词。

1. 垫什么：
   - 人物：每个出场角色至少 3 个视角（正视图 + 侧视图 / 背视图，或正视图 + 三视图）。角色主体里不足 3 个视角时，先补齐再出视频。
   - 道具：本镜出现、需要跨镜一致的关键道具，各一张或多角度。
   - 场景：本镜所在场景的空间图，覆盖本镜机位朝向（门窗、吧台、桌椅等地标可见）。
   - 站位图：每个场景一张站位图（俯视或大全景），标出每个人的位置、朝向、关键道具和摄影机轴线；站位在场景中途改变时（如起身、离场），按状态各出一张，标题写成 `站位｜<场景>｜<状态>`。
2. 不垫什么：正反打、过肩、补拍等镜头画面不作为视频参考；正反打、对白覆盖、机位切换全部写在提示词里。只有用户明确要求锁定构图或首尾帧时，才额外垫本镜分镜图（此时改用图片优先路线，并在回复中说明）。
3. 有几张垫几张：在模型上限内尽量把上述资产垫全。上限以 `listGenerationModels(scene="video", modelIds=[...], detail="full")` 返回的 `scenarioCapabilities.multi_graph.rules.inputs.referenceImages.max` 为准（元极 Seedance 2.5 当前为 30 张图、10 条音频），不按经验值写死；超出上限时按「本镜出场人物 → 站位图 → 场景 → 道具」的优先级取舍。
4. 怎么传：角色、场景、道具、色卡等主体在提示词里 `[@主体名]`，不连线；站位图和主体里没有的补充视角写进 `referenceResources`，不连线。生成前回读，核对实际传入张数与提示词里的【图N】编号一致；`@` 只带入主体主图时，把其余视角补进 referenceResources。
5. 提示词里写清正反打：参考职责之后写「执行与连续性」，明确轴线（谁在画面左、谁在右）、屏幕方向、每个镜头块的景别与机位（如「正打，越过汤米右肩拍亚瑟」），镜头块之间独立一行 `HARD CUT`。

## 强制关卡与用户自由度

下面几项是默认强制关卡，不满足就不提交对应的 generateNodes：

- 分镜前：色卡主体已有图片。
- 视频前：本镜出场角色各有至少 3 个视角；有场景图和对应状态的站位图；提示词 `[@]` 了全部出场主体，并写清轴线和正反打；每个镜头的物料已放进本镜组。
- 准备提交局部生成时：用 getNodes 精读目标、所属组、入向依赖、referenceResources.sourceNodeId 和 subjects.references.elementNodeId 对应节点，以及本批出场角色/所用色卡的必要素材；fileRef 直传的引用没有 sourceNodeId 时不虚构画布节点。依赖按需选 fields：组/Shot 只用 details，参考图片加 media，音频加 content，主体加 subjects；不顺带读取无关素材的完整提示词。保存同一项目、同一版本的真实回执为 {"reads":[回执1,回执2,...],"contextNodeIds":[本批色卡等真实节点ID]}，执行 `scripts/film_gate_check.py batch.json --scope batch --nodes <本批节点ID>`。只补读缺少的本批字段/依赖，不收齐无关节点；已有 ID 时不先读画布目录，同一版本回执复用。局部生成、修改或移除垫图都不触发全画布 full 分页。只有用户要求整片审查时，才按 nextCursor 收齐 full 的全部页为 {"pages":[...]}，执行 project 门禁。门禁用法见 [脚本说明](../../../scripts/README.md)；有未豁免的 FAIL 或退出码 2 不提交 generateNodes。读取失败或主体素材未核验不等于检查通过，缺少素材详情时按相关范围补读，不宣称已验证；用户明确豁免时才跳过对应关卡。本批范围与费用已在对话中确认。

用户可以对任一关卡明确说「跳过」或「这次不用」，照做即可（运行门禁时用 `--skip <关卡名>`）：在回复里点明跳过了哪一项、可能的影响，不反复劝阻。风格、景别、镜头数量、时长、垫图多少、是否先出分镜图等创作选择由用户决定，skill 只给默认值和建议，不替用户做硬性决定。

## 色卡（强制，分镜前完成）

分镜图的色调由色卡控制。生成任何分镜 Frame 之前，先为本幕（色调不同的 Scene 各一张）生成色卡图，用户认可后再出分镜：

1. 顺序：风格参考 / 剧照复刻 → 角色与场景主体 → **色卡** → 分镜 Frame → Video。没有色卡时不提交分镜 Frame 的 generateNodes。
2. 色卡内容：一张 16:9 图片，按暗部、中间调、高光三档排列 8–10 个色块，每块标注 HEX；来源是已认可的参考剧照或已定稿画面的真实取色（按亮度分档取色），不要凭空编色。可以本地取色后拼图上传，也可以在画布上用图片模型生成色卡 Frame。
3. 做成正式色卡主体：先查已有主体与 subjects.subjectTypes；用 `createSubject(kind="scene", subjectType="custom", subjectTypeId=真实分类ID)` 在适合的“色卡”或“其他”分类建档，提供 projectId、idempotencyKey、label、sceneDescription。需要生成计划时按 Schema 加 imagePrompt；已有色卡图片则走真实文件挂载能力，不付费重生。排在分镜组之前，与角色主体同一排。不能用无关联的 `type=element` 空框代替；分类或文件归档能力不足时记录待绑定，继续不依赖它的工作。
4. 引用方式：每个分镜 Frame 和 Video 的提示词都用 `[@色卡]` 提及色卡主体，不连线，也不再把色卡图写进 referenceResources。
5. 生成前用 getNodes/完整主体读取核对：色卡应用节点关联有效 elementId，正式主体 assets 中有可用图片，每个待生成节点的提及都解析到预期主体。子 Frame 有图片不等于图片已归档到主体；正式主体素材为空时不得宣称色卡锁定成功。
6. 提示词：加一行「【色卡】[@色卡] …」，写明它只锁定色调、明暗比例和饱和度，不决定构图、人物和道具，并抄录关键 HEX（如「暗部 #0F0D0A–#282017，中间调 #312C25–#6A523A，高光只在光源附近 #937151–#E4C59F」）。
7. 换色调（如日景转夜景、换场景）时新建对应色卡，不沿用旧色卡。

## 画布分组与排版（强制）

生成分镜图和视频时，必须用组框住每个镜头的相关物料，先建组、再生成，不把节点散放在画布上。

- 每个 Shot 建一个 `type=group` 的组（`content` 不能为空，可填组名），把该镜的分镜图、补拍图、音频和视频的 `parentNode` 设为该组；Shot 与 Scene 的结构归属来自 `parentIds` 连线和 nodeIndex，改 parentNode 不影响结构。
- 风格参考（剧照复刻）单独建一个组；色卡、角色、场景做成主体，放在同一排。过时版本仅在用户明确授权删除时使用 deleteNodes 清理；单纯整理布局时保留。
- `position` 相对于 `parentNode` 计算：组内子节点写相对坐标（建议从 (20, 46) 起，给组标题留出空间），组本身写绝对坐标。通过 MCP 写入不会自动适配尺寸，必须给组写 `dimensions`，否则只显示 284×160。
- 组内固定列：分镜图 → 音频列（每条 260×56，间距 72）→ 视频 → 补拍图，音频和图片不重叠。站位图放在对应场景主体旁或「风格参考」组里，跨镜复用。
- 连线只保留结构和生成必需的：Frame → 本镜 Shot；Video ← 本镜 Frame（归属用）、音频。所有主体都不连线，只在提示词里 `[@主体名]`。


### 空间利用与接近正方形的布局

用户偏好：整个工作区尽量接近正方形，既不要过宽，也不要过高；以素材可读、分区清楚和空间利用率为前提，不为凑方形留下大块空白。

- 先分页读完整大纲，按需精读现有分组、布局和真实引用，记录整理前状态；不为整理布局顺带读取全部提示词和时间轴。区分剧本与主体资料、按剧情排序的制作段落、分镜、参考开发、配音及剪辑素材；同一段的材料集中，当前制作区易于找到。
- 根据实际节点宽高和数量选择行列；整体包围框的宽高尽量接近，段落按左到右、上到下的阅读顺序换行。组内沿用分镜、音频、视频、补拍的语义顺序，材料较多时分行；不强行排成一条横线或竖线。
- 先计算组内节点的相对坐标，再根据子节点边界确定组尺寸，最后排组。为标题、媒体卡片和音频控件留出空间，统一同类卡片尺寸、行距与组间距；不裁切或改变媒体本身的比例。
- 优先利用相邻空位；新增内容放在相关段落附近，并在必要时重排相邻行列，避免每次向最右或最下追加。整体方形只是偏好，不以大量留白或缩小到无法辨认为代价。
- 单纯整理布局只调整位置、显示尺寸和必要的容器归属；保留提示词、主体绑定、素材文件、时间轴、生成配置和真实依赖连线。旧版本按现有归属集中摆放，删除仅在用户明确授权的范围内进行。
- 保存后回读核对节点数量、归属及写入结果，检查同层重叠、子节点越界、标题遮挡和整体宽高；能打开画布时再做视觉检查。接口未返回坐标时，不把计划图当作实际界面截图，明确验证边界。

## 本地参考素材上传

先通过实时工具目录确认 `upload` 已部署。使用插件 [本地上传脚本](../../../scripts/README.md)：本机计算文件元信息 → `upload(action="prepare")` → 本机按返回 URL/headers 直传原文件 → `upload(action="complete")` → 用返回的真实 `fileRef` 绑定节点并读回。支持图片、视频、音频和文本（txt/md）。媒体作为生成输入时用 referenceResource 绑定；文本只返回 fileRef，读取正文后用 createNode(type="text", content=正文) 直接展示，不把文本文件当图片参考。不通过浏览器交接完成上传，不把本地路径冒充远程资源 ID，不把 Base64 放入工具参数。签名 URL 只存私有临时文件，上传或登记超时先核对原 uploadId，不能自动重投或付费生成。宿主没有本地文件传输能力时明确说明缺口。

## 精简工具目录

当前工具包括 listProjects、projectCreate、getCanvasContext、getCanvasOutline、getNodes、createNode、updateNode、deleteNodes、createSubject、upload、listGenerationModels、listSystemVoices、calculateCredits、generateNodes、getGenerationStatus；数量与能力以实时 tools/list 为准，不把这份清单当作连接成功证据。createSubject 的角色、道具、自定义分类用法见 [主体创建](subjects.md)。删除一个或多个节点都使用 deleteNodes，在用户指定的删除范围内直接执行，无需网页确认或 confirmOperation。先读取目标 deletion 观察并传入 expectedDeletions，重试沿用原参数及幂等键。

节点连线使用 createNode/updateNode 的 parentIds：给 B 设置 parentIds=[A的ID] 建立 A → B。该字段替换完整输入列表，追加时保留已有 ID，[] 清空；parentNode 仅表示嵌套归属。需要指定参考图、首尾帧或音视频用途时同步设置 generationParams.referenceResources。

视频 generationParams.bgm 是网页上的「音频」开关，决定是否生成声音（环境声、音效、对白），不是背景音乐开关；需要台词或音效的视频必须为 true，不要为了「不要配乐」传 false——不要配乐写进提示词（如「无背景音乐」）。新后端在设置 model 而不传 bgm 时按模型配置默认值（Seedance 2.5 为开）；提交前用 getNodes 读回 bgm 核对。

已上传的图片、视频、音频需要作为画布上的节点自身素材时（效果同在画布拖入上传），用 createNode(nodes=[{clientRef,type,label,fileRef:{id:上传回执.fileRef.id}}]) 新建，content 可省略：图片用 type="frame"、视频用 type="video"、音频用 type="audio"，文件类型须与节点类型一致；已有节点用 updateNode(nodes=[{nodeId, fileRef:{id}}]) 替换当前文件，多个节点可一次批量挂载，按最新画布提供 expectedNodeStates 和幂等键。fileRef 仅传 id；不重传已有文件，不调用 generateNodes 或 TTS，不扣费；挂载后按读取策略用 getNodes 的 media 字段核对目标文件；只有旧部署缺少此字段时，才在相关 context 中检查 frameFiles/videoFiles/audioFiles。只放进 referenceResources 或连线不会把文件挂成节点自身素材，画布上也看不到。以实时 Schema 中 fileRef 的节点类型为准：旧后端只允许 audio，需要先部署更新。

视频的输入按「视频参考素材（全能参考，强制）」准备：主体 `[@主体名]`，站位图和补充视角写 referenceResources，音频按顺序连线；正反打、补拍画面不作为视频参考。跨镜头参考时显式加入本镜 Shot 并传 nodeIndex，人物图本身无需 Shot。多图模式使用 generationParams.videoType="referenceImg"；需要精确编号时按提示词顺序写 referenceResources，图片用 IMAGE/REFERENCE，配音用 AUDIO/SOURCE_AUDIO，分别对应图1…和音频1…。不要再将“一张图/一条音频”或“人物/补拍图不能连视频”当成通用限制。生成仍需核对具体模型的素材数量、格式与时长要求。首尾帧 keyframe 模式与多图 referenceImg 模式区分使用。

概要/详情分层依赖后端部署。若实时 inputSchema 的 detail 尚不支持 brief，使用现有 getCanvasOutline 定位，再用 getNodes 按 ID/字段读取；不要发送未开放的字段，不把超时解释成节点不存在，也不反复重试 full 全量。
