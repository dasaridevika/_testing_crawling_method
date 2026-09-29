import asyncio
import streamlit as st
import pandas as pd
from extractor import SmartUniversalExtractor, normalize_url

st.set_page_config(
    page_title="Universal Web Data Extractor",
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

    /* Metric Cards */
    .metric-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.9rem;
        text-align: center;
    }
    .metric-val {
        font-size: 1.25rem;
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
    <div class="hero-title">Universal Web Data Extractor</div>
    <div class="hero-subtitle">Enter any website URL to automatically extract clean, noise-free content using optimal anti-bot routing.</div>
</div>
""", unsafe_allow_html=True)

# Single Universal Input Form
with st.form("universal_crawler_form"):
    col_input, col_btn = st.columns([4.8, 1.2])
    with col_input:
        target_url = st.text_input(
            "Website URL",
            value="",
            placeholder="Enter any website URL (e.g. https://example.com/article)",
            label_visibility="collapsed",
        )
    with col_btn:
        submitted = st.form_submit_button("Extract Data", type="primary", use_container_width=True)

# Execution Pipeline
if submitted:
    clean_url = normalize_url(target_url)
    if not clean_url:
        st.error("Please enter a valid website URL.")
    else:
        with st.spinner(f"Extracting content from {clean_url}..."):
            result = asyncio.run(SmartUniversalExtractor.extract_auto(clean_url))

        st.session_state["active_result"] = result

# Results View
if "active_result" in st.session_state:
    res_data = st.session_state["active_result"]

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    if not res_data.get("success"):
        st.error(f"Extraction failed: {res_data.get('error')}")
    else:
        pure_text = res_data.get("pure_text", "")
        formatted_doc = res_data.get("formatted_doc", "")
        links = res_data.get("links", [])
        word_count = len(pure_text.split()) if pure_text else 0

        # Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val" style="color:#059669;">Success</div>
                <div class="metric-lbl">Status</div>
            </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{res_data.get('elapsed_ms', 0)} ms</div>
                <div class="metric-lbl">Response Time</div>
            </div>
            """, unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{word_count:,}</div>
                <div class="metric-lbl">Words</div>
            </div>
            """, unsafe_allow_html=True)
        with m4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-val">{len(links)}</div>
                <div class="metric-lbl">Links Discovered</div>
            </div>
            """, unsafe_allow_html=True)

        st.caption(f"Strategy Used: **{res_data.get('strategy', 'Auto')}**")

        if res_data.get("title"):
            st.subheader(res_data["title"])

        # Clean Tabs
        t1, t2, t3 = st.tabs(["Clean Text", "Document View", "Discovered Links"])
        with t1:
            st.download_button(
                "Download Text (.txt)",
                data=pure_text,
                file_name="clean_text.txt",
                mime="text/plain",
            )
            st.text_area(
                "Clean Text (Zero HTML tags, zero markdown symbols)",
                pure_text,
                height=480,
                label_visibility="collapsed",
            )
        with t2:
            st.download_button(
                "Download Markdown (.md)",
                data=formatted_doc,
                file_name="document.md",
                mime="text/markdown",
            )
            st.markdown(formatted_doc)
        with t3:
            if links:
                df = pd.DataFrame(links)
                st.dataframe(df, use_container_width=True)
                st.download_button(
                    "Export Links as CSV",
                    data=df.to_csv(index=False).encode("utf-8"),
                    file_name="links.csv",
                    mime="text/csv",
                )
            else:
                st.info("No external links found on this page.")
