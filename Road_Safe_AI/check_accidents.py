import sqlite3

connection = sqlite3.connect("roadsafe.db")
connection.row_factory = sqlite3.Row

try:
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(station_accidents_2023)")
    columns = cursor.fetchall()

    print("=== HISTORICAL ACCIDENT TABLE COLUMNS ===")
    for column in columns:
        print(column["name"], "-", column["type"])

    cursor.execute("SELECT * FROM station_accidents_2023 LIMIT 5")
    rows = cursor.fetchall()

    print("\n=== FIRST 5 HISTORICAL RECORDS ===")
    for row in rows:
        print(dict(row))

finally:
    connection.close()