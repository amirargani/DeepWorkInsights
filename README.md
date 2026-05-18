# DeepWorkInsights – German Unemployment Data

[![License](https://img.shields.io/badge/License-Apache_2.0-D22128?style=for-the-badge&logo=apache)](LICENSE.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
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

DeepWorkInsights downloads official monthly unemployment data for Germany, stores it as CSV,
and uses **two independent AutoML engines** (H2O AutoML and Auto-sklearn) to forecast the
current month's unemployment figure.

| | |
|---|---|
| **Data source** | Federal Employment Agency (BA), official Excel time series (Table 2.1.2) |
| **Time range** | January 2005 to current month |
| **Source data** | `files/unemployment_germany.csv` |
| **H2O forecast output** | `files/automl_predictions.csv` |
| **Auto-sklearn forecast output** | `files/autosklearn_predictions.csv` |
| **Unified predictions (CSV)** | `files/unified_predictions.csv` |
| **Unified report (Markdown)** | `files/unified_predictions.md` |

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
| `Dockerfile` | Python 3.11-slim image with Java 17, `swig`, and `build-essential` |
| `docker-compose.yml` | Service definition; mounts the project folder as a live volume |
| `requirements.txt` | Pinned Python dependencies (`auto-sklearn`, `h2o`, `numpy<2`, `scikit-learn<1.5`) |

### Build the image (once)

```bash
docker compose build
```

> The first build takes **2–10 minutes** because auto-sklearn compiles C/C++ extensions
> (SMAC3, pyrfr). Subsequent builds are instant unless `requirements.txt` changes.

### Run scripts inside the container

```bash
# All (default command) — fetch data, run H2O AutoML, then run Auto-sklearn
docker compose run --rm deepwork

# Fetch latest BA data
docker compose run --rm deepwork python fetch_data_to_csv.py

# H2O AutoML forecast
docker compose run --rm deepwork python automl_forecast.py

# Auto-sklearn forecast
docker compose run --rm deepwork python autosklearn_forecast.py
```

### Common Docker Commands

```bash
# Start the container and run all scripts in sequence (prints output to terminal)
docker-compose up

# Start the container in the background (detached mode, runs silently)
docker-compose up -d

# Stop and remove the container (and its associated network)
docker-compose down

# Stop the container and completely remove the built image (useful for a clean rebuild)
docker-compose down --rmi all

# Forcefully remove stopped containers (cleans up any left-over containers)
docker-compose rm -f
```

### How it works

- The project directory is **bind-mounted** into the container at `/app`.  
  Any change to `.py` files or CSV data on the host is immediately visible inside
  the container — no rebuild required.
- The container uses **Python 3.11** and **Java 17** (OpenJDK), satisfying the
  requirements of both auto-sklearn and H2O AutoML.
- `PYTHONUNBUFFERED=1` ensures that all print output appears in real time.

---

## Run

### 1. Fetch latest data from BA

```bash
python3 fetch_data_to_csv.py
```

### 2. Run H2O AutoML forecast

```bash
python3 automl_forecast.py
```

### 3. Run Auto-sklearn forecast

```bash
python3 autosklearn_forecast.py
```

---

## Project Structure

```text
DeepWorkInsights/
├── Dockerfile                          # Python 3.11 + Java 17 + swig image
├── docker-compose.yml                  # Docker service definition (volume mount)
├── requirements.txt                    # Pinned Python dependencies for Docker
├── fetch_data_to_csv.py                # Downloads and updates unemployment CSV
├── forecast_common.py                  # Common forecasting utilities (feature engineering, etc.)
├── automl_forecast.py                  # H2O AutoML forecast for current month
├── autosklearn_forecast.py             # Auto-sklearn forecast for current month
├── files/
│   ├── unemployment_germany.csv            # Official BA monthly figures (2005–present)
│   ├── automl_predictions.csv              # H2O AutoML forecasts (prediction history)
│   ├── autosklearn_predictions.csv         # Auto-sklearn forecasts (prediction history)
│   ├── unified_predictions.csv             # Combined H2O and Auto-sklearn forecasts (CSV format)
│   └── unified_predictions.md              # Combined H2O and Auto-sklearn forecasts (Markdown format)
├── docs/
│   └── DE.md                               # German documentation
├── README.md
└── LICENSE
```

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

### Prediction history & Gap bridging

Each run saves its forecast to `files/automl_predictions.csv`.
On subsequent runs, past predictions are temporarily merged back as training rows to bridge gaps
until official data for those months becomes available.

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

`autosklearn_forecast.py` predicts the unemployment figure for the current calendar month
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

### Prediction history & Gap bridging

Each run saves its forecast to `files/autosklearn_predictions.csv`.
On subsequent runs, past predictions are temporarily merged back as training rows to bridge gaps
until official data for those months becomes available.

### Python version note

Auto-sklearn requires **Python 3.8–3.10**.
If your system runs Python 3.11+, use `pyenv` or `conda`:

```bash
conda create -n deepwork python=3.10
conda activate deepwork
pip install auto-sklearn scikit-learn pandas numpy
python autosklearn_forecast.py
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

### v1.0
#### 🚀 Core Forecasting Engines & Features
- **H2O AutoML Integration** (`automl_forecast.py`)
  - Trains and compares multiple model types (GBM, XGBoost, Random Forest, Deep Learning, Stacked Ensembles).
  - Provides a detailed leaderboard containing R², RMSE, and MAE metrics.
  - Supports configurable execution time budgets and variable leaderboard sizes.
  - Employs a gap-bridging loop via `files/automl_predictions.csv` to maintain continuous historical data.
- **Auto-sklearn Engine** (`autosklearn_forecast.py`)
  - Leverages scikit-learn-based AutoML capabilities with weighted ensemble building.
  - Implements Polynomial Regression (degree 2) and transparent standard regressors as permanent baselines.
  - Delivers a dedicated leaderboard with R², RMSE, and MAE values per model.
  - Enables dynamic data gap bridging using `files/autosklearn_predictions.csv`.
- **Common Forecasting Utilities** (`forecast_common.py`)
  - Centralizes key feature engineering (linear Time Index, cyclical Sine/Cosine month encoding, lag variables, rolling averages, and momentum).
  - Manages history reconstruction by merging past predictions as training inputs where official Federal Employment Agency (BA) figures are still pending.

#### 🐳 Containerization & Setup
- **Docker Setup & Portability** (`Dockerfile`, `docker-compose.yml`, `requirements.txt`)
  - Provides a unified environment with Python 3.11 and OpenJDK Java 17 to run H2O and Auto-sklearn flawlessly across any OS.
  - Mounts the project folder as a live host volume, allowing code changes to take effect instantly without rebuilding.
- **Bilingual Documentation**
  - Fully localized project documentation in German ([docs/DE.md](file:///Users/amirargani/Documents/Python/DeepWorkInsights/docs/DE.md)) and English ([README.md](file:///Users/amirargani/Documents/Python/DeepWorkInsights/README.md)).

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
- **Automated Data Collector** (`fetch_data_to_csv.py`)
  - Downloads and extracts official monthly German unemployment figures (Table 2.1.2) from the Federal Employment Agency (BA).
- **Robust Network Fallback**
  - Wraps BA server downloads in a `try-except` block. If the server is unreachable or offline, the script warns the user and gracefully falls back to local CSV records instead of crashing.
- **Chronological Reindexing & Gap Interpolation**
  - Enforces a continuous monthly timeline reindexing (`freq="MS"`) over the entire historical range.
  - Automatically resolves internal gaps using rounded linear interpolation, guaranteeing mathematically sound lag and rolling window computations.
