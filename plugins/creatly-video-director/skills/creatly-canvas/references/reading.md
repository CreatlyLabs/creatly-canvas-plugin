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

- `getNodes`、`createNode`、`updateNode` 的节点结果可含 `nodeUrl`；生成受理和状态回执提供 `nodeLinks[].nodeUrl`，每个节点状态中也可含 `nodeUrl`。从当前回执按节点 ID 对应取值，用“查看「节点名称」”等明确文字交付链接。
- 链接会在对应画布加载完成后自动居中、选中该节点，并高亮约 3 秒；批量结果分别标注本次目标节点的名称与链接。生成中或失败的节点也能定位，任务状态须如实说明；节点已删除时页面会提示无法定位，仍可使用画布。
- 已拿到链接就直接复用，不为交付链接再次遍历画布。目标节点尚无定位回执时，仅按其 ID 读取一次 `getNodes(detail="brief")`；旧服务仍无 `nodeUrl` 时退回 `projectUrl` 加节点 ID，不持续重试。
- 链接必须保留服务端返回的完整地址、查询参数和环境，不从 MCP 明文 ID 推算网页密文 ID，也不自行拼接地址。它沿用网站登录与项目权限，不能当作免登录授权。
