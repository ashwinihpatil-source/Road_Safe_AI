import sqlite3
import pandas as pd

DATABASE = "roadsafe.db"
OUTPUT_FILE = "roadsafe_historical_risk_ranking.csv"

# Read the historical accident records from the existing database.
with sqlite3.connect(DATABASE) as conn:
    df = pd.read_sql_query(
        """
        SELECT station, zone, fatal_cases, non_fatal_cases,
               total_cases, people_killed, people_injured
        FROM station_accidents_2023
        """,
        conn,
    )

if df.empty:
    raise ValueError("No station accident records were found.")

# Ensure accident-count columns contain numeric values.
columns = ["fatal_cases", "total_cases", "people_killed"]

for column in columns:
    df[column] = pd.to_numeric(df[column], errors="raise")

# Calculate a relative historical-burden score from 0 to 100.
# This is NOT a probability of a future accident.
weights = {
    "total_cases": 0.40,
    "fatal_cases": 0.35,
    "people_killed": 0.25,
}

df["historical_risk_score"] = 0.0

for column, weight in weights.items():
    maximum = df[column].max()

    if maximum > 0:
        df["historical_risk_score"] += (
            df[column] / maximum * 100 * weight
        )

df["historical_risk_score"] = df["historical_risk_score"].round(2)

def classify_risk(score):
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Moderate"
    return "Lower"

df["historical_risk_category"] = (
    df["historical_risk_score"].apply(classify_risk)
)

# Rank stations from highest to lowest historical burden.
df = df.sort_values(
    ["historical_risk_score", "total_cases"],
    ascending=[False, False],
).reset_index(drop=True)

df.insert(0, "historical_rank", range(1, len(df) + 1))

# Save the ranking to a separate CSV file.
df.to_csv(OUTPUT_FILE, index=False)

print("Historical accident-risk ranking created successfully.")
print("Stations analysed:", len(df))
print("Output file:", OUTPUT_FILE)
print()

print(
    df[
        [
            "historical_rank",
            "station",
            "total_cases",
            "fatal_cases",
            "people_killed",
            "historical_risk_score",
            "historical_risk_category",
        ]
    ].head(10).to_string(index=False)
)

print()
print("Note: Scores show relative historical accident burden,")
print("not validated predictions of future accidents.")