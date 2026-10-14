# 本地媒体直传

后端部署 `upload(action="prepare")`、`upload(action="complete")` 后可用。先通过 MCP `tools/list` 确认工具存在；插件更新不等于后端已部署。需要现有 OAuth 写权限，不需要生成权限或浏览器交接。

1. 在本机计算元信息（Python 3.8+，无需安装依赖）：

```bash
python3 scripts/upload_file.py inspect '/absolute/path/reference.png'
```

2. 将输出的 `filename`、`contentType`、`sizeBytes`、`md5` 原样传给 `upload(action="prepare")`。`filename` 仅为文件名，不能把本地绝对路径发给远程服务当文件内容。响应包含 `uploadId`、一小时有效的 PUT URL 和必须携带的请求头。
3. 将 MCP 响应的 `structuredContent` 或 `output` 保存为本机权限 `0600` 的临时 JSON 文件；不要提交 Git、展示签名 URL 或把它保存到剧本/提示词中。然后上传原始二进制文件：

```bash
python3 scripts/upload_file.py put '/absolute/path/reference.png' --prepared '/private/path/prepared.json'
```

4. 将同一个 `uploadId` 传给 `upload(action="complete")`，保存真实返回的 `fileRef`。成功后删除临时 JSON 文件。HTTP 上传成功还不等于素材登记成功。
5. 使用现有 `createNode` / `updateNode` 将 `referenceResource` 放入 `generationParams.referenceResources`，保留其他已授权参考素材；根据具体模型用途选择 `REFERENCE`、`FIRST_FRAME`、`LAST_FRAME`、`SOURCE_AUDIO` 或 `SOURCE_VIDEO`，再读回核对。上传和登记不会自动生成、扣除生成费用或覆盖节点媒体。

支持格式与限制：图片 JPG/JPEG/PNG/WebP/GIF/BMP/TIF/TIFF，5 MiB；视频 MP4/MOV/AVI，300 MiB；音频 MP3/WAV/M4A，200 MiB。限制来自现有素材业务类型；下游模型还可能有更严格的参考文件限制。

PUT 超时、返回 409 或完成登记超时时，先用原 `uploadId` 调用 `upload(action="complete")` 判断结果；不要自动重新申请或重复创建。未上传对象无法登记，MCP 返回的错误是实际依据。URL 过期且确实未登记时才重新申请。登记完成后的同一上传可在会话保留的 24 小时内重查。

脚本使用流式 HTTPS PUT，不加载完整视频进内存，不发送平台 OAuth Token，不跟随重定向，不自动重投。仅有远程 MCP、没有本地文件/HTTP 执行能力的宿主仍需要本地上传执行器，不能声称仅凭路径完成上传。

```bash
python3 -m unittest discover -s scripts -p 'test_upload_file.py'
```

支持 `.txt` (`text/plain`) 和 `.md` (`text/markdown`)，上限 5 MiB。文本登记返回 fileRef，不返回模型媒体参考；需要在画布显示时读取正文，再创建直接输入模式的文本节点。

# 生成前门禁

局部提交分镜或视频的 `generateNodes` 时，直接用 `getNodes(detail="full", fields=["details","content","generationParams","subjects","media"])` 读取本批目标及真实依赖，不收齐整张 full 画布。每批最多 5 个节点；保存同一项目、同一版本回执到 batch.json：`{"reads":[回执对象,...],"contextNodeIds":["本批所用色卡节点ID"]}`。reads 中必须放实际 JSON 对象，不是占位字符串。

目标读取上述五个字段；依赖只读取检查所用字段：组/Shot 用 details，参考图片用 details/media，音频另加 content，主体用 details/media/subjects。`reads` 中放原始回执对象，可合并同一节点不同字段的读取；缺少必需字段不能当作空值。读取目标的 parentNode、parentIds、referenceResources.sourceNodeId、subjects.references.elementNodeId 及 @ 对应主体，再补读本批角色/色卡的必要素材节点。contextNodeIds 标明本批所用的色卡等上下文，避免让无关角色和旧色卡影响本批。fileRef 直传资源无 sourceNodeId 时无需凭空创建或查找节点。主体正式素材仍按实际主体读取核验；脚本看不到的素材不能宣称已经验证。已知 ID 时直接精读，未知 ID 先浏览 brief 目录；同一版本已读字段复用，版本变化只刷新本批。

```bash
python3 scripts/film_gate_check.py '/private/path/batch.json' --scope batch --nodes '<本批节点ID,逗号分隔>' --max-images 30
```

只有整片审查才读取 `getCanvasContext(detail="full")` 的全部页，保存为 `{"pages":[回执1,回执2,...]}`，然后运行 `python3 scripts/film_gate_check.py canvas.json --scope project`。所有页须为同一项目/版本/FULL 范围，最后 complete=true，节点总数与 totalNodes 一致。默认 project 模式保留旧完整 full 回执兼容，并拒绝用 brief/compact 或未读完的页冒充全量。batch 模式要求明确 --nodes，缺少目标、依赖、字段、版本不一致或重复回执冲突均退出码 2；普通非 Shot 图片也会检查本批提示词与引用。

`--max-images` 取实时 `listGenerationModels` 返回的参考图上限。输出每行一条：`FAIL` 是强制关卡，有未豁免的 FAIL 时退出码为 1，不提交生成；`WARN` 只提示，在回复里说明即可。

用户明确说跳过某项时，加 `--skip <关卡名>`，结果标为「用户豁免」，并在回复中点明跳过了什么。

| 关卡 | 级别 | 检查内容 |
| --- | --- | --- |
| color-card / color-card-mention | FAIL | 色卡主体有图；分镜和视频提示词都 @ 了色卡 |
| character-views | FAIL | 每个角色主体至少 3 个视角（三视图按 3 个计） |
| subject-images | WARN | 主体库图片不随快照返回时，提醒到画布确认 |
| unknown-subject / subject-edge | FAIL | @ 的主体存在（名称或 ID 都认）；主体不连线 |
| group | FAIL | 分镜和视频已放进本镜组 |
| ref-limit / ref-index | FAIL | 参考图、音频不超上限；【图N】【音频N】不超过实际传入数量 |
| timing / duration-limit | FAIL | 镜头块从 0 开始、连续、总长等于节点时长；不超过模型最长时长 |
| prompt-hygiene | FAIL | 提示词里没有本地路径或文件名 |
| shot-frame-ref / blocking | WARN | 默认不垫镜头画面；应垫站位图 |
| equal-durations / shot-length / hard-cut | WARN | 镜头时长错落、单镜 2–8 秒、镜头块之间有 HARD CUT |
| axis / dialogue / music / standalone | WARN | 多人戏写轴线；台词与音频逐字一致；默认无配乐；不写「上一段」等依赖上下文的说法 |

```bash
python3 -m unittest discover -s scripts -p 'test_film_gate_check.py'
```
