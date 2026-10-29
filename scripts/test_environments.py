import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('configure', ROOT / 'scripts/configure-environment.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class EnvironmentPackagesTest(unittest.TestCase):
    def test_platform_detail_ids_are_normalized_before_package_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ['plugins', '.claude-plugin', '.codebuddy-plugin']:
                shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns('node_modules'))
            shutil.copy(ROOT / 'README.md', root / 'README.md')
            module.configure(root, 'test', 'plugin_asdk_app_testfixture')
            mapping_path = root / 'config/openai-apps.json'
            self.assertEqual(json.loads(mapping_path.read_text())['test'], 'asdk_app_testfixture')
            app_path = root / 'plugins/creatly-video-director/.app.json'
            self.assertEqual(json.loads(app_path.read_text())['apps']['yuanji']['id'], 'asdk_app_testfixture')
            # Upgrade a mapping written by the previous renderer without requiring a new ID.
            mapping_path.write_text(json.dumps({'test': 'plugin_connector_testfixture', 'dev': None}))
            module.configure(root, 'test')
            self.assertEqual(json.loads(mapping_path.read_text()), {'test': 'connector_testfixture', 'dev': None})
            self.assertEqual(json.loads(app_path.read_text())['apps']['yuanji']['id'], 'connector_testfixture')

    def test_invalid_platform_detail_ids_are_rejected(self):
        for value in [None, 42, 'asdk_app_', 'asdk_app_-bad', 'asdk_app__bad', 'plugin_plugin_asdk_app_fixture', 'https://chatgpt.com/plugins/plugin_asdk_app_fixture']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.normalize_openai_app_id(value)

    def test_registered_account_panel_binding_survives_upgrades_and_cannot_leak_between_environments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ['plugins', '.claude-plugin', '.codebuddy-plugin']:
                shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns('node_modules'))
            shutil.copy(ROOT / 'README.md', root / 'README.md')
            plugin = root / 'plugins/creatly-video-director'
            # This fixture ID never goes into a released package or a live platform request.
            app_id = 'asdk_app_testfixture'
            module.configure(root, 'test', app_id)
            expected = {'apps': {'yuanji': {'id': app_id, 'required': True}}}
            self.assertEqual(json.loads((plugin / '.app.json').read_text()), expected)
            self.assertEqual(json.loads((plugin / '.codex-plugin/plugin.json').read_text())['apps'], './.app.json')
            for host in ['claude', 'codebuddy']:
                self.assertNotIn('apps', json.loads((plugin / f'.{host}-plugin/plugin.json').read_text()))
            module.configure(root, 'test')
            self.assertEqual(json.loads((plugin / '.app.json').read_text()), expected)
            module.configure(root, 'dev')
            self.assertFalse((plugin / '.app.json').exists())
            self.assertNotIn('apps', json.loads((plugin / '.codex-plugin/plugin.json').read_text()))
            module.configure(root, 'test')
            self.assertEqual(json.loads((plugin / '.app.json').read_text()), expected)
            self.assertEqual(json.loads((root / 'config/openai-apps.json').read_text())['test'], app_id)

    def test_bad_platform_id_does_not_modify_the_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ['plugins', '.claude-plugin', '.codebuddy-plugin']:
                shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns('node_modules'))
            shutil.copy(ROOT / 'README.md', root / 'README.md')
            snapshot = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with self.assertRaises(ValueError):
                module.configure(root, 'test', 'oauth-client-or-access-token')
            self.assertEqual(snapshot, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_each_environment_and_repeated_render(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ['plugins', '.claude-plugin', '.codebuddy-plugin']:
                shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns('node_modules'))
            shutil.copy(ROOT / 'README.md', root / 'README.md')
            for env in ['dev', 'test', 'production', 'dev']:
                with self.subTest(environment=env):
                    module.configure(root, env)
                    branch, domain, _, version = module.ENVIRONMENTS[env]
                    plugin = root / 'plugins/creatly-video-director'
                    endpoint = f'https://{domain}/api/agent/mcp/v2'
                    expected = {'yuanji': {'type': 'http', 'url': endpoint}}
                    for filename in ['.mcp.json', '.mcp.claude.json']:
                        self.assertEqual(json.loads((plugin / filename).read_text())['mcpServers'], expected)
                    for host in ['codex', 'claude', 'codebuddy']:
                        manifest = json.loads((plugin / f'.{host}-plugin/plugin.json').read_text())
                        self.assertEqual(manifest['version'], version)
                        self.assertEqual(manifest['homepage'], f'https://{domain}')
                        if host == 'codebuddy': self.assertEqual(manifest['mcpServers'], expected)
                    for path in [root / 'README.md', plugin / 'README.md']:
                        text = path.read_text()
                        self.assertIn(f'--ref {branch}', text)
                        self.assertIn(f'.git#{branch}', text)
                        self.assertIn(f'/heads/{branch}.zip', text)
                    for path in plugin.glob('skills/*/references/mcp-execution.md'):
                        self.assertIn(endpoint, path.read_text())
                    snapshot = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
                    module.configure(root, env)
                    self.assertEqual(snapshot, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_same_environment_upgrade_keeps_oauth_connection_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ['plugins', '.claude-plugin', '.codebuddy-plugin']:
                shutil.copytree(ROOT / directory, root / directory, ignore=shutil.ignore_patterns('node_modules'))
            shutil.copy(ROOT / 'README.md', root / 'README.md')
            plugin = root / 'plugins/creatly-video-director'
            module.configure(root, 'test')
            connections = {name: (plugin / name).read_bytes() for name in ['.mcp.json', '.mcp.claude.json']}
            codebuddy_connection = json.loads((plugin / '.codebuddy-plugin/plugin.json').read_text())['mcpServers']
            branch, domain, label, _ = module.ENVIRONMENTS['test']
            with patch.dict(module.ENVIRONMENTS, {'test': (branch, domain, label, '9.9.9-test')}):
                module.configure(root, 'test')
            for name, previous in connections.items():
                self.assertEqual((plugin / name).read_bytes(), previous)
            for host in ['codex', 'claude', 'codebuddy']:
                manifest = json.loads((plugin / f'.{host}-plugin/plugin.json').read_text())
                self.assertEqual(manifest['name'], 'creatly-video-director')
                self.assertEqual(manifest['version'], '9.9.9-test')
                if host == 'codebuddy':
                    self.assertEqual(manifest['mcpServers'], codebuddy_connection)
            self.assertEqual(list(codebuddy_connection), ['yuanji'])
            for path in [root / 'README.md', plugin / 'README.md']:
                self.assertIn('一次授权与自动续期', path.read_text())

    def test_release_packages_only_declare_remote_oauth_no_local_bridge_or_credentials(self):
        plugin = ROOT / 'plugins/creatly-video-director'
        site = json.loads((plugin / '.codex-plugin/plugin.json').read_text())['homepage']
        self.assertIn(site, {f'https://{domain}'
                             for _, domain, _, _ in module.ENVIRONMENTS.values()})
        for name in ['.mcp.json', '.mcp.claude.json']:
            config = json.loads((plugin / name).read_text())
            self.assertEqual(set(config), {'mcpServers'})
            self.assertEqual(set(config['mcpServers']), {'yuanji'})
            server = config['mcpServers']['yuanji']
            self.assertEqual(set(server), {'type', 'url'})
            self.assertEqual(server['type'], 'http')
            self.assertEqual(server['url'], f'{site}/api/agent/mcp/v2')

class ClientPackagesTest(unittest.TestCase):
    def copy_source(self, destination):
        for directory in ['plugins', '.agents', '.claude-plugin', '.codebuddy-plugin', 'config']:
            shutil.copytree(ROOT / directory, destination / directory,
                            ignore=shutil.ignore_patterns('node_modules', '__pycache__', '*.pyc'))
        shutil.copy(ROOT / 'README.md', destination / 'README.md')
        return destination

    def snapshot(self, root):
        return {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def test_environment_client_matrix_keeps_shared_skill_and_only_selected_json(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = self.copy_source(parent / 'source')
            original = self.snapshot(root)
            for env in ['dev', 'test', 'main']:
                for client in ['codex', 'claude', 'workbuddy', 'all']:
                    with self.subTest(environment=env, client=client):
                        output = parent / env / client
                        module.export_package(root, env, client, output)
                        plugin = output / 'plugins/creatly-video-director'
                        canonical = module.normalize_environment(env)
                        branch, domain, _, version = module.ENVIRONMENTS[canonical]
                        expected = {'yuanji': {'type': 'http', 'url': f'https://{domain}/api/agent/mcp/v2'}}
                        for host, (manifest_dir, marketplace_dir, mcp_file) in module.CLIENTS.items():
                            selected = client in ('all', host)
                            self.assertEqual((plugin / manifest_dir).exists(), selected)
                            self.assertEqual((output / marketplace_dir).exists(), selected)
                            if selected:
                                manifest = json.loads((plugin / manifest_dir / 'plugin.json').read_text())
                                self.assertEqual(manifest['name'], 'creatly-video-director')
                                self.assertEqual(manifest['version'], version)
                                self.assertEqual(manifest['homepage'], f'https://{domain}')
                                if host == 'workbuddy':
                                    self.assertEqual(manifest['mcpServers'], expected)
                                else:
                                    self.assertEqual(manifest['mcpServers'], f'./{mcp_file}')
                            if mcp_file:
                                self.assertEqual((plugin / mcp_file).exists(), selected)
                                if selected:
                                    self.assertEqual(json.loads((plugin / mcp_file).read_text()), {'mcpServers': expected})
                        self.assertEqual((plugin / 'skills/creatly-canvas/SKILL.md').read_bytes(),
                                         (root / 'plugins/creatly-video-director/skills/creatly-canvas/SKILL.md').read_bytes())
                        self.assertIn(expected['yuanji']['url'],
                                      (plugin / 'skills/creatly-canvas/references/mcp-execution.md').read_text())
                        self.assertIn(f'源分支：`{branch}`', (output / 'INSTALL.md').read_text())
                        skill_text = (plugin / 'skills/creatly-canvas/SKILL.md').read_text()
                        self.assertIn('默认将人物、角色、场景、物品或道具', skill_text)
                        self.assertIn('只有用户明确要求', skill_text)
                        self.assertIn('不因此新建主体', skill_text)
                        for path in output.rglob('*'):
                            if path.is_file() and path.suffix in {'.md', '.json', '.yaml'}:
                                self.assertNotIn('\u5143\u6781', path.read_text(), str(path))
                        self.assertFalse((plugin / 'mcp').exists())
                        self.assertFalse((output / 'config').exists())
                        self.assertFalse(any(output.rglob('__pycache__')))
                        # Repeated identical export is safe and makes no changes.
                        exported = self.snapshot(output)
                        module.export_package(root, env, client, output)
                        self.assertEqual(self.snapshot(output), exported)
            self.assertEqual(self.snapshot(root), original)

    def test_openai_binding_is_only_exported_to_codex_in_its_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = self.copy_source(parent / 'source')
            (root / 'config/openai-apps.json').write_text(json.dumps({'test': 'plugin_asdk_app_testfixture'}))
            original = self.snapshot(root)
            for client in ['codex', 'claude', 'workbuddy', 'all']:
                output = parent / client
                module.export_package(root, 'test', client, output)
                app_file = output / 'plugins/creatly-video-director/.app.json'
                self.assertEqual(app_file.exists(), client in ('codex', 'all'))
                if app_file.exists():
                    self.assertEqual(json.loads(app_file.read_text())['apps']['yuanji']['id'], 'asdk_app_testfixture')
                for host in ['claude', 'codebuddy']:
                    manifest = output / f'plugins/creatly-video-director/.{host}-plugin/plugin.json'
                    if manifest.exists():
                        self.assertNotIn('apps', json.loads(manifest.read_text()))
            module.export_package(root, 'dev', 'codex', parent / 'dev-codex')
            self.assertFalse((parent / 'dev-codex/plugins/creatly-video-director/.app.json').exists())
            self.assertEqual(self.snapshot(root), original)

    def test_export_excludes_unreviewed_internal_material(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = self.copy_source(parent / 'source')
            plugin = root / 'plugins/creatly-video-director'
            marker = b'private-method-fixture-not-for-release'
            for relative in ['skills/film-skill/SKILL.md',
                             'skills/creatly-canvas/references/internal-methods.md',
                             'scripts/film_gate_check.py', 'docs/internal-methods.md',
                             'private-methods.zip']:
                path = plugin / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(marker)
            (root / 'config/internal-methods.md').write_bytes(marker)
            original = self.snapshot(root)
            for client in [*module.CLIENTS, 'all']:
                output = parent / client
                module.export_package(root, 'test', client, output)
                public_plugin = output / 'plugins/creatly-video-director'
                self.assertEqual({p.name for p in (public_plugin / 'skills').iterdir()}, {'creatly-canvas'})
                self.assertFalse((public_plugin / 'scripts/film_gate_check.py').exists())
                self.assertFalse((public_plugin / 'skills/creatly-canvas/references/internal-methods.md').exists())
                self.assertTrue(all(marker not in data for data in self.snapshot(output).values()))
            self.assertEqual(self.snapshot(root), original)

    def test_export_rejects_symlinked_public_file(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = self.copy_source(parent / 'source')
            secret = parent / 'internal-methods.md'
            secret.write_text('private-method-fixture-not-for-release')
            source = root / 'plugins/creatly-video-director/scripts/upload_file.py'
            source.unlink()
            source.symlink_to(secret)
            output = parent / 'export'
            with self.assertRaisesRegex(ValueError, 'regular repository file'):
                module.export_package(root, 'test', 'codex', output)
            self.assertFalse(output.exists())

    def test_export_refuses_source_paths_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = self.copy_source(parent / 'source')
            original = self.snapshot(root)
            for output in [root, parent, root / 'plugins/custom', root / '.agents']:
                with self.subTest(output=output), self.assertRaises(ValueError):
                    module.export_package(root, 'test', 'claude', output)
            output = parent / 'existing'
            output.mkdir()
            (output / 'notes.txt').write_text('user notes')
            with self.assertRaisesRegex(ValueError, 'not empty'):
                module.export_package(root, 'test', 'claude', output)
            self.assertEqual(self.snapshot(output), {Path('notes.txt'): b'user notes'})
            with self.assertRaises(ValueError):
                module.export_package(root, 'test', 'claude', parent / 'invalid-app', 'asdk_app_fixture')
            self.assertFalse((parent / 'invalid-app').exists())
            with self.assertRaises(ValueError):
                module.export_package(root, 'unknown', 'codex', parent / 'invalid-env')
            with self.assertRaises(ValueError):
                module.export_package(root, 'test', 'unknown', parent / 'invalid-client')
            self.assertEqual(self.snapshot(root), original)

    def test_cli_accepts_main_branch_and_client_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'workbuddy'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/configure-environment.py'),
                                     'main', '--client', 'workbuddy', '--output', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), str(output.resolve()))
            manifest = json.loads((output / 'plugins/creatly-video-director/.codebuddy-plugin/plugin.json').read_text())
            self.assertEqual(manifest['mcpServers']['yuanji']['url'], 'https://yuanji.studio/api/agent/mcp/v2')
            self.assertFalse((output / 'plugins/creatly-video-director/.codex-plugin').exists())

if __name__ == '__main__': unittest.main()
