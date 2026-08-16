"""System & Airflow Monitoring page module."""

import concurrent.futures
import re
from datetime import datetime
import docker
import pandas as pd
import sqlalchemy as sa
import streamlit as st

from packages.common import get_db_engine
from packages.monitoring_data import (
    TRANSLATIONS,
    get_container_metrics,
    get_docker_client,
    parse_container_logs,
)
from ui import clean_model_name, format_number, format_percent, get_plotly_separators

# ─── Live Docker Service Monitor Fragment ──────────────────────────────────────
@st.fragment
def render_docker_monitor(lang="EN"):
    """Renders Docker containers status and resource utilization monitoring table."""

    t = TRANSLATIONS[lang]
    st.subheader(t["docker_sub"])
    
    try:
        client = get_docker_client()
        if not client:
            st.warning(f"{t['docker_err']} Could not connect to Docker daemon")
            st.info(t["docker_info"])
            return
        containers = client.containers.list(all=True)
    except Exception as e:
        st.warning(f"{t['docker_err']} {e}")
        st.info(t["docker_info"])
        return
    
    def fetch_metrics(c):
        """Fetch CPU and memory performance stats for a single Docker container."""
        if c.status == "running":
            return get_container_metrics(c)
        return {"CPU (%)": "0.0%", "Memory (MB)": "0.0 MB", "Memory (%)": "0.0%"}

    container_to_metrics = {}
    if containers:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(containers)) as executor:
            future_to_container = {executor.submit(fetch_metrics, c): c for c in containers}
            for future in concurrent.futures.as_completed(future_to_container):
                c = future_to_container[future]
                try:
                    metrics = future.result()
                except Exception:
                    metrics = {"CPU (%)": "0.0%", "Memory (MB)": "0.0 MB", "Memory (%)": "0.0%"}
                container_to_metrics[c.id] = metrics

    container_data = []
    for c in containers:
        metrics = container_to_metrics.get(c.id, {"CPU (%)": "0.0%", "Memory (MB)": "0.0 MB", "Memory (%)": "0.0%"})
        ports = ", ".join([f"{k}->{v[0]['HostPort']}" for k, v in c.ports.items() if v]) if c.ports else "None"
        
        # Get Image safely to prevent ImageNotFound crashes
        try:
            img_name = c.image.tags[0] if c.image.tags else c.image.short_id
        except Exception:
            try:
                img_id = c.attrs.get("Image", "Unknown")
                if img_id.startswith("sha256:"):
                    img_name = img_id[7:19]
                else:
                    img_name = img_id
            except Exception:
                img_name = "Unknown"
        
        cpu_val = metrics["CPU (%)"]
        mem_mb_val = metrics["Memory (MB)"]
        mem_pct_val = metrics["Memory (%)"]

        if lang == "DE":
            cpu_val = str(cpu_val).replace(".", ",")
            mem_mb_val = str(mem_mb_val).replace(".", ",")
            mem_pct_val = str(mem_pct_val).replace(".", ",")

        container_data.append({
            "Name": c.name,
            "Status": c.status.upper(),
            "Image": img_name,
            "CpuUsage": cpu_val,
            "MemoryUsage": mem_mb_val,
            "MemoryPct": mem_pct_val,
            "Ports": ports
        })
            
    def style_status(val):
        """Apply color coding to container status (green for RUNNING, red otherwise)."""
        color = "#34D399" if str(val).upper() == "RUNNING" else "#F87171"
        return f"color: {color}; font-weight: bold;"

    df_c = pd.DataFrame(container_data)
    if not df_c.empty:
        df_c_renamed = df_c.rename(columns={
            "Name": "Container",
            "Status": "Status",
            "Image": "Image",
            "CpuUsage": "CPU (%)",
            "MemoryUsage": "Speicher (MB)" if lang == "DE" else "Memory (MB)",
            "MemoryPct": "Speicher (%)" if lang == "DE" else "Memory (%)",
            "Ports": "Ports"
        })

        st.dataframe(
            df_c_renamed.style.map(style_status, subset=["Status"]),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No container information available.")

# ─── Live Airflow Status Fragment ──────────────────────────────────────────────
@st.fragment
def render_airflow_monitor(lang="EN"):
    """Renders Airflow DAG execution stats, task states, control actions, and duration charts."""
    t = TRANSLATIONS[lang]

    st.subheader(t["airflow_sub"])
    
    engine = get_db_engine()
    
    try:
        with engine.connect() as conn:
            # 1. Fetch DAG list
            df_dags = pd.read_sql("SELECT dag_id, is_active, is_paused FROM dag", conn)
            # 2. Fetch Latest DAG Runs
            df_runs = pd.read_sql(
                "SELECT run_id, dag_id, state, execution_date, start_date, end_date FROM dag_run ORDER BY execution_date DESC LIMIT 10", 
                conn
            )
            # 3. Fetch Task Instance States count
            df_tasks = pd.read_sql("SELECT state, COUNT(*) as count FROM task_instance GROUP BY state", conn)
            # 4. Fetch all test runs and archive test runs to match
            df_test_runs = pd.read_sql(
                "SELECT framework, model, run_timestamp, r2, rmse FROM test_runs "
                "UNION "
                "SELECT framework, model, run_timestamp, r2, rmse FROM test_runs_archive",
                conn
            )
    except Exception as e:
        st.info(t["airflow_err"])
        return
        
    # Calculate stable hashes to avoid duplicate figure re-rendering
    runs_hash = int(pd.util.hash_pandas_object(df_runs).sum()) if not df_runs.empty else 0
    test_runs_hash = int(pd.util.hash_pandas_object(df_test_runs).sum()) if not df_test_runs.empty else 0
        
    # Render Task State counts in KPI columns
    st.markdown(f"**{t['task_states']}**")
    
    states_map = {r["state"]: r["count"] for _, r in df_tasks.iterrows()}
    
    col_success, col_failed, col_running, col_queued = st.columns(4)
    with col_success:
        with st.container(border=True):
            st.metric(t["col_success"], format_number(states_map.get("success", 0), lang))
    with col_failed:
        with st.container(border=True):
            st.metric(t["col_failed"], format_number(states_map.get("failed", 0), lang))
    with col_running:
        with st.container(border=True):
            st.metric(t["col_running"], format_number(states_map.get("running", 0), lang))
    with col_queued:
        with st.container(border=True):
            st.metric(t["col_queued"], format_number(states_map.get("queued", 0), lang))

    st.write("")
    
    # Render DAG list and latest runs stacked vertically (Full Width)
    with st.container(border=True):
        st.markdown(f"**{t['dag_title']}**")
        
        df_dags_renamed = df_dags.rename(columns={
            "dag_id": "DAG ID",
            "is_active": "Aktiv" if lang == "DE" else "Active",
            "is_paused": "Pausiert" if lang == "DE" else "Paused"
        })
        
        # Determine if the DAG is running or queued
        is_running = any(df_runs["state"].isin(["running", "queued"]))
        
        # Get active/paused status of DAG
        is_paused = False
        if not df_dags.empty:
            is_paused = bool(df_dags.iloc[0]["is_paused"])
            
        dag_layout_cols = st.columns([2, 1, 1, 1])
        with dag_layout_cols[0]:
            st.dataframe(
                df_dags_renamed,
                use_container_width=True,
                hide_index=True
            )
        with dag_layout_cols[1]:
            st.write("")  # spacing
            if st.button(t["btn_trigger"], type="primary", use_container_width=True, icon=":material/play_arrow:", disabled=is_running):
                try:
                    import docker
                    client = docker.from_env()
                    c = client.containers.get('deepwork-scheduler')
                    res = c.exec_run('airflow dags trigger unemployment_forecast')
                    if res.exit_code == 0:
                        st.toast(t["toast_trigger_success"], icon="✅")
                        st.rerun()
                    else:
                        st.error(f"Error: {res.output.decode('utf-8')}")
                except Exception as e:
                    st.error(f"Docker Error: {e}")
        with dag_layout_cols[2]:
            st.write("")  # spacing
            if st.button(t["btn_stop"], type="secondary", use_container_width=True, icon=":material/stop:", disabled=not is_running):
                try:
                    import docker
                    client = docker.from_env()
                    c = client.containers.get('deepwork-scheduler')
                    py_script = (
                        "from airflow.models.dagrun import DagRun; "
                        "from airflow.utils.state import DagRunState; "
                        "from airflow.utils.session import create_session; "
                        "with create_session() as session: "
                        "    runs = session.query(DagRun).filter(DagRun.dag_id == 'unemployment_forecast', DagRun.state.in_(['running', 'queued'])).all(); "
                        "    for r in runs: r.set_state(DagRunState.FAILED); "
                        "    session.commit()"
                    )
                    res = c.exec_run(['python', '-c', py_script])
                    if res.exit_code == 0:
                        st.toast(t["toast_stop_success"], icon="🛑")
                        st.rerun()
                    else:
                        st.error(f"Error: {res.output.decode('utf-8')}")
                except Exception as e:
                    st.error(f"Docker Error: {e}")
        with dag_layout_cols[3]:
            st.write("")  # spacing
            pause_label = t["btn_unpause"] if is_paused else t["btn_pause"]
            pause_icon = ":material/play_circle:" if is_paused else ":material/pause_circle:"
            if st.button(pause_label, use_container_width=True, icon=pause_icon):
                try:
                    import docker
                    client = docker.from_env()
                    c = client.containers.get('deepwork-scheduler')
                    action = "unpause" if is_paused else "pause"
                    res = c.exec_run(f'airflow dags {action} unemployment_forecast')
                    if res.exit_code == 0:
                        status_msg = t["toast_unpause_success"] if is_paused else t["toast_pause_success"]
                        st.toast(status_msg, icon="ℹ️")
                        st.rerun()
                    else:
                        st.error(f"Error: {res.output.decode('utf-8')}")
                except Exception as e:
                    st.error(f"Docker Error: {e}")
                    
        st.markdown(t["control_guide_html"], unsafe_allow_html=True)
                    
    st.write("")
    
    with st.container(border=True):
        st.markdown(f"**{t['dag_runs_title']}**")
        
        def style_run_state(val):
            """Apply text color coding to DAG Run state (green for success, red for failed, orange running/queued)."""
            if val == "success":
                return "color: #34D399; font-weight: bold;"
            elif val == "failed":
                return "color: #F87171; font-weight: bold;"
            return "color: #FB923C; font-weight: bold;"

        # Ensure comparable datetimes in df_test_runs
        df_test_runs["run_timestamp"] = pd.to_datetime(df_test_runs["run_timestamp"])
        df_test_runs["model"] = df_test_runs["model"].map(clean_model_name)
        
        # Calculate duration and join metrics
        durations = []
        automl_models = []
        automl_r2s = []
        automl_rmses = []
        autosklearn_models = []
        autosklearn_r2s = []
        autosklearn_rmses = []
        
        for idx, r in df_runs.iterrows():
            start = r["start_date"]
            end = r["end_date"]
            if pd.isna(start):
                durations.append("N/A")
                automl_models.append("N/A")
                automl_r2s.append("N/A")
                automl_rmses.append("N/A")
                autosklearn_models.append("N/A")
                autosklearn_r2s.append("N/A")
                autosklearn_rmses.append("N/A")
                continue
                
            start_dt = pd.to_datetime(start).tz_localize(None)
            if pd.isna(end):
                durations.append(t["col_running"])
                end_dt = datetime.utcnow()
            else:
                end_dt = pd.to_datetime(end).tz_localize(None)
                diff = end_dt - start_dt
                total_seconds = int(diff.total_seconds())
                mins = total_seconds // 60
                secs = total_seconds % 60
                durations.append(f"{mins}m {secs}s" if mins > 0 else f"{secs}s")
                
            # Filter test runs inside this DAG run's lifetime (with a 10s write buffer)
            matches = df_test_runs[
                (df_test_runs["run_timestamp"] >= start_dt) & 
                (df_test_runs["run_timestamp"] <= end_dt + pd.Timedelta(seconds=10))
            ]
            
            # H2O AutoML match
            automl_matches = matches[matches["framework"] == "automl"]
            if not automl_matches.empty:
                best_automl = automl_matches.sort_values(by="r2", ascending=False).iloc[0]
                automl_models.append(best_automl["model"])
                automl_r2s.append(format_percent(best_automl['r2'], lang) if pd.notna(best_automl['r2']) else "N/A")
                automl_rmses.append(format_number(best_automl['rmse'], lang) if pd.notna(best_automl['rmse']) else "N/A")
            else:
                automl_models.append("N/A")
                automl_r2s.append("N/A")
                automl_rmses.append("N/A")
                
            # Auto-sklearn match
            autosklearn_matches = matches[matches["framework"] == "autosklearn"]
            if not autosklearn_matches.empty:
                best_autosklearn = autosklearn_matches.sort_values(by="r2", ascending=False).iloc[0]
                autosklearn_models.append(best_autosklearn["model"])
                autosklearn_r2s.append(format_percent(best_autosklearn['r2'], lang) if pd.notna(best_autosklearn['r2']) else "N/A")
                autosklearn_rmses.append(format_number(best_autosklearn['rmse'], lang) if pd.notna(best_autosklearn['rmse']) else "N/A")
            else:
                autosklearn_models.append("N/A")
                autosklearn_r2s.append("N/A")
                autosklearn_rmses.append("N/A")
                
        df_runs["Duration"] = durations
        df_runs["AutoML Model"] = automl_models
        df_runs["AutoML R²"] = automl_r2s
        df_runs["AutoML RMSE"] = automl_rmses
        df_runs["Auto-sklearn Model"] = autosklearn_models
        df_runs["Auto-sklearn R²"] = autosklearn_r2s
        df_runs["Auto-sklearn RMSE"] = autosklearn_rmses

        def localize_to_berlin(val):
            """Convert UTC timestamp to formatted Europe/Berlin local time string."""
            if pd.isna(val):
                return "N/A"
            dt = pd.to_datetime(val)
            if dt.tz is None:
                dt = dt.tz_localize('UTC')
            date_fmt = "%d.%m.%Y %H:%M:%S" if lang == "DE" else "%Y-%m-%d %H:%M:%S"
            return dt.tz_convert('Europe/Berlin').strftime(date_fmt)

        start_hdr = "Startzeit" if lang == "DE" else "Start Time"
        end_hdr = "Endzeit" if lang == "DE" else "End Time"
        dur_hdr = "Dauer" if lang == "DE" else "Duration"
        state_hdr = "Status" if lang == "DE" else "State"
        log_date_hdr = "Logisches Datum (UTC)" if lang == "DE" else "Logical Date (UTC)"
        automl_mod_hdr = "AutoML Modell" if lang == "DE" else "AutoML Model"
        autosk_mod_hdr = "Auto-sklearn Modell" if lang == "DE" else "Auto-sklearn Model"

        df_runs_renamed = df_runs.copy()
        df_runs_renamed[start_hdr] = df_runs_renamed["start_date"].apply(localize_to_berlin)
        df_runs_renamed[end_hdr] = df_runs_renamed["end_date"].apply(localize_to_berlin)

        df_runs_renamed = df_runs_renamed.rename(columns={
            "run_id": "Run ID",
            "state": state_hdr,
            "execution_date": log_date_hdr,
            "Duration": dur_hdr,
            "AutoML Model": automl_mod_hdr,
            "Auto-sklearn Model": autosk_mod_hdr,
        })

        display_cols = [
            "Run ID", state_hdr, start_hdr, end_hdr, dur_hdr, log_date_hdr,
            automl_mod_hdr, "AutoML R²", "AutoML RMSE",
            autosk_mod_hdr, "Auto-sklearn R²", "Auto-sklearn RMSE"
        ]

        date_fmt = "%d.%m.%Y %H:%M:%S" if lang == "DE" else "%Y-%m-%d %H:%M:%S"

        st.dataframe(
            df_runs_renamed[display_cols].style.format({
                log_date_hdr: lambda x: pd.to_datetime(x).strftime(date_fmt) if pd.notna(x) else "N/A"
            }).map(style_run_state, subset=[state_hdr]),
            use_container_width=True,
            hide_index=True
        )

        # ─── Render Performance & Duration Charts ───
        plot_data = []
        for idx, r in df_runs.iterrows():
            if pd.isna(r["start_date"]) or pd.isna(r["end_date"]):
                continue
            
            # Duration in minutes
            start_dt = pd.to_datetime(r["start_date"]).tz_localize(None)
            end_dt = pd.to_datetime(r["end_date"]).tz_localize(None)
            duration_secs = (end_dt - start_dt).total_seconds()
            duration_mins = duration_secs / 60.0
            
            # Get raw numeric metrics from df_test_runs
            matches = df_test_runs[
                (df_test_runs["run_timestamp"] >= start_dt) & 
                (df_test_runs["run_timestamp"] <= end_dt + pd.Timedelta(seconds=10))
            ]
            
            automl_r2 = None
            automl_matches = matches[matches["framework"] == "automl"]
            if not automl_matches.empty:
                r2_val = automl_matches.sort_values(by="r2", ascending=False).iloc[0]["r2"]
                if pd.notna(r2_val):
                    automl_r2 = float(r2_val)
                
            autosklearn_r2 = None
            autosklearn_matches = matches[matches["framework"] == "autosklearn"]
            if not autosklearn_matches.empty:
                r2_val = autosklearn_matches.sort_values(by="r2", ascending=False).iloc[0]["r2"]
                if pd.notna(r2_val):
                    autosklearn_r2 = float(r2_val)
                
            plot_data.append({
                "ExecutionDate": pd.to_datetime(r["execution_date"]),
                "Duration": duration_mins,
                "H2O AutoML": automl_r2,
                "Auto-sklearn": autosklearn_r2
            })
            
        if plot_data:
            df_plot = pd.DataFrame(plot_data).sort_values(by="ExecutionDate")
            
            st.write("")
            
            # --- Chart 1: Model Performance (Full Width) ---
            st.markdown(f"**{t['chart_perf']}**")
            import plotly.graph_objects as go
            
            # Caching the performance chart in session state to prevent reload flashes
            perf_chart_key = hash((runs_hash, test_runs_hash, lang))
            if "perf_chart_key" not in st.session_state or st.session_state.perf_chart_key != perf_chart_key or "fig_perf" not in st.session_state:
                fig_r2 = go.Figure()
                
                # Check if we have valid non-null columns
                has_automl = "H2O AutoML" in df_plot.columns and df_plot["H2O AutoML"].notna().any()
                has_autosklearn = "Auto-sklearn" in df_plot.columns and df_plot["Auto-sklearn"].notna().any()
                
                if has_automl:
                    fig_r2.add_trace(go.Scatter(
                        x=df_plot["ExecutionDate"],
                        y=df_plot["H2O AutoML"],
                        name="H2O AutoML",
                        line=dict(color="#34D399", width=3),
                        mode="lines+markers",
                        hovertemplate="%{y:.2f}%<extra></extra>"
                    ))
                if has_autosklearn:
                    fig_r2.add_trace(go.Scatter(
                        x=df_plot["ExecutionDate"],
                        y=df_plot["Auto-sklearn"],
                        name="Auto-sklearn",
                        line=dict(color="#FB923C", width=3),
                        mode="lines+markers",
                        hovertemplate="%{y:.2f}%<extra></extra>"
                    ))
                
                fig_r2.update_layout(
                    margin=dict(l=40, r=20, t=10, b=40),
                    height=280,
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    separators=get_plotly_separators(lang),
                    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(title="R² Score (%)", range=[0, 100], showgrid=True, gridcolor="rgba(255,255,255,0.05)")
                )
                st.session_state.fig_perf = fig_r2
                st.session_state.perf_chart_key = perf_chart_key
            else:
                fig_r2 = st.session_state.fig_perf
                
            st.plotly_chart(fig_r2, use_container_width=True)
            
            st.write("")
            
            # --- Chart 2: Execution Duration (Full Width) ---
            st.markdown(f"**{t['chart_dur']}**")
            import plotly.graph_objects as go
            
            # Caching the duration chart in session state to prevent reload flashes
            dur_chart_key = hash((runs_hash, test_runs_hash, lang))
            if "dur_chart_key" not in st.session_state or st.session_state.dur_chart_key != dur_chart_key or "fig_dur" not in st.session_state:
                fig_dur = go.Figure()
                
                # Area chart: Line + Markers with a soft transparent blue fill underneath
                fig_dur.add_trace(go.Scatter(
                    x=df_plot["ExecutionDate"],
                    y=df_plot["Duration"],
                    name="Duration",
                    line=dict(color="#3B82F6", width=3),
                    mode="lines+markers",
                    fill="tozeroy",
                    fillcolor="rgba(59, 130, 246, 0.15)",
                    hovertemplate="%{y:.2f} min<extra></extra>"
                ))
                
                fig_dur.update_layout(
                    margin=dict(l=40, r=20, t=10, b=40),
                    height=280,
                    hovermode="x unified",
                    showlegend=False,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    separators=get_plotly_separators(lang),
                    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                    yaxis=dict(title="Duration (Minutes)" if lang == "EN" else "Ausführungsdauer (Minuten)", rangemode="tozero", showgrid=True, gridcolor="rgba(255,255,255,0.05)")
                )
                st.session_state.fig_dur = fig_dur
                st.session_state.dur_chart_key = dur_chart_key
            else:
                fig_dur = st.session_state.fig_dur
                
            st.plotly_chart(fig_dur, use_container_width=True)



def render_monitoring(lang=None):
    """Renders the main system and Airflow monitoring page."""
    if lang is None:
        lang = st.session_state.get("language", "EN")

    t = TRANSLATIONS[lang]
    st.markdown(t["monitoring_desc"])
    render_docker_monitor(lang)
    st.write("")
    render_airflow_monitor(lang)
    st.write("")
    
    # ─── Live Container Log Viewer ──────────────────────────────────────────────
    st.subheader(t["log_viewer_title"])
    try:
        import docker
        client = get_docker_client()
        if client:
            all_containers = client.containers.list(all=True)
            container_names = sorted([c.name for c in all_containers])
        else:
            container_names = []
        
        if container_names:
            log_cols = st.columns([2, 1])
            with log_cols[0]:
                # Find index of scheduler if present, default to 0
                default_idx = 0
                if "deepwork-scheduler" in container_names:
                    default_idx = container_names.index("deepwork-scheduler")
                selected_container_name = st.selectbox(
                    t["log_viewer_select"],
                    options=container_names,
                    index=default_idx,
                    key="log_viewer_container_select"
                )
            with log_cols[1]:
                num_lines = st.number_input(
                    t["log_viewer_lines"],
                    min_value=10,
                    max_value=500,
                    value=50,
                    step=10,
                    key="log_viewer_num_lines"
                )
                
            selected_container = client.containers.get(selected_container_name)
            logs_bytes = selected_container.logs(tail=num_lines, stdout=True, stderr=True)
            logs_text = logs_bytes.decode("utf-8")
            
            logs_df = parse_container_logs(logs_text)
            
            with st.container(border=True):
                st.caption(f"Logs for **{selected_container_name}** (tail: {num_lines})")
                if not logs_df.empty:
                    def style_level(val):
                        """Apply text color coding to log levels (green for INFO, red for ERROR, orange for WARNING)."""
                        if val == "INFO":
                            return "color: #34D399; font-weight: bold;"
                        elif val in ["ERROR", "CRITICAL", "FAILED", "FATAL"]:
                            return "color: #F87171; font-weight: bold;"
                        elif val in ["WARNING", "WARN"]:
                            return "color: #FB923C; font-weight: bold;"
                        return ""
                    
                    logs_df_display = logs_df.copy()
                    if lang == "DE" and "Timestamp" in logs_df_display.columns:
                        logs_df_display["Timestamp"] = logs_df_display["Timestamp"].apply(
                            lambda x: pd.to_datetime(x).strftime("%d.%m.%Y %H:%M:%S") if pd.notna(x) else x
                        )

                    logs_df_renamed = logs_df_display.rename(columns={
                        "Timestamp": "Zeitstempel" if lang == "DE" else "Timestamp",
                        "Level": "Level",
                        "Component": "Komponente" if lang == "DE" else "Component",
                        "Message": "Nachricht" if lang == "DE" else "Message"
                    })

                    st.dataframe(
                        logs_df_renamed.style.map(style_level, subset=["Level"]),
                        use_container_width=True,
                        hide_index=True
                    )

                    # ─── Render Log Timeline Chart ───
                    st.write("")
                    st.markdown(f"**{t['log_chart_title']}**")
                    import plotly.express as px
                    
                    # Caching the log timeline Plotly figure in session state to prevent reload flashes
                    log_chart_key = hash((int(pd.util.hash_pandas_object(logs_df).sum()), selected_container_name, num_lines, lang))
                    if "log_chart_key" not in st.session_state or st.session_state.log_chart_key != log_chart_key or "fig_log" not in st.session_state:
                        df_chart = logs_df.copy()
                        df_chart["Timestamp"] = pd.to_datetime(df_chart["Timestamp"])
                        
                        color_discrete_map = {
                            "INFO": "#34D399",
                            "WARNING": "#FB923C",
                            "WARN": "#FB923C",
                            "ERROR": "#F87171",
                            "FATAL": "#F87171",
                            "CRITICAL": "#F87171",
                            "DEBUG": "#60A5FA"
                        }
                        
                        fig_log = px.histogram(
                            df_chart,
                            x="Timestamp",
                            color="Level",
                            color_discrete_map=color_discrete_map,
                            category_orders={"Level": ["INFO", "WARNING", "WARN", "DEBUG", "ERROR", "FATAL", "CRITICAL"]}
                        )
                        
                        fig_log.update_layout(
                            margin=dict(l=40, r=20, t=10, b=40),
                            height=220,
                            hovermode="x unified",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            separators=get_plotly_separators(lang),
                            xaxis=dict(title=t["log_time_x"], showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                            yaxis=dict(title=t["log_time_y"], showgrid=True, gridcolor="rgba(255,255,255,0.05)")
                        )
                        st.session_state.fig_log = fig_log
                        st.session_state.log_chart_key = log_chart_key
                    else:
                        fig_log = st.session_state.fig_log
                        
                    st.plotly_chart(fig_log, use_container_width=True)
                else:
                    st.info("No logs found for this container.")
        else:
            st.info("No containers found.")
    except Exception as e:
        st.error(f"Could not load log viewer: {e}")


# If run directly as a standalone page (keep backward compatibility)
if __name__ == "__main__":
    st.title("System & Airflow Monitoring")
    render_monitoring()
