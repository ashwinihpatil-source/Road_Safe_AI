import csv
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "roadsafe_historical_risk_ranking.csv"
OUTPUT_FILE = BASE_DIR / "geocode_candidates.csv"

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Missing {INPUT_FILE.name}. Run historical_risk.py first."
    )

with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as file:
    stations = list(csv.DictReader(file))

if not stations:
    raise ValueError("No historical station records were found.")

results = []

for number, station in enumerate(stations, start=1):
    name = station["station"].strip()
    subdivision = station.get("subdivision", "").strip()
    zone = station.get("zone", "").strip()

    query = f"{name} Police Station, Bengaluru, Karnataka, India"

    print(f"[{number}/{len(stations)}] Searching: {name}")

    params = urllib.parse.urlencode({
        "q": query,
        "format": "jsonv2",
        "limit": 3,
        "countrycodes": "in",
    })

    url = f"https://nominatim.openstreetmap.org/search?{params}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "RoadSafeAI-StudentProject/1.0"
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            candidates = json.loads(
                response.read().decode("utf-8")
            )

        if not candidates:
            results.append({
                "station": name,
                "subdivision": subdivision,
                "zone": zone,
                "candidate_number": "",
                "latitude": "",
                "longitude": "",
                "matched_name": "",
                "osm_type": "",
                "review_status": "NOT FOUND",
            })
            print("  No candidates found.")

        else:
            for candidate_number, candidate in enumerate(
                candidates, start=1
            ):
                results.append({
                    "station": name,
                    "subdivision": subdivision,
                    "zone": zone,
                    "candidate_number": candidate_number,
                    "latitude": candidate.get("lat", ""),
                    "longitude": candidate.get("lon", ""),
                    "matched_name": candidate.get("display_name", ""),
                    "osm_type": candidate.get("type", ""),
                    "review_status": "VERIFY BEFORE USE",
                })

            print(f"  Saved {len(candidates)} candidate(s).")

    except Exception as error:
        results.append({
            "station": name,
            "subdivision": subdivision,
            "zone": zone,
            "candidate_number": "",
            "latitude": "",
            "longitude": "",
            "matched_name": "",
            "osm_type": "",
            "review_status": f"LOOKUP ERROR: {error}",
        })

        print(f"  Lookup error: {error}")

    # Keep requests sequential and respect the service's rate limit.
    time.sleep(1.1)

fieldnames = [
    "station",
    "subdivision",
    "zone",
    "candidate_number",
    "latitude",
    "longitude",
    "matched_name",
    "osm_type",
    "review_status",
]

with OUTPUT_FILE.open("w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(results)

print("\nLookup completed.")
print("Historical stations processed:", len(stations))
print("Candidate rows saved:", len(results))
print("Output file:", OUTPUT_FILE.name)
print("All candidate coordinates require verification.")