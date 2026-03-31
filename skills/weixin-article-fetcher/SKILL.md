---
name: weixin-article-fetcher
description: Fetch and extract WeChat (微信) public account articles from URLs. Use this skill whenever the user wants to scrape, crawl, fetch, read, extract, download, analyze, summarize, or process content from WeChat/微信 public account article links (mp.weixin.qq.com). Also trigger for Chinese requests like "抓取微信文章"、"读取公众号内容"、"提取微信链接"、"下载公众号文章"、"分析/总结这篇微信文章". Supports single URL or batch/bulk fetching of multiple articles. Outputs structured data including title, cover image, URL, and full article body in clean Markdown format.
metadata: 
  version: v1.0.0
  author: jiangding1990
---

# WeChat Article Fetcher (微信公众号文章抓取)

Fetches WeChat public account articles by URL, bypassing the slider captcha via iOS WeChat User-Agent spoofing, and extracting structured content as clean Markdown. No browser or Playwright required.

---

## How It Works

WeChat article pages display a slider captcha to non-WeChat clients. Spoofing the iOS WeChat User-Agent bypasses it entirely — the server returns full HTML.

**User-Agent used:**
```
Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)
AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148
MicroMessenger/8.0.34(0x16082222) NetType/WIFI Language/zh_CN
```

---

## Workflow

### Step 1: Install dependencies (if needed)

```bash
python -c "import requests, bs4, markdownify" 2>/dev/null || \
  pip install -r requirements.txt
```

> **Note:** Avoid `--break-system-packages` — it modifies system-level Python and can break other tools. If you're on a managed system, prefer `pip install --user` or a virtual environment.

### Step 2: Run the script

All commands below use paths relative to the skill directory. Run them from there, or substitute the full path to `fetch_weixin.py`.

**Single article (output to stdout):**
```bash
python scripts/fetch_weixin.py "https://mp.weixin.qq.com/s/xxxx"
```

**Multiple URLs (saved to `~/weixin_output/` by default):**
```bash
python scripts/fetch_weixin.py "url1" "url2" "url3"
```

**Batch from file:**
```bash
python scripts/fetch_weixin.py --batch urls.txt
```

**Batch with custom output dir and request delay:**
```bash
python scripts/fetch_weixin.py --batch urls.txt --output ./articles --delay 2
```

`urls.txt` format — one URL per line, `#` lines are comments:
```
# 科技类文章
https://mp.weixin.qq.com/s/abc123
https://mp.weixin.qq.com/s/def456
```

### Step 3: Output

Each article produces a `.md` file named after the article title (illegal filesystem characters stripped). Batch jobs also produce `results.json`:

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

**Incremental / resume support:** if `results.json` already exists in the output directory, URLs already recorded in it are skipped automatically. New results are appended and the file is rewritten after every fetch, so a mid-run interruption loses at most one article.

When the script prints `↷ Already fetched`, **explicitly tell the user** that the article was already downloaded and show the file path from the script output. Do not silently read and summarize the file without first stating it was a duplicate.

The `.md` file structure:
```markdown
# 文章标题

![封面](https://mmbiz.qpic.cn/cover.jpg)

正文内容（标准 Markdown 格式）...
```

---

## Extraction Rules

| Field | Source |
|-------|--------|
| `title` | `<meta property="og:title">` → fallback `<title>` tag (suffix stripped) |
| `cover_image` | `<meta property="og:image" content="...">` |
| `url` | Input URL (passed through unchanged) |
| `markdown` | `#js_content` div → clean Markdown via `markdownify` |

**Content selector priority:** `#js_content` → `#page-content` → `.rich_media_content`

**Lazy images:** WeChat uses `data-src` instead of `src`. The script promotes `data-src → src` before conversion so all images appear in the Markdown output.

**Noise removed:** scripts, styles, iframes, share toolbars, QR codes, reward blocks, mini-program cards, empty block elements.

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Invalid / non-WeChat URL | Skipped immediately with warning |
| Article deleted / restricted | Raises `ValueError` with reason, logged in `results.json` |
| HTTP error / timeout | Retried up to 3×, then logged as failed |
| Rate limiting (429) | Exponential back-off: 3s → 6s → 9s |
| Missing `og:image` | `cover_image: null` in output |
| No content div found | Empty `markdown` body, warning logged |
| Duplicate filename (batch) | Auto-suffixed: `slug_1.md`, `slug_2.md`, … |

Batch jobs always complete — failures are recorded in `results.json` and do not abort the run.

---

## CLI Reference

```
fetch_weixin.py [-h] [--batch FILE] [--output DIR] [--delay SECONDS] [urls ...]

positional arguments:
  urls               One or more WeChat article URLs

options:
  --batch  / -b      Text file with one URL per line
  --output / -o      Output directory (default: ~/weixin_output/)
  --delay  / -d      Seconds between requests (default: 1.5)
```

---

## When to consult `references/html_quirks.md`

Read it if you encounter:
- Images still not rendering (unusual lazy-load variants)
- Garbled CJK content
- Video / audio embeds that need special handling  
- Password-protected or friend-only articles
- QR code images surviving the clean pass
