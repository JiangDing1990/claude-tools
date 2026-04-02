#!/usr/bin/env python3
"""
WeChat (微信) Public Account Article Fetcher
Fetches articles by spoofing the WeChat iOS client User-Agent to bypass slider captchas.

Usage:
    python fetch_weixin.py "https://mp.weixin.qq.com/s/xxxx"
    python fetch_weixin.py "url1" "url2" "url3"
    python fetch_weixin.py --batch urls.txt
    python fetch_weixin.py --batch urls.txt --output ./my_articles
"""

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    from markdownify import markdownify as md_convert
except ImportError:
    print("缺少依赖，请运行：")
    print("  pip install requests beautifulsoup4 markdownify")
    sys.exit(1)


# ── Constants ──────────────────────────────────────────────────────────────────

# ── User-Agent pool ────────────────────────────────────────────────────────────
# Each entry: (ios_version, webkit_version, mobile_build)
# Covers iOS 15–18 as shipped on real devices; WebKit 605.1.15 is what WeChat
# consistently reports across all these versions via WKWebView.
_IOS_PROFILES = [
    ("15_8_3", "605.1.15", "19H370"),
    ("16_6_1", "605.1.15", "20G81"),
    ("16_7_8", "605.1.15", "20H343"),
    ("17_4_1", "605.1.15", "21E236"),
    ("17_5_1", "605.1.15", "21F90"),
    ("17_6_1", "605.1.15", "21G93"),
    ("18_0",   "605.1.15", "22A3354"),
    ("18_1_1", "605.1.15", "22B91"),
    ("18_2",   "605.1.15", "22C152"),
]

# Each entry: (wechat_version, hex_build)
_WECHAT_VERSIONS = [
    ("8.0.47", "0x18002f27"),
    ("8.0.48", "0x18003000"),
    ("8.0.49", "0x18003100"),
    ("8.0.50", "0x18003200"),
    ("8.0.51", "0x18003300"),
    ("8.0.52", "0x18003400"),
]

# Weighted toward WIFI to reflect real-world iPhone usage distribution
_NET_TYPES = ["WIFI"] * 5 + ["4G"] * 3 + ["5G"] * 2


def random_weixin_ua() -> str:
    """Generate a randomized but realistic WeChat iOS User-Agent string."""
    ios_ver, webkit_ver, mobile_build = random.choice(_IOS_PROFILES)
    wechat_ver, wechat_hex = random.choice(_WECHAT_VERSIONS)
    net_type = random.choice(_NET_TYPES)
    return (
        f"Mozilla/5.0 (iPhone; CPU iPhone OS {ios_ver} like Mac OS X) "
        f"AppleWebKit/{webkit_ver} (KHTML, like Gecko) Mobile/{mobile_build} "
        f"MicroMessenger/{wechat_ver}({wechat_hex}) NetType/{net_type} Language/zh_CN"
    )


# Static headers shared across all requests (UA is set per-request)
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://mp.weixin.qq.com/",
}

# Noise elements to remove before Markdown conversion
REMOVE_SELECTORS = [
    "#js_pc_qr_code",
    "#js_profile_outer_wrap",
    "#js_tags_preview_toast",
    "#js_bottom_bar",
    "#js_read_bar",
    "#content_bottom_area",
    ".rich_media_tool",
    ".share_notice",
    ".qr_code_pc",
    ".reward_qrcode_area",       # tip/reward QR block
    ".weapp_display_element",    # mini-program cards
    "script",
    "style",
    "iframe",
]

# Signals that an article is unavailable
UNAVAILABLE_SIGNALS = [
    "该内容已被发布者删除",
    "此内容因违规无法查看",
    "该账号已被封禁",
    "该公众号已迁移",
    "仅限朋友可见",
    "此内容不可见",
]

# WeChat title suffixes to strip
TITLE_SUFFIXES = [
    " - 微信公众平台",
    " | 微信公众平台",
    "—微信公众平台",
    " - 公众号 - 腾讯",
]

# Noisy img attributes to remove
IMG_NOISE_ATTRS = {
    "srcset", "data-srcset", "data-w", "data-ratio",
    "data-type", "data-fail", "_width", "crossorigin",
}


# ── Session ────────────────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    """Create a persistent session with WeChat headers and a random initial UA."""
    session = requests.Session()
    session.headers.update(HEADERS)
    session.headers["User-Agent"] = random_weixin_ua()
    return session


# ── URL validation ─────────────────────────────────────────────────────────────

def is_valid_weixin_url(url: str) -> bool:
    """Return True only for valid mp.weixin.qq.com article URLs."""
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        if parsed.netloc != "mp.weixin.qq.com":
            return False
        return bool(parsed.path.strip("/")) or bool(parsed.query)
    except Exception:
        return False


# ── Fetching ───────────────────────────────────────────────────────────────────

def fetch_html(url: str, session: requests.Session,
               retries: int = 3, delay: float = 3.0) -> str:
    """
    Fetch raw HTML from a WeChat article URL with retry + exponential back-off.
    Rotates the User-Agent on every call to reduce fingerprinting risk.
    Reuses the session for TCP keep-alive across batch requests.
    """
    session.headers["User-Agent"] = random_weixin_ua()
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=20)

            if resp.status_code == 429:
                wait = delay * attempt  # 3s, 6s, 9s
                print(f"  ⚠ 触发限流 (429)，等待 {wait:.0f}s "
                      f"（第 {attempt}/{retries} 次重试）…")
                time.sleep(wait)
                continue

            resp.raise_for_status()

            # WeChat pages are UTF-8. Use Content-Type header rather than
            # apparent_encoding (chardet) which can mis-detect CJK text.
            ct = resp.headers.get("Content-Type", "")
            m = re.search(r"charset=([\w-]+)", ct, re.IGNORECASE)
            resp.encoding = m.group(1) if m else "utf-8"

            return resp.text

        except requests.RequestException as exc:
            print(f"  ✗ 第 {attempt}/{retries} 次请求失败：{exc}")
            if attempt < retries:
                time.sleep(delay)

    raise RuntimeError(f"Failed to fetch after {retries} attempts: {url}")


# ── Content guard ─────────────────────────────────────────────────────────────

def check_unavailable(html: str) -> Optional[str]:
    """Return a reason string if the article is deleted/restricted, else None."""
    for signal in UNAVAILABLE_SIGNALS:
        if signal in html:
            return signal
    return None


# ── Extraction ─────────────────────────────────────────────────────────────────

def extract_title(soup: BeautifulSoup) -> str:
    """Extract article title, preferring og:title (no site suffix) over <title>."""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content", "").strip():
        return og_title["content"].strip()

    title_tag = soup.find("title")
    if not title_tag:
        return "Untitled"
    title = title_tag.get_text(strip=True)
    for suffix in TITLE_SUFFIXES:
        title = title.replace(suffix, "")
    return title.strip() or "Untitled"


def extract_cover_image(soup: BeautifulSoup) -> Optional[str]:
    """Extract cover image URL from og:image meta tag."""
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content", "").strip():
        return og_image["content"].strip()
    tw_image = soup.find("meta", attrs={"name": "twitter:image"})
    if tw_image and tw_image.get("content", "").strip():
        return tw_image["content"].strip()
    return None


def fix_lazy_images(content_div: BeautifulSoup) -> None:
    """
    Promote data-src → src for WeChat's lazy-loaded images so markdownify
    emits the correct URLs. Drops images with no resolvable src.
    """
    for img in content_div.find_all("img"):
        data_src = img.get("data-src") or img.get("data-lazysrc")
        if data_src:
            img["src"] = data_src.strip()
        for attr in IMG_NOISE_ATTRS:
            if img.has_attr(attr):
                del img[attr]
        if not img.get("src"):
            img.decompose()


def clean_content(content_div: BeautifulSoup) -> None:
    """
    Strip noise elements from the content div.
    Collects all targets first to avoid mutating the tree mid-iteration,
    then deduplicates by object id to prevent double-decompose errors.
    """
    to_remove = []
    for selector in REMOVE_SELECTORS:
        to_remove.extend(content_div.select(selector))

    for tag in content_div.find_all(["p", "div", "section", "span"]):
        if not tag.get_text(strip=True) and not tag.find("img"):
            to_remove.append(tag)

    seen: set = set()
    for el in to_remove:
        eid = id(el)
        if eid not in seen:
            seen.add(eid)
            try:
                el.decompose()
            except Exception:
                pass  # already removed as a child of an earlier decomposed parent


def html_to_markdown(content_div: BeautifulSoup) -> str:
    """Convert cleaned content div HTML to well-formatted Markdown."""
    raw = md_convert(
        str(content_div),
        heading_style="ATX",
        bullets="-",
    )
    raw = re.sub(r"\n{3,}", "\n\n", raw)          # collapse excess blank lines
    raw = "\n".join(line.rstrip() for line in raw.splitlines())  # strip trailing spaces
    return raw.strip()


def extract_article(html: str, url: str) -> dict:
    """Parse raw HTML and return a structured article dict."""
    soup = BeautifulSoup(html, "html.parser")

    title = extract_title(soup)
    cover_image = extract_cover_image(soup)

    content_div = (
        soup.find(id="js_content")
        or soup.find(id="page-content")
        or soup.find(class_="rich_media_content")
    )

    if not content_div:
        print(f"  ⚠ 未找到正文内容区域：{url}")
        markdown_body = ""
    else:
        fix_lazy_images(content_div)
        clean_content(content_div)
        markdown_body = html_to_markdown(content_div)

    parts = [f"# {title}", ""]
    if cover_image:
        parts += [f"![封面]({cover_image})", ""]
    parts.append(markdown_body)
    full_markdown = "\n".join(parts).strip()

    return {
        "url": url,
        "title": title,
        "cover_image": cover_image,
        "markdown": full_markdown,
    }


# ── I/O helpers ────────────────────────────────────────────────────────────────

def slug_from_url(url: str) -> str:
    """Derive a filesystem-safe slug from a WeChat article URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    s_param = qs.get("s", [None])[0]
    path_part = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    slug = s_param or path_part or "article"
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", slug)[:64]
    return slug or "article"


def slug_from_title(title: str, max_len: int = 80) -> str:
    """Derive a filesystem-safe filename from the article title.

    Strips characters illegal on common filesystems (Windows-safe superset),
    collapses whitespace, and trims to max_len characters.
    Falls back to "article" if nothing meaningful remains.
    """
    slug = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "", title)
    slug = re.sub(r"\s+", " ", slug).strip().strip(".")
    return slug[:max_len].strip() or "article"


def extract_article_id(url: str) -> str:
    """Extract a stable article ID from a WeChat URL.

    Short URL (…/s/<id>): returns the path segment.
    Long URL with ?s=<id>: returns that query-param value.
    Falls back to the full URL when neither is found.
    """
    parsed = urlparse(url.strip())
    qs = parse_qs(parsed.query)
    s_param = qs.get("s", [None])[0]
    path_part = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return s_param or path_part or url


def unique_path(base: Path) -> Path:
    """Append _1, _2, … to avoid overwriting existing files."""
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix
    counter = 1
    while True:
        candidate = base.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def save_article(article: dict, output_dir: Path) -> Path:
    """Write article Markdown to <output_dir>/<title>.md; returns the path used.

    Uses the article title as the filename (sanitised via slug_from_title).
    Falls back to the URL-derived slug when the title is empty or "Untitled".
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    title = article.get("title", "")
    slug = (
        slug_from_title(title)
        if title and title != "Untitled"
        else slug_from_url(article["url"])
    )
    md_path = unique_path(output_dir / f"{slug}.md")
    md_path.write_text(article["markdown"], encoding="utf-8")
    return md_path


# ── Per-URL processor ─────────────────────────────────────────────────────────

def process_url(url: str, session: requests.Session,
                output_dir: Optional[Path] = None,
                progress: str = "") -> dict:
    """Fetch, extract, and optionally save one article. Always returns a result dict."""
    url = url.strip()
    result: dict = {
        "url": url,
        "article_id": extract_article_id(url),
        "status": "error",
        "title": None, "cover_image": None,
        "markdown": None, "file": None, "error": None,
    }

    if not is_valid_weixin_url(url):
        msg = "非有效的 mp.weixin.qq.com 链接"
        result["error"] = msg
        print(f"\n{progress}✗ 已跳过（{msg}）：{url}")
        return result

    print(f"\n{progress}→ 正在抓取：{url}")
    try:
        html = fetch_html(url, session)
        size_kb = len(html.encode()) / 1024
        print(f"  ✔ 获取成功（{size_kb:.0f} kB），正在解析…")

        reason = check_unavailable(html)
        if reason:
            raise ValueError(f"文章不可访问 — {reason}")

        article = extract_article(html, url)
        result.update(article)
        result["status"] = "ok"

        if output_dir is not None:
            md_path = save_article(article, output_dir)
            result["file"] = str(md_path)
            print(f"  ✓ 【{article['title']}】→ {md_path}")
        else:
            print(f"  ✓ 标题：{article['title']}")

    except Exception as exc:
        result["error"] = str(exc)
        print(f"  ✗ 失败：{exc}")

    return result


# ── Batch runner ──────────────────────────────────────────────────────────────

def load_existing_results(summary_path: Path) -> tuple[list, set]:
    """Load an existing results.json and return (results_list, seen_urls).

    Allows the caller to skip already-fetched URLs and append new results
    without reprocessing. Returns empty defaults if the file is absent or
    malformed.
    """
    if not summary_path.exists():
        return [], set()
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            seen = {r["url"] for r in data if "url" in r}
            return data, seen
    except Exception:
        pass
    return [], set()


def _write_summary(summary_path: Path, results: list) -> None:
    """Write results to summary_path, stripping the markdown body to keep it lean."""
    summary = [{k: v for k, v in r.items() if k != "markdown"} for r in results]
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run(urls: list, output_dir: Optional[Path], inter_delay: float = 1.5) -> None:
    """Fetch all URLs sequentially, sharing one HTTP session.

    Incremental mode: if output_dir already contains a results.json, previously
    fetched URLs are skipped and new results are appended. The file is rewritten
    after every fetch so a mid-run interruption loses at most one article.
    """
    session = make_session()
    summary_path = output_dir / "results.json" if output_dir is not None else None
    existing_results, seen_urls = (
        load_existing_results(summary_path) if summary_path else ([], set())
    )

    clean_urls = [u.strip() for u in urls]
    total = len(clean_urls)
    to_skip = sum(1 for u in clean_urls if u in seen_urls)
    to_fetch = total - to_skip

    # ── Header ────────────────────────────────────────────────────────────────
    sep = "═" * 54
    print(f"\n{sep}")
    if output_dir:
        print(f"  输出目录：{output_dir}")
    if to_skip:
        print(f"  共 {total} 个链接：{to_fetch} 篇待下载，{to_skip} 篇已跳过")
    else:
        print(f"  共 {total} 篇待下载")
    if existing_results:
        print(f"  （已加载 {len(existing_results)} 条历史记录）")
    print("─" * 54)

    # ── Main loop ─────────────────────────────────────────────────────────────
    new_results: list = []
    skipped = 0
    fetch_index = 0
    first_request = True
    url_to_file = {r["url"]: r.get("file") for r in existing_results}

    for url in clean_urls:
        if url in seen_urls:
            file_path = url_to_file.get(url)
            location = f"\n    → {file_path}" if file_path else ""
            print(f"  ↷ 已下载，跳过：{url}{location}")
            skipped += 1
            continue

        fetch_index += 1
        progress = f"[{fetch_index}/{to_fetch}] " if to_fetch > 1 else ""

        if not first_request:
            actual_wait = inter_delay + random.uniform(0.3, 1.5)
            print(f"\n  … 等待 {actual_wait:.1f}s …")
            time.sleep(actual_wait)
        first_request = False

        result = process_url(url, session, output_dir, progress=progress)
        new_results.append(result)
        seen_urls.add(url)

        # Rewrite after every article — a mid-run crash loses at most one entry.
        if summary_path is not None:
            output_dir.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
            _write_summary(summary_path, existing_results + new_results)

    # ── Summary ───────────────────────────────────────────────────────────────
    new_ok = sum(1 for r in new_results if r["status"] == "ok")
    new_fail = len(new_results) - new_ok
    failed_results = [r for r in new_results if r["status"] != "ok"]

    print(f"\n{sep}")
    print("  下载完成")
    print(f"    ✓ 成功   {new_ok} 篇")
    if skipped:
        print(f"    ↷ 跳过   {skipped} 篇（已下载）")
    if new_fail:
        print(f"    ✗ 失败   {new_fail} 篇")

    if summary_path is not None:
        output_dir.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
        print(f"\n  📁 保存位置：{output_dir}")
        print(f"  📄 汇总记录：{summary_path}")

    if failed_results:
        print("\n  失败详情：")
        for r in failed_results:
            print(f"    ✗ {r['url']}")
            print(f"      → {r['error']}")

    print(sep)

    if summary_path is None and new_results:
        print("\n" + "─" * 60 + "\n")
        print(new_results[0].get("markdown") or "（未能提取正文内容）")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch WeChat public account articles and convert to Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "https://mp.weixin.qq.com/s/xxx"
  %(prog)s "url1" "url2" "url3"
  %(prog)s --batch urls.txt
  %(prog)s --batch urls.txt --output ./articles --delay 2
        """,
    )
    parser.add_argument("urls", nargs="*", help="One or more WeChat article URLs")
    parser.add_argument(
        "--batch", "-b", metavar="FILE",
        help="Text file with one WeChat URL per line (lines starting with # are ignored)",
    )
    parser.add_argument(
        "--output", "-o", metavar="DIR", default=None,
        help="Output directory for .md files (default: weixin_output/ for batch, "
             "stdout for single article)",
    )
    parser.add_argument(
        "--delay", "-d", type=float, default=1.5, metavar="SECONDS",
        help="Delay between requests in seconds (default: 1.5)",
    )
    args = parser.parse_args()

    urls = list(args.urls)

    if args.batch:
        batch_path = Path(args.batch)
        if not batch_path.exists():
            print(f"错误：批量文件不存在：{args.batch}", file=sys.stderr)
            sys.exit(1)
        lines = batch_path.read_text(encoding="utf-8").splitlines()
        urls += [ln.strip() for ln in lines
                 if ln.strip() and not ln.startswith("#")]

    if not urls:
        parser.print_help()
        sys.exit(1)

    if args.output:
        output_dir: Optional[Path] = Path(args.output)
    elif len(urls) == 1 and not args.batch:
        output_dir = None  # Single URL: print markdown to stdout
    else:
        output_dir = Path.home() / "weixin_output"

    run(urls, output_dir=output_dir, inter_delay=args.delay)


if __name__ == "__main__":
    main()
