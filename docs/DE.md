# DeepWorkInsights – Deutsche Arbeitslosendaten

[![License](https://img.shields.io/badge/License-Apache_2.0-D22128?style=for-the-badge&logo=apache)](../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit)](https://streamlit.io/)
[![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-Orchestration-017CEE?style=for-the-badge&logo=apacheairflow)](https://airflow.apache.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)
[![H2O AutoML](https://img.shields.io/badge/H2O-AutoML-FFD700?style=for-the-badge&logo=python)](https://h2o.ai/)
[![Auto-sklearn](https://img.shields.io/badge/Auto--sklearn-AutoML-brightgreen?style=for-the-badge&logo=python)](https://automl.github.io/auto-sklearn/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

🇺🇸 [English Version](../README.md)

---

## Inhaltsverzeichnis

- [Projektübersicht](#projektübersicht)
- [Installation & Einrichtung](#installation--einrichtung)
- [Docker-Einrichtung](#docker-einrichtung)
- [Ausführung](#ausführung)
- [Projektstruktur](#projektstruktur)
- [Daten-Pipeline](#daten-pipeline)
- [H2O AutoML Vorhersage](#h2o-automl-vorhersage)
- [Auto-sklearn Vorhersage](#auto-sklearn-vorhersage)
- [Changelog](#changelog)

---

## Projektübersicht

DeepWorkInsights lädt offizielle monatliche Arbeitslosendaten für Deutschland von der Bundesagentur für Arbeit (BA) herunter, speichert diese in einer **PostgreSQL-Datenbank** (Single Source of Truth) und nutzt **zwei unabhängige AutoML-Engines** (H2O AutoML und Auto-sklearn), um monatliche Arbeitslosenzahlen vorherzusagen. Alle Pipeline-Ausführungsstatus, Vorhersagen und Modell-Metriken werden in einem interaktiven **Streamlit Dashboard** visualisiert.

| Komponente | Technologie / Details |
|---|---|
| **Datenquelle** | Bundesagentur für Arbeit (BA), offizielle Excel-Zeitreihen (Tabelle 2.1.2) |
| **Zeitraum** | Januar 2005 bis zum aktuellen Monat |
| **Zentrale Datenbank** | PostgreSQL (`unemployment_raw`, `predictions`, `test_runs`, `test_runs_archive`) |
| **Orchestrierung** | Apache Airflow (`unemployment_forecast` DAG) |
| **Benutzeroberfläche** | Interaktives Streamlit Dashboard (`http://localhost:8501`) |
| **DB Browser UI** | Adminer Web Interface (`http://localhost:8081`) |

---

## Installation & Einrichtung

### Datenerhebung

```bash
python3 -m pip install pandas requests openpyxl
```

### H2O AutoML Vorhersage

```bash
python3 -m pip install h2o pandas numpy
```

### Auto-sklearn Vorhersage

```bash
python3 pip install auto-sklearn scikit-learn pandas numpy
```

> **Hinweis:** Auto-sklearn erfordert **Linux und Python ≤ 3.11**.  
> Das untenstehende Docker-Setup löst beide Einschränkungen automatisch.

---

## Docker-Einrichtung

Docker ist der empfohlene Weg, um **auto-sklearn** (nur Linux) und **H2O AutoML** (erfordert Java) auf jedem Betriebssystem auszuführen.

### Voraussetzungen

Installieren Sie [Docker Desktop](https://www.docker.com/products/docker-desktop/) für Ihr Betriebssystem und stellen Sie sicher, dass der Docker-Daemon läuft, bevor Sie die folgenden Befehle ausführen.

### Dem Projekt hinzugefügte Dateien

| Datei | Zweck |
|---|---|
| `docker/Dockerfile` | Python 3.11-slim Image mit Java 17, `swig` und `build-essential` |
| `docker/docker-compose.yml` | Service-Definition; bindet das übergeordnete Verzeichnis als Live-Volume ein |
| `docker/requirements.txt` | Fixierte Python-Abhängigkeiten (`auto-sklearn`, `h2o`, `numpy<2`, `scikit-learn<1.5`) |

### Image erstellen (einmalig)

```bash
docker compose -f docker/docker-compose.yml build
```

> Der erste Build dauert **2–10 Minuten**, da auto-sklearn C/C++ Erweiterungen kompiliert (SMAC3, pyrfr). Nachfolgende Builds erfolgen sofort, sofern sich die `requirements.txt` nicht ändert.

### Skripte im Container ausführen

```bash
# Alles (Standardbefehl) — Daten abrufen, H2O AutoML starten, dann Auto-sklearn starten
docker compose -f docker/docker-compose.yml up

# Aktuelle BA-Daten abrufen
docker compose -f docker/docker-compose.yml run --rm deepwork python -m packages.fetch_data

# H2O AutoML Vorhersage
docker compose -f docker/docker-compose.yml run --rm deepwork python -m packages.automl

# Auto-sklearn Vorhersage
docker compose -f docker/docker-compose.yml run --rm deepwork python -m packages.autosklearn

# Unit-Tests ausführen
docker compose -f docker/docker-compose.yml run --rm deepwork pytest tests/
```

### Gängige Docker-Befehle

```bash
# Container starten und alle Skripte nacheinander ausführen (Ausgabe im Terminal)
docker compose -f docker/docker-compose.yml up

# Container im Hintergrund starten (Detached-Modus)
docker compose -f docker/docker-compose.yml up -d

# Container stoppen und entfernen (inkl. Netzwerk)
docker compose -f docker/docker-compose.yml down

# Container stoppen und das erstellte Image komplett entfernen (nützlich für sauberen Rebuild)
docker compose -f docker/docker-compose.yml down --rmi all

# Gestoppte Container erzwingend entfernen
docker compose -f docker/docker-compose.yml rm -f
```

### Funktionsweise

- Das Projektverzeichnis wird per **Bind-Mount** in den Container unter `/app` eingebunden.  
  Jede Änderung an `.py`-Dateien oder CSV-Daten auf dem Host ist sofort im Container sichtbar – kein Rebuild erforderlich.
- Der Container nutzt **Python 3.11** und **Java 17** (OpenJDK), was die Anforderungen von auto-sklearn und H2O AutoML erfüllt.
- `PYTHONUNBUFFERED=1` stellt sicher, dass alle Print-Ausgaben in Echtzeit erscheinen.

---

## Apache Airflow Automatisierung

Wir verwenden **Apache Airflow** (ausgeführt in einer eigenen Docker-Umgebung), um die Prognose-Pipeline automatisch zu steuern und zu planen. Die standardmäßigen Airflow-Beispiele wurden deaktiviert, um die Benutzeroberfläche übersichtlich zu halten.

### Web-Oberflächen & Services Overview

Beim Starten von `docker compose -f docker/docker-compose.yml up -d` stehen folgende Web-Dienste bereit:

| Service / Oberfläche | Port / URL | Anmeldedaten / Hinweise | Beschreibung |
|---|---|---|---|
| **Streamlit Dashboard** | [`http://localhost:8501`](http://localhost:8501) | *Keine* | Interaktive Visualisierungen, Saisonalitätsanalyse, Vorhersage-Vergleich & integrierter Database Browser. |
| **Adminer (PostgreSQL UI)** | [`http://localhost:8081`](http://localhost:8081) | System: `PostgreSQL`<br>Server: `postgres`<br>Benutzer: `admin`<br>Passwort: `admin`<br>DB: `airflow` | Leichtgewichtige Web-Oberfläche zur direkten Verwaltung und Einsicht der PostgreSQL-Datenbank (`unemployment_raw`, `predictions`, `test_runs`, etc.). |
| **Airflow Web-UI** | [`http://localhost:8080`](http://localhost:8080) | Benutzer: `admin`<br>Passwort: `admin` | Orchestrierung, DAG-Monitoring & automatische Pipeline-Steuerung. |

### Airflow-Einrichtung & Ausführung

1. **Datenbank initialisieren und Admin-Benutzer erstellen (nur beim ersten Mal)**:
   ```bash
   docker compose -f docker/docker-compose.yml up airflow-init
   ```

2. **Dienste im Hintergrund starten**:
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

3. **Web-Oberflächen nutzen**:
   - **Streamlit Dashboard**: `http://localhost:8501` öffnen.
   - **Adminer DB Browser**: `http://localhost:8081` öffnen.
   - **Airflow Web UI**: `http://localhost:8080` öffnen.

4. **DAG Überprüfen und Ausführen**:
   - Den DAG `unemployment_forecast` auswählen.
   - Den DAG-Schalter auf **ON** stellen und auf **Trigger DAG** klicken, um die Pipeline manuell zu starten.
   - Der DAG ist so geplant, dass er monatlich vom 26. bis zum 31. täglich läuft. Ein `ShortCircuitOperator` stellt jedoch sicher, dass die Vorhersage-Pipeline genau einmal pro Monat ausgeführt wird – und zwar am letzten Werktag des Monats. Liegen an diesem Tag keine neuen Werte vor, bricht der Durchlauf ab und prüft erst im nächsten Monat wieder.
   - Die Pipeline führt drei Schritte nacheinander über den Docker-Socket des Host-Systems im Container `docker-deepwork:latest` aus: `fetch_data` -> `automl_forecast` -> `autosklearn_forecast`.

5. **Dienste stoppen**:
   ```bash
   docker compose -f docker/docker-compose.yml down
   ```

6. **Dienste neu starten (Restart)**:
   ```bash
   docker compose -f docker/docker-compose.yml down
   docker compose -f docker/docker-compose.yml up -d
   ```



### Lokale IDE-Unterstützung (Optional)

Falls der lokale Editor (z. B. VS Code oder PyCharm) Import-Fehlermeldungen für `airflow` oder `docker` in `unemployment_forecast_dag.py` anzeigt, da diese Bibliotheken nur im Docker-Container vorinstalliert sind, können die Entwicklungs-Abhängigkeiten lokal auf dem Host-System installiert werden. Dies stellt die Autovervollständigung und Typprüfung auf dem Mac wieder her:
```bash
pip install apache-airflow apache-airflow-providers-docker
```

---

## Ausführung

### 1. Aktuelle Daten von der BA abrufen

```bash
python3 -m packages.fetch_data
```

### 2. H2O AutoML Vorhersage ausführen

```bash
python3 -m packages.automl
```

### 3. Auto-sklearn Vorhersage ausführen

```bash
python3 -m packages.autosklearn
```

---

## Projektstruktur

```text
DeepWorkInsights/
├── airflow/                            # Airflow Orchestrierung & Docker-Compose Stack
│   ├── dags/                           # DAGs für automatische Pipelines
│   │   └── unemployment_forecast_dag.py
│   ├── logs/                           # Airflow Ausführungsprotokolle
│   ├── plugins/                        # Benutzerdefinierte Airflow-Plugins
│   └── docker-compose.yml              # Gesamter Stack (Airflow, Postgres, Streamlit, Adminer)
├── docker/                             # Core AutoML & Web UI Docker-Setup
│   ├── Dockerfile                      # Python 3.11 + Java 17 + swig Image (ML-Engine)
│   ├── Dockerfile.streamlit            # Streamlit Dashboard Container-Image
│   ├── docker-compose.yml              # Pipeline Service-Definition
│   └── requirements.txt                # Fixierte Python-Abhängigkeiten
├── docs/                               # Dokumentation
│   └── DE.md                           # Deutsche Dokumentation
├── packages/                           # Python-Hauptpakete & ML-Pipelines
│   ├── __init__.py
│   ├── common.py                       # DB-Verbindung, Feature Engineering, Logging
│   ├── fetch_data.py                   # BA Daten-Scraper & Database Updater
│   ├── automl.py                       # H2O AutoML Vorhersage-Pipeline
│   ├── autosklearn.py                  # Auto-sklearn Vorhersage-Pipeline
│   ├── dashboard_data.py               # Dashboard-Datenabfragen & DAG-Status-Abfrage
│   ├── monitoring_data.py              # Docker-Statistiken, Log-Parser & Monitoring-Daten
│   ├── translations.py                 # Zentrales DE/EN Übersetzungsmodul
│   └── model_selection.py              # Modell-Evaluierung & Auswahl
├── streamlit/                          # Web UI Dashboard App (Port 8501)
│   ├── .streamlit/                     # Streamlit-Theme & Konfiguration
│   ├── app_pages/
│   │   ├── dashboard.py                # Saisonalität & Vorhersage-Visualisierung
│   │   └── monitoring.py               # Database Browser, Docker Logs & Benchmarks
│   ├── ui/                             # Modulare UI-Komponenten & Abhängigkeiten
│   │   ├── __init__.py                 # Paket-Exporte für UI-Komponenten
│   │   ├── charts.py                   # Plotly-Diagramme (Verlauf, Saisonalität, Fehler, YoY)
│   │   ├── kpi_cards.py                # KPI-Metrikkarten für Ist-Werte & Prognosen
│   │   ├── navbar.py                   # Navigation-Bar & Tab-/Sprachumschaltung
│   │   ├── scroll_persister.py         # Skript zur Scroll-Positions-Persistenz
│   │   ├── state_persister.py          # Custom Component v2 browser localStorage Sync
│   │   ├── styles.py                   # Globale CSS-Styles & Sichtbarkeitsregeln
│   │   └── tables.py                   # Datensatz-Tabellen & Datenbank-Browser-Fragment
│   ├── Dockerfile                      # Dockerfile für Dashboard Container
│   └── streamlit_app.py                # Haupt-Einstiegspunkt der Dashboard-App
├── tests/                              # Automatische Testsuite (pytest)
│   ├── test_common.py                  # Tests für Hilfsfunktionen
│   ├── test_fetch_data.py              # Tests für Datenabruf
│   ├── test_model_selection.py         # Tests für Modellauswahl
│   └── test_streamlit_views.py         # Tests für Dashboard-Ansichten
├── files/                              # Exportierte Berichte und CSV-Dateien
├── conftest.py                         # pytest Konfiguration
├── setup.py                            # Python-Paketverwaltung
├── README.md                           # Englische Hauptdokumentation
└── LICENSE
```

---

## 🗄️ Datenbank-Schema & Airflow DAG-Orchestrierung

### PostgreSQL Datenbank-Schema

PostgreSQL dient als Single Source of Truth für historische Arbeitslosendaten, aktive Vorhersagen, Evaluierungsläufe und Testberichte:

| Tabellenname | Beschreibung | Hauptspalten |
| :--- | :--- | :--- |
| `unemployment_raw` | Historische monatliche BA-Arbeitslosendaten | `year` (int), `month` (str), `unemployment` (bigint) |
| `predictions` | Freigegebene Gewinner-Prognosen (AutoML & Auto-sklearn) | `id` (PK), `run_timestamp`, `target_date`, `framework`, `predicted_unemployment`, `model_name`, `r2_score`, `rmse` |
| `test_runs` | Aktive Modell-Evaluierungsläufe (bis zu 5 pro Framework/Tag) | `id` (PK), `run_timestamp`, `framework`, `model_name`, `r2_score`, `rmse`, `status` |
| `test_runs_archive` | Historisches Archiv aller vergangenen Modell-Testläufe | `id` (PK), `run_timestamp`, `framework`, `model_name`, `r2_score`, `rmse`, `archived_at` |

---

### Airflow DAG-Orchestrierung (`unemployment_forecast`)

Der Airflow-DAG (`airflow/dags/unemployment_forecast_dag.py`) läuft 5-mal täglich (`0 0,5,10,15,20 * * *`), um die gesamte Forecasting-Pipeline vollautomatisch auszuführen:

```mermaid
graph LR
    A[fetch_data] -->|skip_on_exit_code=10| B[automl_forecast]
    B --> C[autosklearn_forecast]
    C --> D[promote_best_models]
```

1. **`fetch_data`** (`DockerOperator`): Lädt aktuelle BA-Excel-Daten herunter, prüft Wertebereiche sowie Timeline-Lücken und aktualisiert `unemployment_raw`. Gibt Exit-Code 10 zurück, falls Daten bereits aktuell sind.
2. **`automl_forecast`** (`DockerOperator`): Generiert Lag-Features, trainiert **H2O AutoML**-Modelle und protokolliert Testläufe in `test_runs`.
3. **`autosklearn_forecast`** (`DockerOperator`): Trainiert **Auto-sklearn**-Modelle und protokolliert Evaluierungsmetriken in `test_runs`.
4. **`promote_best_models`** (`DockerOperator`): Bewertet die Testläufe ($R^2$ / RMSE), promoviert die Gewinner-Modelle in `predictions` und archiviert Berichte in `test_runs_archive`.

---

## Daten-Pipeline

1. Herunterladen der aktuellen BA Excel-Datei.
2. Extrahieren der monatlichen Werte für Deutschland aus dem Blatt `Tabelle 2.1.2`.
3. Zusammenführen mit bestehenden CSV-Daten, ohne bereits ausgefüllte Werte zu überschreiben.
4. Speichern einer vollständigen monatlichen Zeitreihe ab 2005.

---

## H2O AutoML Vorhersage

`automl_forecast.py` sagt die Arbeitslosenzahl für den aktuellen Kalendermonat mittels **H2O AutoML** voraus. Dabei werden automatisch verschiedene Modelltypen trainiert und verglichen (GBM, XGBoost, Random Forest, Deep Learning, Stacked Ensembles).

### Verwendete Features

| Feature         | Beschreibung                                           |
|-----------------|--------------------------------------------------------|
| `TimeIndex`     | Linearer Trend-Zähler (Zeile 1 = älteste, Zeile N = neueste) |
| `Month_sin/cos` | Zyklische Monatskodierung – Dezember und Januar bleiben benachbart |
| `Lag1/2/3/6`      | Arbeitslosenzahlen der vorangegangenen 1–6 Monate      |
| `Lag12`         | Gleicher Monat im Vorjahr                              |
| `Rolling3/6`    | Gleitender Durchschnitt über 3 und 6 Monate            |
| `MoM_Change`    | Veränderung zum Vormonat (Momentum)                    |
| `YoY_Change`    | Veränderung zum Vorjahresmonat (Momentum)              |

### Trainingsreihenfolge

H2O AutoML trainiert Modelle in dieser Sequenz:

1. **GLM** – schnelle lineare Baseline
2. **GBM** – mehrere Gradient Boosting Varianten mit unterschiedlichen Hyperparametern
3. **XGBoost** – Extreme Gradient Boosting Varianten
4. **DRF + XRT** – Random Forest und Extremely Randomized Trees
5. **Deep Learning** – Feed-Forward neuronale Netze
6. **Stacked Ensembles** – zum Schluss trainiert, kombiniert alle vorherigen Modelle

Das Leaderboard wird nach **RMSE** sortiert (niedrigster Wert = am besten). In der Praxis gewinnen meist `StackedEnsemble_AllModels` oder `StackedEnsemble_BestOfFamily`.

### Historie & PostgreSQL-Persistierung

Jeder Durchlauf speichert seine Vorhersage und Evaluierungsmetriken direkt in der PostgreSQL-Datenbank (Tabellen `test_runs` und `predictions`). Bei nachfolgenden Durchläufen werden diese vergangenen Vorhersagen dynamisch als Trainingsdaten zurückgeführt, um Lücken zu überbrücken, bis die offiziellen BA-Daten für diese Monate verfügbar sind.

### Beispiel-Ausgabe

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

## Auto-sklearn Vorhersage

`packages/autosklearn.py` sagt die Arbeitslosenzahl für den aktuellen Kalendermonat mittels **Auto-sklearn** voraus, einer Python-nativen AutoML-Bibliothek, die auf scikit-learn aufbaut. Sie durchsucht automatisch dutzende Algorithmen und Hyperparameter-Konfigurationen und kombiniert die besten zu einem gewichteten Ensemble.

### Enthaltene Modelle

| Kategorie           | Modelle                                                    |
|--------------------|-----------------------------------------------------------|
| **Linear**         | Ridge, Lasso, ElasticNet, SGD                             |
| **Baumbasiert**     | Random Forest, Extra Trees, GBM, AdaBoost, Decision Tree  |
| **Support Vector** | SVR                                                       |
| **Neuronale Netze** | MLP (Multi-layer Perceptron)                              |
| **Nachbarschaft**   | K-Nearest Neighbors                                       |
| **Gauß-Prozesse**   | Gaussian Process                                          |

Eine **Polynomiale Regression (Grad 2)** Baseline ist neben dem Ensemble immer enthalten:

```
PolynomialFeatures(degree=2) → StandardScaler → LinearRegression
```

Zusätzlich werden mehrere explizite scikit-learn Modelle (wie `DecisionTreeRegressor`, `KNeighborsRegressor`, `SVR` und `SGDRegressor`) als transparente Baselines evaluiert. Skalierungssensitive Modelle werden automatisch in einer `StandardScaler`-Pipeline gekapselt.

### Historie & PostgreSQL-Persistierung

Jeder Durchlauf speichert seine Vorhersage und Evaluierungsmetriken direkt in der PostgreSQL-Datenbank (Tabellen `test_runs` und `predictions`). Bei nachfolgenden Durchläufen werden diese vergangenen Vorhersagen dynamisch als Trainingsdaten zurückgeführt, um Lücken zu überbrücken, bis die offiziellen BA-Daten für diese Monate verfügbar sind.

### Hinweis zur Python-Version

Auto-sklearn erfordert **Python 3.8–3.10** (lokal). Wenn Ihr System Python 3.11+ verwendet, nutzen Sie Docker oder `pyenv`/`conda`:

```bash
conda create -n deepwork python=3.10
conda activate deepwork
pip install auto-sklearn scikit-learn pandas numpy
python -m packages.autosklearn
```

### Beispiel-Ausgabe

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

> **Hinweis:** Der `MLPRegressor` erzeugte in diesem Durchlauf ein negatives R² (–66,90 %) und wurde ausgeschlossen.
> Ein negatives R² bedeutet, dass das Modell schlechter abschneidet als eine einfache Durchschnittsvorhersage – dies wird typischerweise durch unzureichende Trainingsdaten für neuronale Netze oder fehlende Hyperparameter-Optimierung verursacht.

---

## Vorhersage-Vergleich (Mai 2026)

| Metrik | H2O AutoML | Auto-sklearn |
|---|---|---|
| **Prognose Mai 2026** | **3.020.577** | **2.831.281** |
| **Bestes Modell** | `StackedEnsemble` | `RandomForestRegressor` |
| **R² Score** | `98,82 %` | `87,29 %` |
| **RMSE** | `55.953` | `75.280` |
| **MAE** | `38.767` | `65.820` |

---

## Changelog

### v1.4
#### 🔄 Intelligentes Auto-Refresh: Datengesteuerte Aktualisierungen für Dashboard & Monitoring
- **Dashboard — Änderungserkennungs-Watcher** (`streamlit/app_pages/dashboard.py`):
  - `_dashboard_change_watcher`: unsichtbares `@st.fragment(run_every="60s")`, das alle 60s neue Vorhersage- oder Testlauf-Zeitstempel in PostgreSQL prüft. Löst `st.rerun()` nur bei erkannter Änderung aus — die Dashboard-Seite bleibt ansonsten vollständig statisch.
- **Docker Monitor** (`streamlit/app_pages/monitoring.py`):
  - `render_docker_monitor` läuft als `@st.fragment(run_every="30s")`. Nur der Docker-Abschnitt wird alle 30s neu gerendert; der Rest der Monitoring-Seite bleibt unberührt.
- **Airflow Monitor** (`streamlit/app_pages/monitoring.py`):
  - `render_airflow_monitor` läuft als `@st.fragment(run_every="30s")`. Nur der Airflow-Abschnitt wird alle 30s neu gerendert. Buttons (Ausführen, Stoppen, Pausieren) und Toast-Benachrichtigungen funktionieren korrekt innerhalb des Fragment-Scopes.
- **Log-Viewer** (`streamlit/app_pages/monitoring.py`):
  - `render_log_viewer` läuft als `@st.fragment(run_every="30s")`, da Container-Logs fortlaufend erzeugt werden und immer neu sind.
- **Scroll-Positions-Guard** (`streamlit/ui/scroll_persister.py`):
  - Neue Funktion `render_fragment_scroll_guard(key)`, die am Anfang jedes `run_every`-Fragments injiziert wird. Speichert die aktuelle Scroll-Position in `sessionStorage` und stellt sie über einen `MutationObserver` wieder her, nachdem Streamlit den Fragment-DOM gepatcht hat — verhindert, dass die Seite bei jedem Auto-Refresh-Tick nach oben springt.
- **Speicher-Fix** (`streamlit/app_pages/monitoring.py`):
  - Plotly-Figuren-Caching aus `session_state` entfernt (`fig_perf`, `fig_dur`, `fig_log`), das mit jedem Fragment-Rerun wuchs und Browser-Speicherdruck-Neuladen verursachte.
- **Stabiler Daten-Cache** (`packages/dashboard_data.py`):
  - Cache-TTL von `load_dashboard_data` von `5s` auf `55s` erhöht, um redundante Datenbankabfragen zwischen Poll-Zyklen zu vermeiden.

### v1.3
#### 🇩🇪 Deutsche Lokalisierung & sprachbewusste Formatierer
- **Eigenes Formatierer-Modul** (`streamlit/ui/formatters.py`):
  - Neues Modul mit sprachsensitiven Formatierungsfunktionen für Zahlen (`format_number`) und Prozentwerte (`format_percent`), das je nach aktiver Sprachauswahl zwischen deutschem (Punkt als Tausendertrennzeichen, Komma als Dezimaltrennzeichen) und englischem Format umschaltet.
- **Vollständige Dashboard- & Monitoring-Lokalisierung** (`streamlit/app_pages/dashboard.py`, `streamlit/app_pages/monitoring.py`, `streamlit/ui/tables.py`):
  - Lokalisierung aller Metric-Card-Titel, KPI-Beschriftungen, Plotly-Chart-Achsentitel, Tooltips, Tabellenspalten-Köpfe und Log-Inspektions-Steuerungen basierend auf dem aktiven EN/DE-Sprachumschalter.
- **Modul-Dokumentation**:
  - Ergänzung umfassender Modul-Docstrings und Inline-Dokumentation in allen Backend-Paketen (`packages/automl.py`, `packages/autosklearn.py`, `packages/common.py`, `packages/dashboard_data.py`, `packages/fetch_data.py`, `packages/model_selection.py`, `packages/monitoring_data.py`) und Streamlit-UI-Modulen.

#### 🗄️ Automatisierte Testlauf-Archivierung & Datensatz-Limitierung
- **Konfigurierbares Datensatz-Limit** (`packages/model_selection.py`, `packages/common.py`):
  - `archive_test_runs` erzwingt jetzt ein konfigurierbares Maximum von 5 aktiven Testlauf-Einträgen pro Framework pro Tag und archiviert automatisch die ältesten überschüssigen Einträge in `test_runs_archive`.
  - Die Archivierung wird automatisch nach jedem Vorhersage-Lauf ausgelöst und hält `test_runs` schlank, um unbegrenztes Wachstum zu verhindern.
- **Erweiterte Test-Suite** (`tests/test_model_selection.py`, `tests/test_streamlit_views.py`):
  - Hinzufügen umfassender Unit-Tests für die Limit-Durchsetzungslogik, Archivierungs-Trigger, Randbedingungen und Framework-Isolation.

### v1.2
#### 📖 PostgreSQL-Datenbankschema & Airflow DAG-Dokumentation
- **Architektur-Dokumentation** (`README.md`, `docs/DE.md`):
  - Ergänzung einer umfassenden Beschreibung des PostgreSQL-Datenbankschemas für alle vier Tabellen: `unemployment_raw`, `predictions`, `test_runs` und `test_runs_archive`.
  - Ergänzung eines Airflow DAG-Abschnitts mit Ausführungsplan, ShortCircuitOperator-Ablaufsteuerung und Pipeline-Schritten (`fetch_data` → `automl_forecast` → `autosklearn_forecast`).
  - Entfernung aller veralteten v1.0-CSV-Referenzen (`files/automl_predictions.csv`, `files/autosklearn_predictions.csv`, `files/unified_predictions.md`) zugunsten von PostgreSQL als Single Source of Truth.

#### 🎨 Sequenzielles vertikales UI-Layout & Scroll-Persistenz
- **Sequenzielles vertikales Layout** (`streamlit/ui/tables.py`):
  - Ersatz der horizontalen Tab-Navigation für Datenbanktabellen und Ausführungs-Logs durch eine übersichtliche, sequenzielle vertikale Ansicht für bessere Lesbarkeit.
- **Erweiterte Scroll-Persistenz** (`streamlit/ui/scroll_persister.py`):
  - Überarbeitung der Scroll-Persistenz-Logik mit Tab-Tracking und zustandsbehafteten Callbacks zur zuverlässigen Beibehaltung exakter Scrollpositionen bei Streamlit-Reruns.

### v1.1
#### 🏛️ Zentralisierte Docker-Architektur & Ausführung
- **Zentraler Docker Compose Stack** (`docker/docker-compose.yml`):
  - Konsolidierung aller Dienste (**PostgreSQL**, **Airflow Webserver**, **Airflow Scheduler**, **Airflow Init**, **Streamlit Dashboard**, **Adminer DB UI**, **AutoML Runner**) in eine einzige zentrale Docker-Compose-Datei.
  - Vereinfachte Steuerung: `docker compose -f docker/docker-compose.yml up -d` startet das gesamte System.
- **Dedizierte Container-Images** (`docker/Dockerfile`, `docker/Dockerfile.streamlit`):
  - Saubere Trennung der schwere ML-Engine (`Python 3.11 + Java 17 + C++ Build Tools`) vom leichtgewichtigen Dashboard-Container (`Python 3.10-slim + Streamlit + Plotly`).

#### 🗄️ PostgreSQL Datenbank-Integration & Web-Management
- **PostgreSQL als Single Source of Truth**:
  - Vollständige DB-Persistierung für historische Arbeitslosendaten (`unemployment_raw`), promovierte Prognosen (`predictions`), aktive Evaluierungsläufe (`test_runs`) und historische Modell-Archive (`test_runs_archive`).
- **Adminer Database Web UI** ([`http://localhost:8081`](http://localhost:8081)):
  - Integration von Adminer zur direkten Verwaltung, SQL-Abfrage und visuellen Inspektion aller Datenbanktabellen im Browser.
- **Vereinheitlichte Anmeldedaten**:
  - Standardisierte Admin-Zugangsdaten (`admin` / `admin`) für PostgreSQL, Adminer und Airflow.

#### 📊 Streamlit Dashboard & Interaktives Monitoring
- **Backend-Datenmodule** (`packages/dashboard_data.py`, `packages/monitoring_data.py`):
  - Auslagerung von DB-Datenabfragen, DAG-Statusprüfungen, Docker-Statistiken und Log-Parsing in eigene saubere Backend-Pakete.
- **Modulares UI-Komponenten-Paket** (`streamlit/ui/`):
  - Auslagerung und saubere Strukturierung aller UI-Elemente in eigenen Modulen (`styles.py`, `scroll_persister.py`, `state_persister.py`, `navbar.py`, `kpi_cards.py`, `charts.py`, `tables.py`, `__init__.py`).
- **Browser-Status-Synchronisation** (`streamlit/ui/state_persister.py`):
  - Implementierung von `st.components.v1.html` zur Persistierung und Wiederherstellung der Sprachauswahl im `localStorage` des Browsers.
- **Optimierte Scroll- & Stale-Element-Übergänge**:
  - Nahtloser Tab-Wechsel ohne Aufblitzen alter Elemente durch gezielte Steuerung der Element-Sichtbarkeit (`display: none !important`).
- **Dynamische Saisonalitätsanalyse** (`streamlit/app_pages/dashboard.py`):
  - Automatische Berechnung und Anzeige dynamischer Jahresspannen (z. B. `2005 - 2025 vs. Aktuelles Jahr 2026`; schaltet in zukünftigen Jahren wie 2027 automatisch auf `2005 - 2026 vs. Aktuelles Jahr 2027` um).
- **Interaktiver Time-Filter**:
  - Schnellauswahl für Zeiträume (*All Time*, *Last 5 Years*, *Last 3 Years*, *Last 1 Year*) ohne Seiten-Reload.
- **Database & Evaluation Logs Browser** (`streamlit/app_pages/monitoring.py`):
  - Eingebauter Browser zur Live-Inspektion aller Datenbanktabellen, Modell-Bestenlisten, Docker-Container-Status und System-Logs.

#### 🧪 Umfassende pytest Test-Suite
- **10/10 Automatisierte Unit-Tests** (`tests/`):
  - `test_common.py`: Testet Feature-Engineering, Sinus/Kosinus-Transformationen, Lags, `build_target_row` und DB-Logging.
  - `test_fetch_data.py`: Testet Monats-Mapping und Excel-Parsing.
  - `test_model_selection.py`: Testet Modell-Ranking nach $R^2$/RMSE und Testlauf-Archivierung.
  - `test_streamlit_views.py`: Testet Filter-Cutoffs und Benchmark-SQL-Abfragen des Dashboards.

#### 🌐 Englischer Code- & Dokumentations-Standard
- **Vollständige Standardisierung**:
  - Alle Inline-Kommentare, Modul-Docstrings, Docker-Build-Skripte und YAML-Konfigurationen im gesamten Quellcode wurden auf professionelles Englisch umgestellt.

### v1.0
#### 🚀 Vorhersage-Engines & Features
- **H2O AutoML Integration** (`packages/automl.py`)
  - Trainiert und vergleicht diverse Modelltypen (GBM, XGBoost, Random Forest, Deep Learning, Stacked Ensembles).
  - Bietet ein detailliertes Leaderboard mit den Metriken R², RMSE und MAE.
  - Unterstützt konfigurierbare Zeitbudgets und variable Leaderboard-Größen.
  - Integriert eine Lückenüberbrückung mittels `files/automl_predictions.csv` für kontinuierliche Historien.
- **Auto-sklearn Engine** (`packages/autosklearn.py`)
  - Nutzt scikit-learn-basiertes AutoML mit gewichteter Ensemble-Bildung.
  - Implementiert eine Polynomiale Regression (Grad 2) sowie transparente Standard-Regressoren als feste Baselines.
  - Liefert ein separates Leaderboard mit R²-, RMSE- und MAE-Werten pro Modell.
  - Ermöglicht dynamische Überbrückung von Datenlücken über `files/autosklearn_predictions.csv`.
- **Zentrale Vorhersage-Utilities** (`packages/common.py`)
  - Zentralisiertes Feature-Engineering (linearer Zeitindex, zyklische Sinus-/Kosinus-Monatskodierung, Verzögerungsvariablen, gleitende Durchschnitte und Momentum).
  - Steuert die Rekonstruktion der Historie, indem vergangene Prognosen als Trainingszeilen integriert werden, wo offizielle BA-Werte noch fehlen.

#### 🐳 Containerisierung & Setup
- **Docker-Setup & Portability** (`docker/Dockerfile`, `docker/docker-compose.yml`, `docker/requirements.txt`)
  - Stellt eine einheitliche Umgebung mit Python 3.11 und OpenJDK Java 17 bereit, um H2O und Auto-sklearn betriebssystemunabhängig auszuführen.
  - Bindet das Projektverzeichnis als Live-Volume ein, sodass Codeänderungen ohne erneutes Builden sofort wirksam werden.
- **Zweisprachige Dokumentation**
  - Vollständig lokalisierte Dokumentation in Deutsch ([docs/DE.md](file:///Users/amirargani/Documents/GitHub/DeepWorkInsights/docs/DE.md)) und Englisch ([README.md](file:///Users/amirargani/Documents/GitHub/DeepWorkInsights/README.md)).

#### 📊 Berichte, Logging & Synchronisierung
- **Einheitlicher Markdown-Bericht** (`files/unified_predictions.md`)
  - Generiert nach jedem Lauf automatisch einen übersichtlichen, vertikalen Side-by-Side-Vergleich der Prognosen und Leistungsmaße (Prognose, R², RMSE, MAE).
  - Kürzt H2O AutoML-Modellnamen automatisch auf lesbare Kurzbezeichnungen für optimale Übersichtlichkeit.
- **Konsistente Log-Synchronisierung**
  - Erweitert die Funktion `save_prediction` zur dynamischen Erfassung von R² Score, RMSE und MAE.
  - Führt am Ende beider Pipelines automatisch `write_unified_outputs()` aus, wodurch `files/unified_predictions.csv` und `files/unified_predictions.md` immer synchron bleiben.
- **Dynamisches & Sicheres Logging**
  - Speichert den exakten Ausführungstag (z. B. `2026-05-18`) in der Spalte `Date`, statt standardmäßig den Monatsersten zu nehmen.
  - Bietet sicheren Überschreibschutz basierend auf Jahr und Monat, um doppelte Reihen bei mehrmaligen Testläufen zu verhindern.
  - Normalisiert Datumsangaben beim Laden intern automatisch auf den Monatsanfang, um das zeitliche Trainingsraster (`freq="MS"`) perfekt zu wahren.

#### 🛠️ Daten-Pipeline & Ausfallsicherheit
- **Automatisierter Daten-Download** (`packages/fetch_data.py`)
  - Lädt offizielle monatliche deutsche Arbeitslosenzahlen (Tabelle 2.1.2) der Bundesagentur für Arbeit (BA) herunter.
- **Robuster Netzwerk-Fallback**
  - Fängt Server-Verbindungsfehler per `try-except` ab. Ist der BA-Server offline, warnt das Skript und greift sicher auf die lokale `unemployment_germany.csv` zurück, anstatt abzustürzen.
- **Chronologische Reindizierung & Lücken-Interpolation**
  - Führt eine lückenlose monatlichen Reindizierung (`freq="MS"`) über den gesamten historischen Zeitraum durch.
  - Interpoliert eventuelle Lücken im Datenbestand automatisch linear und rundet sie auf ganze Zahlen, um korrekte Verzögerungs- und gleitende Durchschnitts-Fenster zu garantieren.

