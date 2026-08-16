"""KPI metric cards UI component module.

Renders high-level summary cards displaying the latest actual unemployment figures
from the BA alongside the most recent H2O AutoML and Auto-sklearn forecasts.
"""

import pandas as pd
import streamlit as st
from ui.formatters import format_number, format_percent
from ui.tables import clean_model_name


def styled_code(val_str: str) -> str:
    """Helper to style values as green code blocks (pills)."""
    return f"<code style='color: #34D399; background-color: rgba(250, 250, 250, 0.08); padding: 0.15em 0.4em; border-radius: 0.25rem; font-family: monospace; font-size: 0.9em; font-weight: bold;'>{val_str}</code>"


def render_kpi_cards(
    latest_raw_val: int,
    latest_raw_date: str,
    latest_automl,
    latest_autosklearn,
    t: dict,
    lang: str = "EN",
):
    """Renders the top row of KPI metric cards for Actuals, H2O AutoML, and Auto-sklearn forecasts."""
    kpi_cols = st.columns(3)

    with kpi_cols[0]:
        with st.container(border=True):
            st.markdown(f"**{t['actual_label']}**")
            st.subheader(format_number(latest_raw_val, lang))
            st.caption(f"{t['refers_to']} {latest_raw_date}")
            st.markdown(f":material/calendar_month: {t['official_data']}")

    with kpi_cols[1]:
        with st.container(border=True):
            st.markdown(f"**{t['automl_label']}**")
            if latest_automl is not None:
                st.subheader(format_number(latest_automl['prediction'], lang))
                target_dt = pd.to_datetime(latest_automl["target_date"])
                target_str = (
                    f"{t['month_names'][target_dt.month]} {target_dt.year}"
                )
                st.caption(f"{t['target']} {target_str}")

                model_val = clean_model_name(latest_automl["model"])
                r2_val = format_percent(latest_automl['r2'], lang)
                rmse_val = format_number(latest_automl['rmse'], lang)
                mae_val = format_number(latest_automl['mae'], lang)

                st.markdown(
                    f"**{t['model_prefix']}**: {styled_code(model_val)} | "
                    f"**R²**: {styled_code(r2_val)} | "
                    f"**RMSE**: {styled_code(rmse_val)} | "
                    f"**MAE**: {styled_code(mae_val)}",
                    unsafe_allow_html=True,
                )
            else:
                st.write(t["no_pred_avail"])

    with kpi_cols[2]:
        with st.container(border=True):
            st.markdown(f"**{t['autosklearn_label']}**")
            if latest_autosklearn is not None:
                st.subheader(format_number(latest_autosklearn['prediction'], lang))
                target_dt = pd.to_datetime(latest_autosklearn["target_date"])
                target_str = (
                    f"{t['month_names'][target_dt.month]} {target_dt.year}"
                )
                st.caption(f"{t['target']} {target_str}")

                model_val = clean_model_name(latest_autosklearn["model"])
                r2_val = format_percent(latest_autosklearn['r2'], lang)
                rmse_val = format_number(latest_autosklearn['rmse'], lang)
                mae_val = format_number(latest_autosklearn['mae'], lang)

                st.markdown(
                    f"**{t['model_prefix']}**: {styled_code(model_val)} | "
                    f"**R²**: {styled_code(r2_val)} | "
                    f"**RMSE**: {styled_code(rmse_val)} | "
                    f"**MAE**: {styled_code(mae_val)}",
                    unsafe_allow_html=True,
                )
            else:
                st.write(t["no_pred_avail"])

