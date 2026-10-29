# Creatly Canvas Plugin · 测试环境

本分支 `test` 通过远程 MCP 连接 [test.yuanji.studio](https://test.yuanji.studio/)，无需启动本地画布服务。

## 环境对应

| 环境 | 网站 | GitHub 分支 |
| --- | --- | --- |
| 开发 | https://dev.yuanji.studio | dev |
| 测试 | https://test.yuanji.studio | test |
| 生产 | https://yuanji.studio | main |

安装的分支决定连接的环境，打开另一个网站不会自动切换插件。切换环境前，在宿主中移除旧的 `creatly` marketplace 来源，再添加目标分支并重新加载插件；在目标环境完成授权，确认账号与空间。三个环境不共用授权和画布数据。

## Codex 安装

```bash
codex plugin marketplace add https://github.com/CreatlyLabs/creatly-canvas-plugin.git --ref test
codex plugin add creatly-video-director@creatly
```

## Claude Code 安装

```text
/plugin marketplace add https://github.com/CreatlyLabs/creatly-canvas-plugin.git#test
/plugin install creatly-video-director@creatly
```

首次连接时，按宿主提示完成 yuanji 的 OAuth 授权，在 **test.yuanji.studio** 登录并选择空间。之后由宿主保存凭据和自动刷新访问令牌；开启新任务、重启宿主或更新同一环境的插件时先复用已有连接，不每天执行 `/mcp` 验证。完整失效条件与排障见 [账号连接与续期](docs/oauth-connection.md)。

## 一次授权与自动续期

- Creatly 采用标准 OAuth：访问令牌默认 30 分钟，刷新令牌默认 30 天；成功刷新会返回新的访问令牌和刷新令牌，由宿主安全保存。30 天指刷新令牌有效期，不是让一个访问令牌使用 30 天；实际有效期以服务端签发结果为准。
- 同一环境更新时保持插件名 `creatly-video-director`、MCP 名 `yuanji` 和 MCP 地址稳定。通过宿主的更新流程升级，不为日常更新卸载重装、登出或重复添加手动 MCP。
- 正常续期不需要浏览器、保持画布打开或重新输入密码。撤销授权、刷新令牌到期、凭据丢失或切换环境后，才按宿主提示重新连接。网站登录与插件授权是两套凭据。
- 403 是资源权限问题；429、5xx 和连接超时是请求问题。不要因此清除授权或反复登录。`invalid_client` 表示客户端注册/认证异常，`invalid_grant` 表示刷新凭据异常，应先诊断具体原因。

持续授权依赖后端部署：必须发布保留关联授权的 OAuth 客户端清理修复。已被旧服务误删的客户端无法只靠更新插件恢复，修复发布后需重新授权一次；之后使用正常自动续期流程。

## Codex 已连接账户面板

本环境尚未填写平台注册的 Creatly 应用 ID，因此当前安装包仍通过 MCP 连接管理授权，尚不显示平台账户面板。

维护者在平台创建对应环境的自定义 MCP 插件后，将实际应用 ID 写入 `config/openai-apps.json`；详细步骤见 [账号连接与续期](docs/oauth-connection.md)。平台注册、后端部署和真实账户连接均完成后才算面板验收通过。三个环境使用各自的应用 ID，升级时保留已有映射。

## WorkBuddy

申请开放平台连接器市场时，使用独立的 MCP + Skill 包，不能上传下方本地 marketplace 包：

```bash
python3 scripts/package-workbuddy-connector.py test
```

生成 connector-meta.json、mcp.json、icon.svg、公开技能和 ZIP。参见 [开放平台连接器打包与联调](https://github.com/CreatlyLabs/creatly-canvas-plugin/blob/test/connectors/workbuddy/README.md)。目录检查通过不代表网站 OAuth 或平台审核已通过。

下载 [test 分支 ZIP](https://github.com/CreatlyLabs/creatly-canvas-plugin/archive/refs/heads/test.zip)，按宿主的本地 marketplace 安装流程导入。需要支持 HTTP MCP 与 OAuth；完整安装与授权流程尚未端到端验证。

## CLI / 手动 MCP 配置

Codex：

```bash
codex mcp add creatly-test --url https://test.yuanji.studio/api/agent/mcp/v2
codex mcp login creatly-test
```

Claude Code：

```text
claude mcp add --transport http creatly-test https://test.yuanji.studio/api/agent/mcp/v2
/mcp
```

手动 HTTP MCP 配置：

```json
{"mcpServers": {"creatly-test": {"type": "http", "url": "https://test.yuanji.studio/api/agent/mcp/v2"}}}
```

手动 MCP 配置不包含插件创作技能；已通过插件连接时无需重复添加。

## 公开技能与协议

公开技能为 `creatly-canvas`：读取和修改画布、上传本地素材、管理主体、配置生成、估价并查询真实结果。用户提供内容和执行范围，本技能负责落实到画布；同时提供[人物横版四视图模板](skills/creatly-canvas/references/character-four-view.md)，以正脸近景和全身正/侧/背视图保留人物细节。其余内部电影制作方法、创作案例和质量检查脚本不随包提供。基础画布操作无需安装私有技能。

从 0.2.14 起，公开插件使用 `$creatly-canvas`，原 `film-skill` 不再随公开包提供。已有内部电影技能可单独保留；插件名、MCP 名和同环境 OAuth 地址保持稳定，正常升级无需重新添加连接。

图片默认 Sunburst 2K；视频默认 Seedance 2.5、480p、开启音频。用户明确指定优先，能力以实时模型目录为准，不因默认值改变重生成已有节点。

配置使用标准 HTTP MCP，由宿主管理 OAuth 授权与令牌刷新，不打包凭据。通过实时 `tools/list` 获取工具及 Schema，具体见 [执行协议](skills/creatly-canvas/references/mcp-execution.md)。工具能力取决于对应环境的后端部署；插件升级不等于后端已发布，也不代表已完成付费生成验收。

仓库中的旧 stdio 适配器仅为历史开发工具，本版本插件不加载它。

## 维护环境版本

同一个代码库共用 `skills/creatly-canvas`、执行协议和后端 MCP，客户端使用各自的 JSON 配置。`dev`、`test`、`main` 分支分别对应开发、测试、生产环境；每个分支都包含三种客户端的适配。

拉取对应分支后，默认同步全部客户端配置：

```bash
python3 scripts/configure-environment.py test
```

需要单独安装包时，用 `--client` 导出。输出默认位于 `dist/test/<client>/`，可以用 `--output` 指定新目录；导出不会修改源仓库或已有授权。

```bash
python3 scripts/configure-environment.py test --client codex
python3 scripts/configure-environment.py test --client claude
python3 scripts/configure-environment.py test --client workbuddy
```

| 客户端参数 | 插件配置 | MCP 配置 |
| --- | --- | --- |
| `codex` | `.codex-plugin/plugin.json` | `.mcp.json`，已注册应用时附带 `.app.json` |
| `claude` | `.claude-plugin/plugin.json` | `.mcp.claude.json` |
| `workbuddy` | `.codebuddy-plugin/plugin.json` | 内置 `mcpServers` |

导出目录保留该客户端的 marketplace 和一份共享技能、文档与脚本。WorkBuddy 采用已有 CodeBuddy 适配配置，完整安装和 OAuth 仍需在实际客户端验收。`--client all --output <目录>` 可以导出通用安装包。相同输出可重复导出；内容变化时请选择新的或空的目录，避免覆盖已有文件。旧参数 `production` 继续作为 `main` 的别名。

公开安装包使用明确的文件清单导出，不递归打包未知技能、参考文档、内部脚本或 ZIP。私有材料保存于仓库外；不要把它们提交到公开 Git 分支、历史、标签或发布附件。更新清单时先审查文件内容。旧版本和已经下载的副本不会因后续拆分消失。

账号面板与凭据保存由各客户端管理；OpenAI 的应用 ID 仅用于 Codex 配置。每个客户端首次使用分别授权，后续按宿主能力自动续期。

## 图片、视频、音频上传

本地素材通过 upload prepare → 本机 HTTPS PUT → upload complete 登记。保留上传脚本与文件类型检查；详见 [上传脚本说明](scripts/README.md)。上传本身不提交生成、不扣除生成费用，工具可用性以对应后端实时目录为准。

## 画布读取与写入

人物、场景、物品等默认创建普通图片节点；仅用户明确要求创建主体或添加到主体库时才新建主体。

未知节点先读 brief 目录，已知 ID 用 getNodes 精读必要字段。全画布 full 读取只用于确需完整快照的操作，不为局部修改反复分页拉取全部正文。主体、节点和文件 ID 分开使用；文件可挂到节点自身媒体，也可作为生成参考，两者用途不同。

## 生成确认

先核对用户要求、当前模型配置与真实报价，按已授权范围和预算提交并传入 maxCredits。未授权的新增支出在对话中确认；已批准的范围不重复询问。超时先查原任务，任务成功后再核对目标节点实际媒体，不重复扣费修复挂载问题。
