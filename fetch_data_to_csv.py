"""Download and convert BA unemployment data into a normalized CSV file.

This module fetches the German unemployment time-series Excel file from the
Federal Employment Agency (BA), extracts the relevant worksheet, and writes a
clean CSV suitable for model training and forecasting.
"""

import io # Used for handling in-memory byte streams when reading the downloaded Excel file
import csv # Used for reading and writing CSV files in a structured way
import requests # Used for making HTTP requests to download the Excel file from the BA website
import pandas as pd # Used for parsing the Excel file and extracting data from the relevant worksheet
from pathlib import Path # Used for handling file paths in a platform-independent way
from datetime import datetime # Used for getting the current year to determine the time range of interest
import time # Used for caching mechanism to prevent redundant downloads


# Direct URL to the latest BA Excel time series file (public, no login required)
SOURCE_URL = (
    "https://statistik.arbeitsagentur.de/Statistikdaten/Detail/Aktuell/"
    "iiia4/alo-zeitreihe-dwo/alo-zeitreihe-dwo-b-0-xlsx.xlsx?__blob=publicationFile"
)
# Output path of the generated CSV file
OUTPUT_FILE = Path("files/unemployment_germany.csv")
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


# Download the BA Excel file and return its content as raw bytes. The function makes an HTTP GET request to the specified SOURCE_URL with a browser-like user agent to avoid potential blocking by the server, and returns the content of the response as bytes for further processing. It also raises an exception if the HTTP request fails (for example due to a network error or a non-200 status code), allowing the calling code to handle such cases appropriately.
def download_excel() -> bytes:
    """Download the BA Excel file and return its content as raw bytes."""
    # A browser-like user agent is required; BA may reject generic scripted requests
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(SOURCE_URL, headers=headers, timeout=60)
    # Raise an exception for HTTP errors (for example 404 or 500)
    response.raise_for_status()
    return response.content

# Parse the relevant worksheet and extract monthly values for Germany. The function reads the Excel file from bytes, parses the specified sheet, and iterates over each row to extract the year, month, and unemployment count while applying necessary transformations and filters to build a clean dataset of monthly unemployment counts for Germany from 2005 to the current year. It handles forward-filling of years, conversion of German month names
def extract_data(excel_bytes: bytes) -> dict[tuple[int, str], int]:
    """Parse the relevant worksheet and extract monthly values for Germany.

    Sheet column layout:
      Column 0 - Year (present in January row, then blank and forward-filled)
      Column 1 - Month name in German
      Column 2 - Total unemployed in Germany (stock)

    Returns a dictionary with (year, "MM") as key and unemployment count as value.
    """
    xl = pd.ExcelFile(io.BytesIO(excel_bytes))
    raw = xl.parse(SHEET, header=None)

    data: dict[tuple[int, str], int] = {}
    current_year = datetime.now().year
    active_year: int | None = None  # Most recently seen year used for forward-fill

    for _, row in raw.iterrows(): # Iterate over each row in the parsed Excel sheet, extracting the year, month, and unemployment count while applying the necessary transformations and filters to build a clean dataset of monthly unemployment counts for Germany from 2005 to the current year.
        year_cell = row.iloc[0]
        month_cell = row.iloc[1]
        value_cell = row.iloc[2]

        # Update the active year from column 0 when available
        if pd.notna(year_cell):
            try:
                active_year = int(year_cell)
            except (ValueError, TypeError):
                active_year = None

        # Skip rows without a valid year or outside the target time range
        if active_year is None:
            continue
        if active_year < 2005 or active_year > current_year:
            continue

        # Convert month name to two-digit month; skip unknown entries
        if pd.isna(month_cell):
            continue
        month = MONTH_MAP.get(str(month_cell).strip())
        if month is None:
            continue

        # Skip missing or non-convertible numeric values
        if pd.isna(value_cell):
            continue
        try:
            unemployed_count = int(round(float(value_cell))) # Convert the value to a float first to handle cases where it may be stored as a decimal (for example "12345.0"), then round it and convert to int for consistency in the output dataset. This also allows us to handle any potential formatting issues in the source file while still extracting the numeric unemployment count as an integer.
        except (ValueError, TypeError):
            continue

        data[(active_year, month)] = unemployed_count # Store the extracted unemployment count in the data dictionary with a key of (year, month) for easy lookup later when building the full dataset for the CSV output.

    return data

# Build a complete list of rows for all months from January 2005 to December of the current year, using the provided values to fill in the unemployment counts where available. For months without an available data point (for example future months), an empty string is used to indicate missing data. This ensures that the output CSV file has a consistent structure with a row for every month in the target time range, while preserving the actual data points where they exist and leaving gaps for missing entries.
def build_full_rows(values: dict[tuple[int, str], int]) -> list[list[str]]:
    """Build a complete row list for all months from 2005 through today.

    Months without available data (for example future months) get an empty value.
    """
    current_year = datetime.now().year
    rows: list[list[str]] = []
    # Iterate over every month from January 2005 to December of the current year
    for year in range(2005, current_year + 1):
        for month in range(1, 13):
            mm = f"{month:02d}"  # Format month as two digits, for example "03"
            value = values.get((year, mm))
            # Use an empty string for months without an available data point
            rows.append([str(year), mm, "" if value is None else str(value)])
    return rows

# Load existing CSV content if the file already exists, returning a mapping of (year, month) to value. This allows us to preserve previously stored values and only fill in missing entries with new data from the source file, without overwriting any existing values that may have been manually corrected or added in a previous run. The function also handles the case where the CSV file does not exist yet (first run) by returning an empty dictionary.
def load_existing_csv() -> dict[tuple[int, str], str]:
    """Read an existing CSV file and return currently stored values.

    Returns a dictionary with (year, "MM") as key and the value string as value.
    Rows with empty values are also included (empty string).
    Returns an empty dictionary if the file does not exist.
    """
    # If no file exists yet, return an empty mapping (first run)
    if not OUTPUT_FILE.exists():
        return {}

    existing: dict[tuple[int, str], str] = {} # Initialize an empty dictionary to store existing values from the CSV file, where keys are (year, month) tuples and values are the unemployment counts as strings (including empty strings for missing values)
    with OUTPUT_FILE.open("r", newline="", encoding="utf-8-sig") as file: # Open the existing CSV file for reading with UTF-8 BOM encoding to ensure compatibility with Excel, and use csv.DictReader to read the file as a sequence of dictionaries where keys are column names
        reader = csv.DictReader(file)
        for row in reader:
            try:
                # Build key from year (int) and month (two-digit string)
                key = (int(row["Year"]), row["Month"])
                # Store value as string, including empty values
                existing[key] = row["Unemployment"]
            except (KeyError, ValueError):
                # Ignore malformed rows with missing or invalid fields
                continue
    return existing

# Write the complete dataset to a CSV file with UTF-8 BOM encoding for Excel compatibility. The output includes a header row with column names and all data rows, where missing values are represented as empty strings. The function also ensures that the output directory exists before writing the file.
def write_csv(rows: list[list[str]]) -> None:
    """Write data rows to CSV with UTF-8 BOM for Excel compatibility."""
    # Create output directory if it does not exist yet
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        # Write the header row with column names
        writer.writerow(["Year", "Month", "Unemployment"])
        # Write all data rows in a single call
        writer.writerows(rows)

# Main function that orchestrates the entire process: loading existing data, downloading and extracting new data, merging it with existing data while preserving previously stored values, and writing the updated dataset back to the CSV file. It also includes logic to determine if any new entries were added and to avoid rewriting the file if no changes were made, providing informative output to the user about the actions taken.
def main() -> None:
    # Check if we recently fetched data (within the last 10 minutes / 600 seconds)
    if CACHE_FILE.exists():
        if time.time() - CACHE_FILE.stat().st_mtime < 600:
            return

    # Update cache file timestamp
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.touch()

    # Load existing CSV content if the file already exists
    existing = load_existing_csv()

    # Download and extract the latest values from the BA source file
    excel_bytes = download_excel()
    new_values = extract_data(excel_bytes)

    # Merge strategy:
    # Fill only empty CSV entries with new values, keep existing filled values unchanged.
    merged: dict[tuple[int, str], int] = {}
    for key, new_val in new_values.items(): # Iterate over all newly extracted values from the source file
        old_val = existing.get(key, "") # Get the existing value from the CSV for this key, or an empty string if it does not exist
        if old_val == "": # Only update the merged dataset with the new value if the existing CSV entry is empty, to avoid overwriting previously stored values that may have been manually corrected or added in a previous run.
            # Use new value for previously empty entries
            merged[key] = new_val
        else: # If the existing CSV entry already has a value (non-empty), we keep it unchanged in the merged dataset, even if there is a new value from the source file. This ensures that any manual corrections or previously stored values are not overwritten by the new download, which may have changes in the source data or missing values for certain months.
            # Keep already stored value unchanged
            merged[key] = int(old_val)

    # Also keep existing values not present in the current download
    for key, old_val in existing.items(): # Iterate over all existing entries in the CSV file
        if key not in merged and old_val != "": # Only consider it for retention if it was not already included from the new download and if it has a non-empty value
            merged[key] = int(old_val) # This ensures that any previously stored values that are not present in the new download (for example due to changes in the source file) are retained in the merged dataset, as long as they were not empty.

    rows = build_full_rows(merged) # Build a complete list of rows for all months, using the merged values to fill in the unemployment counts where available, and leaving empty strings for missing data points.

    # Determine new entries:
    # Keys available in new_values that were previously empty in the existing CSV
    new_entries = [
        (y, m) # Build a list of (year, month) tuples for new entries that were added to the merged data
        for (y, m), v in new_values.items() # Iterate over all newly extracted values
        if existing.get((y, m), "") == "" and str(v) != "" # Only consider it a new entry if the new value is not empty
    ]

    # If CSV exists and no new entries were added, do not rewrite the file
    if existing and not new_entries:
        filled = sum(1 for r in rows if r[2]) # Count how many rows have a non-empty value for reporting
        print( # Inform the user that no new data was added and the CSV remains unchanged, including a count of how many rows have values for context
            f"No new data. CSV remains unchanged: {OUTPUT_FILE} "
            f"({len(rows)} rows, {filled} with values)"
        )
        return

    write_csv(rows) # Write the merged data to the CSV file, creating or updating it as needed
    filled = sum(1 for r in rows if r[2]) # Count how many rows have a non-empty value for reporting
    if existing:
        # Update case: CSV already existed and was extended with new entries
        print( # Inform the user that the CSV was updated with new entries, including a count of how many new entries were added and how many rows have values in total for context
            f"CSV updated: {OUTPUT_FILE}  "
            f"({len(new_entries)} new entries, {filled} rows with values total)"
        )
        # Print each newly added entry
        for year, month in sorted(new_entries):
            print(f"  + {year}-{month}: {merged[(year, month)]}")
    else:
        # First run: CSV has been created from scratch
        print(f"CSV created: {OUTPUT_FILE}  ({len(rows)} rows, {filled} with values)") # Inform the user that the CSV was created for the first time, including a count of how many rows were created and how many have values for context


# Run the script only when executed directly (not when imported as a module)
if __name__ == "__main__":
    main()
