#!/usr/bin/env python3
"""Local file metadata and streaming transfer for Creatly's remote upload MCP tools."""
import argparse
import base64
import hashlib
import http.client
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

MIME = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.webp': 'image/webp', '.gif': 'image/gif', '.bmp': 'image/bmp',
    '.tif': 'image/tiff', '.tiff': 'image/tiff', '.mp4': 'video/mp4',
    '.mov': 'video/quicktime', '.avi': 'video/x-msvideo', '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav', '.m4a': 'audio/mp4',
    '.txt': 'text/plain', '.md': 'text/markdown',
}


def inspect_file(path):
    mime = MIME.get(path.suffix.lower())
    if mime is None:
        raise ValueError('Unsupported media extension')
    digest = hashlib.md5()
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return {'filename': path.name, 'contentType': mime,
            'sizeBytes': path.stat().st_size, 'md5': digest.hexdigest()}


def find_upload(value):
    if isinstance(value, dict):
        if all(key in value for key in ('uploadId', 'url', 'method', 'headers', 'sizeBytes')):
            return value
        for key in ('upload', 'output', 'result', 'structuredContent'):
            if key in value:
                found = find_upload(value[key])
                if found:
                    return found
    return None


def put_file(path, manifest):
    upload = find_upload(manifest)
    if not upload or upload['method'] != 'PUT':
        raise ValueError('Expected the upload(action=prepare) JSON response')
    meta = inspect_file(path)
    headers = upload['headers']
    expected_md5 = base64.b64encode(bytes.fromhex(meta['md5'])).decode('ascii')
    if (meta['sizeBytes'] != upload['sizeBytes']
            or headers.get('Content-MD5') != expected_md5
            or headers.get('Content-Type') != meta['contentType']
            or headers.get('x-oss-forbid-overwrite') != 'true'):
        raise ValueError('File differs from the prepared upload; no bytes sent')
    uri = urlsplit(upload['url'])
    if (uri.scheme != 'https' or not uri.hostname or uri.username or uri.password
            or uri.fragment or uri.port not in (None, 443)
            or not uri.hostname.endswith('.aliyuncs.com')):
        raise ValueError('Expected an HTTPS Aliyun OSS upload URL')
    connection = http.client.HTTPSConnection(uri.hostname, timeout=120)
    try:
        # No redirects or automatic retries: an uncertain PUT is checked via upload(action=complete).
        connection.putrequest('PUT', uri.path + ('?' + uri.query if uri.query else ''))
        for key in ('Content-Type', 'Content-MD5', 'x-oss-forbid-overwrite'):
            connection.putheader(key, headers[key])
        connection.putheader('Content-Length', str(meta['sizeBytes']))
        connection.endheaders()
        with path.open('rb') as stream:
            while chunk := stream.read(1024 * 1024):
                connection.send(chunk)
        response = connection.getresponse()
        response.read(8192)
        if response.status not in (200, 201):
            raise ValueError(f'OSS returned HTTP {response.status}; check upload(action=complete) before retrying')
        return {'uploaded': True, 'uploadId': upload['uploadId'], 'nextTool': 'upload', 'arguments': {'action': 'complete', 'uploadId': upload['uploadId']}}
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('inspect', 'put'))
    parser.add_argument('file', type=Path)
    parser.add_argument('--prepared', type=Path, help='Private JSON file containing upload(action=prepare) result')
    args = parser.parse_args()
    if args.operation == 'inspect':
        result = inspect_file(args.file)
    else:
        if not args.prepared:
            parser.error('put requires --prepared')
        result = put_file(args.file, json.loads(args.prepared.read_text()))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Never print signed URLs, request headers or credentials.
        print(str(error) if isinstance(error, ValueError) else f'Upload failed: {type(error).__name__}; check upload(action=complete) before retrying', file=sys.stderr)
        sys.exit(1)
