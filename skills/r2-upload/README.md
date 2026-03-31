# r2-upload

A [Claude Code](https://claude.ai/claude-code) skill that uploads images and files to [Cloudflare R2](https://developers.cloudflare.com/r2/) and returns a permanent public URL.

Designed as a reusable building block — other skills (image generation, cover creation, infographics, etc.) can call it directly without writing any upload code.

## Features

- **Four input modes** — local file path, base64 / data-URL string, base64 file (avoids shell limits), or remote URL (fetch + re-upload)
- **Auto-prefix by file type** — images → `images/`, videos → `videos/`, audio → `audios/`, everything else → `files/`; override anytime with `--prefix`
- **Auto MIME detection** — infers content type from file extension or base64 data-URL prefix
- **Flexible output paths** — `--prefix` for bucket directories, `--name` for custom filenames
- **Multi-bucket support** — `--bucket` overrides the default bucket per upload
- **HTTP headers** — `--cache-control` and `--content-disposition` for fine-grained control
- **500 MB upload limit** — enforced across all input modes to prevent accidental OOM
- **Clean JSON output** — `{ url, key, size, contentType, uploadedAt }` on stdout; errors on stderr
- **Zero dependencies beyond boto3** — runs with standard Python 3.8+

## Prerequisites

### 1. Python 3.8+

Python 3.8 or higher is required. Check with:

```bash
python3 --version
```

### 2. Install boto3

```bash
pip3 install boto3
```

Or using the bundled requirements file:

```bash
pip3 install -r requirements.txt
```

### 3. Configure Cloudflare R2

You need a Cloudflare account with R2 enabled. Then:

1. Go to **Cloudflare Dashboard → R2 → Manage API tokens**
2. Create a token with **Object Read & Write** permission on your bucket
3. Note your **Account ID** (top-right of the Cloudflare dashboard)
4. (Optional) Enable **Public access** on your bucket to get a `pub-xxx.r2.dev` URL, or connect a custom domain

### 4. Set environment variables

Add these to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export R2_ACCOUNT_ID="your-cloudflare-account-id"
export R2_ACCESS_KEY_ID="your-r2-token-key-id"
export R2_SECRET_ACCESS_KEY="your-r2-token-secret"
export R2_BUCKET_NAME="your-default-bucket-name"
export R2_PUBLIC_URL="https://pub-xxx.r2.dev"   # or your custom domain
```

Then reload your shell: `source ~/.zshrc`

## Installation

### Install as a Claude Code skill

```bash
# Clone or copy the skill directory into Claude's skills folder
cp -r r2-upload ~/.claude/skills/

# Install script dependencies (one-time)
pip3 install -r ~/.claude/skills/r2-upload/requirements.txt
```

Claude Code will automatically detect and load the skill.

### Manual (standalone CLI use)

```bash
git clone https://github.com/<your-username>/r2-upload
cd r2-upload/scripts
pip3 install -r requirements.txt
python3 upload.py --help
```

## Usage

### Upload a local file

```bash
python3 scripts/upload.py --file /path/to/image.png
```

With options:

```bash
python3 scripts/upload.py \
  --file /path/to/photo.jpg \
  --prefix images/travel \
  --name tokyo-tower
```

### Upload a base64 / data-URL string

```bash
# Short strings — inline is fine
python3 scripts/upload.py \
  --base64 "data:image/png;base64,iVBORw0KGgo..."

# Long strings — use --base64-file to avoid shell ARG_MAX limits
printf '%s' "$BASE64_DATA" > /tmp/upload_input.b64
python3 scripts/upload.py \
  --base64-file /tmp/upload_input.b64
rm -f /tmp/upload_input.b64
```

### Re-upload from a remote URL

Fetches the remote file and stores a copy in your R2 bucket. The prefix is chosen
automatically from the MIME type (e.g. images go to `images/`):

```bash
python3 scripts/upload.py \
  --url "https://example.com/original.jpg"
```

### Upload to a specific bucket

```bash
python3 scripts/upload.py \
  --file /path/to/doc.pdf \
  --bucket my-private-bucket \
  --prefix documents/2024
```

### Upload with custom HTTP headers

```bash
# Set custom cache policy
python3 scripts/upload.py \
  --file /path/to/image.png \
  --cache-control "public, max-age=3600"

# Force download with filename
python3 scripts/upload.py \
  --file /path/to/report.pdf \
  --content-disposition "attachment; filename=report.pdf"
```

## Options

| Flag                    | Required      | Description                                                   |
|-------------------------|---------------|---------------------------------------------------------------|
| `--file`                | One of four   | Path to a local file                                          |
| `--base64`              | One of four   | Base64 string or data URL (`data:image/png;base64,…`)         |
| `--base64-file`         | One of four   | Path to a file containing base64 data (recommended for large payloads) |
| `--url`                 | One of four   | Remote URL to fetch and re-upload                             |
| `--prefix`              | No            | Path prefix inside the bucket (auto-selected by MIME type if omitted) |
| `--name`                | No            | Custom filename without extension (auto-generated if omitted)  |
| `--content-type`        | No            | Override auto-detected MIME type, e.g. `image/webp`           |
| `--bucket`              | No            | Override the default bucket from `R2_BUCKET_NAME`             |
| `--cache-control`       | No            | Cache-Control header (default: `public, max-age=31536000, immutable`) |
| `--content-disposition` | No            | Content-Disposition header, e.g. `attachment; filename=f.pdf` |
| `--timeout`             | No            | Network timeout in seconds (default: 60)                      |

Exactly one of `--file`, `--base64`, `--base64-file`, or `--url` must be provided.

### Auto-prefix by file type

When `--prefix` is omitted, the bucket path prefix is chosen automatically:

| File category     | Auto prefix |
|-------------------|-------------|
| Images (`image/*`) | `images`   |
| Videos (`video/*`) | `videos`   |
| Audio  (`audio/*`) | `audios`   |
| Everything else    | `files`    |

## Output

On success, the script prints a single JSON object to **stdout**:

```json
{
  "url": "https://pub-xxx.r2.dev/images/travel/tokyo-tower-a1b2c3d.jpg",
  "key": "images/travel/tokyo-tower-a1b2c3d.jpg",
  "size": 204800,
  "contentType": "image/jpeg",
  "uploadedAt": 1710835200000
}
```

| Field         | Type   | Description                            |
|---------------|--------|----------------------------------------|
| `url`         | string | Permanent public URL of the uploaded file |
| `key`         | string | Object key (path) inside the bucket   |
| `size`        | number | File size in bytes                     |
| `contentType` | string | MIME type of the uploaded file         |
| `uploadedAt`  | number | Unix timestamp (ms) of the upload      |

On error, the script writes a message to **stderr** and exits with a non-zero code.

### Extracting the URL in shell

```bash
RESULT=$(python3 scripts/upload.py --file image.png)
URL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")
echo "Uploaded: $URL"
```

## Supported file types

MIME types are detected automatically from the file extension or base64 data-URL prefix:

| Extension       | Content-Type            |
|-----------------|-------------------------|
| jpg / jpeg      | image/jpeg              |
| png             | image/png               |
| gif             | image/gif               |
| webp            | image/webp              |
| svg             | image/svg+xml           |
| avif            | image/avif              |
| bmp             | image/bmp               |
| tiff            | image/tiff              |
| mp4             | video/mp4               |
| mov             | video/quicktime         |
| webm            | video/webm              |
| mp3             | audio/mpeg              |
| wav             | audio/wav               |
| ogg             | audio/ogg               |
| aac             | audio/aac               |
| pdf             | application/pdf         |
| others          | application/octet-stream |

Use `--content-type` to override when needed.

## Integration with other Claude Code skills

This skill is designed to be called from other skills. After any skill generates a file,
it can delegate hosting to `r2-upload`. The prefix is chosen automatically from the MIME
type, so callers rarely need to pass `--prefix` explicitly.

```
# Typical pattern used by image-gen, cover, infographic skills:

1. Generate image → save to /tmp/output.png
2. Run r2-upload: python3 upload.py --file /tmp/output.png
3. Parse JSON output → extract "url"
4. Return the URL to the user
```

Example in shell:

```bash
# After generating the image...
OUTPUT=$(python3 ~/.claude/skills/r2-upload/scripts/upload.py \
  --file /tmp/cover.png)

PUBLIC_URL=$(echo "$OUTPUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['url'])")

echo "Image hosted at: $PUBLIC_URL"
```

Pass `--prefix` only when a specific sub-path is needed (e.g. `--prefix images/covers`).

## Environment variables reference

| Variable               | Required | Description                                               |
|------------------------|----------|-----------------------------------------------------------|
| `R2_ACCOUNT_ID`        | Yes      | Your Cloudflare Account ID                                |
| `R2_ACCESS_KEY_ID`     | Yes      | R2 API token key ID                                       |
| `R2_SECRET_ACCESS_KEY` | Yes      | R2 API token secret                                       |
| `R2_BUCKET_NAME`       | Yes      | Default bucket name (overridable with `--bucket`)         |
| `R2_PUBLIC_URL`        | Yes      | Public base URL, e.g. `https://pub-xxx.r2.dev`            |

## File structure

```
r2-upload/
├── SKILL.md              # Claude Code skill instructions (auto-loaded)
├── README.md             # This file
├── requirements.txt      # Python dependencies (boto3)
└── scripts/
    ├── upload.py         # CLI upload script
    └── check_env.py      # Environment checker (run before first upload)
```

## Environment check

You don't need to run the checker before every upload — `upload.py` already
produces clear error messages on its own. Run `check_env.py` only when:

- This is your **first time** setting up the skill, **or**
- An upload just **failed** and you want a full diagnosis

```bash
python3 scripts/check_env.py
```

Example output when everything is ready:

```json
{
  "ok": true,
  "checks": [
    { "name": "python_version", "label": "Python 3.8+", "ok": true, "value": "3.11.0", "fix": null },
    { "name": "boto3",          "label": "boto3 installed", "ok": true, "value": "1.34.0", "fix": null },
    { "name": "R2_ACCOUNT_ID",  "label": "$R2_ACCOUNT_ID (Cloudflare Account ID)", "ok": true, "value": "abc1…d234", "fix": null },
    ...
  ],
  "summary": "All checks passed. Ready to upload."
}
```

If any check fails, the `fix` field tells you exactly what to run or configure.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Missing required environment variable: R2_ACCOUNT_ID` | Env vars not set | Add all 5 vars to your shell profile and reload |
| `ModuleNotFoundError: No module named 'boto3'` | Deps not installed | Run `pip3 install boto3` |
| `File is too large` | Local file exceeds 500 MB | Compress or split the file before uploading |
| `Decoded data is too large` | base64 payload exceeds 500 MB after decoding | Use a smaller file or compress first |
| `Remote file is too large` | Remote file exceeds 500 MB | Download manually and use `--file` instead |
| `Invalid base64 data` | Corrupted or truncated base64 string | Re-generate the base64 data and try again |
| `File not found` | Path passed to `--file` or `--base64-file` does not exist | Check the file path and try again |
| `Failed to fetch URL (HTTP 403)` | Remote URL is access-controlled | Download it manually, use `--file` instead |
| Upload succeeds but URL returns 403 | Bucket not public | Enable Public Access in Cloudflare R2 dashboard |
| `python3: command not found` | Python 3 not installed | Install from https://python.org |
| Process exits with `InvalidAccessKeyId` | Wrong credentials | Double-check Account ID, Key ID, and Secret |
| `NoSuchBucket` error | Bucket doesn't exist | Create the bucket in Cloudflare Dashboard first |
| URL looks wrong after upload | `R2_PUBLIC_URL` missing `https://` | Re-run `check_env.py` — it now validates the URL format |

## Requirements

- Python 3.8+
- [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) ≥ 1.26
- Cloudflare R2 bucket with an API token (Object Read & Write)
- Public access enabled on the bucket (for public URLs)

## License

MIT
