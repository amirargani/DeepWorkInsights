"""Unit tests for BA data scraping and Excel parsing logic."""

import io
import pandas as pd
from packages.fetch_data import extract_data, MONTH_MAP


def test_month_map():
    """Verify that German month names map to correct two-digit month strings."""
    assert MONTH_MAP["Januar"] == "01"
    assert MONTH_MAP["Oktober"] == "10"
    assert MONTH_MAP["Dezember"] == "12"


def test_extract_data():
    """Verify Excel extraction logic extracts correctly formatted rows."""
    # Construct mock data for Excel Sheet Tabelle 2.1.2
    mock_rows = [
        [2026, "Januar", 3000000],
        [None, "Februar", 3100000],
        [None, "März", 2900000],
    ]
    df = pd.DataFrame(mock_rows)

    # Save to Excel bytes in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Tabelle 2.1.2", index=False, header=False)
    excel_bytes = output.getvalue()

    # Extract data
    data = extract_data(excel_bytes)

    assert data == {
        (2026, "01"): 3000000,
        (2026, "02"): 3100000,
        (2026, "03"): 2900000,
    }
