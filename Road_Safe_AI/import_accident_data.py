import sqlite3
import pandas as pd

DATABASE = "roadsafe.db"
CSV_FILE = "roadsafe_station_accidents_2023.csv"


def import_accident_data():
    # Read the cleaned 2023 police-station dataset.
    df = pd.read_csv(CSV_FILE)

    required_columns = [
        "Zone",
        "Sub-division",
        "Station",
        "2023 - Fatal Cases",
        "2023 - Killed People",
        "2023 - Non-Fatal",
        "2023 - Injured People",
        "2023 - Total Cases",
    ]

    # Check that all required columns exist.
    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    # Validate the accident counts.
    count_columns = required_columns[3:]

    for column in count_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="raise"
        )

    if df[count_columns].isna().any().any():
        raise ValueError("Accident counts contain missing values.")

    if (df[count_columns] < 0).any().any():
        raise ValueError("Accident counts cannot be negative.")

    # Remove summary rows, retaining station-level records.
    df["Station"] = df["Station"].astype(str).str.strip()

    df = df[
        ~df["Station"].str.lower().isin(
            ["total", "grand total"]
        )
    ].copy()

    df = df.dropna(
        subset=["Zone", "Sub-division", "Station"]
    )

    # Confirm that the dataset contains 48 station records.
    if len(df) != 48:
        raise ValueError(
            f"Expected 48 station records, found {len(df)}."
        )

    # Confirm that station totals equal fatal + non-fatal cases.
    expected_totals = (
        df["2023 - Fatal Cases"]
        + df["2023 - Non-Fatal"]
    )

    if not expected_totals.equals(df["2023 - Total Cases"]):
        raise ValueError(
            "Some station totals do not match fatal + non-fatal cases."
        )

    # Prepare records before opening the database transaction.
    records = []

    for _, row in df.iterrows():
        records.append(
            (
                str(row["Zone"]).strip(),
                str(row["Sub-division"]).strip(),
                str(row["Station"]).strip(),
                int(row["2023 - Fatal Cases"]),
                int(row["2023 - Killed People"]),
                int(row["2023 - Non-Fatal"]),
                int(row["2023 - Injured People"]),
                int(row["2023 - Total Cases"]),
            )
        )

    # Prevent duplicate station names from causing a partial import.
    station_names = [record[2].casefold() for record in records]

    if len(station_names) != len(set(station_names)):
        raise ValueError(
            "Duplicate station names found. Import cancelled."
        )

    # Import into a separate table; leave users and risk_zones unchanged.
    connection = sqlite3.connect(DATABASE)

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS station_accidents_2023 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone TEXT NOT NULL,
                subdivision TEXT NOT NULL,
                station TEXT NOT NULL UNIQUE,
                fatal_cases INTEGER NOT NULL,
                people_killed INTEGER NOT NULL,
                non_fatal_cases INTEGER NOT NULL,
                people_injured INTEGER NOT NULL,
                total_cases INTEGER NOT NULL
            )
        """)

        # Replace only the data in this dedicated table.
        connection.execute(
            "DELETE FROM station_accidents_2023"
        )

        connection.executemany("""
            INSERT INTO station_accidents_2023 (
                zone,
                subdivision,
                station,
                fatal_cases,
                people_killed,
                non_fatal_cases,
                people_injured,
                total_cases
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, records)

        connection.commit()

        print("Import successful!")
        print("Station records imported:", len(records))
        print(
            "Reported total accident cases:",
            sum(record[7] for record in records)
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    import_accident_data()