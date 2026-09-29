import re
import time
import json
import asyncio
from typing import Dict, Any, List, Optional, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

from curl_cffi import requests as curl_requests
import trafilatura

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from playwright.async_api import async_playwright


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
# ENGINE 1: CRAWL4AI (Dynamic JavaScript / SPAs)
# ==========================================

class Crawl4AiEngine:
    """
    Headless Browser & Dynamic DOM Engine:
    Executes JavaScript and captures fully rendered content.
    """

    @staticmethod
    async def extract_page(url: str, timeout_ms: int = 30000) -> Dict[str, Any]:
        target_url = normalize_url(url)
        start_time = time.perf_counter()
        try:
            browser_cfg = BrowserConfig(
                headless=True,
                verbose=False,
            )
            run_cfg = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=timeout_ms,
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

                links: List[Dict[str, str]] = []
                for a in soup.find_all("a", href=True):
                    abs_url = urljoin(target_url, a["href"].strip())
                    text = a.get_text(strip=True)
                    if abs_url.startswith(("http://", "https://")) and len(text) > 1:
                        links.append({"Title": text[:80], "URL": abs_url})

                seen_urls = set()
                deduped_links = []
                for link in links:
                    if link["URL"] not in seen_urls:
                        seen_urls.add(link["URL"])
                        deduped_links.append(link)

                return {
                    "success": True,
                    "url": target_url,
                    "title": title,
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
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 1),
                "error": str(err),
            }

    @staticmethod
    async def intercept_network_apis(url: str, listen_seconds: float = 4.0) -> Dict[str, Any]:
        """Intercepts background JSON API responses as the page executes."""
        target_url = normalize_url(url)
        start_time = time.perf_counter()
        intercepted: List[Dict[str, Any]] = []

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            async def on_response(response):
                try:
                    content_type = response.headers.get("content-type", "")
                    if "application/json" in content_type:
                        req_url = response.url
                        try:
                            json_data = await response.json()
                            intercepted.append({
                                "URL": req_url,
                                "Status": response.status,
                                "Content-Type": content_type,
                                "Raw JSON": json_data,
                            })
                        except Exception:
                            pass
                except Exception:
                    pass

            page.on("response", on_response)
            try:
                await page.goto(target_url, wait_until="networkidle", timeout=20000)
            except Exception:
                pass

            await asyncio.sleep(listen_seconds)
            await browser.close()

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        return {
            "success": True,
            "url": target_url,
            "total_intercepted": len(intercepted),
            "elapsed_ms": elapsed_ms,
            "endpoints": intercepted,
        }


# ==========================================
# ENGINE 2: CURL_CFFI (Fast TLS HTTP)
# ==========================================

class CurlCffiEngine:
    """
    High-Speed HTTP Engine:
    Uses TLS fingerprint impersonation to bypass basic bot filters at pure HTTP speed.
    """

    @staticmethod
    def extract_page(url: str, timeout: int = 15) -> Dict[str, Any]:
        target_url = normalize_url(url)
        start_time = time.perf_counter()
        try:
            resp = curl_requests.get(
                target_url,
                impersonate="chrome124",
                timeout=timeout,
                allow_redirects=True,
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)

            soup = BeautifulSoup(resp.text, "html.parser")
            for t in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"]):
                t.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            txt = trafilatura.extract(resp.text, output_format="txt") or soup.get_text(separator="\n", strip=True)
            md_txt = trafilatura.extract(resp.text, output_format="markdown") or txt

            links: List[Dict[str, str]] = []
            for a in soup.find_all("a", href=True):
                abs_url = urljoin(target_url, a["href"].strip())
                text = a.get_text(strip=True)
                if abs_url.startswith(("http://", "https://")) and len(text) > 1:
                    links.append({"Title": text[:80], "URL": abs_url})

            seen_urls = set()
            deduped_links = []
            for link in links:
                if link["URL"] not in seen_urls:
                    seen_urls.add(link["URL"])
                    deduped_links.append(link)

            return {
                "success": True,
                "url": resp.url,
                "title": title,
                "elapsed_ms": elapsed_ms,
                "pure_text": sanitize_pure_text(txt),
                "formatted_doc": sanitize_markdown_doc(md_txt),
                "links": deduped_links,
                "headers": dict(resp.headers),
                "cookies": dict(resp.cookies),
                "error": None,
            }
        except Exception as err:
            return {
                "success": False,
                "url": target_url,
                "elapsed_ms": round((time.perf_counter() - start_time) * 1000, 1),
                "pure_text": "",
                "formatted_doc": "",
                "links": [],
                "error": str(err),
            }

    @staticmethod
    def recursive_crawl(
        start_url: str,
        max_depth: int = 2,
        max_pages: int = 8,
        url_filter_pattern: str = "",
    ) -> Dict[str, Any]:
        target_url = normalize_url(start_url)
        start_time = time.perf_counter()
        parsed_start = urlparse(target_url)
        base_domain = parsed_start.netloc

        queue = [(target_url, 0)]
        visited: Set[str] = set()
        crawled_pages: List[Dict[str, Any]] = []

        while queue and len(crawled_pages) < max_pages:
            current_url, depth = queue.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                resp = curl_requests.get(
                    current_url,
                    impersonate="chrome124",
                    timeout=10,
                    allow_redirects=True,
                )
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                title = soup.title.string.strip() if soup.title and soup.title.string else current_url
                txt = trafilatura.extract(resp.text, output_format="txt") or soup.get_text(separator="\n", strip=True)
                clean_text = sanitize_pure_text(txt)

                crawled_pages.append({
                    "URL": current_url,
                    "Title": title,
                    "Depth": depth,
                    "Word Count": len(clean_text.split()),
                    "Text Preview": clean_text[:350] + ("..." if len(clean_text) > 350 else ""),
                    "Full Text": clean_text,
                })

                if depth < max_depth:
                    for a in soup.find_all("a", href=True):
                        child_url = urljoin(current_url, a["href"].strip())
                        child_parsed = urlparse(child_url)

                        if child_parsed.netloc != base_domain:
                            continue
                        if url_filter_pattern and not re.search(url_filter_pattern, child_url):
                            continue
                        if child_url.startswith(("http://", "https://")) and child_url not in visited:
                            queue.append((child_url, depth + 1))
            except Exception:
                continue

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        return {
            "success": True,
            "start_url": target_url,
            "total_pages": len(crawled_pages),
            "elapsed_ms": elapsed_ms,
            "pages": crawled_pages,
        }

    @staticmethod
    def sitemap_crawl(base_url: str, max_urls: int = 5) -> Dict[str, Any]:
        target_url = normalize_url(base_url)
        start_time = time.perf_counter()
        parsed = urlparse(target_url)
        sitemaps_to_check = [
            f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
        ]

        discovered_urls: List[str] = []
        for sm_url in sitemaps_to_check:
            try:
                resp = curl_requests.get(sm_url, impersonate="chrome124", timeout=10)
                if resp.status_code == 200 and ("<urlset" in resp.text or "<sitemapindex" in resp.text):
                    root = ET.fromstring(resp.content)
                    for elem in root.iter():
                        if elem.tag.endswith("loc") and elem.text:
                            loc_val = elem.text.strip()
                            if loc_val.startswith(("http://", "https://")) and not loc_val.endswith(".xml"):
                                discovered_urls.append(loc_val)
                    if discovered_urls:
                        break
            except Exception:
                continue

        extracted_data = []
        for url in discovered_urls[:max_urls]:
            try:
                r = curl_requests.get(url, impersonate="chrome124", timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    title = soup.title.string.strip() if soup.title and soup.title.string else url
                    txt = trafilatura.extract(r.text, output_format="txt") or soup.get_text(separator="\n", strip=True)
                    clean_txt = sanitize_pure_text(txt)
                    extracted_data.append({
                        "URL": url,
                        "Title": title,
                        "Word Count": len(clean_txt.split()),
                        "Text Preview": clean_txt[:350] + ("..." if len(clean_txt) > 350 else ""),
                        "Full Text": clean_txt,
                    })
            except Exception:
                continue

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)
        return {
            "success": len(discovered_urls) > 0,
            "total_discovered": len(discovered_urls),
            "total_scraped": len(extracted_data),
            "elapsed_ms": elapsed_ms,
            "extracted_pages": extracted_data,
        }
