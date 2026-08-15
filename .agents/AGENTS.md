# DeepWorkInsights Agent Rules & Guidelines

This workspace containing the DeepWorkInsights project holds monthly German unemployment data and forecasts it using H2O AutoML and Auto-sklearn.

Because the local development environment is macOS, special configuration and execution rules apply due to library/OS constraints.

---

## 💻 Environment & Execution Rules

### 1. Auto-sklearn Execution Constraint
> [!IMPORTANT]
> `auto-sklearn` is Linux-only and requires Python ≤ 3.11.
> **DO NOT** attempt to run `packages/autosklearn.py` directly on the macOS host. It will fail.
> Always execute Auto-sklearn tasks inside the Docker container.

### 2. Docker & Docker Compose Commands
Use the following commands to build and run the services:
- **Build the image**:
  ```bash
  docker compose -f docker/docker-compose.yml build
  ```
- **Run all pipelines (Fetch -> H2O AutoML -> Auto-sklearn)**:
  ```bash
  # Starts the pipeline container and automatically deletes it upon completion
  docker compose -f docker/docker-compose.yml run --rm deepwork
  ```
  *Alternatively, run with standard up (containers persist until cleaned up with docker compose down):*
  ```bash
  docker compose -f docker/docker-compose.yml up
  ```
- **Run H2O AutoML forecast pipeline only**:
  ```bash
  docker compose -f docker/docker-compose.yml run --rm deepwork python -m packages.automl
  ```
- **Run Auto-sklearn forecast pipeline only**:
  ```bash
  docker compose -f docker/docker-compose.yml run --rm deepwork python -m packages.autosklearn
  ```
- **Run unit tests**:
  ```bash
  docker compose -f docker/docker-compose.yml run --rm deepwork pytest tests/
  ```

### 3. Apache Airflow Automation Commands
- **Init Airflow DB & Admin User**:
  ```bash
  docker compose -f docker/docker-compose.yml up airflow-init
  ```
- **Start Airflow Stack (Detached)**:
  ```bash
  docker compose -f docker/docker-compose.yml up -d
  ```
- **Stop Airflow Stack**:
  ```bash
  docker compose -f docker/docker-compose.yml down
  ```
- **Local IDE support installation (Optional)**:
  ```bash
  pip install apache-airflow apache-airflow-providers-docker
  ```

---

## 📂 File Map & Modular Architecture

### 1. Backend ML & Data Packages (`packages/`)
- **`common.py`**: Shared database engine, feature engineering (`engineer_features`), gap-free timeline loading (`load_data`), and prediction logging (`save_prediction`).
- **`fetch_data.py`**: Scrapes official BA Excel data, validates values, and loads into PostgreSQL `unemployment_raw`. Returns exit code 10 if data is up to date.
- **`automl.py`**: H2O AutoML training & prediction pipeline.
- **`autosklearn.py`**: Auto-sklearn training & prediction pipeline (Linux/Docker only).
- **`model_selection.py`**: Evaluates test runs, calculates $R^2$ / RMSE benchmarks, and promotes winning models to `predictions`.
- **`dashboard_data.py`**: Backend data loader for raw history, predictions, evaluation logs, and active DAG status check.
- **`monitoring_data.py`**: Docker container stats collector, multi-format regex log parser, and Airflow monitoring queries.
- **`translations.py`**: Centralized bilingual EN/DE translation dictionaries for dashboard and monitoring views.

### 2. Streamlit Web Application (`streamlit/`)
- **`streamlit_app.py`**: Main entry point orchestrating top navigation, scroll persistence, and language state hydration.
- **`streamlit/app_pages/`**: Single-page view logic (`dashboard.py`, `monitoring.py`).
- **`streamlit/ui/`**: Modular UI components package:
  - `styles.py`: Global CSS definitions, KPI card equal heights, and stale-element hide transitions (`[data-stale="true"] { display: none !important; }`).
  - `scroll_persister.py`: Smooth scroll position persistence HTML/JS component.
  - `state_persister.py`: Browser `localStorage` language state persistence via `st.components.v1.html`.
  - `navbar.py`: Floating sticky top navbar component and instant tab hide DOM callbacks.
  - `kpi_cards.py`: Metric cards row for Actuals BA, H2O AutoML, and Auto-sklearn.
  - `charts.py`: Plotly chart functions with session state figure caching (`render_historical_timeline_chart`, `render_seasonality_chart`, `render_forecast_error_chart`, `render_yoy_change_chart`).
  - `tables.py`: Dataframe viewers, `clean_model_name` formatter, and `@st.fragment` database browser.

---

## 🛠️ Code Architecture & Standards

### 1. Shared Utilities & Import Conventions
- Do not duplicate data loading, feature engineering, prediction logging, or target row construction logic in individual pipeline scripts.
- Always import backend logic using the canonical package namespace (`from packages.common import ...`, `from packages.dashboard_data import ...`).

### 2. Warning Suppression
- Suppress non-critical warnings from `pandas`, `numpy`, `h2o`, and `scikit-learn` using:
  ```python
  import warnings
  warnings.filterwarnings("ignore")
  ```
- Keep console logs clean and readable.

### 3. Dependencies
- Pinned python dependencies must be updated in both `docker/requirements.txt` and the multi-step `pip install` commands in `docker/Dockerfile` to keep the container runtime environments synchronized.

---

## 📊 Database & Data Quality Guidelines

### 1. Database Schema & Tables
PostgreSQL is the single source of truth for all historical data, forecasts, and evaluations. Avoid using CSV files directly for calculations:
* **`unemployment_raw`**: Stores historical monthly unemployment numbers with columns `year` (int), `month` (str), and `unemployment` (int).
* **`predictions`**: Stores promoted AutoML and Auto-sklearn forecasts.
* **`test_runs`**: Stores active model evaluation test logs (up to 5 per framework per day).
* **`test_runs_archive`**: Archive of all past test logs.

### 2. Data Quality Checks
Whenever raw data is loaded or inspected, run the following automated checks:
* **Timeline Gaps**: Build a continuous date index from `MIN(Date)` to `MAX(Date)` and verify that all months are present without gaps.
* **Value Ranges**: Validate that all unemployment values are within reasonable limits (`[0, 8000000]`).
* **Completeness/Nulls**: Scan the historical database for missing (`Null`/`NaN`) unemployment numbers. Note that target rows for future months may have missing values before publication.

### 3. Streamlit UI & Formatting Rules
To prevent runtime crashes (TypeErrors or AttributeErrors), any edits to Streamlit dashboard pages must respect version limitations:
* **Integer Formatting**: Always format the `year` column using `year: "{:.0f}"` or cast it to prevent default thousands-separator comma rendering (e.g. `2026` instead of `2,026`).
* **Timestamp Formatting**: Style all datetime columns (`run_timestamp`, `execution_date`, `start_date`, `end_date`) using `lambda x: pd.to_datetime(x).strftime("%Y-%m-%d %H:%M:%S")` to remove microseconds and show a uniform format.
* **Spinner Loading**: Use `st.spinner(...)` instead of `st.skeleton`.
* **Selection Widgets**: Use `st.radio(..., horizontal=True)` instead of `st.segmented_control`.
* **Element Widths & Heights**:
  * Use `use_container_width=True` on `st.dataframe` and `st.plotly_chart` instead of `width="stretch"` (which throws a TypeError).
  * Do not specify `height="stretch"` on `st.container` (unsupported).
* **Metric Cards**: Wrap metrics inside `st.container(border=True)` to display a bordered card container instead of calling `st.metric(..., border=True)` directly.
* **Expander Layout**: Use standard Python `with st.expander("Title"):` context blocks. Do not check `.open` or pass `on_change` as arguments.
* **Stale Element Hiding**: In CSS, apply `[data-stale="true"] { display: none !important; }` so that switching tabs hides previous DOM elements instantly while new tab content loads.
