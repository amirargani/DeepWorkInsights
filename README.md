# DeepWorkInsights – German Unemployment Data

[![License](https://img.shields.io/badge/License-Apache_2.0-D22128?style=for-the-badge&logo=apache)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit)](https://streamlit.io/)
[![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-Orchestration-017CEE?style=for-the-badge&logo=apacheairflow)](https://airflow.apache.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![H2O AutoML](https://img.shields.io/badge/H2O-AutoML-FFD700?style=for-the-badge&logo=python)](https://h2o.ai/)
[![Auto-sklearn](https://img.shields.io/badge/Auto--sklearn-AutoML-brightgreen?style=for-the-badge&logo=python)](https://automl.github.io/auto-sklearn/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

🇩🇪 [Deutsche Version](docs/DE.md)

---

## Table of Contents

- [Project Overview](#project-overview)
- [Installation & Setup](#installation--setup)
- [Docker Setup](#docker-setup)
- [Run](#run)
- [Project Structure](#project-structure)
- [Data Pipeline](#data-pipeline)
- [H2O AutoML Forecast](#h2o-automl-forecast)
- [Auto-sklearn Forecast](#auto-sklearn-forecast)
- [Changelog](#changelog)

---

## Project Overview

DeepWorkInsights fetches official monthly unemployment data for Germany from the Federal Employment Agency (BA), stores it in a **PostgreSQL database** (Single Source of Truth), and uses **two independent AutoML engines** (H2O AutoML and Auto-sklearn) to forecast upcoming monthly unemployment figures. All pipeline execution states, forecasts, and model performance metrics are visualized in an interactive **Streamlit Dashboard**.

| Component | Technology / Details |
|---|---|
| **Data Source** | Federal Employment Agency (BA), official Excel time series (Table 2.1.2) |
| **Time Horizon** | January 2005 to current month |
| **Primary Database** | PostgreSQL (`unemployment_raw`, `predictions`, `test_runs`, `test_runs_archive`) |
| **Orchestration** | Apache Airflow (`unemployment_forecast` DAG) |
| **User Interface** | Interactive Streamlit Dashboard (`http://localhost:8501`) |
| **DB Browser UI** | Adminer Web Interface (`http://localhost:8081`) |

---

## Installation & Setup

### Data collection

```bash
python3 -m pip install pandas requests openpyxl
```

### H2O AutoML forecast

```bash
python3 -m pip install h2o pandas numpy
```

### Auto-sklearn forecast

```bash
python3 pip install auto-sklearn scikit-learn pandas numpy
```

> **Note:** Auto-sklearn requires **Linux and Python ≤ 3.11**.  
> The Docker setup below solves both constraints automatically.

---

## Docker Setup

Docker is the recommended way to run **auto-sklearn** (Linux-only) and **H2O AutoML**
(requires Java) on any operating system.

### Prerequisites

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for your OS
and make sure the Docker daemon is running before executing any command below.

### Files added to the project

| File | Purpose |
|---|---|
| `docker/Dockerfile` | Python 3.11-slim image with Java 17, `swig`, and `build-essential` |
| `docker/docker-compose.yml` | Service definition; mounts the parent folder as a live volume |
| `docker/requirements.txt` | Pinned Python dependencies (`auto-sklearn`, `h2o`, `numpy<2`, `scikit-learn<1.5`) |

### Build the image (once)

```bash
docker compose -f docker/docker-compose.yml build
```

> The first build takes **2–10 minutes** because auto-sklearn compiles C/C++ extensions
> (SMAC3, pyrfr). Subsequent builds are instant unless `requirements.txt` changes.

### Run scripts inside the container

```bash
# All (default command) — fetch data, run H2O AutoML, then run Auto-sklearn
docker compose -f docker/docker-compose.yml up

# Fetch latest BA data
docker compose -f docker/docker-compose.yml run --rm deepwork python -m packages.fetch_data

# H2O AutoML forecast
docker compose -f docker/docker-compose.yml run --rm deepwork python -m packages.automl

# Auto-sklearn forecast
docker compose -f docker/docker-compose.yml run --rm deepwork python -m packages.autosklearn

# Run unit tests
docker compose -f docker/docker-compose.yml run --rm deepwork pytest tests/
```

### Common Docker Commands

```bash
# Start the container and run all scripts in sequence (prints output to terminal)
docker compose -f docker/docker-compose.yml up

# Start the container in the background (detached mode, runs silently)
docker compose -f docker/docker-compose.yml up -d

# Stop and remove the container (and its associated network)
docker compose -f docker/docker-compose.yml down

# Stop the container and completely remove the built image (useful for a clean rebuild)
docker compose -f docker/docker-compose.yml down --rmi all

# Forcefully remove stopped containers (cleans up any left-over containers)
docker compose -f docker/docker-compose.yml rm -f
```

### How it works

- The project directory is **bind-mounted** into the container at `/app`.  
  Any change to `.py` files or CSV data on the host is immediately visible inside
  the container — no rebuild required.
- The container uses **Python 3.11** and **Java 17** (OpenJDK), satisfying the
  requirements of both auto-sklearn and H2O AutoML.
- `PYTHONUNBUFFERED=1` ensures that all print output appears in real time.

---

## Apache Airflow Automation

We use **Apache Airflow** (running in its own Docker environment) to orchestrate and schedule the forecasting pipeline automatically. Default examples are disabled to keep the Airflow interface clean.

### Web Interfaces & Services Overview

Running `docker compose -f docker/docker-compose.yml up -d` spins up the following Web services:

| Service / Interface | Port / URL | Credentials / Notes | Description |
|---|---|---|---|
| **Streamlit Dashboard** | [`http://localhost:8501`](http://localhost:8501) | *None* | Interactive visualizations, seasonality analysis, forecast comparison & embedded Database Browser. |
| **Adminer (PostgreSQL UI)** | [`http://localhost:8081`](http://localhost:8081) | System: `PostgreSQL`<br>Server: `postgres`<br>User: `admin`<br>Password: `admin`<br>DB: `airflow` | Lightweight Web UI to directly view and query the PostgreSQL database (`unemployment_raw`, `predictions`, `test_runs`, etc.). |
| **Airflow Web UI** | [`http://localhost:8080`](http://localhost:8080) | User: `admin`<br>Password: `admin` | Pipeline orchestration, DAG monitoring & execution tracking. |

### Airflow Setup & Execution

1. **Initialise database & create admin user (first-time only)**:
   ```bash
   docker compose -f docker/docker-compose.yml up airflow-init
   ```

2. **Start services in detached mode**:
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

3. **Access Web UIs**:
   - **Streamlit Dashboard**: `http://localhost:8501`
   - **Adminer DB Browser**: `http://localhost:8081`
   - **Airflow Web UI**: `http://localhost:8080`

4. **Verify and Run**:
   - Locate the `unemployment_forecast` DAG.
   - Turn the DAG toggle **ON** and click **Trigger DAG** to run the pipeline.
   - The DAG is scheduled to run daily from the 26th to the 31st of every month, but uses a `ShortCircuitOperator` to ensure that the forecasting pipeline is executed exactly once per month, precisely on the last business day of the month. If no new data is available on that day, it stops and will not check again until the next month.
   - The pipeline executes three containerized steps in sequence: `fetch_data` -> `automl_forecast` -> `autosklearn_forecast` using the host's Docker daemon.

5. **Stop services**:
   ```bash
   docker compose -f docker/docker-compose.yml down
   ```

6. **Restart services**:
   ```bash
   docker compose -f docker/docker-compose.yml down
   docker compose -f docker/docker-compose.yml up -d
   ```



### Local IDE Support (Optional)

If your local IDE flags imports from `airflow` or `docker` (e.g. `unresolved import` warnings in `unemployment_forecast_dag.py`) because these libraries are executed inside Docker but not installed on your host system, you can install the development packages locally to restore auto-completion and type checking:
```bash
pip install apache-airflow apache-airflow-providers-docker
```

---

## Run

### 1. Fetch latest data from BA

```bash
python3 -m packages.fetch_data
```

### 2. Run H2O AutoML forecast

```bash
python3 -m packages.automl
```

### 3. Run Auto-sklearn forecast

```bash
python3 -m packages.autosklearn
```

---

## Project Structure

```text
DeepWorkInsights/
├── airflow/                            # Airflow Orchestration & Docker-Compose Stack
│   ├── dags/                           # DAGs for automated pipeline execution
│   │   └── unemployment_forecast_dag.py
│   ├── logs/                           # Airflow execution logs
│   ├── plugins/                        # Custom Airflow plugins
│   └── docker-compose.yml              # Complete stack (Airflow, Postgres, Streamlit, Adminer)
├── docker/                             # Core AutoML & Web UI Docker setup
│   ├── Dockerfile                      # Python 3.11 + Java 17 + swig image (ML Engine)
│   ├── Dockerfile.streamlit            # Streamlit Dashboard container image
│   ├── docker-compose.yml              # Pipeline service definition
│   └── requirements.txt                # Pinned Python dependencies
├── docs/                               # Documentation
│   └── DE.md                           # German documentation
├── packages/                           # Core Python packages & ML pipelines
│   ├── __init__.py
│   ├── common.py                       # DB connection, feature engineering, logging
│   ├── fetch_data.py                   # BA Data Scraper & Database Updater
│   ├── automl.py                       # H2O AutoML forecast pipeline
│   ├── autosklearn.py                  # Auto-sklearn forecast pipeline
│   ├── dashboard_data.py               # Dashboard data loader & DAG status queries
│   ├── monitoring_data.py              # Docker metrics, log parser & monitoring queries
│   ├── translations.py                 # Centralized EN/DE translation dictionaries
│   └── model_selection.py              # AutoML model selection & promotion
├── streamlit/                          # Web UI Dashboard App (Port 8501)
│   ├── .streamlit/                     # Streamlit theme & config
│   ├── app_pages/
│   │   ├── dashboard.py                # Seasonality & forecast charts
│   │   └── monitoring.py               # Database browser, Docker logs & benchmarks
│   ├── ui/                             # Modular UI components & dependencies
│   │   ├── __init__.py                 # Package exports for UI components
│   │   ├── charts.py                   # Plotly charts (timeline, seasonality, errors, YoY)
│   │   ├── kpi_cards.py                # Metric cards row for Actuals & Forecasts
│   │   ├── navbar.py                   # Floating navigation bar & tab/language toggles
│   │   ├── scroll_persister.py         # Scroll position persistence component
│   │   ├── state_persister.py          # Custom Component v2 browser localStorage sync
│   │   ├── styles.py                   # Global CSS styles & opacity rules
│   │   └── tables.py                   # Dataframe viewers & database browser fragment
│   ├── Dockerfile                      # Dockerfile for dashboard container
│   └── streamlit_app.py                # Main entry point for dashboard
├── tests/                              # Automated test suite (pytest)
│   ├── test_common.py                  # Utility tests
│   ├── test_fetch_data.py              # Data fetching tests
│   ├── test_model_selection.py         # Model selection tests
│   └── test_streamlit_views.py         # Dashboard view tests
├── files/                              # Exported predictions and reports
├── conftest.py                         # pytest configuration
├── setup.py                            # Python package distribution configuration
├── README.md                           # Main English documentation
└── LICENSE
```

---

## 🗄️ Database Schema & Airflow DAG Orchestration

### PostgreSQL Database Schema

PostgreSQL serves as the Single Source of Truth for raw historical data, active forecasts, evaluation test runs, and test log archives:

| Table Name | Description | Key Columns |
| :--- | :--- | :--- |
| `unemployment_raw` | Historical monthly BA unemployment records | `year` (int), `month` (str), `unemployment` (bigint) |
| `predictions` | Promoted winning AutoML & Auto-sklearn forecasts | `id` (PK), `run_timestamp`, `target_date`, `framework`, `predicted_unemployment`, `model_name`, `r2_score`, `rmse` |
| `test_runs` | Active test evaluation logs (up to 5 per framework/day) | `id` (PK), `run_timestamp`, `framework`, `model_name`, `r2_score`, `rmse`, `status` |
| `test_runs_archive` | Complete historical archive of all model test runs | `id` (PK), `run_timestamp`, `framework`, `model_name`, `r2_score`, `rmse`, `archived_at` |

---

### Airflow DAG Orchestration (`unemployment_forecast`)

The Airflow DAG (`airflow/dags/unemployment_forecast_dag.py`) executes 5 times daily (`0 0,5,10,15,20 * * *`) to automate the end-to-end forecasting pipeline:

```mermaid
graph LR
    A[fetch_data] -->|skip_on_exit_code=10| B[automl_forecast]
    B --> C[autosklearn_forecast]
    C --> D[promote_best_models]
```

1. **`fetch_data`** (`DockerOperator`): Downloads latest BA data, validates ranges and timeline gaps, and inserts into `unemployment_raw`. Returns exit code 10 if data is up to date.
2. **`automl_forecast`** (`DockerOperator`): Generates lag features, trains **H2O AutoML**, and logs model evaluation runs to `test_runs`.
3. **`autosklearn_forecast`** (`DockerOperator`): Trains **Auto-sklearn** models and logs evaluation metrics to `test_runs`.
4. **`promote_best_models`** (`DockerOperator`): Benchmarks test runs ($R^2$ / RMSE), promotes winning models to `predictions`, and archives logs to `test_runs_archive`.

---

## Data Pipeline

1. Download the current BA Excel file.
2. Extract German monthly values from sheet `Tabelle 2.1.2`.
3. Merge with existing CSV data without overwriting filled values.
4. Save a complete month-by-month timeline from 2005 onward.

---

## H2O AutoML Forecast

`automl_forecast.py` predicts the unemployment figure for the current calendar month
using **H2O AutoML**, which automatically trains and compares multiple model types
(GBM, XGBoost, Random Forest, Deep Learning, Stacked Ensembles).

### Features used

| Feature         | Description                                        |
|-----------------|----------------------------------------------------|
| `TimeIndex`     | Linear trend counter (row 1 = oldest, row N = latest) |
| `Month_sin/cos` | Cyclical month encoding – December and January stay adjacent |
| `Lag1/2/3/6`      | Unemployment values from the prior 1–6 months      |
| `Lag12`         | Same month in the previous year                    |
| `Rolling3/6`    | 3- and 6-month rolling average (leak-free)         |
| `MoM_Change`    | Month-over-month momentum                          |
| `YoY_Change`    | Year-over-year momentum                            |

### Training order

H2O AutoML trains models in this sequence:

1. **GLM** – fast linear baseline
2. **GBM** – multiple Gradient Boosting variants with different hyperparameters
3. **XGBoost** – extreme gradient boosting variants
4. **DRF + XRT** – Random Forest and Extremely Randomized Trees
5. **Deep Learning** – feed-forward neural network
6. **Stacked Ensembles** – trained last, combining all previous models

The leaderboard is sorted by **RMSE** (lowest = best).
In practice, `StackedEnsemble_AllModels` or `StackedEnsemble_BestOfFamily` wins.

### Prediction history & PostgreSQL Logging

Each run saves its forecast and evaluation metrics directly into the PostgreSQL database (`test_runs` and `predictions` tables).
On subsequent runs, past predictions are dynamically merged back as training rows to bridge gaps
until official BA data for those months becomes available.

### Example output

```
============================================================
  DeepWorkInsights – H2O AutoML Unemployment Forecast
============================================================

--- Model Leaderboard (Top 10) ---
                                                  Model  R2 (%)  RMSE          MAE
StackedEnsemble_BestOfFamily_4_AutoML_1_20260518_140401   98.82 55953 38766.850556
           GBM_grid_1_AutoML_1_20260518_140401_model_49   98.77 57166 39655.815948
           GBM_grid_1_AutoML_1_20260518_140401_model_44   98.61 60728 43736.549761
           GBM_grid_1_AutoML_1_20260518_140401_model_30   98.56 61826 42310.922136
           GBM_grid_1_AutoML_1_20260518_140401_model_51   98.49 63180 44619.747179
           GBM_grid_1_AutoML_1_20260518_140401_model_31   98.49 63211 45281.143899
           GBM_grid_1_AutoML_1_20260518_140401_model_48   98.49 63228 47060.539171
            GBM_grid_1_AutoML_1_20260518_140401_model_5   98.48 63391 45031.183299
           GBM_grid_1_AutoML_1_20260518_140401_model_26   98.46 63941 46250.507541
           GBM_grid_1_AutoML_1_20260518_140401_model_25   98.41 64845 42611.163126

============================================================
  Forecast for May 2026
  Predicted unemployment: 3,020,577
  Best model:             StackedEnsemble_BestOfFamily_4_AutoML_1_20260518_140401
  R²:                     98.82 %
  RMSE:                   55,953
============================================================
```

---

## Auto-sklearn Forecast

`packages/autosklearn.py` predicts the unemployment figure for the current calendar month
using **Auto-sklearn**, a Python-native AutoML library built on top of scikit-learn.
It automatically searches over dozens of algorithms and hyperparameter configurations,
then combines the best into a weighted ensemble.

### Models included

| Category           | Models                                                    |
|--------------------|-----------------------------------------------------------|
| **Linear**         | Ridge, Lasso, ElasticNet, SGD                             |
| **Tree-based**     | Random Forest, Extra Trees, GBM, AdaBoost, Decision Tree  |
| **Support Vector** | SVR                                                       |
| **Neural Network** | MLP (Multi-layer Perceptron)                              |
| **Neighbours**     | K-Nearest Neighbors                                       |
| **Gaussian**       | Gaussian Process                                          |

A **Polynomial Regression (degree 2)** baseline is always included alongside the ensemble:

```
PolynomialFeatures(degree=2) → StandardScaler → LinearRegression
```

`StandardScaler` is required because polynomial feature expansion produces large values
that would otherwise destabilize the linear solver.

In addition, several explicit scikit-learn models are always evaluated as transparent baselines alongside the ensemble (including `DecisionTreeRegressor`, `KNeighborsRegressor`, `SVR`, and `SGDRegressor`). Scale-sensitive models are automatically wrapped in a `StandardScaler` pipeline.

### Prediction history & PostgreSQL Logging

Each run saves its forecast and evaluation metrics directly into the PostgreSQL database (`test_runs` and `predictions` tables).
On subsequent runs, past predictions are dynamically merged back as training rows to bridge gaps
until official BA data for those months becomes available.

### Python version note

Auto-sklearn requires **Python 3.8–3.10**.
If your system runs Python 3.11+, use `pyenv` or `conda`:

```bash
conda create -n deepwork python=3.10
conda activate deepwork
pip install auto-sklearn scikit-learn pandas numpy
python -m packages.autosklearn
```

### Example output

```
==============================================================
  DeepWorkInsights – Auto-sklearn Unemployment Forecast
==============================================================

--- Model Leaderboard (Top 10) ---
                       Model  R2 (%)   RMSE    MAE
       RandomForestRegressor   87.29  75280  65820
         ExtraTreesRegressor   86.40  77857  65430
           AdaBoostRegressor   86.05  78864  65868
                       Lasso   84.83  82233  76093
   GradientBoostingRegressor   84.72  82548  73720
                  ElasticNet   84.46  83242  77389
PolynomialRegression (deg 2)   82.93  87250  67209
                SGDRegressor   79.45  95710  84276
       DecisionTreeRegressor   79.05  96639  85803
         KNeighborsRegressor   14.53 195211 168930

==============================================================
  Forecast for May 2026
  Predicted unemployment: 2,831,281
  Best model:             RandomForestRegressor
  R²:                     87.29 %
  RMSE:                   75,280
==============================================================
```

> **Note:** `MLPRegressor` produced a negative R² (–66.90 %) in this run and was excluded.
> Negative R² means the model performs worse than a simple mean prediction – typically caused
> by insufficient training data for neural networks or missing hyperparameter tuning.

---

## Forecast Comparison (May 2026)

| Metric | H2O AutoML | Auto-sklearn |
|---|---|---|
| **Predicted Unemployment** | **3,020,577** | **2,831,281** |
| **Best Model** | `StackedEnsemble` | `RandomForestRegressor` |
| **R² Score** | `98.82 %` | `87.29 %` |
| **RMSE** | `55,953` | `75,280` |
| **MAE** | `38,767` | `65,820` |

---

## Changelog

### v1.3
#### 🇩🇪 German Localization & Language-Aware Formatters
- **Dedicated Formatter Module** (`streamlit/ui/formatters.py`):
  - New module with locale-sensitive formatting functions for numbers (`format_number`) and percentages (`format_percent`), switching between German (dot-separated thousands, comma decimal) and English notation based on active language selection.
- **Full Dashboard & Monitoring Localization** (`streamlit/app_pages/dashboard.py`, `streamlit/app_pages/monitoring.py`, `streamlit/ui/tables.py`):
  - Localized all metric card titles, KPI labels, Plotly chart axis titles, tooltips, table column headers, and log inspection controls based on the active EN/DE language toggle.
- **Module-Level Documentation**:
  - Added comprehensive module docstrings and inline documentation across all backend packages (`packages/automl.py`, `packages/autosklearn.py`, `packages/common.py`, `packages/dashboard_data.py`, `packages/fetch_data.py`, `packages/model_selection.py`, `packages/monitoring_data.py`) and Streamlit UI modules.

#### 🗄️ Automated Test Run Archival & Record Capping
- **Configurable Active Record Cap** (`packages/model_selection.py`, `packages/common.py`):
  - `archive_test_runs` now enforces a configurable maximum of 5 active test run records per framework per day, automatically archiving the oldest excess entries to `test_runs_archive`.
  - Archival is triggered automatically after each prediction run, keeping `test_runs` lean and preventing unbounded growth.
- **Expanded Test Suite** (`tests/test_model_selection.py`, `tests/test_streamlit_views.py`):
  - Added comprehensive unit tests covering the cap enforcement logic, archival triggers, boundary conditions, and framework isolation.

### v1.2
#### 📖 PostgreSQL Database Schema & Airflow DAG Documentation
- **Architecture Documentation** (`README.md`, `docs/DE.md`):
  - Added comprehensive PostgreSQL database schema descriptions for all four tables: `unemployment_raw`, `predictions`, `test_runs`, and `test_runs_archive`.
  - Added Airflow DAG orchestration section with execution schedule, ShortCircuitOperator control flow, and pipeline step breakdown (`fetch_data` → `automl_forecast` → `autosklearn_forecast`).
  - Purged all obsolete v1.0 CSV file references (`files/automl_predictions.csv`, `files/autosklearn_predictions.csv`, `files/unified_predictions.md`) in favor of PostgreSQL as the single source of truth.

#### 🎨 Sequential Vertical UI Layout & Scroll Persistence
- **Sequential Vertical Layout** (`streamlit/ui/tables.py`):
  - Replaced horizontal tab-based navigation for database tables and execution logs with a clean, sequential vertical view for improved readability and simpler scrolling.
- **Enhanced Scroll Persistence** (`streamlit/ui/scroll_persister.py`):
  - Refactored scroll persistence logic with active tab tracking and stateful callbacks to reliably retain exact scroll positions across Streamlit reruns.

### v1.1
#### 🏛️ Centralized Docker Architecture & Execution
- **Unified Docker Compose Stack** (`docker/docker-compose.yml`):
  - Consolidated all services (**PostgreSQL**, **Airflow Webserver**, **Airflow Scheduler**, **Airflow Init**, **Streamlit Dashboard**, **Adminer DB UI**, **AutoML Runner**) into a single centralized Docker Compose file.
  - Simplified execution: `docker compose -f docker/docker-compose.yml up -d` launches the entire infrastructure.
- **Dedicated Container Images** (`docker/Dockerfile`, `docker/Dockerfile.streamlit`):
  - Clean separation of the heavy ML engine (`Python 3.11 + Java 17 + C++ Build Tools`) from the lightweight UI container (`Python 3.10-slim + Streamlit + Plotly`).

#### 🗄️ PostgreSQL Database Integration & Web Management
- **PostgreSQL as Single Source of Truth**:
  - Full database persistence for historical unemployment data (`unemployment_raw`), promoted forecasts (`predictions`), active evaluation runs (`test_runs`), and historical model archives (`test_runs_archive`).
- **Adminer Database Web UI** ([`http://localhost:8081`](http://localhost:8081)):
  - Integrated Adminer for direct web-based management, SQL querying, and visual inspection of PostgreSQL database tables.
- **Unified Security Credentials**:
  - Standardized admin credentials (`admin` / `admin`) across PostgreSQL, Adminer, and Airflow.

#### 📊 Streamlit Dashboard & Interactive Monitoring
- **Backend Data Modules** (`packages/dashboard_data.py`, `packages/monitoring_data.py`):
  - Extracted backend data fetching, database cache queries, DAG state verification, Docker container metrics collection, and multi-format log parsing into dedicated reusable packages.
- **Modular UI Component Package** (`streamlit/ui/`):
  - Extracted and organized all UI elements into single-responsibility Python modules (`styles.py`, `scroll_persister.py`, `state_persister.py`, `navbar.py`, `kpi_cards.py`, `charts.py`, `tables.py`, `__init__.py`).
- **Browser State Synchronization** (`streamlit/ui/state_persister.py`):
  - Implemented `st.components.v1.html` script to seamlessly persist and hydrate language selections across reruns via browser `localStorage`.
- **Scroll & Stale Element Transition Optimization**:
  - Instant DOM element transition management (`display: none !important` on stale elements) ensuring seamless tab switching without previous tab content flickering.
- **Dynamic Seasonality Analysis** (`streamlit/app_pages/dashboard.py`):
  - Automatic calculation and rendering of dynamic year ranges (e.g. `2005 - 2025 vs. Current Year 2026`; automatically shifts in future years like 2027 to `2005 - 2026 vs. Current Year 2027`).
- **Interactive Time-Filter**:
  - Quick period selector (*All Time*, *Last 5 Years*, *Last 3 Years*, *Last 1 Year*) without page reloads.
- **Database & Evaluation Logs Browser** (`streamlit/app_pages/monitoring.py`):
  - Embedded browser for live inspection of database tables, model leaderboards, Docker container status, and system logs.

#### 🧪 Comprehensive pytest Suite
- **10/10 Automated Unit Tests** (`tests/`):
  - `test_common.py`: Verifies feature engineering, sine/cosine cyclical encoding, lags, `build_target_row`, and database logging.
  - `test_fetch_data.py`: Tests month mapping and Excel parsing routines.
  - `test_model_selection.py`: Validates model ranking by $R^2$/RMSE and test run archiving.
  - `test_streamlit_views.py`: Tests dashboard filter cutoffs and benchmark SQL queries.

#### 🌐 English Codebase & Documentation Standard
- **Full Standardization**:
  - Standardized all inline comments, module docstrings, Docker build scripts, and YAML configurations across the entire codebase to professional English.

### v1.0
#### 🚀 Core Forecasting Engines & Features
- **H2O AutoML Integration** (`packages/automl.py`)
  - Trains and compares multiple model types (GBM, XGBoost, Random Forest, Deep Learning, Stacked Ensembles).
  - Provides a detailed leaderboard containing R², RMSE, and MAE metrics.
  - Supports configurable execution time budgets and variable leaderboard sizes.
  - Employs a gap-bridging loop via `files/automl_predictions.csv` to maintain continuous historical data.
- **Auto-sklearn Engine** (`packages/autosklearn.py`)
  - Leverages scikit-learn-based AutoML capabilities with weighted ensemble building.
  - Implements Polynomial Regression (degree 2) and transparent standard regressors as permanent baselines.
  - Delivers a dedicated leaderboard with R², RMSE, and MAE values per model.
  - Enables dynamic data gap bridging using `files/autosklearn_predictions.csv`.
- **Common Forecasting Utilities** (`packages/common.py`)
  - Centralizes key feature engineering (linear Time Index, cyclical Sine/Cosine month encoding, lag variables, rolling averages, and momentum).
  - Manages history reconstruction by merging past predictions as training inputs where official Federal Employment Agency (BA) figures are still pending.

#### 🐳 Containerization & Setup
- **Docker Setup & Portability** (`docker/Dockerfile`, `docker/docker-compose.yml`, `docker/requirements.txt`)
  - Provides a unified environment with Python 3.11 and OpenJDK Java 17 to run H2O and Auto-sklearn flawlessly across any OS.
  - Mounts the project folder as a live host volume, allowing code changes to take effect instantly without rebuilding.
- **Bilingual Documentation**
  - Fully localized project documentation in German ([docs/DE.md](file:///Users/amirargani/Documents/GitHub/DeepWorkInsights/docs/DE.md)) and English ([README.md](file:///Users/amirargani/Documents/GitHub/DeepWorkInsights/README.md)).

#### 📊 Reports, Logging & Sync
- **Unified Markdown Report** (`files/unified_predictions.md`)
  - Automatically compiles and renders a clear vertical side-by-side comparison of forecasts and performance metrics (predictions, R², RMSE, MAE) after each run.
  - Curates and formats long H2O and scikit-learn model names for premium readability.
- **Consistent Log Synchronization**
  - Extends the `save_prediction` function to dynamically log full performance metrics (R² Score, RMSE, and MAE).
  - Automatically invokes `write_unified_outputs()` at the end of both pipelines, ensuring that `files/unified_predictions.csv` and `files/unified_predictions.md` always remain perfectly synchronized.
- **Dynamic & Safe Execution Logging**
  - Records the exact day of execution (e.g., `2026-05-18`) in the `Date` column, rather than defaulting to the first day of the calendar month.
  - Provides overwrite protection based on Year and Month matching, preventing duplicate rows during multiple test runs.
  - Standardizes logged dates to the start of the month (`freq="MS"`) inside the ML engine to preserve the grid's chronological integrity.

#### 🛠️ Data Pipeline & Resiliency
- **Automated Data Collector** (`packages/fetch_data.py`)
  - Downloads and extracts official monthly German unemployment figures (Table 2.1.2) from the Federal Employment Agency (BA).
- **Robust Network Fallback**
  - Wraps BA server downloads in a `try-except` block. If the server is unreachable or offline, the script warns the user and gracefully falls back to local CSV records instead of crashing.
- **Chronological Reindexing & Gap Interpolation**
  - Enforces a continuous monthly timeline reindexing (`freq="MS"`) over the entire historical range.
  - Automatically resolves internal gaps using rounded linear interpolation, guaranteeing mathematically sound lag and rolling window computations.
