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
