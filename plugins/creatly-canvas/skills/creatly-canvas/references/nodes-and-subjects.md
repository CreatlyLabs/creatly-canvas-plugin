# 节点、主体与素材

## 写入和分组

createNode/updateNode 只传实时 Schema 开放的字段。根据当前回执提供 idempotencyKey、expectedNodeStates、expectedSourceFiles 或实际要求的校验字段，不能凭空构造摘要。相同操作复用原幂等键，参数或范围改变时按工具契约处理。生成中的节点先查询原任务，避免覆盖正在执行的输入。

自定义显示名使用实时 Schema 的名称字段（当前为 label），不把提示词、content 或本地文件名当作已保存的标题。用户指定分组时，parentNode 传实际分组 ID；parentIds 不决定分组归属。写入后从回执或按目标 ID 的 getNodes 回读核对 label 与 parentNode；标题仍是「视频」等默认值或分组未保存时，说明或修正实际差异后再交付，不声称已正确命名、归组。

`type="text"` 的 content 是直接展示的正文，不是要执行的生成提示词。创建后读回正文；不为显示文字调用 generateNodes。若旧服务只保存到 prompt，报告部署差异，不用付费文本生成弥补。

parentNode 表示容器嵌套，parentIds 表示输入依赖：给 B 设置 parentIds=[A的ID] 形成 A → B。parentIds 替换完整列表；追加时保留原 ID，[] 才是清空。分组的子节点 position 相对容器，组本身使用其父级坐标；组尺寸按实际子节点边界写 dimensions。整理布局保留正文、素材、依赖和参数，只修改用户指定范围。新建批次和整理布局先按[二维紧凑排版](layout.md)规划节点及分组边界，优先让整体宽高接近，不能只固定 x 不断增加 y，或只固定 y 不断增加 x。

删除使用 deleteNodes。先取得目标 deletion 摘要，按实时 Schema 传 expectedDeletions 等要求；执行用户明确授权的范围，重试保持原参数与幂等键。创建、修改、移动和删除后回读核对实际结果。

## 默认创建图片

人物、角色、场景、物品、道具和设定图默认使用普通图片节点（当前类型为 `frame`），按实时 Schema 设置标题、提示词、参考素材及生成参数。用户授权生成时，按[媒体生成](generation.md)估价并提交；有成品时直接挂载真实文件。创建普通图不调用主体查询、创建、资产计划或绑定工具，不因为“人物设定”“角色图”或“物品图”而新建主体。

## 正式主体（仅用户明确要求时）

仅当用户明确要求创建主体、建立主体库记录或添加到主体库时，才使用 `createSubject` 及必要的主体建档、资产计划工具。用户明确要求引用已有主体时可按需查询和引用，不能据此自行创建新的主体。

普通 `type="element"` 容器不等于主体库记录。正式主体用 createSubject；先查已有主体避免重复。当前必填 projectId、idempotencyKey、kind、label；kind 为 character/scene，scene 还需要 sceneDescription。道具和自定义分类通过 scene 的 subjectType/subjectTypeId 选择，不自行传 kind=prop/custom。

保存返回的 elementId、subjectNodeId、generationNodeIds 和 assetTaskPlans，各自用途不互换。按用户要求创建基础形象或其他计划；基础三视图字段为 threeView，旧 triView 别名和 look 等字段是否可用只看实时定义。三视图计划需要真实基础形象绑定，文字写“沿用已有图”不等于传入图像。用户要求横版四视图时，使用[近景＋全身三视图模板](character-four-view.md)，默认按当前 Schema 写入图像节点；仅在用户明确要求主体建档时才使用主体资产计划，不新增 fourView 字段。建档和图片生成分别核对；待生成时不重建主体。

引用优先使用读取结果的 mentionToken；只返回 mentionId 时按工具说明组成 token，重名不靠裸名称猜。先确认应用节点关联有效 elementId，主体 assets 中有实际文件。当前 v2 写入不接受 generationParams.elementBindings：在 content 中使用真实 token，让服务端解析后读回检查。读取结果包含的 referenceMode、selectedAssetIds 等字段不自动成为可写参数。

“正式主体不存在或已删除”时核对项目、应用节点、elementId、主体记录与媒体；空关联容器不是有效主体，不通过换 ID、改数据库或重复付费生成排错。

## 上传文件的两种用途

- **节点自身媒体**：createNode 新建时传 fileRef:{id:真实文件ID}；图片 type=frame、视频 type=video、音频 type=audio，content 可省略。updateNode 可替换目标当前文件。fileRef 只传 id，核对文件类型与节点类型一致；挂载本身不调用生成。旧服务可能只允许 audio，以实时 Schema 为准。
- **生成输入参考**：按目标模型要求放入 generationParams.referenceResources；仅放入参考列表或建立连线，不会把它显示成节点自身文件。

referenceResources 的媒体类型与用途必须相容：图片 IMAGE/REFERENCE，视频 VIDEO/SOURCE_VIDEO，音频 AUDIO/SOURCE_AUDIO；图片首尾帧按实时 Schema 使用 FIRST_FRAME/LAST_FRAME。不能把 VIDEO/REFERENCE 写成合法视频引用。多图 referenceImg 与首尾帧 keyframe 模式分别核对，不混用槽位。保留用户指定的顺序与其他素材，不按固定创作模板增加或删除引用。

资源来自 fileRef 直传且没有 sourceNodeId 时，不编造一个来源节点。挂载后用 getNodes 的 media 字段验证；字段尚未开放的旧部署才在相关 context 中检查 frameFiles/videoFiles/audioFiles。
