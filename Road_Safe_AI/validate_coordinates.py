import csv
from pathlib import Path

file_path = Path(__file__).parent / "station_coordinates.csv"

errors = []
valid_rows = 0

with file_path.open("r", newline="", encoding="utf-8-sig") as file:
    reader = csv.DictReader(file)

    required_columns = {
        "station", "subdivision", "latitude", "longitude"
    }

    if not required_columns.issubset(reader.fieldnames or []):
        print("ERROR: CSV column names are missing or incorrect.")
        raise SystemExit(1)

    for row_number, row in enumerate(reader, start=2):
        station = (row.get("station") or "").strip()

        try:
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])

            if not (-90 <= latitude <= 90):
                raise ValueError("Latitude is outside -90 to 90.")

            if not (-180 <= longitude <= 180):
                raise ValueError("Longitude is outside -180 to 180.")

            if not station:
                raise ValueError("Station name is missing.")

            valid_rows += 1

        except (ValueError, TypeError):
            errors.append(
                f"Row {row_number} ({station or 'Unknown station'}): "
                f"invalid or missing coordinates"
            )

print(f"Rows with numeric coordinates: {valid_rows}")
print(f"Rows needing correction: {len(errors)}")

for error in errors:
    print("-", error)

print("\nNote: numeric coordinates are not necessarily geographically verified.")