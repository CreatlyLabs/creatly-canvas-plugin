#!/usr/bin/env python3
"""Build a WorkBuddy Open Platform MCP + Skill connector directory and ZIP."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('configure_environment', ROOT / 'scripts/configure-environment.py')
environment_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(environment_config)


def copy_file(source, target, boundary):
    source, boundary = Path(source), Path(boundary).resolve()
    if source.is_symlink() or not source.resolve().is_relative_to(boundary):
        raise ValueError(f'Connector source must be a regular reviewed file: {source.name}')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def snapshot(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob('*') if p.is_file()}


def validate_connector(directory):
    metadata = json.loads((directory / 'connector-meta.json').read_text())
    for key in ['name', 'name_zh', 'name_en', 'description', 'description_zh', 'description_en',
                'source', 'type', 'version', 'minWorkbuddyVersion']:
        if not isinstance(metadata.get(key), str) or not metadata[key]:
            raise ValueError(f'Missing connector metadata: {key}')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', metadata['source']):
        raise ValueError('Connector source must use lowercase kebab-case.')
    for key in ['examples_zh', 'examples_en']:
        if not isinstance(metadata.get(key), list) or not 2 <= len(metadata[key]) <= 5:
            raise ValueError(f'Provide 2-5 examples: {key}')
        if not all(isinstance(item, str) and item for item in metadata[key]):
            raise ValueError(f'Examples must be non-empty strings: {key}')
    if metadata['type'] != 'mcp' or 'auth_mode' in metadata:
        raise ValueError('Use native MCP OAuth, not a token form or managed-auth mode.')
    mcp = json.loads((directory / 'mcp.json').read_text())
    if set(mcp) != {'mcpServers'} or set(mcp['mcpServers']) != {'creatly'}:
        raise ValueError('Exactly one MCP server is required.')
    server = mcp['mcpServers']['creatly']
    valid_urls = {f'https://{domain}/api/agent/mcp/v2'
                  for _, domain, _, _ in environment_config.ENVIRONMENTS.values()}
    if (set(server) != {'type', 'url', 'timeout'} or server['type'] != 'streamableHttp'
            or server['url'] not in valid_urls or server['timeout'] != 30000):
        raise ValueError('Invalid remote MCP transport, environment URL or timeout.')
    if ET.parse(directory / 'icon.svg').getroot().tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('The connector icon must be an SVG.')
    skill = directory / 'skills/creatly-canvas/SKILL.md'
    text = skill.read_text()
    for field in ['name', 'display_name', 'display_name_en', 'description', 'description_zh',
                  'description_en', 'version', 'author']:
        if not re.search(rf'^{field}: .+', text, re.MULTILINE):
            raise ValueError(f'Missing WorkBuddy skill metadata: {field}')
    for path in directory.rglob('*.md'):
        for dest in re.findall(r'\]\(([^\s)]+)\)', path.read_text()):
            if dest.startswith(('https://', 'http://', 'mailto:', '#')):
                continue
            target = (path.parent / dest.split('#')[0]).resolve()
            if not target.is_relative_to(directory.resolve()) or not target.is_file():
                raise ValueError(f'Broken or external local reference: {path.name} -> {dest}')
    for dest in re.findall(r'@(references/[A-Za-z0-9._/-]+)', text):
        if not (skill.parent / dest).is_file():
            raise ValueError(f'Unresolved WorkBuddy reference: {dest}')
    for path in directory.rglob('*'):
        if path.is_symlink() or path.suffix in {'.zip', '.token', '.pyc'} or path.name == '.env':
            raise ValueError('Unexpected private or generated file in connector.')
    return metadata


def package_connector(root, environment, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    environment = environment_config.normalize_environment(environment)
    branch, domain, label, version = environment_config.ENVIRONMENTS[environment]
    source = 'creatly-canvas' if branch == 'main' else f'creatly-canvas-{branch}'
    if root == output or root.is_relative_to(output):
        raise ValueError('Output cannot be the source repository or its parent.')
    if output.is_relative_to(root) and not output.is_relative_to(root / 'dist'):
        raise ValueError('Inside the repository, export only under dist/.')
    archive = output.parent / f'{source}-{version}.zip'
    if output.is_symlink() or archive.is_symlink():
        raise ValueError('Output and archive must not be symbolic links.')
    if output.exists() and not output.is_dir():
        raise ValueError('Output must be a directory.')
    with tempfile.TemporaryDirectory(prefix='creatly-workbuddy-') as temp:
        temp = Path(temp)
        # Reuse the reviewed public export, never copy the repository wholesale.
        marketplace = environment_config.export_package(root, environment, 'workbuddy', temp / 'marketplace')
        public = marketplace / 'plugins/creatly-canvas'
        staged = temp / 'connector'
        staged.mkdir()
        title = 'Creatly 画布' + (f' · {label}' if branch != 'main' else '')
        english = 'Creatly Canvas' + (f' ({branch})' if branch != 'main' else '')
        chinese_description = '连接 Creatly 画布，读取和修改项目节点、上传素材、按需管理主体，并按授权提交图片或视频生成及查询结果。'
        english_description = 'Read and update Creatly canvas projects, upload assets, manage subjects, and submit authorized media generation.'
        metadata = {
            'name': title, 'name_zh': title, 'name_en': english,
            'description': chinese_description, 'description_zh': chinese_description,
            'description_en': english_description, 'source': source, 'type': 'mcp',
            'version': version, 'minWorkbuddyVersion': '4.24.0',
            'examples_zh': ['列出我在 Creatly 中的项目，并查看指定画布的节点目录。',
                            '把我提供的图片上传到 Creatly 画布，创建图片节点，不提交生成。',
                            '查看这个视频节点的模型和分辨率，估算生成费用，先不要提交。'],
            'examples_en': ['List my Creatly projects and show the selected canvas node directory.',
                            'Upload my image and create an image node without generating media.',
                            'Check this video node model and resolution, then estimate the cost without submitting.'],
        }
        (staged / 'connector-meta.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
        (staged / 'mcp.json').write_text(json.dumps({'mcpServers': {'creatly': {
            'type': 'streamableHttp', 'url': f'https://{domain}/api/agent/mcp/v2', 'timeout': 30000,
        }}}, ensure_ascii=False, indent=2) + '\n')
        copy_file(root / 'connectors/workbuddy/icon.svg', staged / 'icon.svg', root)
        skill = staged / 'skills/creatly-canvas'
        for relative in environment_config.PUBLIC_PLUGIN_FILES:
            if relative.startswith('skills/creatly-canvas/') and '/agents/' not in relative:
                copy_file(public / relative, staged / relative, public)
        for name in ['README.md', 'upload_file.py']:
            copy_file(public / 'scripts' / name, skill / 'scripts' / name, public)
        copy_file(public / 'docs/oauth-connection.md', skill / 'references/oauth-connection.md', public)
        copy_file(root / 'connectors/workbuddy/tool-guide.md', skill / 'references/workbuddy-tools.md', root)
        for path in (skill / 'references').glob('*.md'):
            text = path.read_text().replace('../../../docs/oauth-connection.md', 'oauth-connection.md')
            path.write_text(text.replace('../../../scripts/README.md', '../scripts/README.md'))
        body = (skill / 'SKILL.md').read_text().split('---', 2)[2].lstrip()
        body = re.sub(r'\[([^\]]+)\]\((references/[^)]+)\)', r'@\2（\1）', body)
        header = {
            'name': 'creatly-canvas', 'display_name': title, 'display_name_en': english,
            'description': chinese_description, 'description_zh': chinese_description,
            'description_en': english_description, 'version': version, 'author': 'Creatly',
        }
        intro = ('在 WorkBuddy 中通过连接器自带的 creatly MCP 操作；首次使用在连接器页面点击连接，'
                 '由宿主完成网站 OAuth，后续复用已有连接。工具说明和只读示例见 @references/workbuddy-tools.md。'
                 '本地上传脚本需要可用的 Python 3；没有本机执行或文件传输能力时说明限制，'
                 '其他远程画布操作仍可执行，不把本地路径当作已上传素材。\n\n')
        (skill / 'SKILL.md').write_text('---\n' + ''.join(
            f'{key}: {json.dumps(value, ensure_ascii=False)}\n' for key, value in header.items())
            + '---\n\n' + intro + body)
        validate_connector(staged)
        expected = snapshot(staged)
        if output.exists() and any(output.iterdir()) and snapshot(output) != expected:
            raise ValueError('Output is not empty and differs; choose a new or empty directory.')
        packed = temp / 'connector.zip'
        with zipfile.ZipFile(packed, 'w', zipfile.ZIP_DEFLATED) as z:
            for relative, data in sorted(expected.items()):
                # Root-level metadata for upload parsers; no extra wrapper directory.
                item = zipfile.ZipInfo(relative, date_time=(2020, 1, 1, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.external_attr = 0o100644 << 16
                z.writestr(item, data)
        if archive.exists() and archive.read_bytes() != packed.read_bytes():
            raise ValueError('Archive already exists and differs; choose another output parent.')
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, output, dirs_exist_ok=True)
        if not archive.exists():
            shutil.copyfile(packed, archive)
    return output, archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=('dev', 'test', 'main', 'production'))
    parser.add_argument('--output', type=Path, help='A new or matching connector directory; a ZIP is created beside it.')
    args = parser.parse_args()
    environment = environment_config.normalize_environment(args.environment)
    branch = environment_config.ENVIRONMENTS[environment][0]
    source = 'creatly-canvas' if branch == 'main' else f'creatly-canvas-{branch}'
    output = args.output or ROOT / 'dist' / branch / 'workbuddy-connector' / source
    try:
        directory, archive = package_connector(ROOT, environment, output)
        print(json.dumps({'directory': str(directory), 'zip': str(archive)}, ensure_ascii=False))
    except (ValueError, FileNotFoundError) as error:
        parser.error(str(error))
