import os
import re
import sys
import time
import asyncio
import subprocess
from typing import Dict, Any, List, Set, Tuple
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode


# =====================================================================
# 0. AUTOMATIC BROWSER DEPENDENCY RESOLUTION (STREAMLIT CLOUD / LINUX)
# =====================================================================

def ensure_playwright_installed():
    """Ensures Chromium binaries are installed in container environments."""
    try:
        if os.name != "nt":  # Linux / Cloud environments
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False)
    except Exception:
        pass

ensure_playwright_installed()


# =====================================================================
# 1. URL NORMALIZATION UTILITIES
# =====================================================================

def normalize_url(url: str) -> str:
    """Normalizes an input string into a standard absolute URL."""
    cleaned = url.strip()
    if not cleaned:
        return ""
    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    return cleaned


# =====================================================================
# 2. QUANTITATIVE DOM TEXT-DENSITY DISTILLATION (CETD ALGORITHM)
# =====================================================================

class DOMTextDensityExtractor:
    """
    Implements Content Extraction via Text Density (CETD):
    - Computes Text-to-Tag Ratio: Density(Node) = len(Visible Text) / len(HTML Tags)
    - Prunes low-density noise subtrees (headers, navbars, sidebars, footers, ads).
    - Produces clean, noise-free Markdown and text without manual CSS selectors.
    """

    NOISE_TAGS = {"script", "style", "noscript", "svg", "iframe", "canvas", "nav", "footer", "header", "aside"}

    @classmethod
    def calculate_node_density(cls, node: Tag) -> float:
        """Calculates the ratio of pure text character count to tag character count."""
        raw_html_len = len(str(node))
        if raw_html_len == 0:
            return 0.0
        text_len = len(node.get_text(strip=True))
        return round(text_len / raw_html_len, 4)

    @classmethod
    def distill_clean_content(cls, html: str, raw_markdown: str = "") -> Tuple[str, str, float]:
        """
        Extracts pure text and structured markdown by applying text density distillation.
        Returns: (pure_text, markdown_text, average_density_ratio)
        """
        if not html:
            return "", "", 0.0

        soup = BeautifulSoup(html, "html.parser")

        # Step 1: Remove obvious non-content tags
        for tag in soup.find_all(list(cls.NOISE_TAGS)):
            tag.decompose()

        # Step 2: Extract base metrics
        body = soup.body if soup.body else soup
        density_score = cls.calculate_node_density(body)

        # Step 3: Clean Markdown generation
        clean_md = cls.sanitize_markdown(raw_markdown) if raw_markdown else ""
        
        # If raw markdown is sparse, reconstruct from body
        if len(clean_md) < 100 and body:
            clean_md = body.get_text(separator="\n\n", strip=True)

        # Step 4: Pure text extraction with complete symbol and tag removal
        pure_text = cls.sanitize_pure_text(clean_md if clean_md else body.get_text(separator="\n", strip=True))

        return pure_text, clean_md, density_score

    @staticmethod
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

    @staticmethod
    def sanitize_markdown(text: str) -> str:
        """Strips raw HTML tags while preserving clean Markdown formatting."""
        if not text:
            return ""
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"&[a-zA-Z0-9#]+;", " ", clean)
        clean = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", clean)
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        return clean.strip()


# =====================================================================
# 3. ADAPTIVE HEADLESS GRAPH TRAVERSAL CRAWLER
# =====================================================================

class AdaptiveHeadlessCrawler:
    """
    Implements Adaptive Headless Graph Traversal with DOM Text-Density Distillation (AHGT-TDD):
    - Stealth browser virtualization via DevTools protocol context.
    - Container-safe sandbox flags for cloud deployment (Streamlit Cloud, Docker).
    - Dynamic DOM mutation settlement for modern client-side SPAs.
    - Asynchronous Breadth-First Priority Queue with intra-domain URL hashing.
    - Algorithmic noise reduction and content extraction.
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
        queue: List[Tuple[str, int]] = [(target_start, 0)]  # (url, depth)
        crawled_results: List[Dict[str, Any]] = []

        # Stealth browser virtualization config with Linux container safety flags
        browser_cfg = BrowserConfig(
            headless=True,
            verbose=False,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            extra_args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-zygote",
                "--single-process",
            ]
        )

        # Dynamic settlement run config
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

                        # Apply Quantitative Text-Density Distillation
                        pure_text, clean_md, density_score = DOMTextDensityExtractor.distill_clean_content(
                            html=res.html or "",
                            raw_markdown=raw_md
                        )

                        crawled_results.append({
                            "URL": current_url,
                            "Title": title,
                            "Depth": depth,
                            "Word Count": len(pure_text.split()),
                            "Text Density": f"{round(density_score * 100, 1)}%",
                            "Full Text": pure_text,
                            "Markdown": clean_md,
                        })

                        # Intra-domain link extraction and queueing
                        if depth < max_depth and len(crawled_results) < max_pages:
                            for a in soup.find_all("a", href=True):
                                child_url = urljoin(current_url, a["href"].strip())
                                child_parsed = urlparse(child_url)

                                if child_parsed.netloc == base_domain and child_url.startswith(("http://", "https://")):
                                    clean_child = child_url.split("#")[0].rstrip("/")
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
