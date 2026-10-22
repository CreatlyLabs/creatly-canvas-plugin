#!/usr/bin/env python3
"""Configure an environment or export a client-specific remote MCP plugin package."""
import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

ENVIRONMENTS = {
    'dev': ('dev', 'dev.yuanji.studio', '开发', '0.2.22-dev'),
    'test': ('test', 'test.yuanji.studio', '测试', '0.2.22-test'),
    'production': ('main', 'yuanji.studio', '生产', '0.2.22'),
}

# Keep the host's OAuth credential identity stable when releasing a new plugin version.
MCP_SERVER_NAME = 'yuanji'

# Each host discovers its own manifest; the workflow and remote backend are shared.
CLIENTS = {
    'codex': ('.codex-plugin', '.agents', '.mcp.json'),
    'claude': ('.claude-plugin', '.claude-plugin', '.mcp.claude.json'),
    'workbuddy': ('.codebuddy-plugin', '.codebuddy-plugin', None),
}

# Only explicitly reviewed public files belong in a client package.
# Do not recursively copy skill/reference folders: an internal file added beside
# these sources must never silently become part of every client download.
PUBLIC_PLUGIN_FILES = (
    'README.md', 'docs/oauth-connection.md',
    '.codex-plugin/plugin.json', '.claude-plugin/plugin.json', '.codebuddy-plugin/plugin.json',
    '.mcp.json', '.mcp.claude.json',
    'scripts/README.md', 'scripts/upload_file.py', 'scripts/test_upload_file.py',
    'skills/creatly-canvas/SKILL.md', 'skills/creatly-canvas/agents/openai.yaml',
    'skills/creatly-canvas/references/mcp-execution.md',
    'skills/creatly-canvas/references/reading.md',
    'skills/creatly-canvas/references/canvas-preview.md',
    'skills/creatly-canvas/references/nodes-and-subjects.md',
    'skills/creatly-canvas/references/layout.md',
    'skills/creatly-canvas/references/character-four-view.md',
    'skills/creatly-canvas/references/generation.md',
    'skills/creatly-canvas/references/uploads.md',
)

def normalize_environment(environment):
    environment = 'production' if environment == 'main' else environment
    if environment not in ENVIRONMENTS:
        raise ValueError('Environment must be dev, test, or main (production is an alias).')
    return environment

def normalize_openai_app_id(value):
    if not isinstance(value, str):
        raise ValueError('Use the actual registered OpenAI app ID, not an OAuth client ID or URL.')
    # The platform detail URL uses plugin_<app ID>; .app.json requires the app ID itself.
    value = value.removeprefix('plugin_')
    if not re.fullmatch(r'(?:asdk_app|connector|templated_apps)_[A-Za-z0-9][A-Za-z0-9_-]*', value):
        raise ValueError('Use the actual registered OpenAI app ID, not an OAuth client ID or URL.')
    return value

def configure(root, environment, openai_app_id=None):
    environment = normalize_environment(environment)
    branch, domain, label, version = ENVIRONMENTS[environment]
    plugin = root / 'plugins/creatly-video-director'
    site = f'https://{domain}'
    endpoint = f'{site}/api/agent/mcp/v2'
    server = 'creatly' if environment == 'production' else f'creatly-{environment}'
    servers = {MCP_SERVER_NAME: {'type': 'http', 'url': endpoint}}
    def write_json(path, data):
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    mapping_path = root / 'config/openai-apps.json'
    mappings = json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    previous_mappings = mappings.copy()
    if openai_app_id is not None:
        mappings[environment] = normalize_openai_app_id(openai_app_id)
    registered_app_id = mappings.get(environment)
    if registered_app_id is not None:
        registered_app_id = normalize_openai_app_id(registered_app_id)
        mappings[environment] = registered_app_id
    if openai_app_id is not None or mappings != previous_mappings:
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(mapping_path, mappings)
    app_path = plugin / '.app.json'
    if registered_app_id:
        write_json(app_path, {'apps': {MCP_SERVER_NAME: {'id': registered_app_id, 'required': True}}})
    elif app_path.exists():
        app_path.unlink()
    for name in ['.mcp.json', '.mcp.claude.json']:
        write_json(plugin / name, {'mcpServers': servers})
    for host in ['codex', 'claude', 'codebuddy']:
        path = plugin / f'.{host}-plugin/plugin.json'
        data = json.loads(path.read_text())
        assert data['name'] == 'creatly-video-director'
        data.update(version=version, homepage=site)
        if 'url' in data.get('author', {}): data['author']['url'] = site
        if 'interface' in data: data['interface']['websiteURL'] = site
        if host == 'codebuddy': data['mcpServers'] = servers
        if host == 'codex':
            if registered_app_id:
                data['apps'] = './.app.json'
            else:
                data.pop('apps', None)
        write_json(path, data)
    for host in ['claude', 'codebuddy']:
        path = root / f'.{host}-plugin/marketplace.json'
        data = json.loads(path.read_text())
        assert data['name'] == 'creatly'
        for item in data['plugins']:
            if item['name'] == 'creatly-video-director':
                item.update(version=version, homepage=site)
        write_json(path, data)
    for path in plugin.glob('skills/*/references/mcp-execution.md'):
        text = path.read_text()
        for _, known_domain, _, _ in ENVIRONMENTS.values():
            text = text.replace(f'https://{known_domain}/api/agent/mcp/v2', endpoint)
        path.write_text(text)
    for path in [root / 'README.md', plugin / 'README.md']:
        old = path.read_text()
        # Keep workflow documentation separate from generated installation instructions.
        tail = old[old.index('## 图片、视频、音频上传'):] if '## 图片、视频、音频上传' in old else old[old.index('## 生成确认'):]
        protocol = 'skills/creatly-canvas/references/mcp-execution.md'
        connection_guide = 'docs/oauth-connection.md'
        four_view_guide = 'skills/creatly-canvas/references/character-four-view.md'
        if path == root / 'README.md': protocol = 'plugins/creatly-video-director/' + protocol
        if path == root / 'README.md': connection_guide = 'plugins/creatly-video-director/' + connection_guide
        if path == root / 'README.md': four_view_guide = 'plugins/creatly-video-director/' + four_view_guide
        header = f'''# Creatly Canvas Plugin · {label}环境

本分支 `{branch}` 通过远程 MCP 连接 [{domain}]({site}/)，无需启动本地画布服务。

## 环境对应

| 环境 | 网站 | GitHub 分支 |
| --- | --- | --- |
| 开发 | https://dev.yuanji.studio | dev |
| 测试 | https://test.yuanji.studio | test |
| 生产 | https://yuanji.studio | main |

安装的分支决定连接的环境，打开另一个网站不会自动切换插件。切换环境前，在宿主中移除旧的 `creatly` marketplace 来源，再添加目标分支并重新加载插件；在目标环境完成授权，确认账号与空间。三个环境不共用授权和画布数据。

## Codex 安装

```bash
codex plugin marketplace add https://github.com/CreatlyLabs/creatly-canvas-plugin.git --ref {branch}
codex plugin add creatly-video-director@creatly
```

## Claude Code 安装

```text
/plugin marketplace add https://github.com/CreatlyLabs/creatly-canvas-plugin.git#{branch}
/plugin install creatly-video-director@creatly
```

首次连接时，按宿主提示完成 yuanji 的 OAuth 授权，在 **{domain}** 登录并选择空间。之后由宿主保存凭据和自动刷新访问令牌；开启新任务、重启宿主或更新同一环境的插件时先复用已有连接，不每天执行 `/mcp` 验证。完整失效条件与排障见 [账号连接与续期]({connection_guide})。

## 一次授权与自动续期

- 元极采用标准 OAuth：访问令牌默认 30 分钟，刷新令牌默认 30 天；成功刷新会返回新的访问令牌和刷新令牌，由宿主安全保存。30 天指刷新令牌有效期，不是让一个访问令牌使用 30 天；实际有效期以服务端签发结果为准。
- 同一环境更新时保持插件名 `creatly-video-director`、MCP 名 `yuanji` 和 MCP 地址稳定。通过宿主的更新流程升级，不为日常更新卸载重装、登出或重复添加手动 MCP。
- 正常续期不需要浏览器、保持画布打开或重新输入密码。撤销授权、刷新令牌到期、凭据丢失或切换环境后，才按宿主提示重新连接。网站登录与插件授权是两套凭据。
- 403 是资源权限问题；429、5xx 和连接超时是请求问题。不要因此清除授权或反复登录。`invalid_client` 表示客户端注册/认证异常，`invalid_grant` 表示刷新凭据异常，应先诊断具体原因。

持续授权依赖后端部署：必须发布保留关联授权的 OAuth 客户端清理修复。已被旧服务误删的客户端无法只靠更新插件恢复，修复发布后需重新授权一次；之后使用正常自动续期流程。

## Codex 已连接账户面板

{'本环境已关联平台注册的元极应用。安装后在插件设置中连接账户；账户名称由后端的 `getProfile` 返回，面板由平台展示。' if registered_app_id else '本环境尚未填写平台注册的元极应用 ID，因此当前安装包仍通过 MCP 连接管理授权，尚不显示平台账户面板。'}

维护者在平台创建对应环境的自定义 MCP 插件后，将实际应用 ID 写入 `config/openai-apps.json`；详细步骤见 [账号连接与续期]({connection_guide})。平台注册、后端部署和真实账户连接均完成后才算面板验收通过。三个环境使用各自的应用 ID，升级时保留已有映射。

## WorkBuddy

申请开放平台连接器市场时，使用独立的 MCP + Skill 包，不能上传下方本地 marketplace 包：

```bash
python3 scripts/package-workbuddy-connector.py {branch}
```

生成 connector-meta.json、mcp.json、icon.svg、公开技能和 ZIP。参见 [开放平台连接器打包与联调](https://github.com/CreatlyLabs/creatly-canvas-plugin/blob/{branch}/connectors/workbuddy/README.md)。目录检查通过不代表网站 OAuth 或平台审核已通过。

下载 [{branch} 分支 ZIP](https://github.com/CreatlyLabs/creatly-canvas-plugin/archive/refs/heads/{branch}.zip)，按宿主的本地 marketplace 安装流程导入。需要支持 HTTP MCP 与 OAuth；完整安装与授权流程尚未端到端验证。

## CLI / 手动 MCP 配置

Codex：

```bash
codex mcp add {server} --url {endpoint}
codex mcp login {server}
```

Claude Code：

```text
claude mcp add --transport http {server} {endpoint}
/mcp
```

手动 HTTP MCP 配置：

```json
{{"mcpServers": {{"{server}": {{"type": "http", "url": "{endpoint}"}}}}}}
```

手动 MCP 配置不包含插件创作技能；已通过插件连接时无需重复添加。

## 公开技能与协议

公开技能为 `creatly-canvas`：读取和修改画布、上传本地素材、管理主体、配置生成、估价并查询真实结果。用户提供内容和执行范围，本技能负责落实到画布；同时提供[人物横版四视图模板]({four_view_guide})，以正脸近景和全身正/侧/背视图保留人物细节。其余内部电影制作方法、创作案例和质量检查脚本不随包提供。基础画布操作无需安装私有技能。

从 0.2.14 起，公开插件使用 `$creatly-canvas`，原 `film-skill` 不再随公开包提供。已有内部电影技能可单独保留；插件名、MCP 名和同环境 OAuth 地址保持稳定，正常升级无需重新添加连接。

图片默认 Sunburst 2K；视频默认 Seedance 2.5、480p、开启音频。用户明确指定优先，能力以实时模型目录为准，不因默认值改变重生成已有节点。

配置使用标准 HTTP MCP，由宿主管理 OAuth 授权与令牌刷新，不打包凭据。通过实时 `tools/list` 获取工具及 Schema，具体见 [执行协议]({protocol})。工具能力取决于对应环境的后端部署；插件升级不等于后端已发布，也不代表已完成付费生成验收。

仓库中的旧 stdio 适配器仅为历史开发工具，本版本插件不加载它。

## 维护环境版本

同一个代码库共用 `skills/creatly-canvas`、执行协议和后端 MCP，客户端使用各自的 JSON 配置。`dev`、`test`、`main` 分支分别对应开发、测试、生产环境；每个分支都包含三种客户端的适配。

拉取对应分支后，默认同步全部客户端配置：

```bash
python3 scripts/configure-environment.py {branch}
```

需要单独安装包时，用 `--client` 导出。输出默认位于 `dist/{branch}/<client>/`，可以用 `--output` 指定新目录；导出不会修改源仓库或已有授权。

```bash
python3 scripts/configure-environment.py {branch} --client codex
python3 scripts/configure-environment.py {branch} --client claude
python3 scripts/configure-environment.py {branch} --client workbuddy
```

| 客户端参数 | 插件配置 | MCP 配置 |
| --- | --- | --- |
| `codex` | `.codex-plugin/plugin.json` | `.mcp.json`，已注册应用时附带 `.app.json` |
| `claude` | `.claude-plugin/plugin.json` | `.mcp.claude.json` |
| `workbuddy` | `.codebuddy-plugin/plugin.json` | 内置 `mcpServers` |

导出目录保留该客户端的 marketplace 和一份共享技能、文档与脚本。WorkBuddy 采用已有 CodeBuddy 适配配置，完整安装和 OAuth 仍需在实际客户端验收。`--client all --output <目录>` 可以导出通用安装包。相同输出可重复导出；内容变化时请选择新的或空的目录，避免覆盖已有文件。旧参数 `production` 继续作为 `main` 的别名。

公开安装包使用明确的文件清单导出，不递归打包未知技能、参考文档、内部脚本或 ZIP。私有材料保存于仓库外；不要把它们提交到公开 Git 分支、历史、标签或发布附件。更新清单时先审查文件内容。旧版本和已经下载的副本不会因后续拆分消失。

账号面板与凭据保存由各客户端管理；OpenAI 的应用 ID 仅用于 Codex 配置。每个客户端首次使用分别授权，后续按宿主能力自动续期。

'''
        path.write_text(header + tail)

def export_package(root, environment, client, output, openai_app_id=None):
    """Render from shared sources in isolation; never overwrite an existing package."""
    environment = normalize_environment(environment)
    if client not in (*CLIENTS, 'all'):
        raise ValueError('Client must be all, codex, claude, or workbuddy.')
    if openai_app_id is not None and client not in ('all', 'codex'):
        raise ValueError('--openai-app-id applies only to codex or all clients.')
    root, output = root.resolve(), output.resolve()
    if root == output or root.is_relative_to(output):
        raise ValueError('Output must be a separate package directory, not the source or its parent.')
    if output.is_relative_to(root) and not output.is_relative_to(root / 'dist'):
        raise ValueError('Inside the repository, export packages only under dist/.')
    if output.exists() and not output.is_dir():
        raise ValueError('Output must be a directory.')

    with tempfile.TemporaryDirectory(prefix='creatly-package-') as temp:
        staged = Path(temp)
        plugin = staged / 'plugins/creatly-video-director'
        for relative in PUBLIC_PLUGIN_FILES:
            source = root / 'plugins/creatly-video-director' / relative
            if source.is_symlink() or not source.resolve().is_relative_to(root):
                raise ValueError(f'Public package source must be a regular repository file: {relative}')
            target = plugin / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for relative in ['.agents/plugins/marketplace.json', '.claude-plugin/marketplace.json',
                         '.codebuddy-plugin/marketplace.json', 'config/openai-apps.json']:
            source = root / relative
            if source.exists():
                if source.is_symlink() or not source.resolve().is_relative_to(root):
                    raise ValueError(f'Public package source must be a regular repository file: {relative}')
                target = staged / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        shutil.copy(root / 'README.md', staged / 'README.md')
        configure(staged, environment, openai_app_id)
        selected = CLIENTS if client == 'all' else {client: CLIENTS[client]}
        for host, (manifest, marketplace, connection) in CLIENTS.items():
            if host not in selected:
                shutil.rmtree(plugin / manifest)
                shutil.rmtree(staged / marketplace)
                if connection:
                    (plugin / connection).unlink()
        if 'codex' not in selected:
            (plugin / '.app.json').unlink(missing_ok=True)
        shutil.rmtree(staged / 'config', ignore_errors=True)
        branch, domain, _, version = ENVIRONMENTS[environment]
        manifests = '\n'.join(f'- `plugins/creatly-video-director/{adapter[0]}/plugin.json`'
                              for adapter in selected.values())
        (staged / 'INSTALL.md').write_text(f'''# Creatly {client} 安装包

源分支：`{branch}`；版本：`{version}`；MCP：`https://{domain}/api/agent/mcp/v2`。

本目录是参数生成的公开安装包，技能来自同一份 `creatly-canvas`，不包含私有电影制作方法。将本目录作为对应客户端的本地 marketplace 导入；完整使用说明见 [README](README.md)。WorkBuddy 的完整安装及 OAuth 尚需实测。

包含的客户端配置：

{manifests}

生成文件在本目录中维护；更新时从源仓库重新导出到新目录。插件不包含账号凭据，授权由客户端保存。
''')
        expected = {p.relative_to(staged): p.read_bytes() for p in staged.rglob('*') if p.is_file()}
        if output.exists() and any(output.iterdir()):
            existing = {p.relative_to(output): p.read_bytes() for p in output.rglob('*') if p.is_file()}
            if existing == expected:
                return output
            raise ValueError('Output is not empty and differs from this package; choose a new or empty directory.')
        shutil.copytree(staged, output, dirs_exist_ok=True)
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=(*ENVIRONMENTS, 'main'))
    parser.add_argument('--client', choices=('all', *CLIENTS), default='all',
                        help='Export only this client; default all configures the shared source in place.')
    parser.add_argument('--output', type=Path, help='Export to a new or empty marketplace directory.')
    parser.add_argument('--openai-app-id', help='Actual registered OpenAI app ID for this environment.')
    args = parser.parse_args()
    source_root = Path(__file__).resolve().parents[1]
    try:
        if args.client != 'all' or args.output is not None:
            environment = normalize_environment(args.environment)
            branch = ENVIRONMENTS[environment][0]
            output = args.output or source_root / 'dist' / branch / args.client
            print(export_package(source_root, environment, args.client, output, args.openai_app_id))
        else:
            configure(source_root, args.environment, args.openai_app_id)
    except ValueError as error:
        parser.error(str(error))
