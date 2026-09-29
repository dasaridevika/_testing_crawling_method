import re
import time
import asyncio
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from curl_cffi import requests as curl_requests
import trafilatura

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode


# ==========================================
# TEXT SANITIZATION & NORMALIZATION UTILS
# ==========================================

def normalize_url(url: str) -> str:
    """Normalizes input string into a standard absolute URL."""
    cleaned = url.strip()
    if not cleaned:
        return ""
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    return cleaned


def sanitize_pure_text(text: str) -> str:
    """Strips all HTML tags, entities, and Markdown syntax to produce pure plain text."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"&[a-zA-Z0-9#]+;", " ", clean)
    clean = re.sub(r"^#{1,6}\s+", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
    clean = re.sub(r"\*([^*]+)\*", r"\1", clean)
    clean = re.sub(r"__([^_]+)__", r"\1", clean)
    clean = re.sub(r"_([^_]+)_", r"\1", clean)
    clean = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", clean)
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
    clean = re.sub(r"^>\s+", "", clean, flags=re.MULTILINE)
    clean = re.sub(r"^-{3,}", "", clean, flags=re.MULTILINE)
    clean = clean.replace("`", "")
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return "\n".join(line.rstrip() for line in clean.splitlines()).strip()


def sanitize_markdown_doc(text: str) -> str:
    """Strips raw HTML tags while preserving clean Markdown formatting."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"&[a-zA-Z0-9#]+;", " ", clean)
    clean = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


# ==========================================
# SMART AUTO-ADAPTIVE UNIVERSAL EXTRACTOR
# ==========================================

class SmartUniversalExtractor:
    """
    Intelligent Adaptive Extraction Pipeline:
    1. Tier 1 (Speed): Attempts ultra-fast HTTP request via curl_cffi with Chrome 124 TLS spoofing.
    2. Tier 2 (Dynamic SPA): If Tier 1 detects sparse content or client-side JavaScript,
       it automatically promotes the request to Crawl4AI headless browser.
    """

    @staticmethod
    async def extract_auto(url: str) -> Dict[str, Any]:
        target_url = normalize_url(url)
        start_time = time.perf_counter()

        # Step 1: Ultra-Fast TLS HTTP Attempt (curl_cffi)
        try:
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            }
            resp = curl_requests.get(
                target_url,
                impersonate="chrome124",
                headers=headers,
                timeout=8,
                allow_redirects=True,
            )

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for t in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"]):
                    t.decompose()

                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                txt = trafilatura.extract(resp.text, output_format="txt") or soup.get_text(separator="\n", strip=True)
                pure_text = sanitize_pure_text(txt)

                # If Tier 1 retrieved rich text (>250 characters), return immediately in sub-second time
                if len(pure_text) >= 250:
                    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
                    md_txt = trafilatura.extract(resp.text, output_format="markdown") or txt
                    formatted_doc = sanitize_markdown_doc(md_txt)

                    links = []
                    for a in soup.find_all("a", href=True):
                        abs_url = urljoin(target_url, a["href"].strip())
                        text = a.get_text(strip=True)
                        if abs_url.startswith(("http://", "https://")) and len(text) > 1:
                            links.append({"Title": text[:80], "URL": abs_url})

                    seen = set()
                    deduped_links = []
                    for l in links:
                        if l["URL"] not in seen:
                            seen.add(l["URL"])
                            deduped_links.append(l)

                    return {
                        "success": True,
                        "url": resp.url,
                        "title": title,
                        "strategy": "Fast HTTP (Sub-Second)",
                        "elapsed_ms": elapsed_ms,
                        "pure_text": pure_text,
                        "formatted_doc": formatted_doc,
                        "links": deduped_links,
                        "error": None,
                    }
        except Exception:
            pass  # Automatically escalate to Tier 2 (Crawl4AI)

        # Step 2: Dynamic Browser Execution (Crawl4AI for SPAs & heavy JavaScript)
        try:
            browser_cfg = BrowserConfig(
                headless=True,
                verbose=False,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            )
            run_cfg = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=30000,
                wait_until="domcontentloaded",
                delay_before_return_html=2.0,
            )
            async with AsyncWebCrawler(config=browser_cfg) as crawler:
                res = await crawler.arun(url=target_url, config=run_cfg)
                elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)

                if not res.success:
                    return {
                        "success": False,
                        "url": target_url,
                        "strategy": "Dynamic Browser",
                        "elapsed_ms": elapsed_ms,
                        "error": res.error_message or "Extraction failed",
                    }

                raw_md = res.markdown.raw_markdown if hasattr(res.markdown, "raw_markdown") else str(res.markdown or "")
                soup = BeautifulSoup(res.html or "", "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else ""

                pure_text = sanitize_pure_text(raw_md)
                if len(pure_text) < 80 and soup.body:
                    for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"]):
                        tag.decompose()
                    pure_text = sanitize_pure_text(soup.body.get_text(separator="\n", strip=True))

                formatted_doc = sanitize_markdown_doc(raw_md) if len(raw_md) > 50 else pure_text

                links = []
                for a in soup.find_all("a", href=True):
                    abs_url = urljoin(target_url, a["href"].strip())
                    text = a.get_text(strip=True)
                    if abs_url.startswith(("http://", "https://")) and len(text) > 1:
                        links.append({"Title": text[:80], "URL": abs_url})

                seen = set()
                deduped_links = []
                for l in links:
                    if l["URL"] not in seen:
                        seen.add(l["URL"])
                        deduped_links.append(l)

                return {
                    "success": True,
                    "url": target_url,
                    "title": title,
                    "strategy": "Dynamic Browser (JavaScript Rendered)",
                    "elapsed_ms": elapsed_ms,
                    "pure_text": pure_text,
                    "formatted_doc": formatted_doc,
                    "links": deduped_links,
                    "error": None,
                }
        except Exception as err:
            return {
                "success": False,
                "url": target_url,
                "strategy": "Auto-Adaptive",
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 1),
                "error": str(err),
            }
