# weixin-article-fetcher

A [Claude Code](https://claude.ai/claude-code) skill that fetches WeChat public account articles by URL and converts them to clean Markdown — no browser or Playwright required.

Bypasses the WeChat slider captcha by spoofing the iOS WeChat User-Agent, then extracts structured content including title, cover image, and full article body.

## Features

- **No browser needed** — pure HTTP request via iOS WeChat User-Agent spoofing
- **Three fetch modes** — single article (stdout), multiple URLs, or batch from a text file
- **Clean Markdown output** — lazy-loaded images promoted, noise elements stripped
- **Resume support** — already-fetched URLs are skipped automatically via `results.json`
- **Rate limit handling** — HTTP 429 triggers linear back-off (3s → 6s → 9s)
- **Randomized User-Agent pool** — rotates across iOS 15–18 and WeChat 8.0.47–8.0.52 profiles
- **Structured output** — title, cover image URL, article body, and fetch status per article

## Prerequisites

Python 3.8+ with the following packages:

```bash
pip install -r requirements.txt
```

## Installation

Copy the skill directory into Claude Code's skills folder:

```bash
cp -r weixin-article-fetcher ~/.claude/skills/
```

Claude Code auto-loads skills from `~/.claude/skills/` on startup.

## Usage

### Single article (printed to stdout)

```bash
python3 scripts/fetch_weixin.py "https://mp.weixin.qq.com/s/xxxx"
```

### Multiple URLs (saved to `~/weixin_output/`)

```bash
python3 scripts/fetch_weixin.py "url1" "url2" "url3"
```

### Batch from a file

```bash
python3 scripts/fetch_weixin.py --batch urls.txt
```

`urls.txt` format — one URL per line, lines starting with `#` are ignored:

```
# 科技类文章
https://mp.weixin.qq.com/s/abc123
https://mp.weixin.qq.com/s/def456
```

### Custom output directory and request delay

```bash
python3 scripts/fetch_weixin.py --batch urls.txt --output ./articles --delay 2
```

## Options

| Flag | Description |
|------|-------------|
| `--batch` / `-b` | Text file with one URL per line |
| `--output` / `-o` | Output directory (default: stdout for single URL, `~/weixin_output/` for multiple) |
| `--delay` / `-d` | Seconds between requests (default: 1.5) |

## Output

**Single URL** — markdown is printed to stdout in this format:

```markdown
# 文章标题

![封面](https://mmbiz.qpic.cn/cover.jpg)

正文内容（标准 Markdown 格式）...
```

**Multiple URLs / batch** — each article is saved as `<title>.md` in the output directory. A `results.json` summary is also written:

```json
{
  "url": "https://mp.weixin.qq.com/s/...",
  "article_id": "xxxxxxxxxxxxxxxx",
  "title": "文章标题",
  "cover_image": "https://mmbiz.qpic.cn/...",
  "status": "ok",
  "file": "weixin_output/文章标题.md"
}
```

If `results.json` already exists in the output directory, previously fetched URLs are skipped and new results are appended — safe to re-run after an interruption.

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid / non-WeChat URL | Skipped with warning |
| Article deleted / restricted | Logged as failed in `results.json` |
| HTTP error / timeout | Retried up to 3×, then logged as failed |
| Rate limiting (429) | Linear back-off: 3s → 6s → 9s |
| Missing cover image | `cover_image: null` in output |
| No content div found | Empty body, warning logged |
| Duplicate filename | Auto-suffixed: `title_1.md`, `title_2.md`, … |

## File Structure

```
weixin-article-fetcher/
├── SKILL.md              # Claude Code skill entry point (auto-loaded)
├── README.md             # This file
├── requirements.txt      # Python dependencies
└── scripts/
    └── fetch_weixin.py   # CLI fetch script
```

## Requirements

- Python 3.8+
- [requests](https://docs.python-requests.org/) ≥ 2.28
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) ≥ 4.12
- [markdownify](https://github.com/matthewwithanm/python-markdownify) ≥ 0.11

## License

MIT
