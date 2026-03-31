# WeChat Article HTML Quirks Reference

Reference for edge cases encountered when scraping WeChat articles.

---

## 1. Lazy-loaded Images (`data-src`)

WeChat uses `data-src` instead of `src` for images to defer loading.

**Problem**: `<img data-src="https://mmbiz.qpic.cn/..." src="">` — `src` is empty.

**Fix** (already in `fix_lazy_images()`):
```python
data_src = img.get("data-src") or img.get("data-lazysrc")
if data_src:
    img["src"] = data_src
```

**markdownify** then picks up the corrected `src` when generating `![](url)`.

---

## 2. Video Embeds

WeChat embeds videos as `<mpvoice>` or `<iframe>` tags pointing to `v.qq.com`.

**Behavior**: These are stripped by default (iframes removed). If you want to preserve them:
```python
# In html_to_markdown(), use markdownify's convert_iframe or add custom converter
```

For a simple text placeholder:
```python
for video in content_div.find_all(["mpvoice", "mpvideo"]):
    video.replace_with(soup.new_tag("p"))
    # or replace with a [视频] placeholder
```

---

## 3. Password-Protected Articles

If the article requires a password, the `js_content` div will be empty or replaced with a login prompt. There is no programmatic bypass — these articles cannot be scraped.

**Detection**:
```python
if "该内容已被作者设置" in html or "仅限朋友可见" in html:
    raise ValueError("Article is password-protected or friend-only")
```

---

## 4. Deleted / Expired Articles

WeChat articles can be deleted by the author or taken down by WeChat.

**Detection**:
```python
if "该内容已被删除" in html or "此内容因违规无法查看" in html:
    raise ValueError("Article has been deleted or removed")
```

---

## 5. Garbled Encoding

WeChat pages declare their encoding in the `Content-Type` response header (`charset=utf-8`). The script parses this header directly and falls back to UTF-8 if absent — it does **not** use `apparent_encoding` / chardet, since chardet can mis-detect CJK text.

If you still see garbled characters after the header is parsed correctly, force UTF-8 explicitly:

```python
resp.encoding = "utf-8"
```

---

## 6. QR Code Images

WeChat often injects a QR code image at the bottom of articles for sharing.

**The `js_pc_qr_code` selector** handles most cases. If you still see rogue QR images, look for:
```python
for img in content_div.find_all("img"):
    src = img.get("src", "")
    if "qrcode" in src or "qr_code" in src:
        img.decompose()
```

---

## 7. `rich_media_area_primary` vs `js_content`

Some article templates use `#rich_media_area_primary` as the outer wrapper with `#js_content` inside. The script already handles this by targeting `#js_content` first, which is always the innermost content container.

---

## 8. Rate Limiting

WeChat returns **HTTP 429** when you make too many requests in quick succession from the same IP. The script handles this automatically with exponential back-off (3 s → 6 s → 9 s, up to 3 retries). If all retries are exhausted, the URL is marked as failed in `results.json`.

**Additional mitigations**:
- The `--delay` flag (default 1.5 s) controls the pause *between* articles in batch mode; increase it if you still hit limits.
- Consider varying the `MicroMessenger` version in the User-Agent string across sessions.

---

## 9. CDN Image URLs

Cover images from `og:image` are served from `mmbiz.qpic.cn`. These are publicly accessible without authentication and can be downloaded directly.

Image URLs follow this pattern:
```
https://mmbiz.qpic.cn/mmbiz_jpg/<hash>/<id>/640?wx_fmt=jpeg
```

To download images locally, append `&wx_co=1` is sometimes needed for certain CDN nodes.
