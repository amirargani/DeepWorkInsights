import os
import sys
import re
import docker
import pandas as pd
import streamlit as st

from packages.common import get_db_engine

# Bilingual Translation Dictionary for Monitoring Page
MONITORING_TRANSLATIONS = {
    "EN": {
        "docker_sub": "Docker Container Performance",
        "docker_err": "Unable to connect to Docker socket on `/var/run/docker.sock`:",
        "docker_info": "Ensure the Docker socket is mounted to the container and has correct permissions.",
        "docker_loading": "Loading container performance footprint...",
        "airflow_sub": "Airflow Workflow Statistics",
        "airflow_err": "Airflow metadata tables not found in database. Once Airflow scheduler initializes the database, DAG stats will appear here.",
        "task_states": "Current Task Instance States (Total)",
        "dag_title": "Registered DAGs",
        "dag_runs_title": "Latest DAG Runs (Execution History)",
        "monitoring_desc": "Real-time view of Airflow DAG execution states, database health, and Docker container performance.",
        "col_success": "Success",
        "col_failed": "Failed",
        "col_running": "Running",
        "col_queued": "Queued",
        "btn_trigger": "Trigger DAG",
        "btn_stop": "Stop DAG",
        "btn_unpause": "Unpause",
        "btn_pause": "Pause",
        "log_viewer_title": "Container Log Viewer",
        "log_viewer_select": "Select Container",
        "log_viewer_lines": "Lines",
        "toast_trigger_success": "DAG triggered successfully!",
        "toast_stop_success": "DAG stopped successfully!",
        "toast_unpause_success": "DAG activated!",
        "toast_pause_success": "DAG paused!",
        "control_guide_html": """
            <div style="font-size: 0.85em; color: #9CA3AF; margin-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 0.75rem;">
                <strong>💡 Control Guide:</strong>
                <ul style="margin: 0.25rem 0 0 1.25rem; padding: 0;">
                    <li><strong>Trigger DAG</strong>: Instantly starts the model training and forecasting pipeline manually. Disabled if a run is already active.</li>
                    <li><strong>Stop DAG</strong>: Instantly terminates any currently running or queued execution step (marks it as failed in the DB).</li>
                    <li><strong>Pause / Unpause</strong>: Pauses or resumes the fully automated cron schedule (runs 5 times a day: 00:00, 05:00, 10:00, 15:00, 20:00 UTC / 02:00, 07:00, 12:00, 17:00, 22:00 local time). When "Paused", no automatic background runs occur.</li>
                </ul>
            </div>
        """,
        "chart_perf": "Model Performance (R²) Trend",
        "chart_dur": "Execution Duration (Minutes)",
        "log_chart_title": "Log Frequency & Level Timeline",
        "log_time_x": "Time",
        "log_time_y": "Log Count",
    },
    "DE": {
        "docker_sub": "Docker-Container-Performance",
        "docker_err": "Verbindung zum Docker-Socket unter `/var/run/docker.sock` nicht möglich:",
        "docker_info": "Stellen Sie sicher, dass das Docker-Socket im Container gemountet ist und die richtigen Berechtigungen hat.",
        "docker_loading": "Lade Container-Performance-Footprint...",
        "airflow_sub": "Airflow-Workflow-Statistiken",
        "airflow_err": "Airflow-Metadaten-Tabellen in der Datenbank nicht gefunden. Sobald der Airflow-Scheduler die Datenbank initialisiert, werden die DAG-Statistiken hier angezeigt.",
        "task_states": "Aktuelle Task-Instanz-Status (Gesamt)",
        "dag_title": "Registrierte DAGs",
        "dag_runs_title": "Neueste DAG-Läufe (Ausführungshistorie)",
        "monitoring_desc": "Echtzeit-Ansicht der Airflow DAG-Ausführungsstatus, Datenbank-Integrität und Docker-Container-Performance.",
        "col_success": "Erfolgreich",
        "col_failed": "Fehlgeschlagen",
        "col_running": "Laufend",
        "col_queued": "Warteschlange",
        "btn_trigger": "DAG ausführen",
        "btn_stop": "Beenden",
        "btn_unpause": "Aktivieren",
        "btn_pause": "Deaktivieren",
        "log_viewer_title": "Container-Logs einsehen",
        "log_viewer_select": "Container auswählen",
        "log_viewer_lines": "Zeilen",
        "toast_trigger_success": "DAG erfolgreich gestartet!",
        "toast_stop_success": "DAG erfolgreich beendet!",
        "toast_unpause_success": "DAG reaktiviert!",
        "toast_pause_success": "DAG pausiert!",
        "control_guide_html": """
            <div style="font-size: 0.85em; color: #9CA3AF; margin-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 0.75rem;">
                <strong>💡 Bedienungshilfen:</strong>
                <ul style="margin: 0.25rem 0 0 1.25rem; padding: 0;">
                    <li><strong>DAG ausführen</strong>: Startet die Modeltraining- und Vorhersage-Pipeline sofort manuell. Deaktiviert, wenn bereits ein Lauf aktiv ist.</li>
                    <li><strong>Beenden</strong>: Bricht einen aktuell laufenden oder in der Warteschlange befindlichen Ausführungsschritt sofort ab (setzt den Status in der DB auf fehlgeschlagen).</li>
                    <li><strong>Aktivieren / Deaktivieren</strong>: Pausiert oder reaktiviert den vollautomatischen Zeitplan (5-mal täglich: 00:00, 05:00, 10:00, 15:00, 20:00 UTC / 02:00, 07:00, 12:00, 17:00, 22:00 Ortszeit). Bei "Pause" finden keine automatischen Hintergrundläufe statt.</li>
                </ul>
            </div>
        """,
        "chart_perf": "Modell-Performance (R²) Trend",
        "chart_dur": "Ausführungsdauer (Minuten)",
        "log_chart_title": "Log-Frequenz & Level-Zeitverlauf",
        "log_time_x": "Uhrzeit",
        "log_time_y": "Log-Anzahl",
    },
}

TRANSLATIONS = MONITORING_TRANSLATIONS


@st.cache_resource
def get_docker_client():
    """Connects to the local/container Docker daemon."""
    try:
        return docker.from_env()
    except Exception:
        return None


def parse_container_logs(logs_text: str) -> pd.DataFrame:
    """Parses raw Docker container stdout/stderr log text into a structured dataframe."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    clean_text = ansi_escape.sub("", logs_text)

    lines = clean_text.split("\n")
    parsed_records = []

    airflow_pattern = re.compile(
        r"^\[(?P<timestamp>[^\]]+)\]\s*\{(?P<source>[^\}]+)\}\s*(?P<level>[A-Z]+)\s*-\s*(?P<message>.*)$"
    )

    gunicorn_pattern = re.compile(
        r"^\[(?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(?:\s[+-]\d{4})?)\]\s*\[(?P<pid>\d+)\]\s*\[(?P<level>[A-Z]+)\]\s*(?P<message>.*)$"
    )

    access_pattern = re.compile(
        r'^(?P<ip>\S+)\s+-\s+-\s+\[(?P<timestamp>[^\]]+)\]\s+"(?P<request>[^"]*)"\s+(?P<status>\d+)\s+(?P<bytes>\d+).*$'
    )

    postgres_pattern = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\s+[A-Z]+)?)\s*\[(?P<pid>\d+)\]\s*(?P<level>[A-Z]+):\s*(?P<message>.*)$"
    )

    generic_pattern = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+(?P<message>.*)$"
    )

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue

        matched = False

        m = airflow_pattern.match(line_str)
        if m:
            gd = m.groupdict()
            ts = gd["timestamp"]
            try:
                ts_formatted = pd.to_datetime(ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                ts_formatted = ts
            parsed_records.append(
                {
                    "Timestamp": ts_formatted,
                    "Level": gd["level"].upper(),
                    "Source": gd["source"],
                    "Message": gd["message"],
                }
            )
            matched = True

        if not matched:
            m = gunicorn_pattern.match(line_str)
            if m:
                gd = m.groupdict()
                ts = gd["timestamp"]
                try:
                    ts_clean = ts.split()[0] + " " + ts.split()[1]
                    ts_formatted = pd.to_datetime(ts_clean).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except Exception:
                    ts_formatted = ts
                parsed_records.append(
                    {
                        "Timestamp": ts_formatted,
                        "Level": gd["level"].upper(),
                        "Source": f"PID:{gd['pid']}",
                        "Message": gd["message"],
                    }
                )
                matched = True

        if not matched:
            m = access_pattern.match(line_str)
            if m:
                gd = m.groupdict()
                ts = gd["timestamp"]
                try:
                    ts_clean = ts.split()[0]
                    ts_formatted = pd.to_datetime(
                        ts_clean, format="%d/%b/%Y:%H:%M:%S"
                    ).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    ts_formatted = ts

                status = int(gd["status"])
                level = "INFO"
                if status >= 500:
                    level = "ERROR"
                elif status >= 400:
                    level = "WARNING"

                parsed_records.append(
                    {
                        "Timestamp": ts_formatted,
                        "Level": level,
                        "Source": f"Access ({gd['ip']})",
                        "Message": f'"{gd["request"]}" {gd["status"]} {gd["bytes"]}',
                    }
                )
                matched = True

        if not matched:
            m = postgres_pattern.match(line_str)
            if m:
                gd = m.groupdict()
                ts = gd["timestamp"]
                try:
                    ts_clean = (
                        ts.split(" UTC")[0].split()[0]
                        + " "
                        + ts.split(" UTC")[0].split()[1]
                    )
                    ts_formatted = pd.to_datetime(ts_clean).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except Exception:
                    ts_formatted = ts

                level = gd["level"].upper()
                if level == "LOG":
                    level = "INFO"

                parsed_records.append(
                    {
                        "Timestamp": ts_formatted,
                        "Level": level,
                        "Source": f"DB PID:{gd['pid']}",
                        "Message": gd["message"],
                    }
                )
                matched = True

        if not matched:
            m = generic_pattern.match(line_str)
            if m:
                gd = m.groupdict()
                ts = gd["timestamp"]
                try:
                    ts_formatted = pd.to_datetime(ts).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except Exception:
                    ts_formatted = ts

                msg = gd["message"]
                level = "INFO"
                if "ERROR" in msg.upper():
                    level = "ERROR"
                elif "WARNING" in msg.upper() or "WARN" in msg.upper():
                    level = "WARNING"

                parsed_records.append(
                    {
                        "Timestamp": ts_formatted,
                        "Level": level,
                        "Source": "App Log",
                        "Message": msg,
                    }
                )
                matched = True

        if not matched:
            if parsed_records and not (
                line_str.startswith("[")
                or re.match(r"^\d{4}-\d{2}-\d{2}", line_str)
                or re.match(r"^\S+\s+-\s+-", line_str)
            ):
                parsed_records[-1]["Message"] += "\n" + line_str
            else:
                parsed_records.append(
                    {
                        "Timestamp": "N/A",
                        "Level": "INFO",
                        "Source": "N/A",
                        "Message": line_str,
                    }
                )

    df = pd.DataFrame(parsed_records)
    if not df.empty:
        df = df[df["Timestamp"] != "N/A"]
    return df


def get_container_metrics(container) -> dict:
    """Computes CPU %, Memory usage (MB and %), and I/O metrics for a running Docker container."""
    try:
        stats = container.stats(stream=False)

        mem_usage = stats.get("memory_stats", {}).get("usage", 0)
        mem_limit = stats.get("memory_stats", {}).get("limit", 1)
        mem_pct = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
        mem_mb = mem_usage / (1024 * 1024)

        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})

        cpu_usage_total = cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        precpu_usage_total = precpu_stats.get("cpu_usage", {}).get("total_usage", 0)

        system_cpu_usage = cpu_stats.get("system_cpu_usage", 0)
        presystem_cpu_usage = precpu_stats.get("system_cpu_usage", 0)

        cpu_delta = cpu_usage_total - precpu_usage_total
        system_delta = system_cpu_usage - presystem_cpu_usage

        num_cpus = cpu_stats.get("online_cpus", 1)

        if cpu_delta > 0 and system_delta > 0:
            cpu_pct = (cpu_delta / system_delta) * num_cpus * 100.0
        else:
            cpu_pct = 0.0

        return {
            "CPU (%)": f"{cpu_pct:.1f}%",
            "Memory (MB)": f"{mem_mb:.1f} MB",
            "Memory (%)": f"{mem_pct:.1f}%",
        }
    except Exception:
        return {
            "CPU (%)": "N/A",
            "Memory (MB)": "N/A",
            "Memory (%)": "N/A",
        }
