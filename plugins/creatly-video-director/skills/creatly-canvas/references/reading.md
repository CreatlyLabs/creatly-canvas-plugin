# 画布读取

工具参数和上限先核对实时 inputSchema。以下记录对应当前 v2；未开放的字段不发送。

## 先目录，后目标详情

- 未知节点 ID：`getCanvasContext(detail="brief", includeSubjects=false)` 返回简要目录，含 ID、名称、类型、状态与关系，不带正文或生成参数。当前默认最多 500 个/页；256 KiB 响应上限可能使一页自动缩小，旧部署也可能只有 100 个，以回执为准。
- 已知 nodeId/externalKey：直接 `getNodes`，无需先拉目录。看概要用 `detail="brief"`，默认 summary，最多 20 个节点，正文只是 60 字预览。
- `getCanvasOutline` 用于需要正文预览的大纲；旧部署不支持 brief 时也可用它定位。`getCanvasContext(detail="compact")` 含正文，最多 20 个/页；full 最多 5 个/页。仅在确需完整快照时遍历 full。
- `complete=false` 表示仍有后续页；nextCursor 原样传回，项目、detail、nodeType、includeSubjects 与初始范围保持一致。版本变化从第一页重读，不混合版本。
- 保存并复用同版本回执，不把大份 JSON 反复回显。过滤结果不能作为全画布，未返回字段不能当作空值或节点不存在。

## 按工作选择 getNodes 字段

| 工作 | 读取 |
| --- | --- |
| 标题、状态和媒体概况 | `detail="brief", fields=["summary"]` |
| 正文或提示词修改 | `detail="full", fields=["content","writeState"]` |
| 模型、分辨率及音频开关 | `detail="full", fields=["generationSettings"]` |
| 检查或替换参考素材 | `detail="full", fields=["generationParams","writeState"]`，按需加 subjects |
| 节点当前实际文件 | `detail="full", fields=["media"]` |
| 容器、位置和依赖 | 读取实时 Schema 对应 details 等字段 |
| 删除前检查 | `fields=["deletion"]`，取得实际删除摘要和影响范围 |

full 每批最多 5 个节点，长正文通常一次只读一个。generationParams 不重复返回 prompt，正文从 content 读。不能用截短预览覆盖全文。summary 的直接引用数量与主体绑定数量不等于展开后的图片总数；核对模型参考限制时再读目标 generationParams/subjects。

旧部署不支持 summary/generationSettings 时，以已开放的 details、content、generationParams、media 等字段精读；不要每次都读取所有 fields，也不为局部改动补全无关节点。

主体详情通过 `getCanvasContext` 的 subjects 读取，按当前 Schema 的 subjectId/subjectQuery 定位。subjectTypes 是可用分类，elements 是正式主体资产；full 可返回 assets、fileRefList 和 referenceLayout。结果最多 100 个主体，目录未出现目标时先搜索或精读。elementId 是正式主体 ID；subjectNodeId 和分组中的 id 是画布节点，不能互换。

## 给用户定位链接

面向用户的节点回执使用宿主支持的 Markdown 富文本，隐藏地址、突出节点名称。节点链接打开对应画布后会自动居中、选中目标，并短暂高亮约 3 秒。

### 用户看到的格式

- 单个节点：`[镜头 03｜开场](https://example.com/node) · 视频 · 已完成（13 秒）`。示例地址仅演示语法，交付时替换为真实回执中的 `nodeUrl`；整条内容直接渲染，不放进代码块或行内代码。
- 多个节点：每行一个节点，用短列表；需要比较时用「节点｜类型｜状态/时长」表格，节点单元格仍是可点击名称。只交付本次目标，不贴整份画布目录。
- 链接文字优先采用回读后的真实显示名，或用户明确指定的镜头名；不要写「点击这里」「链接」或用密文 ID 代替已有名称。确实没有名称时，用「视频节点（节点 ID）」等类型与原样 ID 作为链接文字，不编造已保存的标题。表格内的名称含 `|`、`[]` 等 Markdown 保留字符时转义显示文字，不修改原节点名称和地址。
- 类型写图片、视频、音频、文本或分组。状态按真实回执写「已创建，待生成」「生成中」「已完成」「失败」等；时长、费用等仅在回执已确认且有用时附上，缺少的字段直接省略；状态未返回时写「状态待确认」或省略，不猜测完成。
- 受理不等于出片；任务成功但尚未挂载时写「生成成功，待挂载」。生成中或失败的节点仍可给定位链接，并简要说明待处理问题；链接可打开不代表生成或内容验收已通过。
- 不直接展示裸 URL、反引号包裹的长地址、整段 JSON 或一串无标题的链接。用户明确要求复制原始链接或排错数据时，再按其要求提供。

### 链接来源与回退

- `getNodes`、`createNode`、`updateNode` 的节点结果可含 `nodeUrl`；生成受理和状态回执提供 `nodeLinks[].nodeUrl`，每个节点状态中也可含 `nodeUrl`。按节点 ID 对应取值，不把一个节点的链接配给另一个节点。
- 已拿到链接就直接复用，不为美化交付再次遍历画布。目标节点尚无定位回执且本次尚未精读该节点时，仅按其 ID 读取一次 `getNodes(detail="brief")`；如果当前已经是目标 getNodes 的读取结果却没有链接，直接回退，不再补读。
- 旧服务仍无 `nodeUrl` 时，用 Markdown 项目链接加可识别的节点名称与 ID，例如 `[打开项目](https://example.com/project)，查找「镜头 03」（节点 ID：…）`，示例地址须替换为真实 `projectUrl`，并说明暂不能直接定位；不要自行拼接链接或持续重试。
- 保留服务端返回的完整地址、查询参数和环境，不从 MCP 明文 ID 推算网页密文 ID。链接沿用网站登录与项目权限，不是免登录授权；节点已删除时如实说明，不能仍称可定位。
