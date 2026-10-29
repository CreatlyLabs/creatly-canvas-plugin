# WorkBuddy 开放平台连接器

按 [连接器规范](https://open.workbuddy.cn/docs/connector) 生成独立的 **MCP + Skill** 入驻包。
已有 `configure-environment.py --client workbuddy` 仍是 CodeBuddy 风格的本地 marketplace 包，不能当作开放平台连接器提交。

```bash
python3 scripts/package-workbuddy-connector.py main
python3 scripts/package-workbuddy-connector.py test
python3 scripts/package-workbuddy-connector.py dev
```

输出为 `dist/<分支>/workbuddy-connector/<source>/` 及旁边的 `<source>-<版本>.zip`。
可用 `--output <新目录>` 指定目录。相同内容可重复导出，遇到不同内容的已有目录或 ZIP 会拒绝覆盖。
ZIP 根目录直接包含 connector-meta.json、mcp.json、icon.svg 和 skills/，不包裹 Git 仓库、marketplace、其他客户端配置或私有电影技能。

| 环境 | source | 连接地址 |
| --- | --- | --- |
| main | creatly-canvas | https://creatly.cn/api/agent/mcp/v2 |
| test | creatly-canvas-test | https://test.yuanji.studio/api/agent/mcp/v2 |
| dev | creatly-canvas-dev | https://dev.yuanji.studio/api/agent/mcp/v2 |

`source` 是拟申请标识，能否使用需以平台审核为准。首次发布后保持标识稳定。正式市场使用 main 包，测试环境用于联调。
使用中英文名称、描述及示例，声明最低 WorkBuddy 4.24.0；远程传输使用平台要求的 streamableHttp，单 Server、30 秒超时。
不设置 auth_mode，使用 WorkBuddy 内置的标准 MCP OAuth，不打包令牌或要求填写长期 Token。
图标复用网站 `venus-ailsc/public/logo-tab.svg` 的 Creatly 标识。

## 提交前联调

1. 开通开放平台开发者/企业资格，创建“连接器”，上传本脚本生成的 ZIP，核对解析出的名称、图标与使用示例。
2. 在目标环境检查 MCP 未登录返回 401 与 WWW-Authenticate，资源元数据及授权服务器元数据返回 JSON；OAuth 应声明公共客户端、S256 和 refresh_token。
3. 用 WorkBuddy 完成一次真实连接：动态注册应回显 redirect_uris，授权后可读取项目；重启客户端和令牌续期后验证连接保留。
4. 平台优先使用 `workbuddy://workbuddy/mcp/connector%3A<source>/oauth/callback`，被服务端拒绝时官方客户端会回退本机 `http://127.0.0.1:<动态端口>/oauth/callback`。后端仅支持 HTTPS/回环时须实测回退，不能把元数据检查当作完整授权通过。
5. 验证只读目录、字段精读、用户授权的写入和上传；付费生成按实际报价及用户授权单独验收，不自动为审核提交付费任务。上传的本机脚本需要可用 Python 3 和文件执行能力，其他远程工具不依赖本地 Python。

联调通过后提交团队审核；本地结构验证和打包成功不代表已入驻、已授权或已通过平台审核。
开放平台要求见 [连接器](https://open.workbuddy.cn/docs/connector) 和 [技能格式](https://open.workbuddy.cn/docs/skill)。
