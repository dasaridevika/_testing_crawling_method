# Adaptive Headless Graph Traversal with DOM Text-Density Distillation (AHGT-TDD)

A high-performance, asynchronous web crawling framework engineered to extract clean, LLM-ready structured text and Markdown from modern dynamic web applications and multi-page websites.

---

## Methodology & Architectural Overview

The AHGT-TDD framework operates across three distinct algorithmic phases:

```
[Target Starting URL]
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Dynamic State-Aware Browser Virtualization               │
│    • Renders client-side JavaScript (React, Vue, SPAs).     │
│    • Waits for network idle and DOM mutation settlement.    │
│    • Applies stealth context injection to bypass anti-bot.  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Asynchronous Frontier Graph Traversal                    │
│    • Discovers and queues internal domain links via BFS.    │
│    • Deduplicates visited URLs via O(1) hash sets.          │
│    • Manages non-blocking concurrent requests.              │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Quantitative Text-Density Distillation (CETD)            │
│    • Calculates Density(Node) = len(Text) / len(HTML Tags). │
│    • Eliminates boilerplate (navbars, ads, footers).        │
│    • Strips all raw HTML tags and syntax artifacts.         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
               [100% Clean Structured Markdown / Text]
```

---

## Key Features

1. **Dynamic Execution:** Employs headless browser virtualization (`Crawl4AI`) to render client-side JavaScript and single-page applications.
2. **Mathematical Boilerplate Removal:** Evaluates text-to-tag ratios (CETD) to isolate primary body content without requiring brittle, manual CSS selectors.
3. **Asynchronous Multi-Page Crawling:** Discovers and scrapes intra-domain subpages concurrently using Python's `asyncio` event loop.
4. **Pure Output Sanitization:** Completely removes raw HTML elements, inline script residue, and formatting noise.
5. **Interactive Dashboard:** Built with Streamlit, providing real-time extraction metrics (Text Density %, latency, word count), subpage summary tables, and one-click data exports (.txt, .csv).

---

## Installation & Setup

### Prerequisites
* Python 3.10+
* Google Chrome / Chromium

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Run the Dashboard
```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

---

## Project Structure

```
├── app.py              # Streamlit dashboard and metric visualization
├── extractor.py        # AHGT-TDD crawler engine and text density extractor
├── requirements.txt    # Project dependencies
└── README.md           # Documentation and methodology specification
```
