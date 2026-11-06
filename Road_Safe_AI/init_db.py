import sqlite3

connection = sqlite3.connect("roadsafe.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS risk_zones (
id INTEGER PRIMARY KEY AUTOINCREMENT,
zone_name TEXT NOT NULL,
latitude REAL NOT NULL,
longitude REAL NOT NULL,
risk_level TEXT NOT NULL,
explanation TEXT
)
""")

sample_zones = [
(
"Demo Zone A",
12.9716,
77.5946,
"High",
"Illustrative demo data only; not a verified accident hotspot."
),
(
"Demo Zone B",
12.9815,
77.6050,
"Moderate",
"Illustrative demo data only; not a verified accident hotspot."
),
(
"Demo Zone C",
12.9615,
77.5840,
"Low",
"Illustrative demo data only; not a verified accident hotspot."
),
(
"Demo Zone D",
12.9900,
77.5800,
"High",
"Illustrative demo data only; not a verified accident hotspot."
)
]

cursor.executemany("""
INSERT INTO risk_zones
(zone_name, latitude, longitude, risk_level, explanation)
SELECT ?, ?, ?, ?, ?
WHERE NOT EXISTS (
    SELECT 1 FROM risk_zones
    WHERE zone_name = ?
)
""", [
    (*zone, zone[0]) for zone in sample_zones
])
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

connection.commit()
connection.close()

print("RoadSafe AI risk zones and users table are ready!")

print("RoadSafe AI sample risk zones added successfully!")
