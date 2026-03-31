#!/usr/bin/env python3
"""
R2 Upload CLI

Uploads a file to Cloudflare R2 and prints the public URL as JSON.

Usage:
  python3 upload.py --file <path>            # local file
  python3 upload.py --base64 <data>          # base64 string or data URL
  python3 upload.py --base64-file <path>     # base64 data read from a file (avoids shell ARG_MAX)
  python3 upload.py --url <url>              # fetch remote file and re-upload

Options:
  --prefix <path>         path prefix in bucket, e.g. "images/covers"
  --name <filename>       custom filename (without extension)
  --content-type <mime>   override detected MIME type
  --bucket <name>         override R2_BUCKET_NAME env var

Required env vars:
  R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET_NAME
  R2_PUBLIC_URL           e.g. https://pub-xxx.r2.dev or custom domain

Output (stdout, JSON):
  { "url": "...", "key": "...", "size": 123, "contentType": "image/png", "uploadedAt": 1234567890 }

Errors are written to stderr; exit code is non-zero on failure.
"""

import argparse
import base64
import binascii
import json
import mimetypes
import os
import re
import secrets
import sys
import time
from pathlib import Path
from typing import NoReturn, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    import sys
    print(
        "[r2-upload] Error: boto3 is not installed.\n"
        "  Run:  pip3 install boto3\n"
        "  Then retry the upload.",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fatal(message: str) -> NoReturn:
    print(f"[r2-upload] Error: {message}", file=sys.stderr)
    sys.exit(1)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fatal(f"Missing required environment variable: {name}")
    return value  # type: ignore[return-value]


def generate_key(prefix: Optional[str], name: Optional[str], ext: str) -> str:
    timestamp = int(time.time() * 1000)
    random_suffix = secrets.token_hex(4)  # 8-char hex, cryptographically random
    safe_name = (
        re.sub(r'-{2,}', '-', re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5_-]', '-', name)).strip('-')
        if name
        else f"upload-{timestamp}"
    )
    filename = f"{safe_name}-{random_suffix}.{ext}"
    return f"{prefix.rstrip('/')}/{filename}" if prefix else filename


def ext_to_mime(ext: str) -> str:
    mime, _ = mimetypes.guess_type(f"file.{ext.lower().lstrip('.')}")
    return mime or 'application/octet-stream'


def mime_to_ext(mime: str) -> str:
    mime = mime.split(';')[0].strip()
    # mimetypes.guess_extension can return platform-specific results; use a
    # curated fallback first for the most common types.
    known = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/gif': 'gif',
        'image/webp': 'webp',
        'image/svg+xml': 'svg',
        'image/avif': 'avif',
        'image/bmp': 'bmp',
        'image/tiff': 'tiff',
        'video/mp4': 'mp4',
        'video/quicktime': 'mov',
        'video/webm': 'webm',
        'audio/mpeg': 'mp3',
        'audio/wav': 'wav',
        'audio/ogg': 'ogg',
        'audio/aac': 'aac',
        'application/pdf': 'pdf',
    }
    if mime in known:
        return known[mime]
    ext = mimetypes.guess_extension(mime)
    return ext.lstrip('.') if ext else 'bin'


def parse_base64(data: str) -> Tuple[bytes, str, str]:
    """Returns (raw_bytes, mime, ext)."""
    try:
        match = re.match(r'^data:([\w/+.-]+);base64,(.+)', data, re.DOTALL)
        if match:
            mime = match.group(1)
            raw = base64.b64decode(match.group(2), validate=True)
            return raw, mime, mime_to_ext(mime)
        # Raw base64 without data URL prefix — assume PNG
        raw = base64.b64decode(data, validate=True)
        return raw, 'image/png', 'png'
    except binascii.Error as e:
        fatal(f"Invalid base64 data: {e}")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB — applies to all input modes


# ---------------------------------------------------------------------------
# Input resolution
# ---------------------------------------------------------------------------

def resolve_input(args: argparse.Namespace) -> Tuple[bytes, str, str, Optional[str]]:
    """Returns (body, content_type, ext, suggested_name)."""

    if args.file:
        path = Path(args.file)
        if not path.exists():
            fatal(f"File not found: {args.file}")
        file_size = path.stat().st_size
        if file_size > MAX_UPLOAD_BYTES:
            fatal(
                f"File is too large ({file_size // (1024 * 1024)} MB). "
                f"Maximum allowed is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
            )
        ext = path.suffix.lstrip('.') or 'bin'
        content_type = args.content_type or ext_to_mime(ext)
        return path.read_bytes(), content_type, ext, path.stem

    if args.base64:
        body, mime, ext = parse_base64(args.base64)
        content_type = args.content_type or mime
        return body, content_type, ext, None

    if args.base64_file:
        b64_path = Path(args.base64_file)
        if not b64_path.exists():
            fatal(f"File not found: {args.base64_file}")
        body, mime, ext = parse_base64(b64_path.read_text().strip())
        if len(body) > MAX_UPLOAD_BYTES:
            fatal(
                f"Decoded data is too large ({len(body) // (1024 * 1024)} MB). "
                f"Maximum allowed is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
            )
        content_type = args.content_type or mime
        return body, content_type, ext, None

    if args.url:
        try:
            req = Request(args.url, headers={'User-Agent': 'r2-upload/1.0'})
            with urlopen(req, timeout=args.timeout) as resp:
                raw_mime = resp.headers.get('Content-Type', 'application/octet-stream')
                mime = raw_mime.split(';')[0].strip()
                content_type = args.content_type or mime
                ext = mime_to_ext(mime)
                # Pre-check via Content-Length header to fail fast before downloading
                content_length = resp.headers.get('Content-Length')
                if content_length and int(content_length) > MAX_UPLOAD_BYTES:
                    fatal(
                        f"Remote file is too large ({int(content_length) // (1024 * 1024)} MB). "
                        f"Maximum allowed is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
                        f"Download it manually and use --file instead."
                    )
                # Extract filename stem from URL path for a more meaningful object key
                url_path = urlparse(args.url).path
                url_stem = Path(url_path).stem or None
                body = resp.read()
                # Post-check: Content-Length may be absent or inaccurate
                if len(body) > MAX_UPLOAD_BYTES:
                    fatal(
                        f"Remote file is too large ({len(body) // (1024 * 1024)} MB). "
                        f"Maximum allowed is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. "
                        f"Download it manually and use --file instead."
                    )
                return body, content_type, ext, url_stem
        except HTTPError as e:
            fatal(f"Failed to fetch URL (HTTP {e.code}): {args.url}")
        except URLError as e:
            fatal(f"Failed to fetch URL: {e.reason}")

    fatal("Provide one of --file, --base64, --base64-file, or --url")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Upload a file to Cloudflare R2 and return a public URL as JSON.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python3 upload.py --file photo.jpg
  python3 upload.py --file photo.jpg --prefix images/covers --name my-photo
  python3 upload.py --base64 "data:image/png;base64,iVBOR..."
  python3 upload.py --url https://example.com/image.jpg --prefix imported
  python3 upload.py --file video.mp4 --bucket media-bucket --prefix videos
        """,
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--file',        metavar='PATH', help='Path to a local file')
    source.add_argument('--base64',      metavar='DATA', help='Base64 string or data URL')
    source.add_argument('--base64-file', metavar='PATH', help='Path to a file containing base64 data (avoids shell ARG_MAX limits)')
    source.add_argument('--url',         metavar='URL',  help='Remote URL to fetch and re-upload')

    parser.add_argument('--prefix',              metavar='PATH',  help='Path prefix inside the bucket')
    parser.add_argument('--name',                metavar='NAME',  help='Custom filename without extension')
    parser.add_argument('--content-type',        metavar='MIME',  help='Override auto-detected MIME type')
    parser.add_argument('--bucket',              metavar='NAME',  help='Override R2_BUCKET_NAME env var')
    parser.add_argument('--cache-control',       metavar='VALUE', help='Cache-Control header, e.g. "public, max-age=3600"')
    parser.add_argument('--content-disposition', metavar='VALUE', help='Content-Disposition header, e.g. "attachment; filename=file.pdf"')
    parser.add_argument('--timeout',             metavar='SECS',  type=int, default=60, help='Network timeout in seconds (default: 60)')

    args = parser.parse_args()

    # Credentials
    account_id        = require_env('R2_ACCOUNT_ID')
    access_key_id     = require_env('R2_ACCESS_KEY_ID')
    secret_access_key = require_env('R2_SECRET_ACCESS_KEY')
    bucket_name       = args.bucket or require_env('R2_BUCKET_NAME')
    public_url        = require_env('R2_PUBLIC_URL').rstrip('/')

    # Resolve input → bytes
    body, content_type, ext, suggested_name = resolve_input(args)

    # Build object key — auto-assign prefix by MIME category when not specified
    if args.prefix is not None:
        prefix = args.prefix
    elif content_type.startswith('image/'):
        prefix = 'images'
    elif content_type.startswith('video/'):
        prefix = 'videos'
    elif content_type.startswith('audio/'):
        prefix = 'audios'
    else:
        prefix = 'files'

    key = generate_key(
        prefix=prefix,
        name=args.name or suggested_name,
        ext=ext,
    )

    # Upload
    client = boto3.client(
        's3',
        region_name='auto',
        endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )

    put_kwargs: dict = dict(
        Bucket=bucket_name,
        Key=key,
        Body=body,
        ContentType=content_type,
        CacheControl=args.cache_control or 'public, max-age=31536000, immutable',
    )
    if args.content_disposition:
        put_kwargs['ContentDisposition'] = args.content_disposition

    try:
        client.put_object(**put_kwargs)
    except ClientError as e:
        fatal(f"Upload failed: {e.response['Error']['Message']}")
    except BotoCoreError as e:
        fatal(f"Upload failed: {e}")

    result = {
        'url': f'{public_url}/{key}',
        'key': key,
        'size': len(body),
        'contentType': content_type,
        'uploadedAt': int(time.time() * 1000),
    }

    print(json.dumps(result))


if __name__ == '__main__':
    main()
