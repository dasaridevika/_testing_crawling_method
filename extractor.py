import re
import time
import asyncio
from typing import Dict, Any, List, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode


# ==========================================
# TEXT SANITIZATION UTILITIES
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
# PURE CRAWL4AI MULTI-PAGE ENGINE
# ==========================================

class Crawl4AiPipeline:
    """
    100% Crawl4AI Crawling Pipeline:
    - Uses AsyncWebCrawler for dynamic JavaScript execution and DOM settlement.
    - Concurrently processes multiple internal subpages across any domain.
    """

    @staticmethod
    async def crawl_website(
        start_url: str,
        max_pages: int = 5,
        max_depth: int = 2,
        concurrency: int = 3,
    ) -> Dict[str, Any]:
        target_start = normalize_url(start_url)
        start_time = time.perf_counter()

        parsed_start = urlparse(target_start)
        base_domain = parsed_start.netloc

        visited: Set[str] = set()
        queue: List[tuple] = [(target_start, 0)]  # (url, depth)
        crawled_results: List[Dict[str, Any]] = []

        browser_cfg = BrowserConfig(
            headless=True,
            verbose=False,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )
        run_cfg = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=30000,
            wait_until="domcontentloaded",
            delay_before_return_html=1.5,
        )

        semaphore = asyncio.Semaphore(concurrency)

        async with AsyncWebCrawler(config=browser_cfg) as crawler:

            async def process_url(current_url: str, depth: int):
                nonlocal queue, visited, crawled_results
                async with semaphore:
                    if len(crawled_results) >= max_pages:
                        return
                    try:
                        res = await crawler.arun(url=current_url, config=run_cfg)
                        if not res.success:
                            return

                        raw_md = res.markdown.raw_markdown if hasattr(res.markdown, "raw_markdown") else str(res.markdown or "")
                        soup = BeautifulSoup(res.html or "", "html.parser")
                        title = soup.title.string.strip() if soup.title and soup.title.string else current_url

                        pure_text = sanitize_pure_text(raw_md)
                        if len(pure_text) < 80 and soup.body:
                            for tag in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer", "header"]):
                                tag.decompose()
                            pure_text = sanitize_pure_text(soup.body.get_text(separator="\n", strip=True))

                        crawled_results.append({
                            "URL": current_url,
                            "Title": title,
                            "Depth": depth,
                            "Word Count": len(pure_text.split()),
                            "Full Text": pure_text,
                            "Markdown": sanitize_markdown_doc(raw_md),
                        })

                        if depth < max_depth and len(crawled_results) < max_pages:
                            for a in soup.find_all("a", href=True):
                                child_url = urljoin(current_url, a["href"].strip())
                                child_parsed = urlparse(child_url)

                                if child_parsed.netloc == base_domain and child_url.startswith(("http://", "https://")):
                                    clean_child = child_url.split("#")[0]
                                    if clean_child not in visited:
                                        visited.add(clean_child)
                                        queue.append((clean_child, depth + 1))
                    except Exception:
                        pass

            visited.add(target_start)

            while queue and len(crawled_results) < max_pages:
                batch = []
                while queue and len(batch) < concurrency and (len(crawled_results) + len(batch)) < max_pages:
                    batch.append(queue.pop(0))

                if not batch:
                    break

                tasks = [process_url(u, d) for u, d in batch]
                await asyncio.gather(*tasks)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)

        return {
            "success": len(crawled_results) > 0,
            "start_url": target_start,
            "total_pages_crawled": len(crawled_results),
            "elapsed_ms": elapsed_ms,
            "pages": crawled_results,
        }
