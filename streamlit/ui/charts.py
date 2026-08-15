from datetime import datetime
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def render_historical_timeline_chart(
    df_raw_filtered: pd.DataFrame,
    df_pred_filtered: pd.DataFrame,
    time_filter: str,
    lang: str,
    t: dict,
    raw_hash: int,
    pred_hash: int,
):
    """Renders the historical actuals and model forecasts Plotly chart with caching."""
    timeline_key = hash((raw_hash, pred_hash, time_filter, lang))
    if (
        "timeline_key" not in st.session_state
        or st.session_state.timeline_key != timeline_key
        or "fig_timeline" not in st.session_state
    ):
        df_raw_plot = df_raw_filtered.dropna(subset=["unemployment"])
        now = datetime.now()
        xaxis_config = dict(
            showgrid=True,
            gridcolor="#334155",
            title=t["date_label"],
            hoverformat="%b %Y",
        )
        if time_filter == "Current Year":
            xaxis_config["range"] = [f"{now.year}-01-01", f"{now.year + 1}-01-01"]

        fig = go.Figure()

        if not df_raw_plot.empty:
            last_actual = df_raw_plot.iloc[-1]
            last_actual_date = last_actual["Date"]
            last_actual_val = last_actual["unemployment"]
        else:
            last_actual = None
            last_actual_date = pd.to_datetime("2026-07-01")

        fig.add_trace(
            go.Scatter(
                x=df_raw_plot["Date"],
                y=df_raw_plot["unemployment"],
                mode="lines+markers",
                name=t["actual_name"],
                line=dict(color="#60A5FA", width=3),
                marker=dict(size=4),
                hovertemplate=f"{t['actual_name']}: %{{y:,}}<extra></extra>",
            )
        )

        # AutoML predictions
        if not df_pred_filtered.empty:
            df_pred_aml = df_pred_filtered[
                df_pred_filtered["framework"] == "automl"
            ]
            if not df_pred_aml.empty:
                df_pred_aml["PlotDate"] = pd.to_datetime(
                    df_pred_aml["target_date"]
                ).map(lambda x: datetime(x.year, x.month, 1))

                if last_actual is not None:
                    connect_df = pd.DataFrame(
                        [
                            {
                                "PlotDate": last_actual_date,
                                "prediction": last_actual_val,
                            }
                        ]
                    )
                    df_plot_aml = pd.concat(
                        [connect_df, df_pred_aml[["PlotDate", "prediction"]]],
                        ignore_index=True,
                    )
                else:
                    df_plot_aml = df_pred_aml

                fig.add_trace(
                    go.Scatter(
                        x=df_plot_aml["PlotDate"],
                        y=df_plot_aml["prediction"],
                        mode="lines+markers+text",
                        name=t["automl_name"],
                        line=dict(color="#34D399", width=2, dash="dash"),
                        marker=dict(size=8, symbol="diamond"),
                        text=[
                            f"{int(x):,}" if i == len(df_plot_aml) - 1 else ""
                            for i, x in enumerate(df_plot_aml["prediction"])
                        ],
                        textposition="top center",
                        hovertemplate=f"{t['automl_name']}: %{{y:,}}<extra></extra>",
                    )
                )

            # Auto-sklearn predictions
            df_pred_ask = df_pred_filtered[
                df_pred_filtered["framework"] == "autosklearn"
            ]
            if not df_pred_ask.empty:
                df_pred_ask["PlotDate"] = pd.to_datetime(
                    df_pred_ask["target_date"]
                ).map(lambda x: datetime(x.year, x.month, 1))

                if last_actual is not None:
                    connect_df = pd.DataFrame(
                        [
                            {
                                "PlotDate": last_actual_date,
                                "prediction": last_actual_val,
                            }
                        ]
                    )
                    df_plot_ask = pd.concat(
                        [connect_df, df_pred_ask[["PlotDate", "prediction"]]],
                        ignore_index=True,
                    )
                else:
                    df_plot_ask = df_pred_ask

                fig.add_trace(
                    go.Scatter(
                        x=df_plot_ask["PlotDate"],
                        y=df_plot_ask["prediction"],
                        mode="lines+markers+text",
                        name=t["autosklearn_name"],
                        line=dict(color="#FB923C", width=2, dash="dash"),
                        marker=dict(size=8, symbol="triangle-up"),
                        text=[
                            f"{int(x):,}" if i == len(df_plot_ask) - 1 else ""
                            for i, x in enumerate(df_plot_ask["prediction"])
                        ],
                        textposition="bottom center",
                        hovertemplate=f"{t['autosklearn_name']}: %{{y:,}}<extra></extra>",
                    )
                )

        fig.add_vline(
            x=last_actual_date,
            line_width=2,
            line_dash="dot",
            line_color="#E2E8F0",
            annotation_text=t["forecast_start"],
            annotation_position="top left",
            annotation_font=dict(color="#F1F5F9", size=10),
        )

        if time_filter == "Current Year":
            fig.add_vrect(
                x0=last_actual_date,
                x1=pd.to_datetime(f"{now.year + 1}-01-01"),
                fillcolor="rgba(96, 165, 250, 0.04)",
                layer="below",
                line_width=0,
                annotation_text=t["forecast_horizon"],
                annotation_position="bottom right",
                annotation_font=dict(color="#94A3B8", size=10),
            )

        tick_vals = [0, 1000000, 2000000, 3000000, 4000000, 5000000]
        tick_text = t["y_axis_ticks"]

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#F1F5F9"),
            xaxis=xaxis_config,
            yaxis=dict(
                showgrid=True,
                gridcolor="#334155",
                title=t["y_axis_title"],
                range=[0, 5500000],
                rangemode="tozero",
                tickvals=tick_vals,
                ticktext=tick_text,
            ),
            margin=dict(l=40, r=40, t=20, b=40),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            hovermode="x unified",
        )
        st.session_state.fig_timeline = fig
        st.session_state.timeline_key = timeline_key
    else:
        fig = st.session_state.fig_timeline

    st.plotly_chart(fig, use_container_width=True)


def render_historical_timeline_area_chart(
    df_raw: pd.DataFrame, t: dict, raw_hash: int, lang: str
):
    """Renders the historical timeline area Plotly chart with caching."""
    timeline_area_key = hash((raw_hash, lang))
    if (
        "timeline_area_key" not in st.session_state
        or st.session_state.timeline_area_key != timeline_area_key
        or "fig_timeline_area" not in st.session_state
    ):
        df_timeline = df_raw.dropna(subset=["unemployment"])
        fig_timeline = px.area(
            df_timeline,
            x="Date",
            y="unemployment",
            labels={
                "Date": t["date_label"],
                "unemployment": t["unemployed_label"],
            },
            color_discrete_sequence=["#60A5FA"],
        )
        tick_vals = [0, 1000000, 2000000, 3000000, 4000000, 5000000]
        tick_text = t["y_axis_ticks"]

        fig_timeline.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font_color="#F1F5F9",
            xaxis=dict(showgrid=True, gridcolor="#334155", hoverformat="%b %Y"),
            yaxis=dict(
                showgrid=True,
                gridcolor="#334155",
                title=t["y_axis_title"],
                range=[0, 5500000],
                tickvals=tick_vals,
                ticktext=tick_text,
            ),
            margin=dict(l=40, r=40, t=40, b=40),
        )
        fig_timeline.update_traces(
            line=dict(width=2),
            hovertemplate="<b>Date: %{x|%B %Y}</b><br>Unemployed: %{y:,}<extra></extra>",
        )
        st.session_state.fig_timeline_area = fig_timeline
        st.session_state.timeline_area_key = timeline_area_key
    else:
        fig_timeline = st.session_state.fig_timeline_area

    st.plotly_chart(fig_timeline, use_container_width=True)


def render_seasonality_chart(
    df_raw: pd.DataFrame,
    df_pred: pd.DataFrame,
    lang: str,
    t: dict,
    raw_hash: int,
    pred_hash: int,
):
    """Renders the seasonality distribution box plot and overlay traces with caching."""
    season_key = hash((raw_hash, pred_hash, lang))
    if (
        "season_key" not in st.session_state
        or st.session_state.season_key != season_key
        or "fig_season" not in st.session_state
    ):
        current_year = int(df_raw.dropna(subset=["unemployment"])["year"].max())
        df_season = df_raw[
            (df_raw["unemployment"].notnull()) & (df_raw["year"] < current_year)
        ].copy()
        df_season["month"] = df_season["month"].astype(int)
        df_season["MonthName"] = df_season["month"].map(t["month_names"])
        df_season = df_season.sort_values("month")

        fig_season = px.box(
            df_season,
            x="MonthName",
            y="unemployment",
            labels={
                "MonthName": t["month_axis_label"],
                "unemployment": t["unemployment_count_label"],
            },
            color_discrete_sequence=["#334155"],
            points=False,
        )

        outlier_rows = []
        for m_name in df_season["MonthName"].unique():
            df_m = df_season[df_season["MonthName"] == m_name]
            if len(df_m) < 4:
                continue
            q1 = df_m["unemployment"].quantile(0.25)
            q3 = df_m["unemployment"].quantile(0.75)
            iqr = q3 - q1
            lower_fence = q1 - 1.5 * iqr
            upper_fence = q3 + 1.5 * iqr

            df_out = df_m[
                (df_m["unemployment"] < lower_fence)
                | (df_m["unemployment"] > upper_fence)
            ]
            if not df_out.empty:
                outlier_rows.append(df_out)

        if outlier_rows:
            df_outliers = pd.concat(outlier_rows)
            for idx, row in df_outliers.iterrows():
                fig_season.add_trace(
                    go.Scatter(
                        x=[row["MonthName"]],
                        y=[row["unemployment"]],
                        mode="markers",
                        name="Outlier",
                        showlegend=False,
                        marker=dict(color="#475569", size=5, symbol="circle"),
                        hovertemplate=f"{row['MonthName']} {row['year']}: %{{y:,}}<extra></extra>",
                    )
                )

        df_curr_actuals = df_raw[
            (df_raw["year"] == current_year) & (df_raw["unemployment"].notnull())
        ].copy()
        df_curr_actuals["MonthName"] = (
            df_curr_actuals["month"].astype(int).map(t["month_names"])
        )
        df_curr_actuals = df_curr_actuals.sort_values("month")

        fig_season.add_trace(
            go.Scatter(
                x=df_curr_actuals["MonthName"],
                y=df_curr_actuals["unemployment"],
                mode="lines+markers",
                name=f"{current_year} {t['actual_y_name']}",
                line=dict(color="#60A5FA", width=3),
                marker=dict(size=8, symbol="circle"),
                hovertemplate=f"{current_year} {t['actual_name']}: %{{y:,}}<extra></extra>",
            )
        )

        if not df_pred.empty:
            df_curr_pred = df_pred[df_pred["year"] == current_year].copy()
            if not df_curr_pred.empty:
                df_curr_pred["MonthName"] = (
                    df_curr_pred["month"].astype(int).map(t["month_names"])
                )

                df_pred_aml = df_curr_pred[df_curr_pred["framework"] == "automl"]
                if not df_pred_aml.empty:
                    fig_season.add_trace(
                        go.Scatter(
                            x=df_pred_aml["MonthName"],
                            y=df_pred_aml["prediction"],
                            mode="markers",
                            name=f"{current_year} {t['automl_y_name']}",
                            marker=dict(
                                color="#34D399", size=10, symbol="diamond"
                            ),
                            hovertemplate=f"{t['automl_name']}: %{{y:,}}<extra></extra>",
                        )
                    )

                df_pred_ask = df_curr_pred[
                    df_curr_pred["framework"] == "autosklearn"
                ]
                if not df_pred_ask.empty:
                    fig_season.add_trace(
                        go.Scatter(
                            x=df_pred_ask["MonthName"],
                            y=df_pred_ask["prediction"],
                            mode="markers",
                            name=f"{current_year} {t['autosklearn_y_name']}",
                            marker=dict(
                                color="#FB923C", size=10, symbol="triangle-up"
                            ),
                            hovertemplate=f"{t['autosklearn_name']}: %{{y:,}}<extra></extra>",
                        )
                    )

        tick_vals = [0, 1000000, 2000000, 3000000, 4000000, 5000000]
        tick_text = t["y_axis_ticks"]

        fig_season.update_layout(
            hovermode="x",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#F1F5F9"),
            xaxis=dict(showgrid=False),
            yaxis=dict(
                showgrid=True,
                gridcolor="#334155",
                title=t["y_axis_title"],
                range=[0, 5500000],
                tickvals=tick_vals,
                ticktext=tick_text,
            ),
            margin=dict(l=40, r=40, t=20, b=40),
        )
        st.session_state.fig_season = fig_season
        st.session_state.season_key = season_key
    else:
        fig_season = st.session_state.fig_season

    st.plotly_chart(fig_season, use_container_width=True)


def render_forecast_error_chart(
    df_archive: pd.DataFrame,
    df_raw: pd.DataFrame,
    lang: str,
    t: dict,
    archive_hash: int,
    raw_hash: int,
):
    """Renders historical forecast error (residuals) chart with caching."""
    if df_archive.empty:
        return

    df_actuals_join = (
        df_raw.dropna(subset=["unemployment"])[["year", "month", "unemployment"]]
        .copy()
    )
    df_actuals_join["year"] = df_actuals_join["year"].astype(int)
    df_actuals_join["month"] = df_actuals_join["month"].astype(int)

    df_archive_copy = df_archive.copy()
    df_archive_copy["year"] = df_archive_copy["year"].astype(int)
    df_archive_copy["month"] = df_archive_copy["month"].astype(int)

    df_errors = df_archive_copy.merge(
        df_actuals_join, on=["year", "month"], how="inner"
    )
    if df_errors.empty:
        return

    df_errors["Error (%)"] = (
        (df_errors["prediction"] - df_errors["unemployment"])
        / df_errors["unemployment"]
    ) * 100
    df_errors["Date"] = pd.to_datetime(
        df_errors["year"].astype(str)
        + "-"
        + df_errors["month"].astype(str).str.zfill(2)
        + "-01"
    )
    df_errors = df_errors.sort_values("Date")

    residuals_key = hash((archive_hash, raw_hash, lang))
    if (
        "residuals_key" not in st.session_state
        or st.session_state.residuals_key != residuals_key
        or "fig_residuals" not in st.session_state
    ):
        fig_errors = px.line(
            df_errors,
            x="Date",
            y="Error (%)",
            color="framework",
            labels={
                "Date": t["target_date_label"],
                "Error (%)": t["pred_error_label"],
                "framework": "Framework",
            },
            color_discrete_map={"automl": "#34D399", "autosklearn": "#FB923C"},
            markers=True,
        )
        fig_errors.add_hline(
            y=0,
            line_dash="dash",
            line_color="gray",
            annotation_text=t["perfect_forecast"],
        )
        fig_errors.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#F1F5F9"),
            xaxis=dict(showgrid=True, gridcolor="#334155", hoverformat="%b %Y"),
            yaxis=dict(showgrid=True, gridcolor="#334155"),
            margin=dict(l=40, r=40, t=20, b=40),
        )
        st.session_state.fig_residuals = fig_errors
        st.session_state.residuals_key = residuals_key
    else:
        fig_errors = st.session_state.fig_residuals

    st.plotly_chart(fig_errors, use_container_width=True)


def render_yoy_change_chart(
    df_raw: pd.DataFrame,
    cutoff: pd.Timestamp,
    time_filter: str,
    lang: str,
    t: dict,
    raw_hash: int,
):
    """Renders the Year-over-Year (YoY) percentage change bar chart with caching."""
    df_yoy = df_raw.dropna(subset=["unemployment"]).copy()
    df_yoy = df_yoy.sort_values("Date").reset_index(drop=True)
    df_yoy["YoY Change (%)"] = df_yoy["unemployment"].pct_change(periods=12) * 100
    df_yoy_plot = df_yoy.dropna(subset=["YoY Change (%)"]).copy()
    df_yoy_plot = df_yoy_plot[df_yoy_plot["Date"] >= cutoff]

    if not df_yoy_plot.empty:
        df_yoy_plot["Color"] = df_yoy_plot["YoY Change (%)"].map(
            lambda x: "#F87171" if x > 0 else "#60A5FA"
        )
        now = datetime.now()
        xaxis_config = dict(
            showgrid=True,
            gridcolor="#334155",
            title=t["date_label"],
            hoverformat="%b %Y",
        )
        if time_filter == "Current Year":
            xaxis_config["range"] = [f"{now.year}-01-01", f"{now.year + 1}-01-01"]

        yoy_key = hash((raw_hash, time_filter, lang))
        if (
            "yoy_key" not in st.session_state
            or st.session_state.yoy_key != yoy_key
            or "fig_yoy" not in st.session_state
        ):
            fig_yoy = px.bar(
                df_yoy_plot,
                x="Date",
                y="YoY Change (%)",
                title=t["yoy_plot_title"],
                labels={
                    "Date": t["date_label"],
                    "YoY Change (%)": t["yoy_change_label"],
                },
            )
            fig_yoy.update_traces(
                marker_color=df_yoy_plot["Color"],
                hovertemplate="<b>Date: %{x|%B %Y}</b><br>YoY Change: %{y:.2f}%<extra></extra>",
            )
            fig_yoy.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#F1F5F9"),
                xaxis=xaxis_config,
                yaxis=dict(showgrid=True, gridcolor="#334155"),
                margin=dict(l=40, r=40, t=20, b=40),
            )
            st.session_state.fig_yoy = fig_yoy
            st.session_state.yoy_key = yoy_key
        else:
            fig_yoy = st.session_state.fig_yoy

        st.plotly_chart(fig_yoy, use_container_width=True)
    else:
        st.info("Insufficient historical range to display YoY changes.")
