# RoadSafe AI — Urban Traffic Intelligence Prototype

## What this version does
- Flask + SQLite registration, login and session-protected dashboard.
- Historical 2023 accident statistics and station-risk markers from the supplied project data.
- AI demonstration road-risk prediction using the bundled model, with time/day, festival/event and optional weather visibility inputs.
- Traffic profile API with transparent weekday/weekend/peak-hour estimates.
- Alternative route planner using OpenStreetMap Nominatim geocoding and OSRM road routes.
- Backend route analysis ranks available alternatives by estimated travel time with a time/day congestion adjustment.
- Leaflet map, GPS monitoring, simulated location and browser voice alerts.
- Backend/database health indicator.

## Run on Windows
1. Extract the ZIP into a new folder. Keep your original project unchanged.
2. Open the `RoadSafeAI` folder in VS Code.
3. Open Terminal → New Terminal.
4. Create a virtual environment: `py -m venv .venv`
5. Activate it:
   - PowerShell: `.venv\\Scripts\\Activate.ps1`
   - Command Prompt: `.venv\\Scripts\\activate.bat`
6. Install packages: `py -m pip install -r requirements.txt`
7. Start the website: `py app.py`
8. Open `http://127.0.0.1:5000`.
9. Sign in with an existing local account or register a new one.

## Route planner
Enter a starting location and destination (or enable GPS monitoring and select the current-location option). The app geocodes the places, requests alternative driving routes from OSRM, and asks Flask to rank the returned routes. The selected time/day/festival/event context is used by the backend ranking endpoint.

## Important limitations
- The bundled ML model was trained using synthetic demonstration data. Its output is not a validated accident forecast.
- Traffic conditions are estimated from time/day and optional festival/event selections. This project does not currently receive live road-speed or traffic sensor feeds.
- OSRM route duration is a routing estimate, not a live traffic ETA. The same city-wide traffic multiplier is applied to each alternative, so route ranking is mainly influenced by route duration and distance.
- Weather is retrieved from Open-Meteo only when GPS location is available and permission is granted.
- Historical station coordinates need independent geographic verification before operational use.
- Internet access is needed for map tiles, geocoding, routing and weather. Public services can have rate limits or temporary outages.
- GPS requires localhost or HTTPS and browser permission.

## Data safety
The supplied `roadsafe.db` and backup databases are retained. The original ZIP was not modified. The default local session secret is for classroom demonstration only; set `ROADSAFE_SECRET_KEY` before deployment.

## Update: multi-year data & safest-route planner
- `data/` holds the Bengaluru Traffic Police station-wise files for 2018-2025 and the Karnataka district file. `multi_year_risk.py` combines them (recent years weigh more) into station risk scores used by the map and route planner. Run `py multi_year_risk.py` to regenerate `roadsafe_multi_year_risk.csv`.
- Tap 📍 in the Starting location box to use your current location.
- Route lines on the map: dotted green = safest recommended, dotted blue = alternatives, dotted yellow = other possible paths.
- Live traffic (not shown in the UI): the TomTom key is stored in the `.env` file in this folder and loaded automatically. Keep `.env` private and do not upload it publicly.
