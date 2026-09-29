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
        if os.name != "nt":
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
# 2. HIERARCHICAL DOM TEXT-DENSITY DISTILLATION (ORDER-PRESERVING)
# =====================================================================

class DOMTextDensityExtractor:
    """
    Advanced Order-Preserving DOM Distillation:
    - Normalizes Unicode punctuation and standardizes spacing around punctuation.
    - Strips citation footnotes (e.g. [1], [a], [citation needed]).
    - Filters out navigation sidebars, infoboxes, hatnotes, and reference dumps.
    - Preserves semantic hierarchy (Headings, Paragraphs, Lists, Tables).
    """

    NOISE_TAGS = {"script", "style", "noscript", "svg", "iframe", "canvas", "nav", "footer", "header", "aside", "form"}
    
    NOISE_PATTERNS = re.compile(
        r"cookie|banner|modal|popup|sidebar|widget|comment|footer|nav|breadcrumb|social|share|advertisement|ad-container|newsletter|subscription|infobox|hatnote|navbox|mw-jump-link|mw-editsection|toc|reflist|mw-references-wrap",
        re.I
    )

    @staticmethod
    def normalize_unicode_text(text: str) -> str:
        """Cleans and standardizes Unicode characters, punctuation, and footnotes."""
        if not text:
            return ""
        replacements = {
            "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
            "\u2014": " - ", "\u2013": " - ", "\u00a0": " ", "\u2026": "...",
            "\ufffd": "", "«": '"', "»": '"'
        }
        for k, v in replacements.items():
            text = text.replace(k, v)

        # Strip Wikipedia/academic citation footnotes: [ 1 ], [ a ], [ 120 ], [ citation needed ]
        text = re.sub(r"\[\s*(?:\d+|[a-zA-Z]+|\b\w+\s+\w+\b)\s*\]", "", text)
        text = re.sub(r"\[\s*citation needed\s*\]", "", text, flags=re.I)

        # Fix spacing around punctuation
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        text = re.sub(r"\(\s+", "(", text)
        text = re.sub(r"\s+\)", ")", text)

        return text

    @classmethod
    def calculate_density(cls, tag: Tag) -> float:
        """Calculates text-to-tag character density ratio."""
        raw_html_len = len(str(tag))
        if raw_html_len == 0:
            return 0.0
        text_len = len(tag.get_text(strip=True))
        return round(text_len / raw_html_len, 4)

    @classmethod
    def find_main_content_root(cls, soup: BeautifulSoup) -> Tag:
        """Locates the primary content subtree in the DOM hierarchy."""
        mw_content = soup.find(id="mw-content-text")
        if mw_content:
            parser_output = mw_content.find(class_="mw-parser-output")
            if parser_output:
                return parser_output
            return mw_content

        for semantic_tag in ["main", "article"]:
            found = soup.find(semantic_tag)
            if found and len(found.get_text(strip=True)) > 150:
                return found

        role_main = soup.find(attrs={"role": "main"})
        if role_main and len(role_main.get_text(strip=True)) > 150:
            return role_main

        candidates = soup.find_all(["div", "section", "body"])
        best_node = soup.body if soup.body else soup
        best_score = 0.0

        for node in candidates:
            text = node.get_text(strip=True)
            text_len = len(text)
            if text_len < 100:
                continue
            density = cls.calculate_density(node)
            score = text_len * (density ** 1.5)
            if score > best_score:
                best_score = score
                best_node = node

        return best_node

    @classmethod
    def clean_noise_elements(cls, root: Tag):
        """Removes script, style, ads, infoboxes, sidebars, and noise containers."""
        for tag in root.find_all(list(cls.NOISE_TAGS)):
            tag.decompose()

        for tag in root.find_all(True):
            if tag.decomposed:
                continue
            classes = " ".join(tag.get("class", [])) if isinstance(tag.get("class"), list) else str(tag.get("class", ""))
            element_id = str(tag.get("id", ""))
            
            if cls.NOISE_PATTERNS.search(classes) or cls.NOISE_PATTERNS.search(element_id):
                tag.decompose()

    @classmethod
    def extract_structured_blocks(cls, root: Tag) -> List[Tuple[str, str]]:
        """Traverses the DOM in sequential reading order, extracting ordered blocks."""
        blocks: List[Tuple[str, str]] = []
        processed_elements = set()

        block_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "blockquote", "pre", "table", "div", "section"]

        for elem in root.find_all(block_tags):
            if id(elem) in processed_elements or elem.decomposed:
                continue

            tag_name = elem.name.lower()

            if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                processed_elements.add(id(elem))
                text = cls.normalize_unicode_text(elem.get_text(separator=" ", strip=True))
                text = re.sub(r"\s+", " ", text).strip()
                if 2 <= len(text) <= 250:
                    blocks.append((tag_name, text))

            elif tag_name in ["p", "blockquote"]:
                processed_elements.add(id(elem))
                text = cls.normalize_unicode_text(elem.get_text(separator=" ", strip=True))
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 15:
                    blocks.append(("quote" if tag_name == "blockquote" else "p", text))

            elif tag_name in ["ul", "ol"]:
                processed_elements.add(id(elem))
                for child in elem.find_all(["ul", "ol", "li"]):
                    processed_elements.add(id(child))
                items = []
                for li in elem.find_all("li", recursive=False):
                    li_text = cls.normalize_unicode_text(li.get_text(separator=" ", strip=True))
                    li_text = re.sub(r"\s+", " ", li_text).strip()
                    if li_text and not li_text.startswith("Jump up to:"):
                        items.append(li_text)
                if items:
                    blocks.append(("list", "\n".join(f"- {it}" for it in items)))

            elif tag_name == "pre":
                processed_elements.add(id(elem))
                blocks.append(("code", elem.get_text().strip()))

            elif tag_name == "table":
                processed_elements.add(id(elem))
                for child in elem.find_all(True):
                    processed_elements.add(id(child))
                rows = []
                for tr in elem.find_all("tr"):
                    cells = [cls.normalize_unicode_text(td.get_text(separator=" ", strip=True)) for td in tr.find_all(["td", "th"])]
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    blocks.append(("table", "\n".join(rows)))

            elif tag_name in ["div", "section"]:
                has_nested_blocks = bool(elem.find(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table", "pre"]))
                if not has_nested_blocks:
                    processed_elements.add(id(elem))
                    text = cls.normalize_unicode_text(elem.get_text(separator=" ", strip=True))
                    text = re.sub(r"\s+", " ", text).strip()
                    if len(text) > 20:
                        blocks.append(("p", text))

        return blocks

    @classmethod
    def distill_clean_content(cls, html: str, raw_markdown: str = "") -> Tuple[str, str, float]:
        """Performs full hierarchical distillation in exact document order."""
        if not html:
            return "", "", 0.0

        soup = BeautifulSoup(html, "html.parser")
        main_root = cls.find_main_content_root(soup)
        density_score = cls.calculate_density(main_root)

        cls.clean_noise_elements(main_root)
        blocks = cls.extract_structured_blocks(main_root)

        if not blocks:
            raw_text = cls.normalize_unicode_text(main_root.get_text(separator="\n\n", strip=True))
            clean_plain = cls.sanitize_plain_lines(raw_text)
            return clean_plain, clean_plain, density_score

        md_lines: List[str] = []
        plain_lines: List[str] = []
        seen_blocks = set()

        for btype, bcontent in blocks:
            block_fingerprint = f"{btype}:{bcontent[:100]}"
            if block_fingerprint in seen_blocks:
                continue
            seen_blocks.add(block_fingerprint)

            if btype == "h1":
                md_lines.append(f"# {bcontent}\n")
                plain_lines.append(f"\n{bcontent.upper()}\n{'=' * len(bcontent)}\n")
            elif btype == "h2":
                md_lines.append(f"## {bcontent}\n")
                plain_lines.append(f"\n{bcontent}\n{'-' * len(bcontent)}\n")
            elif btype == "h3":
                md_lines.append(f"### {bcontent}\n")
                plain_lines.append(f"\n{bcontent}\n")
            elif btype in ["h4", "h5", "h6"]:
                md_lines.append(f"#### {bcontent}\n")
                plain_lines.append(f"\n{bcontent}\n")
            elif btype == "p":
                md_lines.append(f"{bcontent}\n")
                plain_lines.append(f"{bcontent}\n")
            elif btype == "list":
                md_lines.append(f"{bcontent}\n")
                plain_lines.append(f"{bcontent}\n")
            elif btype == "quote":
                md_lines.append(f"> {bcontent}\n")
                plain_lines.append(f"\"{bcontent}\"\n")
            elif btype == "code":
                md_lines.append(f"```\n{bcontent}\n```\n")
                plain_lines.append(f"\n{bcontent}\n")
            elif btype == "table":
                md_lines.append(f"{bcontent}\n")
                plain_lines.append(f"{bcontent}\n")

        ordered_markdown = "\n".join(md_lines).strip()
        ordered_plain_text = "\n".join(plain_lines).strip()

        ordered_markdown = re.sub(r"\n{3,}", "\n\n", ordered_markdown)
        ordered_plain_text = re.sub(r"\n{3,}", "\n\n", ordered_plain_text)

        return ordered_plain_text, ordered_markdown, density_score

    @staticmethod
    def sanitize_plain_lines(text: str) -> str:
        """Fallback sanitization for plain text."""
        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"&[a-zA-Z0-9#]+;", " ", clean)
        clean = re.sub(r"\n{3,}", "\n\n", clean)
        return "\n".join(line.rstrip() for line in clean.splitlines()).strip()


# =====================================================================
# 3. CRAWL4AI MULTI-PAGE PIPELINE
# =====================================================================

class Crawl4AiPipeline:
    """
    Pure Crawl4AI Crawling Pipeline:
    - Uses AsyncWebCrawler for dynamic JavaScript execution and DOM settlement.
    - Concurrently processes multiple internal subpages across any domain.
    - Uses DOM Text-Density distillation for clean, ordered Markdown/text output.
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
        queue: List[Tuple[str, int]] = [(target_start, 0)]
        crawled_results: List[Dict[str, Any]] = []

        browser_cfg = BrowserConfig(
            headless=True,
            verbose=False,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            extra_args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1920,1080",
            ]
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
