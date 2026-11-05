# ChatGPT 与 Claude 聊天接入

ChatGPT 与 Claude 聊天使用各自的平台连接远程 Creatly MCP，不需要在电脑上启动画布服务。它们与 Codex、Claude Code 的插件安装及授权是独立的；每个平台、每个环境都要分别连接。

## MCP 地址

| 环境 | MCP 地址 |
| --- | --- |
| 开发 | `https://dev.yuanji.studio/api/agent/mcp/v2` |
| 测试 | `https://test.yuanji.studio/api/agent/mcp/v2` |
| 国内正式 | `https://creatly.cn/api/agent/mcp/v2` |
| 海外正式 | `https://creatly.ai/api/agent/mcp/v2` |

先用测试地址完成联调。各环境使用各自的账号、空间和画布数据，不会因切换网站而自动切换聊天连接。

## ChatGPT

1. 打开 [ChatGPT 插件目录](https://chatgpt.com/plugins)，选择添加自定义 MCP 服务器；账号或工作区可能需要先启用开发者模式，入口和可用权限以当前平台为准。
2. 填写 Creatly 的名称、说明和上表中目标环境的 MCP 地址，选择平台提供的 OAuth 连接方式。
3. 按提示在对应 Creatly 网站登录、选择空间并授权。检查平台显示连接成功，查看实际发现的工具列表。
4. 新建聊天，通过 `@` 选择该应用，先试“列出我的 Creatly 项目”。再按测试计划验证节点读取、写入和生成。

平台支持的写入能力取决于账号类型、工作区设置和应用权限。应用注册、显示在列表或连接成功，都不等于已经验证创建节点或生成；更新服务端工具后按平台指引刷新工具列表。[OpenAI 接入与测试说明](https://developers.openai.com/apps-sdk/deploy/connect-chatgpt)

## Claude 聊天

1. 打开 Claude 的 **Customize → Connectors**，选择添加自定义连接器，填入 Creatly 名称及目标环境的 MCP 地址。
2. 选择 OAuth；如客户端识别方式有多种，先按页面推荐配置，注册或授权失败时再检查服务端发现信息并尝试“Register automatically”。不要填写或分享手工复制的 token。
3. 在对应 Creatly 网站登录、选择空间并授权。成功后，在聊天输入区的 **+ → Connectors** 中启用该连接器。
4. 先试“列出我的 Creatly 项目”，然后验证节点读取、写入和生成。

Claude 个人、团队和企业账号的入口及添加权限可能不同；团队连接器可能需要管理员添加。[Claude 自定义连接器说明](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)

## 功能边界与验收

- 聊天连接器可发现的工具以平台实际返回为准。分别核对 `listProjects`、`getCanvasContext`、`getNodes`、`createNode`、`calculateCredits`、`generateNodes`、`getGenerationStatus`。
- 现有本机插件的公开 Skill 和私有电影 Skill 不会因仅添加远程 MCP 自动在聊天中生效；需要按目标平台支持的插件或技能机制单独集成、测试。不得把私有电影方法打包进公开连接器。
- 本地插件的上传流程依赖本机脚本及文件读取。聊天附件能否安全传给 Creatly、能否调用上传登记，必须单独联调；没有验证前，先在 Creatly 网站上传素材，再在聊天中操作已有素材。
- 每个平台先验证只读项目列表与节点详情，再使用专门的测试画布验证写入；生成要核对模型、参数和报价，并以实际任务结果为准。不要为了验证连接重复提交生成。
- 为测试、国内正式和海外正式分别记录连接状态与工具列表。客户端登录或可从本机访问接口，不代表平台云端已经授权成功。
