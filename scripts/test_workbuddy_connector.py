import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('workbuddy_connector', ROOT / 'scripts/package-workbuddy-connector.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WorkBuddyConnectorTest(unittest.TestCase):
    def source(self, destination):
        files = ['plugins/creatly-canvas/' + name
                 for name in module.environment_config.PUBLIC_PLUGIN_FILES]
        files += ['README.md', '.agents/plugins/marketplace.json', '.claude-plugin/marketplace.json',
                  '.codebuddy-plugin/marketplace.json', 'config/openai-apps.json',
                  'connectors/workbuddy/icon.svg', 'connectors/workbuddy/tool-guide.md']
        for relative in files:
            path = ROOT / relative
            if path.exists():
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        return destination

    def test_environment_matrix_has_native_connector_schema_and_clean_archive_root(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            source = self.source(parent / 'source')
            original = module.snapshot(source)
            sources = set()
            for branch, domain in [('main', 'creatly.cn'), ('test', 'test.yuanji.studio'),
                                   ('dev', 'dev.yuanji.studio')]:
                with self.subTest(branch=branch):
                    output, archive = module.package_connector(source, branch, parent / branch / 'connector')
                    metadata = module.validate_connector(output)
                    sources.add(metadata['source'])
                    self.assertEqual(metadata['minWorkbuddyVersion'], '4.24.0')
                    self.assertNotIn('auth_mode', metadata)
                    mcp = json.loads((output / 'mcp.json').read_text())
                    self.assertEqual(mcp, {'mcpServers': {'creatly': {
                        'type': 'streamableHttp', 'url': f'https://{domain}/api/agent/mcp/v2', 'timeout': 30000}}})
                    skill = (output / 'skills/creatly-canvas/SKILL.md').read_text()
                    self.assertIn('@references/workbuddy-tools.md', skill)
                    self.assertIn('description_zh:', skill)
                    self.assertIn('description_en:', skill)
                    self.assertIn('author: "Creatly"', skill)
                    self.assertIn('只有用户明确要求', skill)
                    self.assertIn('不因此新建主体', skill)
                    self.assertTrue(metadata['name_zh'].startswith('Creatly '))
                    for path in output.rglob('*'):
                        if path.is_file() and path.suffix in {'.md', '.json', '.yaml'}:
                            self.assertNotIn('\u5143\u6781', path.read_text(), str(path))
                    self.assertIn(f'https://{domain}/api/agent/mcp/v2',
                                  (output / 'skills/creatly-canvas/references/mcp-execution.md').read_text())
                    with zipfile.ZipFile(archive) as z:
                        self.assertIsNone(z.testzip())
                        names = z.namelist()
                        self.assertTrue({'connector-meta.json', 'mcp.json', 'icon.svg'} <= set(names))
                        self.assertFalse(any(name.startswith(('plugins/', '.codebuddy-plugin/', '.agents/')) for name in names))
                        self.assertFalse(any('/agents/' in name or '/film-skill/' in name for name in names))
                        self.assertFalse(any(name.startswith('/') or '..' in Path(name).parts for name in names))
                        self.assertEqual({name: z.read(name) for name in names}, module.snapshot(output))
                    packed = archive.read_bytes()
                    module.package_connector(source, branch, output)
                    self.assertEqual(archive.read_bytes(), packed)
            self.assertEqual(sources, {'creatly-canvas', 'creatly-canvas-test', 'creatly-canvas-dev'})
            self.assertEqual(module.snapshot(source), original)

    def test_private_material_added_beside_public_files_is_not_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            source = self.source(parent / 'source')
            marker = b'private-workflow-fixture-not-for-distribution'
            for relative in ['skills/film-skill/SKILL.md', 'skills/creatly-canvas/references/private-method.md',
                             'scripts/film_gate_check.py', 'private.zip']:
                path = source / 'plugins/creatly-canvas' / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(marker)
            output, archive = module.package_connector(source, 'main', parent / 'connector')
            self.assertTrue(all(marker not in data for data in module.snapshot(output).values()))
            with zipfile.ZipFile(archive) as z:
                self.assertTrue(all(marker not in z.read(name) for name in z.namelist()))

    def test_existing_directory_and_archive_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            source = self.source(parent / 'source')
            output = parent / 'connector'
            output.mkdir()
            (output / 'notes.txt').write_text('user notes')
            with self.assertRaisesRegex(ValueError, 'not empty'):
                module.package_connector(source, 'test', output)
            self.assertEqual(module.snapshot(output), {'notes.txt': b'user notes'})
            other = parent / 'new-connector'
            version = module.environment_config.ENVIRONMENTS['test'][3]
            archive = parent / f'creatly-canvas-test-{version}.zip'
            archive.write_bytes(b'user archive')
            with self.assertRaisesRegex(ValueError, 'Archive already exists'):
                module.package_connector(source, 'test', other)
            self.assertEqual(archive.read_bytes(), b'user archive')
            self.assertFalse(other.exists())

    def test_source_paths_symlink_and_invalid_transport_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            source = self.source(parent / 'source')
            for output in [source, parent, source / 'private-export']:
                with self.assertRaises(ValueError):
                    module.package_connector(source, 'main', output)
            output, archive = module.package_connector(source, 'main', parent / 'connector')
            mcp_file = output / 'mcp.json'
            data = json.loads(mcp_file.read_text())
            data['mcpServers']['creatly']['type'] = 'http'
            mcp_file.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'transport'):
                module.validate_connector(output)
            icon = source / 'connectors/workbuddy/icon.svg'
            icon.unlink()
            icon.symlink_to(ROOT / 'connectors/workbuddy/icon.svg')
            with self.assertRaisesRegex(ValueError, 'regular reviewed file'):
                module.package_connector(source, 'test', parent / 'symlink-connector')

    def test_cli_builds_submission_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'connector'
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/package-workbuddy-connector.py'),
                                     'test', '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = json.loads(result.stdout)
            self.assertEqual(Path(result['directory']), output.resolve())
            self.assertTrue(Path(result['zip']).is_file())
            self.assertEqual(module.validate_connector(output)['source'], 'creatly-canvas-test')


if __name__ == '__main__':
    unittest.main()
