# Universal Web Crawling & Data Extraction Suite

An advanced, anti-bot resilient web crawling and data extraction system featuring a modern Streamlit interface. It decouples extraction into two specialized engines:

1. **Crawl4AI Engine**: Stealth headless browser automation powered by Playwright to execute JavaScript bundles, settle dynamic DOM trees (SPAs like React/Vue/Angular), and sniff background JSON APIs.
2. **curl_cffi Engine**: Ultra-fast pure HTTP client that impersonates real browser TLS JA3/JA4 cryptographic fingerprints (Chrome 124) to bypass anti-bot firewalls with zero browser overhead.

---

## 🚀 Features

- **Pristine Text Extraction**: Sanitizes DOM and Markdown to strip 100% of raw HTML tags and Markdown syntax (`**`, `#`, `[]()`), leaving clean human-readable text.
- **Universal Dynamic Extractor (`Crawl4AI`)**: Extracts dynamic Single-Page Applications (SPAs) with automatic DOM settlement.
- **Fast Static HTTP Extractor (`curl_cffi`)**: Sub-second extraction for static articles, Wikipedia, and blogs.
- **Recursive Deep Crawler**: Breadth-First Search (BFS) graph traversal across internal subpages with regex path filtering.
- **Sitemap-First XML Ingestion**: Parses `sitemap.xml` directly to discover and harvest canonical URLs in parallel.
- **Background API Sniffer**: Intercepts background XHR/Fetch JSON API responses from dynamic SPAs in real-time.
- **Multi-Format Export**: 1-click downloads for `.txt`, `.md`, `.csv`, and `.json`.

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

---

## 📂 Project Structure

```
├── app.py             # Streamlit web dashboard
├── extractor.py       # Core crawling engines (Crawl4AiEngine & CurlCffiEngine)
├── requirements.txt   # Dependencies
├── .gitignore         # Ignored cache files
└── README.md          # Project documentation
```
