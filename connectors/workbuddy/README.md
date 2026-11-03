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
ZIP 根目录直接包含 connector-meta.json、mcp.json、icon.png 和 skills/，不包裹 Git 仓库、marketplace、其他客户端配置或私有电影技能。

| 环境 | source | 连接地址 |
| --- | --- | --- |
| main | creatly-canvas | https://creatly.cn/api/agent/mcp/v2 |
| test | creatly-canvas-test | https://test.yuanji.studio/api/agent/mcp/v2 |
| dev | creatly-canvas-dev | https://dev.yuanji.studio/api/agent/mcp/v2 |

`source` 是拟申请标识，能否使用需以平台审核为准。首次发布后保持标识稳定。正式市场使用 main 包，测试环境用于联调。
使用中英文名称、描述及示例，声明最低 WorkBuddy 4.24.0；远程传输使用平台要求的 streamableHttp，单 Server、30 秒超时。
官方市场包声明 `auth_mode: "server-side"` 与 `server_auth.auth_type: "mcp_oauth"`。WorkBuddy 云端通过 MCP 资源地址发现元数据、动态注册客户端、完成 OAuth 并托管令牌；包中不填写注册后才产生的 client_id、client_secret、redirect_uri，也不要求用户填写长期 Token。
MCP Server 键名与当前环境的 source 一致。图标使用用户提供的 Creatly PNG 原图，尺寸为 128×128，不缩放或重绘。包内只保留可执行的使用说明，开发测试命令不进入提交包。

## 提交前联调

1. 开通开放平台开发者/企业资格，创建“连接器”，上传本脚本生成的 ZIP，核对解析出的名称、图标与使用示例。
2. 发布后端 OAuth 修复。检查 MCP 入口及尾斜杠入口未登录均返回 401 与 WWW-Authenticate；资源元数据及授权服务器元数据返回 JSON，发行者和资源使用相同环境的正式 HTTPS 地址，支持 S256 和 refresh_token。PKCE plain 应返回 400，不降级接受。
3. 与 WorkBuddy 团队完成云端授权接入。检查平台生成的 client_name（WorkBuddy / CodeBuddy）及 HTTPS 回调能注册并原样回显；支持官方列出的多级子域名与指定域名。目前后端允许合法 HTTPS 回调，继续按每个客户端已登记的完整地址匹配授权，不把通配域名保存为客户端回调。用正式连接器完成真实授权、只读查询、客户端重启及续期验收。
4. 官方市场包使用云端 OAuth，回调由平台生成，不手填本机端口或 workbuddy:// 地址。旧客户端的原生回调兼容仍由后端保留，只允许已列入白名单的精确回调，不代表官方云端流程使用同一种地址。详细规则见 [WorkBuddy OAuth](oauth-connection.md)。
5. 验证只读目录、字段精读、用户授权的写入和上传；付费生成按实际报价及用户授权单独验收，不自动为审核提交付费任务。上传的本机脚本需要可用 Python 3 和文件执行能力，其他远程工具不依赖本地 Python。

平台规范见 [认证方式与服务端授权配置](https://open.workbuddy.cn/docs/connector#%E9%80%89%E6%8B%A9%E8%AE%A4%E8%AF%81%E6%96%B9%E5%BC%8F)。上述资料与 ZIP 可先准备，真实云端接入仍需 WorkBuddy 团队配合。联调通过后提交团队审核；本地结构验证和打包成功不代表已入驻、已授权或已通过平台审核。
开放平台要求见 [连接器](https://open.workbuddy.cn/docs/connector) 和 [技能格式](https://open.workbuddy.cn/docs/skill)。

上线验收还须核对站点自身的未知路由 404、CDN 公开资源命名及签名密钥的公开标识。这些由网站路由或部署配置决定，重新打包不会自动改变；密钥标识调整需要保留存量令牌的验签能力。
