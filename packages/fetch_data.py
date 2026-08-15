"""Download and convert BA unemployment data into a PostgreSQL database.

This module fetches the German unemployment time-series Excel file from the
Federal Employment Agency (BA), extracts the relevant worksheet, and writes
directly to the PostgreSQL database table 'unemployment_raw'.
"""

import io
import time
import requests
import pandas as pd
from pathlib import Path
from datetime import datetime

# Direct URL to the latest BA Excel time series file (public, no login required)
SOURCE_URL = (
    "https://statistik.arbeitsagentur.de/Statistikdaten/Detail/Aktuell/"
    "iiia4/alo-zeitreihe-dwo/alo-zeitreihe-dwo-b-0-xlsx.xlsx?__blob=publicationFile"
)

# Cache file to prevent redundant downloads within a short timeframe
CACHE_FILE = Path("/tmp/.last_fetch")
# Name of the relevant worksheet inside the BA time series file
SHEET = "Tabelle 2.1.2"

# Mapping German month names to two-digit month numbers
MONTH_MAP = {
    "Januar": "01",
    "Februar": "02",
    "März": "03",
    "April": "04",
    "Mai": "05",
    "Juni": "06",
    "Juli": "07",
    "August": "08",
    "September": "09",
    "Oktober": "10",
    "November": "11",
    "Dezember": "12",
}


def download_excel() -> bytes:
    """Download the BA Excel file and return its content as raw bytes.

    :return: The Excel file content as raw bytes.
    :rtype: bytes
    :raises requests.HTTPError: If the HTTP request fails.
    """
    # A browser-like user agent is required; BA may reject generic scripted requests
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(SOURCE_URL, headers=headers, timeout=60)
        response.raise_for_status()
        return response.content
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
        # Retry with SSL verification bypass if BA server handshake fails
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(SOURCE_URL, headers=headers, timeout=60, verify=False)
        response.raise_for_status()
        return response.content


def extract_data(excel_bytes: bytes) -> dict[tuple[int, str], int]:
    """Parse the relevant worksheet and extract monthly values for Germany.

    Sheet column layout:
      Column 0 - Year (present in January row, then blank and forward-filled)
      Column 1 - Month name in German
      Column 2 - Total unemployed in Germany (stock)

    :param excel_bytes: Raw bytes of the downloaded Excel file.
    :type excel_bytes: bytes
    :return: A dictionary with (year, "MM") as key and unemployment count as value.
    :rtype: dict[tuple[int, str], int]
    """
    xl = pd.ExcelFile(io.BytesIO(excel_bytes))
    raw = xl.parse(SHEET, header=None)

    data: dict[tuple[int, str], int] = {}
    current_year = datetime.now().year
    active_year: int | None = None

    for _, row in raw.iterrows():
        year_cell = row.iloc[0]
        month_cell = row.iloc[1]
        value_cell = row.iloc[2]

        if pd.notna(year_cell):
            try:
                active_year = int(year_cell)
            except (ValueError, TypeError):
                active_year = None

        if active_year is None:
            continue
        if active_year < 2005 or active_year > current_year:
            continue

        if pd.isna(month_cell):
            continue
        month = MONTH_MAP.get(str(month_cell).strip())
        if month is None:
            continue

        if pd.isna(value_cell):
            continue
        try:
            unemployed_count = int(round(float(value_cell)))
        except (ValueError, TypeError):
            continue

        data[(active_year, month)] = unemployed_count

    return data


def load_existing_db() -> dict[tuple[int, str], int]:
    """Read existing data from database table 'unemployment_raw'.

    :return: A dictionary with (year, "MM") as key and the unemployment count.
    :rtype: dict[tuple[int, str], int]
    """
    from .common import get_db_engine
    import sqlalchemy as sa
    engine = get_db_engine()
    
    existing: dict[tuple[int, str], int] = {}
    with engine.connect() as conn:
        try:
            res = conn.execute(sa.text("SELECT year, month, unemployment FROM unemployment_raw"))
            for row in res.fetchall():
                if row[2] is not None:
                    existing[(int(row[0]), str(row[1]))] = int(row[2])
        except Exception:
            pass
    return existing


def write_to_db(data: dict[tuple[int, str], int]) -> None:
    """Write merged data to PostgreSQL database table 'unemployment_raw'.

    :param data: Dict containing year/month keys and unemployment values.
    :type data: dict
    """
    from .common import get_db_engine
    import sqlalchemy as sa
    engine = get_db_engine()
    
    with engine.connect() as conn:
        for (year, month), val in data.items():
            conn.execute(
                sa.text("DELETE FROM unemployment_raw WHERE year = :year AND month = :month"),
                {"year": year, "month": month}
            )
            conn.execute(
                sa.text("INSERT INTO unemployment_raw (year, month, unemployment) VALUES (:year, :month, :unemployment)"),
                {"year": year, "month": month, "unemployment": val}
            )
        conn.commit()


def main() -> None:
    """Main function that orchestrates downloading, merging, and saving BA data."""
    import os
    # If running inside Airflow, only check for new data between days 26 and 31
    if "AIRFLOW_CTX_DAG_ID" in os.environ:
        now_dt = datetime.now()
        if not (26 <= now_dt.day <= 31):
            print(f"Today is day {now_dt.day}. Skipping BA download inside Airflow (active only from 26 to 31).")
            import sys
            sys.exit(10)

    # Check if we recently fetched data (within the last 10 minutes)
    if CACHE_FILE.exists():
        if time.time() - CACHE_FILE.stat().st_mtime < 600:
            return

    # Update cache file timestamp
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.touch()

    print("Downloading BA data series ...")
    try:
        excel_bytes = download_excel()
    except Exception as exc:
        print(f"  [WARNING] BA download skipped ({exc.__class__.__name__}). Using existing database records.")
        return

    print("Parsing downloaded Excel file ...")
    new_data = extract_data(excel_bytes)
    print(f"  Extracted {len(new_data)} data point(s) from Excel file.")

    print("Reading existing database records ...")
    existing_data = load_existing_db()

    # Check if there are any new values or changes in existing data points
    has_changes = False
    for key, val in new_data.items():
        if key not in existing_data or existing_data[key] != val:
            has_changes = True
            break

    if not has_changes:
        # Exit with status 10 to signal "no new data" to caller
        print(f"No new data. Database table 'unemployment_raw' remains unchanged ({len(existing_data)} records)")
        import sys
        sys.exit(10)

    # Merge: keep old values but overwrite/update with new Excel values
    merged: dict[tuple[int, str], int] = {}
    merged.update(existing_data)
    merged.update(new_data)

    print("Saving merged dataset to database table 'unemployment_raw' ...")
    write_to_db(merged)
    print(f"Database successfully updated: 'unemployment_raw' table ({len(merged)} records)")


if __name__ == "__main__":
    main()
