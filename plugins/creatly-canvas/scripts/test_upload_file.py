import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from upload_file import inspect_file, put_file


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name) / '参考.png'
        self.file.write_bytes(b'abc')
        self.manifest = {'uploadId': 'test', 'method': 'PUT', 'sizeBytes': 3,
                         'url': 'https://bucket.oss-cn-hangzhou.aliyuncs.com/file?signature=secret',
                         'headers': {'Content-Type': 'image/png', 'Content-MD5': 'kAFQmDzST7DWlj99KOF/cg==',
                                     'x-oss-forbid-overwrite': 'true'}}

    def test_inspects_all_three_media_without_reading_into_prompt(self):
        for name, mime in [('a.png', 'image/png'), ('b.mp4', 'video/mp4'), ('c.wav', 'audio/wav'), ('d.txt', 'text/plain'), ('e.md', 'text/markdown')]:
            path = self.file.with_name(name)
            path.write_bytes(b'abc')
            self.assertEqual(inspect_file(path), {'filename': name, 'contentType': mime, 'sizeBytes': 3,
                                                  'md5': '900150983cd24fb0d6963f7d28e17f72'})

    @patch('upload_file.http.client.HTTPSConnection')
    def test_streams_exact_bytes_and_preserves_required_headers(self, constructor):
        conn = constructor.return_value
        conn.getresponse.return_value.status = 200
        result = put_file(self.file, {'structuredContent': {'output': {'upload': self.manifest}}})
        self.assertEqual(result, {'uploaded': True, 'uploadId': 'test', 'nextTool': 'upload', 'arguments': {'action': 'complete', 'uploadId': 'test'}})
        conn.send.assert_called_once_with(b'abc')
        conn.putheader.assert_any_call('Content-MD5', 'kAFQmDzST7DWlj99KOF/cg==')
        conn.putheader.assert_any_call('Content-Length', '3')
        conn.close.assert_called_once()

    @patch('upload_file.http.client.HTTPSConnection')
    def test_changed_file_rejected_before_network(self, constructor):
        self.file.write_bytes(b'xyz')
        with self.assertRaises(ValueError):
            put_file(self.file, self.manifest)
        constructor.assert_not_called()

    @patch('upload_file.http.client.HTTPSConnection')
    def test_does_not_follow_redirects_or_retry_uncertain_writes(self, constructor):
        constructor.return_value.getresponse.return_value.status = 307
        with self.assertRaises(ValueError):
            put_file(self.file, self.manifest)
        self.assertEqual(constructor.return_value.send.call_count, 1)

    def test_rejects_other_destinations(self):
        for url in ['http://bucket.aliyuncs.com/file', 'https://localhost/file', 'https://evil.example/file']:
            with self.assertRaises(ValueError):
                put_file(self.file, {**self.manifest, 'url': url})


if __name__ == '__main__':
    unittest.main()
