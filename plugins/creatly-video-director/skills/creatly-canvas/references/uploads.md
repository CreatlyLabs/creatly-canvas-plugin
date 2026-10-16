# 本地素材上传

先通过实时工具目录确认 upload 已部署。完整命令与格式限制见 [上传脚本说明](../../../scripts/README.md)。插件升级不代表后端已发布，宿主必须具备本地文件读取与 HTTPS PUT 能力。

1. 本机运行 upload_file.py inspect，得到 filename、contentType、sizeBytes、md5；filename 只是文件名，不把绝对路径当成远程文件内容。
2. 调用 upload(action="prepare")，将真实返回的 URL/headers/上传 ID 保存为权限 0600 的私有临时 JSON。
3. 本机运行 upload_file.py put 直传原始二进制；不向对象存储发送平台 OAuth Token，不将 Base64 放进 MCP 参数。
4. 用同一 uploadId 调用 upload(action="complete")，保存真实 fileRef。HTTP PUT 成功不等于登记完成；完成后删除含签名 URL 的临时文件。
5. 按用户要求挂成节点自身媒体或生成参考，见 [节点与素材](nodes-and-subjects.md)，然后读回核对。上传和登记不会自动提交付费生成。

支持图片、视频、音频以及 txt/md；文本登记只有 fileRef，需要在画布显示时读取正文并创建直接输入文本节点，不作为模型图片参考。

PUT 或登记超时、409 时先用原 uploadId 查询 complete，不自动重传或重新申请。确认 URL 已过期且没有登记才重新准备。签名 URL、用户原始媒体和临时回执不写入 Git、公开文档或提示词。
