# WorkBuddy 工具使用说明

先在连接器中完成 Creatly 网站 OAuth。账户与空间由授权绑定，用 listProjects/getProfile 回执核对，不向用户索取密码、令牌或重复填写空间。通过当前连接发现工具定义，以下为功能索引；不同环境部署可能不同，只调用已暴露的工具和字段。

| 工作 | 工具及关键输入 |
| --- | --- |
| 账户与项目 | getProfile；listProjects 的 page 默认 1、pageSize 默认 20、最大 50；projectCreate 按实际定义提供项目名称和幂等键 |
| 画布目录 | getCanvasContext：projectId 为真实字符串，detail=brief、includeSubjects=false；有 nextCursor 才继续分页 |
| 节点精读 | getNodes：projectId、nodeIds 或已开放的外部键；brief 概要，full 按 fields 取正文、参数或媒体 |
| 创建和修改 | createNode/updateNode：projectId、nodes 及 Schema 要求的幂等键、当前观察摘要；节点类型和 ID 不互换 |
| 删除 | deleteNodes：只执行用户指定范围，先读取 deletion，传真实删除观察摘要 |
| 主体分类与建档 | 仅用户明确要求创建主体时使用 listSubjectTypes、resolveElements、createSubject；普通人物或物品图片使用图片节点 |
| 主体素材与引用 | 用户明确要求使用已有主体或创建主体时，按需使用主体工具；不得为普通图片自动建档 |
| 上传 | upload action=prepare/complete：先登记文件元信息，本机直传，再 complete 获取 fileRef；不能只发送本地路径 |
| 模型及音色 | listGenerationModels 先 detail=compact 定位，再 modelIds + full；listSystemVoices 查询可用音色，不猜模型或音色 ID |
| 费用和生成 | calculateCredits 取得报价，核对用户已授权范围和预算，generateNodes 使用真实节点、预算上限及稳定幂等键 |
| 任务与文件 | getGenerationStatus 查原任务，getNodes media 核对目标节点文件；生成成功与挂载成功分别判断 |

参数类型、必填项和默认值以实时工具 inputSchema 为准。下面是只读示例，尖括号中的文字是待替换说明，不可当成真实 ID 发送。

```json
{"page":1,"pageSize":20}
```

上例传给 listProjects，从 output 取得 projectId 和 projectUrl。需要指定项目时，先用目录匹配名称，不让用户从加密画布 URL 推算 ID。

```json
{"projectId":"<listProjects 返回的项目ID>","detail":"brief","includeSubjects":false}
```

上例传给 getCanvasContext。已知目标节点 ID 后直接精读，不反复遍历全画布：

```json
{"projectId":"<项目ID>","nodeIds":["<目标节点ID>"],"detail":"full","fields":["generationSettings"]}
```

上例传给 getNodes，只检查模型、分辨率和音频等配置；正文用 content，参考素材用 generationParams/subjects，媒体用 media。只有当前 Schema 开放相应字段时才发送。

回执可能包含 output、execution、affectedNodeIds、错误 code/message 和写入前置条件等；保存实际返回值，不假造成功结构。资源 ID 保持字符串，游标和任务标识原样使用。401 由宿主续期；403 查权限；5xx/超时先查询原操作，不能因此重复上传、建档或扣费。参数错误对照实时 Schema 修正，正文预览不能覆盖全文。完整执行规则见 reading.md、nodes-and-subjects.md、generation.md 和 mcp-execution.md。
