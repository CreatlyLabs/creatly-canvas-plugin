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
codex plugin marketplace add https://github.com/loushengtao/creatly-canvas-plugin.git --ref test
codex plugin add creatly-video-director@creatly
```

## Claude Code 安装

```text
/plugin marketplace add https://github.com/loushengtao/creatly-canvas-plugin.git#test
/plugin install creatly-video-director@creatly
```

首次连接时，按宿主提示完成 yuanji 的 OAuth 授权，在 **test.yuanji.studio** 登录并选择空间。之后由宿主保存凭据和自动刷新访问令牌；开启新任务、重启宿主或更新同一环境的插件时先复用已有连接，不每天执行 `/mcp` 验证。完整失效条件与排障见 [账号连接与续期](docs/oauth-connection.md)。

## 一次授权与自动续期

- 元极采用标准 OAuth：访问令牌默认 30 分钟，刷新令牌默认 30 天；成功刷新会返回新的访问令牌和刷新令牌，由宿主安全保存。30 天指刷新令牌有效期，不是让一个访问令牌使用 30 天；实际有效期以服务端签发结果为准。
- 同一环境更新时保持插件名 `creatly-video-director`、MCP 名 `yuanji` 和 MCP 地址稳定。通过宿主的更新流程升级，不为日常更新卸载重装、登出或重复添加手动 MCP。
- 正常续期不需要浏览器、保持画布打开或重新输入密码。撤销授权、刷新令牌到期、凭据丢失或切换环境后，才按宿主提示重新连接。网站登录与插件授权是两套凭据。
- 403 是资源权限问题；429、5xx 和连接超时是请求问题。不要因此清除授权或反复登录。`invalid_client` 表示客户端注册/认证异常，`invalid_grant` 表示刷新凭据异常，应先诊断具体原因。

持续授权依赖后端部署：必须发布保留关联授权的 OAuth 客户端清理修复。已被旧服务误删的客户端无法只靠更新插件恢复，修复发布后需重新授权一次；之后使用正常自动续期流程。

## Codex 已连接账户面板

本环境尚未填写平台注册的元极应用 ID，因此当前安装包仍通过 MCP 连接管理授权，尚不显示平台账户面板。

维护者在平台创建对应环境的自定义 MCP 插件后，将实际应用 ID 写入 `config/openai-apps.json`；详细步骤见 [账号连接与续期](docs/oauth-connection.md)。平台注册、后端部署和真实账户连接均完成后才算面板验收通过。三个环境使用各自的应用 ID，升级时保留已有映射。

## WorkBuddy

下载 [test 分支 ZIP](https://github.com/loushengtao/creatly-canvas-plugin/archive/refs/heads/test.zip)，按宿主的本地 marketplace 安装流程导入。需要支持 HTTP MCP 与 OAuth；完整安装与授权流程尚未端到端验证。

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

## 创作与协议

技能统一为 `film-skill`：一个入口覆盖剧本、选角、分镜、运镜、视频提示词、画布执行和剪辑，按叙事短片或写实电影路线推进，细节按需读取 `references/`。视频默认 Seedance 2.5、480p、开启音频；用户明确指定的模型、画质和音频参数优先。

配置使用标准 HTTP MCP，由宿主管理 OAuth 授权与令牌刷新，不打包凭据。通过实时 `tools/list` 获取工具及 Schema，具体见 [执行协议](skills/film-skill/references/mcp-execution.md)。工具能力取决于对应环境的后端部署；插件升级不等于后端已发布，也不代表已完成付费生成验收。

仓库中的旧 stdio 适配器仅为历史开发工具，本版本插件不加载它。

## 维护环境版本

同一个代码库共用 `skills/film-skill`、执行协议和后端 MCP，客户端使用各自的 JSON 配置。`dev`、`test`、`main` 分支分别对应开发、测试、生产环境；每个分支都包含三种客户端的适配。

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

账号面板与凭据保存由各客户端管理；OpenAI 的应用 ID 仅用于 Codex 配置。每个客户端首次使用分别授权，后续按宿主能力自动续期。

## 图片、视频、音频上传

配套后端部署后，使用统一的 `upload(action="prepare"|"complete")` 上传本地参考素材，不依赖浏览器交接。操作和限制见 [媒体上传说明](scripts/README.md)。

## 0.2.0 精简工具目录

当前工具包括 `listProjects`、`projectCreate`、`getCanvasContext`、`getCanvasOutline`、`getNodes`、`createNode`、`updateNode`、`deleteNodes`、`createSubject`、`upload`、`listGenerationModels`、`listSystemVoices`、`calculateCredits`、`generateNodes`、`getGenerationStatus`；能力以实时 `tools/list` 为准。

`getCanvasContext` 新接口默认 brief，仅返回节点 ID、名称、类型、状态和关系；按 nextCursor 翻页（新版 brief 500、compact 20、full 5 个/页；brief 超过 256 KiB 时自动缩小页数）。已知 ID 直接用 `getNodes` 按 fields 精读；局部生成使用 batch 门禁，不遍历整张 full 画布。旧部署以实时 inputSchema 为准，尚无 brief 时使用 getCanvasOutline。主体列表按需读取 includeSubjects。`createSubject` 的 kind 为 character/scene；道具和自定义主体使用 scene 分支的 subjectType=prop/custom，自定义分类传真实 subjectTypeId。

上传统一走 `upload`：`action="prepare"` 申请直传 → 本机上传原始字节 → `action="complete"` 登记。支持图片、视频、音频、文本（txt/md）；文本返回文件引用，需要在画布展示时再创建直接输入的文本节点。上传不自动发起生成。

先部署对应后端，再升级插件并刷新宿主加载的工具定义，同一环境复用已有 OAuth 连接。旧后端不会因为安装插件自动获得新工具；实时 `tools/list` 才是能力依据。默认目录不再提供 Film DSL、浏览器交接、独立确认或 previewAssemble。

### 0.2.1：已上传配音挂载

后端支持节点级 fileRef 后，可通过 createNode/updateNode 将已上传的图片（frame）、视频（video）、音频（audio）直接挂成画布节点自身素材，效果同在画布拖入上传，无需生成或重复上传。已有节点可批量更新；挂载后读回 frameFiles/videoFiles/audioFiles。先部署配套后端，再更新插件并刷新 MCP 工具目录。

### 0.2.2：视频素材列表

配套后端支持多图片、多音频输入连线，人物正视图和跨镜头补拍图可作为视频参考。跨镜头引用时用显式 Shot 确定归属，多图采用 referenceImg，按素材顺序编写提示词编号。

### 0.2.3：正式主体库

`createSubject` 写入正式主体资产并应用到画布，支持人物、场景、道具及已有自定义分类。图片生成完成后自动归档主体素材。

`getCanvasContext` 同时返回主体分类、资产列表和画布主体；full 模式包含参考项和文件，subjectId/subjectQuery 可精读或检索。使用返回的 mentionToken 在图片或视频提示词中 @ 主体，由服务端解析绑定，无需连线。当前已核验的 createNode/updateNode 不接收 generationParams.elementBindings；素材子集选择以实时写入 Schema 为准，读取字段不能直接当作写入参数。

需要部署配套主体库后端并刷新宿主工具目录。0.2.6-test 补充正式主体、参数校验与失败恢复说明；三视图优先使用 threeView，其他字段以实时 Schema 为准。插件升级不代表后端修复已部署。
