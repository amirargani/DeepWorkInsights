"""Global CSS styles injector module.

Injects custom CSS overrides into the Streamlit app DOM to handle stale element
hiding, radio control visibility, and equal-height layout formatting for KPI cards.
"""

import streamlit as st


def inject_global_styles():
    """Inject global CSS rules for opacity, hidden radio widgets, and KPI card container alignment."""
    st.markdown(
        """
        <style>
            /* Completely hide stale data elements during reruns/tab loads */
            [data-stale="true"],
            [stale-data="true"],
            div[data-stale="true"],
            div[stale-data="true"] {
                display: none !important;
            }
            /* Hide radio button widget from UI while keeping it active for sticky nav JS handler */
            div[data-testid="stRadio"] {
                display: none !important;
            }
            /* Inject equal height CSS for KPI cards */
            div[data-testid="column"][style*="33.3"] div[data-testid="stVerticalBlockBorderContainer"] {
                min-height: 220px !important;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }
        </style>
    """,
        unsafe_allow_html=True,
    )
