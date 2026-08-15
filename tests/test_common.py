"""Unit tests for shared common utilities, feature engineering, and database logging."""

from unittest.mock import patch
import pandas as pd
import numpy as np
import sqlalchemy as sa
from datetime import datetime
from packages.common import get_feature_columns, engineer_features, build_target_row


def test_feature_columns():
    """Verify that get_feature_columns returns a valid list of features."""
    cols = get_feature_columns()
    assert isinstance(cols, list)
    assert "Year" in cols
    assert "Month" in cols
    assert "TimeIndex" in cols
    assert "Lag1" in cols
    assert "Rolling3" in cols


def test_engineer_features():
    """Verify feature engineering outputs the expected columns and values."""
    # Create mock data with enough rows to avoid NaN issues on basic rolling/lag computations
    data = {
        "Year": [2024] * 15,
        "Month": list(range(1, 13)) + [1, 2, 3],
        "Unemployment": [2000000 + i * 10000 for i in range(15)]
    }
    df = pd.DataFrame(data)
    df_feat = engineer_features(df)

    # Basic shape checks
    assert len(df_feat) == 15
    assert "TimeIndex" in df_feat.columns
    assert "Month_sin" in df_feat.columns
    assert "Month_cos" in df_feat.columns
    assert "Lag1" in df_feat.columns
    assert "Lag2" in df_feat.columns
    assert "Lag3" in df_feat.columns
    assert "Lag6" in df_feat.columns
    assert "Lag12" in df_feat.columns
    assert "Rolling3" in df_feat.columns
    assert "Rolling6" in df_feat.columns
    assert "MoM_Change" in df_feat.columns
    assert "YoY_Change" in df_feat.columns

    # Verify lag logic
    assert df_feat["Lag1"].iloc[1] == df["Unemployment"].iloc[0]
    assert df_feat["Lag12"].iloc[12] == df["Unemployment"].iloc[0]


def test_build_target_row():
    """Verify that build_target_row constructs a single feature row for the next forecast month."""
    data = {
        "Year": [2025] * 12 + [2026] * 3,
        "Month": list(range(1, 13)) + [1, 2, 3],
        "Unemployment": [2500000 + i * 5000 for i in range(15)]
    }
    df = pd.DataFrame(data)
    df_feat = engineer_features(df)
    
    target_date = datetime(2026, 4, 1)
    target_row = build_target_row(df_feat, target_date)

    assert len(target_row) == 1
    assert target_row["Year"].iloc[0] == 2026
    assert target_row["Month"].iloc[0] == 4
    assert target_row["TimeIndex"].iloc[0] == 16
    assert target_row["Lag1"].iloc[0] == df["Unemployment"].iloc[-1]
    assert not pd.isna(target_row["Rolling3"].iloc[0])


@patch('packages.common.get_db_engine')
def test_save_prediction(mock_engine):
    """Verify save_prediction persists test run data correctly into SQLite/database."""
    test_engine = sa.create_engine("sqlite:///:memory:")
    mock_engine.return_value = test_engine

    metadata = sa.MetaData()
    test_runs = sa.Table(
        "test_runs",
        metadata,
        sa.Column("framework", sa.String(20)),
        sa.Column("year", sa.Integer),
        sa.Column("month", sa.Integer),
        sa.Column("run_timestamp", sa.DateTime),
        sa.Column("prediction", sa.Integer),
        sa.Column("model", sa.String(255)),
        sa.Column("r2", sa.Float),
        sa.Column("rmse", sa.Float),
        sa.Column("mae", sa.Float),
    )
    metadata.create_all(test_engine)

    from packages.common import save_prediction
    target_dt = datetime(2026, 8, 1)
    save_prediction(
        target_date=target_dt,
        prediction=2950000.4,
        best_model="GBM_Model_1",
        framework="automl",
        r2=96.5,
        rmse=45000.0,
        mae=32000.0,
        overwrite=False
    )

    with test_engine.connect() as conn:
        res = conn.execute(sa.text("SELECT framework, year, month, prediction, model, r2 FROM test_runs")).fetchone()
        assert res is not None
        assert res[0] == "automl"
        assert res[1] == 2026
        assert res[2] == 8
        assert res[3] == 2950000
        assert res[4] == "GBM_Model_1"
        assert res[5] == 96.5

