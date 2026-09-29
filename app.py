import asyncio
import streamlit as st
import pandas as pd
from extractor import MultiPageDynamicCrawler, normalize_url

st.set_page_config(
    page_title="Dynamic Multi-Page Web Crawler",
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
        max-width: 980px !important;
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

    /* Metric Cards */
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
        color: #2563eb;
        background-color: #eff6ff;
    }

    #MainMenu, footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# App Header
st.markdown("""
<div class="hero-container">
    <div class="hero-title">Dynamic Multi-Page Web Crawler</div>
    <div class="hero-subtitle">Concurrent stealth browser engine designed to crawl dynamic JavaScript websites, traverse internal subpages, and extract clean text.</div>
</div>
""", unsafe_allow_html=True)

# Main Form
with st.form("multipage_crawler_form"):
    col_url, col_pages, col_btn = st.columns([5, 2, 1.5])
    with col_url:
        target_url = st.text_input(
            "Website URL",
            value="",
            placeholder="Enter starting website URL (e.g. https://example.com)",
            label_visibility="collapsed",
        )
    with col_pages:
        max_pages = st.slider("Max Pages to Crawl", min_value=2, max_value=20, value=5)
    with col_btn:
        submitted = st.form_submit_button("Start Crawl", type="primary", use_container_width=True)

# Execution Pipeline
if submitted:
    clean_url = normalize_url(target_url)
    if not clean_url:
        st.error("Please enter a valid website URL.")
    else:
        with st.spinner(f"Crawling dynamic pages from {clean_url} (up to {max_pages} pages)..."):
            result = asyncio.run(
                MultiPageDynamicCrawler.crawl_site(
                    start_url=clean_url,
                    max_pages=max_pages,
                    max_depth=2,
                    concurrency=3,
                )
            )

        st.session_state["crawl_results"] = result

# Result Rendering
if "crawl_results" in st.session_state:
    res_data = st.session_state["crawl_results"]
    pages = res_data.get("pages", [])

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    if not res_data.get("success") or not pages:
        st.error("No pages could be extracted from this website.")
    else:
        total_words = sum(p["Word Count"] for p in pages)
        avg_time = round(res_data.get("elapsed_ms", 0) / len(pages), 1)

        # Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val" style="color:#059669;">{len(pages)} Pages</div>
                <div class="metric-lbl">Pages Crawled</div>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{res_data.get('elapsed_ms', 0)} ms</div>
                <div class="metric-lbl">Total Time</div>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{total_words:,}</div>
                <div class="metric-lbl">Total Words Extracted</div>
            </div>
            """, unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{avg_time} ms</div>
                <div class="metric-lbl">Avg Time Per Page</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        # Summary Table
        st.subheader("Crawled Subpages Summary")
        df_summary = pd.DataFrame([
            {"Title": p["Title"], "Words": p["Word Count"], "Depth": p["Depth"], "URL": p["URL"]}
            for p in pages
        ])
        st.dataframe(df_summary, use_container_width=True)

        # Action Buttons
        col_d1, col_d2 = st.columns([1, 1])
        with col_d1:
            combined_text = "\n\n" + "=" * 60 + "\n\n".join([
                f"PAGE: {p['Title']}\nURL: {p['URL']}\nWORD COUNT: {p['Word Count']}\n\n{p['Full Text']}"
                for p in pages
            ])
            st.download_button(
                "Download All Crawled Pages (.txt)",
                data=combined_text,
                file_name="multipage_crawl_results.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col_d2:
            csv_data = df_summary.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Export Pages Index as CSV",
                data=csv_data,
                file_name="crawled_pages_index.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

        # Individual Page Viewer
        st.subheader("Individual Page Content Viewer")
        page_titles = [f"{idx+1}. {p['Title']} ({p['Word Count']} words)" for idx, p in enumerate(pages)]
        selected_page_idx = st.selectbox("Select Page to View:", range(len(pages)), format_func=lambda i: page_titles[i])

        active_page = pages[selected_page_idx]

        t1, t2 = st.tabs(["Clean Text", "Document View"])
        with t1:
            st.text_area(
                f"Clean Text for: {active_page['Title']}",
                active_page["Full Text"],
                height=450,
                label_visibility="collapsed",
            )
        with t2:
            st.markdown(active_page["Markdown"])
