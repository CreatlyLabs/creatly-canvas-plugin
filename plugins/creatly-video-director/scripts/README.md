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

提交分镜或视频的 `generateNodes` 之前，先把 `getCanvasContext(detail="full")` 的结果存成 JSON，再运行：

新后端的 full 每页最多 5 个节点。按 nextCursor 收齐同一项目、版本、FULL 范围的全部页，将原始回执存成 `{"pages":[回执1,回执2,...]}`。最后一页必须 complete=true，且节点总数与 totalNodes 一致。脚本拒绝未读完、brief/compact、混版本及重复节点的回执，退出码为 2。旧后端无分页的完整 full 回执仍可读取。概要浏览用 brief，单节点检查用 getNodes，无需为它们读取完整门禁快照。

```bash
python3 scripts/film_gate_check.py '/private/path/canvas.json' --nodes '<本批节点ID,逗号分隔>' --max-images 30
```

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
