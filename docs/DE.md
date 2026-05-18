# DeepWorkInsights – Deutsche Arbeitslosendaten

[![License](https://img.shields.io/badge/License-Apache_2.0-D22128?style=for-the-badge&logo=apache)](LICENSE.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/)
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

DeepWorkInsights lädt offizielle monatliche Arbeitslosendaten für Deutschland herunter, speichert diese als CSV und nutzt **zwei unabhängige AutoML-Engines** (H2O AutoML und Auto-sklearn), um die Arbeitslosenzahlen des aktuellen Monats vorherzusagen.

| | |
|---|---|
| **Datenquelle** | Bundesagentur für Arbeit (BA), offizielle Excel-Zeitreihen (Tabelle 2.1.2) |
| **Zeitraum** | Januar 2005 bis zum aktuellen Monat |
| **Quelldaten** | `files/unemployment_germany.csv` |
| **H2O Vorhersage-Output** | `files/automl_predictions.csv` |
| **Auto-sklearn Vorhersage-Output** | `files/autosklearn_predictions.csv` |
| **Zusammengeführte Vorhersagen (CSV)** | `files/unified_predictions.csv` |
| **Zusammengeführter Bericht (Markdown)** | `files/unified_predictions.md` |

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
| `Dockerfile` | Python 3.11-slim Image mit Java 17, `swig` und `build-essential` |
| `docker-compose.yml` | Service-Definition; bindet den Projektordner als Live-Volume ein |
| `requirements.txt` | Fixierte Python-Abhängigkeiten (`auto-sklearn`, `h2o`, `numpy<2`, `scikit-learn<1.5`) |

### Image erstellen (einmalig)

```bash
docker compose build
```

> Der erste Build dauert **2–10 Minuten**, da auto-sklearn C/C++ Erweiterungen kompiliert (SMAC3, pyrfr). Nachfolgende Builds erfolgen sofort, sofern sich die `requirements.txt` nicht ändert.

### Skripte im Container ausführen

```bash
# Alles (Standardbefehl) — Daten abrufen, H2O AutoML starten, dann Auto-sklearn starten
docker compose run --rm deepwork

# Aktuelle BA-Daten abrufen
docker compose run --rm deepwork python fetch_data_to_csv.py

# H2O AutoML Vorhersage
docker compose run --rm deepwork python automl_forecast.py

# Auto-sklearn Vorhersage
docker compose run --rm deepwork python autosklearn_forecast.py
```

### Gängige Docker-Befehle

```bash
# Container starten und alle Skripte nacheinander ausführen (Ausgabe im Terminal)
docker-compose up

# Container im Hintergrund starten (Detached-Modus)
docker-compose up -d

# Container stoppen und entfernen (inkl. Netzwerk)
docker-compose down

# Container stoppen und das erstellte Image komplett entfernen (nützlich für sauberen Rebuild)
docker-compose down --rmi all

# Gestoppte Container erzwingend entfernen
docker-compose rm -f
```

### Funktionsweise

- Das Projektverzeichnis wird per **Bind-Mount** in den Container unter `/app` eingebunden.  
  Jede Änderung an `.py`-Dateien oder CSV-Daten auf dem Host ist sofort im Container sichtbar – kein Rebuild erforderlich.
- Der Container nutzt **Python 3.11** und **Java 17** (OpenJDK), was die Anforderungen von auto-sklearn und H2O AutoML erfüllt.
- `PYTHONUNBUFFERED=1` stellt sicher, dass alle Print-Ausgaben in Echtzeit erscheinen.

---

## Ausführung

### 1. Aktuelle Daten von der BA abrufen

```bash
python3 fetch_data_to_csv.py
```

### 2. H2O AutoML Vorhersage ausführen

```bash
python3 automl_forecast.py
```

### 3. Auto-sklearn Vorhersage ausführen

```bash
python3 autosklearn_forecast.py
```

---

## Projektstruktur

```text
DeepWorkInsights/
├── Dockerfile                          # Python 3.11 + Java 17 + swig Image
├── docker-compose.yml                  # Docker Service-Definition (Volume Mount)
├── requirements.txt                    # Fixierte Python-Abhängigkeiten für Docker
├── fetch_data_to_csv.py                # Lädt Arbeitslosen-CSV herunter und aktualisiert sie
├── forecast_common.py                  # Gemeinsame Vorhersage-Dienstprogramme (Feature Engineering, etc.)
├── automl_forecast.py                  # H2O AutoML Vorhersage für den aktuellen Monat
├── autosklearn_forecast.py             # Auto-sklearn Vorhersage für den aktuellen Monat
├── files/
│   ├── unemployment_germany.csv            # Offizielle BA-Monatszahlen (2005–heute)
│   ├── automl_predictions.csv              # H2O AutoML Vorhersagen (Vorhersagehistorie)
│   ├── autosklearn_predictions.csv         # Auto-sklearn Vorhersagen (Vorhersagehistorie)
│   ├── unified_predictions.csv             # Kombinierte H2O- und Auto-sklearn-Vorhersagen (CSV-Format)
│   └── unified_predictions.md              # Kombinierte H2O- und Auto-sklearn-Vorhersagen (Markdown-Format)
├── docs/
│   └── DE.md                               # Deutsche Dokumentation
├── README.md
└── LICENSE
```

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

### Vorhersagehistorie & Lückenüberbrückung

Jeder Durchlauf speichert seine Vorhersage in `files/automl_predictions.csv`. Bei nachfolgenden Durchläufen werden diese vergangenen Vorhersagen vorübergehend als Trainingsdaten zurückgeführt, um Lücken zu überbrücken, bis die offiziellen Daten für diese Monate verfügbar sind.

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

`autosklearn_forecast.py` sagt die Arbeitslosenzahl für den aktuellen Kalendermonat mittels **Auto-sklearn** voraus, einer Python-nativen AutoML-Bibliothek, die auf scikit-learn aufbaut. Sie durchsucht automatisch dutzende Algorithmen und Hyperparameter-Konfigurationen und kombiniert die besten zu einem gewichteten Ensemble.

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

### Vorhersagehistorie & Lückenüberbrückung

Jeder Durchlauf speichert seine Vorhersage in `files/autosklearn_predictions.csv`. Bei nachfolgenden Durchläufen werden diese vergangenen Vorhersagen vorübergehend als Trainingszeilen integriert, um Lücken zu überbrücken, bis die offiziellen Daten für diese Monate verfügbar sind.

### Hinweis zur Python-Version

Auto-sklearn erfordert **Python 3.8–3.10** (lokal). Wenn Ihr System Python 3.11+ verwendet, nutzen Sie Docker oder `pyenv`/`conda`:

```bash
conda create -n deepwork python=3.10
conda activate deepwork
pip install auto-sklearn scikit-learn pandas numpy
python autosklearn_forecast.py
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

### v1.0
#### 🚀 Vorhersage-Engines & Features
- **H2O AutoML Integration** (`automl_forecast.py`)
  - Trainiert und vergleicht diverse Modelltypen (GBM, XGBoost, Random Forest, Deep Learning, Stacked Ensembles).
  - Bietet ein detailliertes Leaderboard mit den Metriken R², RMSE und MAE.
  - Unterstützt konfigurierbare Zeitbudgets und variable Leaderboard-Größen.
  - Integriert eine Lückenüberbrückung mittels `files/automl_predictions.csv` für kontinuierliche Historien.
- **Auto-sklearn Engine** (`autosklearn_forecast.py`)
  - Nutzt scikit-learn-basiertes AutoML mit gewichteter Ensemble-Bildung.
  - Implementiert eine Polynomiale Regression (Grad 2) sowie transparente Standard-Regressoren als feste Baselines.
  - Liefert ein separates Leaderboard mit R²-, RMSE- und MAE-Werten pro Modell.
  - Ermöglicht dynamische Überbrückung von Datenlücken über `files/autosklearn_predictions.csv`.
- **Zentrale Vorhersage-Utilities** (`forecast_common.py`)
  - Zentralisiertes Feature-Engineering (linearer Zeitindex, zyklische Sinus-/Kosinus-Monatskodierung, Verzögerungsvariablen, gleitende Durchschnitte und Momentum).
  - Steuert die Rekonstruktion der Historie, indem vergangene Prognosen als Trainingszeilen integriert werden, wo offizielle BA-Werte noch fehlen.

#### 🐳 Containerisierung & Setup
- **Docker-Setup & Portabilität** (`Dockerfile`, `docker-compose.yml`, `requirements.txt`)
  - Stellt eine einheitliche Umgebung mit Python 3.11 und OpenJDK Java 17 bereit, um H2O und Auto-sklearn betriebssystemunabhängig auszuführen.
  - Bindet das Projektverzeichnis als Live-Volume ein, sodass Codeänderungen ohne erneutes Builden sofort wirksam werden.
- **Zweisprachige Dokumentation**
  - Vollständig lokalisierte Dokumentation in Deutsch ([docs/DE.md](file:///Users/amirargani/Documents/Python/DeepWorkInsights/docs/DE.md)) und Englisch ([README.md](file:///Users/amirargani/Documents/Python/DeepWorkInsights/README.md)).

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
- **Automatisierter Daten-Download** (`fetch_data_to_csv.py`)
  - Lädt offizielle monatliche deutsche Arbeitslosenzahlen (Tabelle 2.1.2) der Bundesagentur für Arbeit (BA) herunter.
- **Robuster Netzwerk-Fallback**
  - Fängt Server-Verbindungsfehler per `try-except` ab. Ist der BA-Server offline, warnt das Skript und greift sicher auf die lokale `unemployment_germany.csv` zurück, anstatt abzustürzen.
- **Chronologische Reindizierung & Lücken-Interpolation**
  - Führt eine lückenlose monatlichen Reindizierung (`freq="MS"`) über den gesamten historischen Zeitraum durch.
  - Interpoliert eventuelle Lücken im Datenbestand automatisch linear und rundet sie auf ganze Zahlen, um korrekte Verzögerungs- und gleitende Durchschnitts-Fenster zu garantieren.

