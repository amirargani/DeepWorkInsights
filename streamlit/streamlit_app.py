import os
import sys

# Ensure the root directory is on the python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Ensure app_pages directory is in python path
app_pages_dir = os.path.abspath(os.path.dirname(__file__))
if app_pages_dir not in sys.path:
    sys.path.insert(0, app_pages_dir)

import streamlit as st
from app_pages.dashboard import render_dashboard
from app_pages.monitoring import render_monitoring
from ui import (
    inject_global_styles,
    render_lang_persister,
    render_navbar,
    render_scroll_persister,
)

# Configure page settings
st.set_page_config(
    page_title="DeepWorkInsights Dashboard",
    page_icon=":material/analytics:",
    layout="wide",
)

# Initialize language and hydration flag in session state
if "language" not in st.session_state:
    st.session_state.language = "EN"
if "language_hydrated" not in st.session_state:
    st.session_state.language_hydrated = False
# Sync active tab with query parameters
if "tab" in st.query_params:
    st.session_state.active_tab = st.query_params["tab"]
else:
    st.session_state.active_tab = "dashboard"
    st.query_params["tab"] = "dashboard"

# Scroll Position Persister (Inline HTML onerror hack to maintain scroll state across reruns)
render_scroll_persister(st.session_state.active_tab)

# Custom Component v2 to persist selected language in browser's localStorage
render_lang_persister()

# Top-level Header & Global Styles
st.title("DeepWorkInsights Dashboard")
inject_global_styles()

# Render sticky mini-nav & hidden tab/language selectors
render_navbar()

# Render active tab inside dedicated container
tab_container = st.container()
with tab_container:
    if st.session_state.active_tab == "dashboard":
        sp_msg = (
            "Lade Forecasting Dashboard..."
            if st.session_state.language == "DE"
            else "Loading Forecasting Dashboard..."
        )
        with st.spinner(sp_msg):
            render_dashboard(st.session_state.language)
    else:
        sp_msg = (
            "Lade System & Airflow Monitoring..."
            if st.session_state.language == "DE"
            else "Loading System & Airflow Monitoring..."
        )
        with st.spinner(sp_msg):
            render_monitoring(st.session_state.language)
