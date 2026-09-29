import asyncio
import json
import streamlit as st
import pandas as pd
from extractor import (
    Crawl4AiEngine,
    CurlCffiEngine,
    normalize_url,
)

st.set_page_config(
    page_title="Universal Web Crawler",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 4rem !important;
        max-width: 960px !important;
        margin: 0 auto;
    }

    .hero-container {
        margin-bottom: 2rem;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0f172a;
        letter-spacing: -0.025em;
        margin-bottom: 0.35rem;
    }
    .hero-subtitle {
        font-size: 1rem;
        color: #64748b;
        line-height: 1.5;
    }

    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.9rem;
        text-align: center;
    }
    .metric-val {
        font-size: 1.3rem;
        font-weight: 700;
        color: #0f172a;
    }
    .metric-lbl {
        font-size: 0.72rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        margin-top: 2px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 2px solid #f1f5f9;
        margin-bottom: 1.25rem;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        font-size: 0.92rem;
        color: #64748b;
        border-radius: 8px;
        padding: 8px 16px;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #4f46e5;
        background-color: #eef2ff;
    }

    #MainMenu, footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown("""
<div class="hero-container">
    <div class="hero-title">🕸️ Universal Web Crawler</div>
    <div class="hero-subtitle">Select a crawling method and enter any target URL to extract clean data.</div>
</div>
""", unsafe_allow_html=True)

# Method Selector
crawling_methods = [
    "🤖 Universal Dynamic Extractor (Crawl4AI — for JavaScript SPAs & Dynamic Sites)",
    "⚡ Fast Static HTTP Extractor (curl_cffi — for Static HTML, Articles, Blogs)",
    "🕸️ Recursive Deep Crawler (curl_cffi — crawls internal subpages across domain)",
    "🗺️ Sitemap-First XML Ingestion (curl_cffi — harvests canonical URLs)",
    "📡 Network API Sniffer (Crawl4AI — captures background JSON endpoints)",
]

selected_method = st.selectbox(
    "Select Crawling Method from List:",
    crawling_methods,
    index=0,
)

# Input Form
with st.form("crawler_execution_form"):
    target_url = st.text_input(
        "Website URL",
        value="",
        placeholder="https://example.com/page",
        help="Enter any target website URL",
    )

    if "Recursive Deep" in selected_method:
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1: max_depth = st.slider("Crawl Depth", 1, 3, 2)
        with col_r2: max_pages = st.slider("Max Pages", 2, 20, 5)
        with col_r3: regex_filter = st.text_input("URL Path Filter (Optional)", placeholder="e.g. /category/ or /product/")
    elif "Sitemap" in selected_method:
        max_sitemap_urls = st.slider("Max Sitemap URLs to Harvest", 2, 20, 5)

    submitted = st.form_submit_button("🚀 Run Extraction", type="primary", use_container_width=True)

# Execution Pipeline
if submitted:
    clean_url = normalize_url(target_url)
    if not clean_url:
        st.error("Please enter a valid website URL.")
    else:
        with st.spinner(f"Extracting {clean_url}..."):
            if "Universal Dynamic" in selected_method:
                result = asyncio.run(Crawl4AiEngine.extract_page(clean_url))
            elif "Fast Static" in selected_method:
                result = CurlCffiEngine.extract_page(clean_url)
            elif "Recursive Deep" in selected_method:
                result = CurlCffiEngine.recursive_crawl(clean_url, max_depth=max_depth, max_pages=max_pages, url_filter_pattern=regex_filter)
            elif "Sitemap" in selected_method:
                result = CurlCffiEngine.sitemap_crawl(clean_url, max_urls=max_sitemap_urls)
            elif "Network API" in selected_method:
                result = asyncio.run(Crawl4AiEngine.intercept_network_apis(clean_url))

        st.session_state["executed_result"] = {
            "method": selected_method,
            "data": result,
        }

# Result Rendering
if "executed_result" in st.session_state:
    res_obj = st.session_state["executed_result"]
    res_method = res_obj["method"]
    res_data = res_obj["data"]

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # 1. Single Page Extraction Results
    if "Universal Dynamic" in res_method or "Fast Static" in res_method:
        if not res_data.get("success"):
            st.error(f"❌ Extraction failed: {res_data.get('error')}")
        else:
            pure_text = res_data.get("pure_text", "")
            formatted_doc = res_data.get("formatted_doc", "")
            links = res_data.get("links", [])
            word_count = len(pure_text.split()) if pure_text else 0

            m1, m2, m3, m4 = st.columns(4)
            with m1: st.markdown(f'<div class="metric-card"><div class="metric-val" style="color:#059669;">Success</div><div class="metric-lbl">Status</div></div>', unsafe_allow_html=True)
            with m2: st.markdown(f'<div class="metric-card"><div class="metric-val">{res_data.get("elapsed_ms", 0)} ms</div><div class="metric-lbl">Duration</div></div>', unsafe_allow_html=True)
            with m3: st.markdown(f'<div class="metric-card"><div class="metric-val">{word_count:,}</div><div class="metric-lbl">Words</div></div>', unsafe_allow_html=True)
            with m4: st.markdown(f'<div class="metric-card"><div class="metric-val">{len(links)}</div><div class="metric-lbl">Links Found</div></div>', unsafe_allow_html=True)

            if res_data.get("title"):
                st.subheader(f"📄 {res_data['title']}")

            t1, t2, t3 = st.tabs(["📝 Pure Clean Text", "📖 Formatted Document", "🔗 Discovered Links"])
            with t1:
                st.download_button("⬇️ Download Pure Text (.txt)", data=pure_text, file_name="clean_text.txt", mime="text/plain")
                st.text_area("Pure Clean Text (Zero HTML tags, zero markdown symbols)", pure_text, height=480, label_visibility="collapsed")
            with t2:
                st.download_button("⬇️ Download Markdown (.md)", data=formatted_doc, file_name="document.md", mime="text/markdown")
                st.markdown(formatted_doc)
            with t3:
                if links:
                    df = pd.DataFrame(links)
                    st.dataframe(df, use_container_width=True)
                    st.download_button("⬇️ Export Links as CSV", data=df.to_csv(index=False).encode('utf-8'), file_name="links.csv", mime="text/csv")

    # 2. Recursive Deep Crawler Results
    elif "Recursive Deep" in res_method:
        pages = res_data.get("pages", [])
        m1, m2 = st.columns(2)
        with m1: st.markdown(f'<div class="metric-card"><div class="metric-val">{len(pages)} Pages</div><div class="metric-lbl">Crawled Subpages</div></div>', unsafe_allow_html=True)
        with m2: st.markdown(f'<div class="metric-card"><div class="metric-val">{res_data.get("elapsed_ms", 0)} ms</div><div class="metric-lbl">Total Time</div></div>', unsafe_allow_html=True)

        if pages:
            df_p = pd.DataFrame([{"Title": p["Title"], "Depth": p["Depth"], "Words": p["Word Count"], "URL": p["URL"]} for p in pages])
            st.dataframe(df_p, use_container_width=True)
            combined = "\n\n" + "="*50 + "\n\n".join([f"PAGE: {p['Title']}\nURL: {p['URL']}\n\n{p['Full Text']}" for p in pages])
            st.download_button("⬇️ Download All Pages (.txt)", data=combined, file_name="recursive_crawl.txt", mime="text/plain")

    # 3. Sitemap Ingestion Results
    elif "Sitemap" in res_method:
        extracted = res_data.get("extracted_pages", [])
        m1, m2 = st.columns(2)
        with m1: st.markdown(f'<div class="metric-card"><div class="metric-val">{len(extracted)}</div><div class="metric-lbl">Harvested Pages</div></div>', unsafe_allow_html=True)
        with m2: st.markdown(f'<div class="metric-card"><div class="metric-val">{res_data.get("elapsed_ms", 0)} ms</div><div class="metric-lbl">Total Time</div></div>', unsafe_allow_html=True)

        if extracted:
            df_sm = pd.DataFrame([{"Title": p["Title"], "Words": p["Word Count"], "URL": p["URL"]} for p in extracted])
            st.dataframe(df_sm, use_container_width=True)
            combined_sm = "\n\n" + "="*50 + "\n\n".join([f"TITLE: {p['Title']}\nURL: {p['URL']}\n\n{p['Full Text']}" for p in extracted])
            st.download_button("⬇️ Download Sitemap Harvest (.txt)", data=combined_sm, file_name="sitemap_harvest.txt", mime="text/plain")
        else:
            st.warning("No valid sitemap.xml found on this domain.")

    # 4. Network API Sniffer Results
    elif "Network API" in res_method:
        endpoints = res_data.get("endpoints", [])
        m1, m2 = st.columns(2)
        with m1: st.markdown(f'<div class="metric-card"><div class="metric-val">{len(endpoints)}</div><div class="metric-lbl">Captured JSON APIs</div></div>', unsafe_allow_html=True)
        with m2: st.markdown(f'<div class="metric-card"><div class="metric-val">{res_data.get("elapsed_ms", 0)} ms</div><div class="metric-lbl">Duration</div></div>', unsafe_allow_html=True)

        if endpoints:
            st.subheader("📡 Captured Background JSON Endpoints")
            for idx, ep in enumerate(endpoints[:10]):
                with st.expander(f"API #{idx+1}: {ep['URL'][:80]}...", expanded=(idx == 0)):
                    st.write(f"**URL:** `{ep['URL']}`")
                    st.json(ep["Raw JSON"])
            all_json = json.dumps([{"url": ep["URL"], "data": ep["Raw JSON"]} for ep in endpoints], indent=2)
            st.download_button("⬇️ Download All Intercepted JSON (.json)", data=all_json, file_name="captured_apis.json", mime="application/json")
        else:
            st.info("No JSON API requests were detected during page load.")
