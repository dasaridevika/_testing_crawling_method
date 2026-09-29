# Crawl4AI Web Crawler & Content Extractor

A web crawler and extraction pipeline powered exclusively by **Crawl4AI**. Designed to crawl multi-page websites, execute client-side JavaScript (SPAs like React/Vue/Angular), traverse internal subpages concurrently, and extract clean text without HTML/Markdown artifacts.

---

## 🚀 Features

- **Pure Crawl4AI Architecture**: Employs `AsyncWebCrawler` with anti-detection browser automation and dynamic DOM settlement.
- **Dynamic Multi-Page Crawling**: Traverses internal domain links up to configurable depths and page limits.
- **Concurrent Execution**: Spawns concurrent browser tabs to process multiple subpages in parallel.
- **Pristine Output**: 100% clean text stripped of all raw HTML tags and Markdown formatting symbols.
- **Bulk & Individual Exports**: 1-click download for all pages combined into `.txt`, `.csv` page indices, or individual page views.

---

## 🛠️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dasaridevika/_testing_crawling_method.git
   cd _testing_crawling_method
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Run the Streamlit Dashboard:**
   ```bash
   streamlit run app.py
   ```
   Open `http://localhost:8501` in your browser.
