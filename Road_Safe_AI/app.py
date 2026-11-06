from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from pathlib import Path
import os
import pandas as pd
from datetime import datetime
from predict_risk import predict_risk
from multi_year_risk import build_multi_year_risk
from route_intelligence import analyse_routes, live_traffic_for_points

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("ROADSAFE_SECRET_KEY", "roadsafe-ai-local-demo-key-change-before-deployment")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

BASE_DIR = Path(__file__).resolve().parent
DATABASE = str(BASE_DIR / "roadsafe.db")

def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection

@app.route("/")
def home():
    return render_template("welcome.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = get_db_connection()

        try:
            user = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
        finally:
            connection.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["full_name"]
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not full_name or not email or not password:
            flash("Please fill in all fields.")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        connection = get_db_connection()

        try:
            cursor = connection.execute(
                """
                INSERT INTO users (full_name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (full_name, email, password_hash)
            )
            connection.commit()

            user_id = cursor.lastrowid

        except sqlite3.IntegrityError:
            flash("An account with this email already exists.")
            return redirect(url_for("register"))

        finally:
            connection.close()

        session["user_id"] = user_id
        session["user_name"] = full_name

        flash("Account created successfully!")
        return redirect(url_for("dashboard"))

    return render_template("register.html")



@app.route("/api/health")
def health():
    try:
        with get_db_connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return jsonify({"status": "ok", "database": "connected"})
    except sqlite3.Error:
        app.logger.exception("Health check failed")
        return jsonify({"status": "error", "database": "unavailable"}), 500


@app.route("/api/zones")
def get_zones():
    connection = get_db_connection()
    zones = connection.execute("SELECT * FROM risk_zones").fetchall()
    connection.close()
    return jsonify([dict(zone) for zone in zones])
@app.route("/api/historical-zones")
def get_historical_zones():
    try:
        df = build_multi_year_risk()
        return jsonify([{
            "zone_name": r["station"], "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]), "risk_level": r["risk_category"],
            "explanation": (f"Multi-year (2018-2025) accident risk score: {r['risk_score']}/100. "
                            f"Average crashes per year: {round(r['crash_rate'])}, "
                            f"fatal crashes per year: {round(r['fatal_rate'])}."),
        } for _, r in df.iterrows()])
    except Exception:
        app.logger.exception("Could not load historical station data")
        return jsonify({"error": "Could not load historical station data."}), 500


def _traffic_label(ratio):
    """Map freeFlow/current speed ratio to a traffic level."""
    if ratio >= 1.6:
        return "High"
    if ratio >= 1.25:
        return "Moderate"
    return "Low"


@app.route("/api/live-traffic-zones")
def live_traffic_zones():
    """Every station with its current traffic level (live TomTom data, time-of-day fallback)."""
    try:
        now = datetime.now()
        profile = _traffic_profile(now.hour, now.weekday())
        fallback = {1: 1.1, 2: 1.4, 3: 1.8}[profile["level"]]
        df = build_multi_year_risk()
        points = [(float(r["latitude"]), float(r["longitude"])) for _, r in df.iterrows()]
        flows = live_traffic_for_points(points, fallback)
        out = []
        for (_, r), (ratio, source) in zip(df.iterrows(), flows):
            level = _traffic_label(ratio)
            speed_note = ("Live traffic" if source == "live" else "Estimated traffic (time of day)")
            out.append({
                "zone_name": r["station"], "latitude": float(r["latitude"]),
                "longitude": float(r["longitude"]), "risk_level": r["risk_category"],
                "traffic_level": level, "traffic_ratio": round(float(ratio), 2),
                "traffic_source": source,
                "explanation": (f"{speed_note}: {level} traffic "
                                f"(about {round((ratio - 1) * 100)}% slower than free-flow). "
                                f"Historical accident risk: {r['risk_category']} "
                                f"(score {r['risk_score']}/100)."),
            })
        return jsonify({"updated": now.isoformat(timespec="seconds"),
                        "live": any(z["traffic_source"] == "live" for z in out),
                        "zones": out})
    except Exception:
        app.logger.exception("Could not load live traffic zones")
        return jsonify({"error": "Could not load live traffic zones."}), 500


@app.route("/api/historical-risk-summary")
def historical_risk_summary():
    try:
        ranking = pd.read_csv(BASE_DIR / "roadsafe_historical_risk_ranking.csv")
        counts = ranking["historical_risk_category"].value_counts()

        return jsonify({
            "high": int(counts.get("High", 0)),
            "moderate": int(counts.get("Moderate", 0)),
            "low": int(counts.get("Lower", 0)),
            "total": int(len(ranking))
        })

    except Exception:
        app.logger.exception("Could not load historical risk summary")
        return jsonify({"error": "Could not load historical risk summary"}), 500


@app.route("/api/station-accidents")
def get_station_accidents():
    connection = get_db_connection()

    try:
        rows = connection.execute("""
            SELECT
                zone,
                subdivision,
                station,
                fatal_cases,
                people_killed,
                non_fatal_cases,
                people_injured,
                total_cases
            FROM station_accidents_2023
            ORDER BY total_cases DESC
        """).fetchall()

        return jsonify({
"year": 2023,
"record_count": len(rows),
"total_cases": sum(row["total_cases"] or 0 for row in rows),
"fatal_cases": sum(row["fatal_cases"] or 0 for row in rows),
"non_fatal_cases": sum(row["non_fatal_cases"] or 0 for row in rows),
"people_killed": sum(row["people_killed"] or 0 for row in rows),
"people_injured": sum(row["people_injured"] or 0 for row in rows),
"top_10_stations": [
dict(row) for row in rows[:10]
],
"stations": [dict(row) for row in rows]
})


    finally:
        connection.close()





def _traffic_profile(hour, weekday, festival=False, event=False):
    """Transparent rule-based estimate; not a live traffic measurement."""
    is_weekend = weekday in (5, 6)
    if festival:
        if 5 <= hour < 12:
            level, label, reason = 3, "High", "festival travel and shopping activity"
        elif 12 <= hour < 17:
            level, label, reason = 2, "Moderate", "festival-period daytime travel"
        elif 17 <= hour < 22:
            level, label, reason = 3, "High", "festival evening travel"
        else:
            level, label, reason = 1, "Low", "late-night festival-period travel"
    elif event:
        level, label, reason = (3, "High", "scheduled event activity") if 15 <= hour < 22 else (2, "Moderate", "event-day travel")
    elif is_weekend:
        if 11 <= hour < 20:
            level, label, reason = 3, "High", "weekend shopping and leisure travel"
        elif 8 <= hour < 11 or 20 <= hour < 22:
            level, label, reason = 2, "Moderate", "weekend daytime travel"
        else:
            level, label, reason = 1, "Low", "late-night or early-morning travel"
    elif 7 <= hour < 10:
        level, label, reason = 3, "High", "morning office and college commute"
    elif 10 <= hour < 16:
        level, label, reason = 1, "Low", "afternoon working hours"
    elif 16 <= hour < 20:
        level, label, reason = 3, "High", "evening return commute"
    elif 20 <= hour < 22:
        level, label, reason = 2, "Moderate", "evening travel"
    else:
        level, label, reason = 1, "Low", "late-night or early-morning travel"
    return {"level": level, "label": label, "reason": reason,
            "multiplier": {1: 1.05, 2: 1.20, 3: 1.45}[level]}


@app.route("/api/traffic-profile")
def traffic_profile():
    try:
        now = datetime.now()
        hour = int(request.args.get("hour", now.hour))
        weekday = int(request.args.get("weekday", now.weekday()))
        festival = request.args.get("festival", "0").lower() in ("1", "true", "yes")
        event = request.args.get("event", "0").lower() in ("1", "true", "yes")
        if not 0 <= hour <= 23 or not 0 <= weekday <= 6:
            return jsonify({"error": "Hour must be 0-23 and weekday must be 0-6."}), 400
        profile = _traffic_profile(hour, weekday, festival, event)
        return jsonify({
            **profile, "hour": hour, "weekday": weekday,
            "day_type": "Weekend" if weekday >= 5 else "Weekday",
            "festival": festival, "event": event,
            "note": "Estimated from typical time/day patterns; not live sensor traffic."
        })
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid traffic profile input."}), 400


@app.route("/api/route-analysis", methods=["POST"])
def route_analysis():
    """Rank candidate routes by safety (multi-year accident data + traffic)."""
    try:
        payload = request.get_json(silent=True) or {}
        routes = payload.get("routes", [])
        if not isinstance(routes, list) or not routes or len(routes) > 8:
            return jsonify({"error": "Provide between 1 and 8 routes."}), 400
        now = datetime.now()
        hour = int(payload.get("hour", now.hour))
        weekday = int(payload.get("weekday", now.weekday()))
        if not 0 <= hour <= 23 or not 0 <= weekday <= 6:
            return jsonify({"error": "Invalid hour or weekday."}), 400
        profile = _traffic_profile(hour, weekday, bool(payload.get("festival")), bool(payload.get("event")))
        ranked = analyse_routes(routes, build_multi_year_risk(), profile["multiplier"])
        return jsonify({"routes": ranked})
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid route analysis input."}), 400
    except Exception:
        app.logger.exception("Route analysis failed")
        return jsonify({"error": "Could not analyse route options."}), 500


@app.route("/api/predict")
def predict():
    """Return a clearly labelled demonstration risk estimate."""
    try:
        now = datetime.now()
        hour = int(request.args.get("hour", now.hour))
        weekday = int(request.args.get("weekday", now.weekday()))
        poor_visibility = int(request.args.get("poor_visibility", 0))
        festival = request.args.get("festival", "0").lower() in ("1", "true", "yes")
        event = request.args.get("event", "0").lower() in ("1", "true", "yes")
        if not 0 <= hour <= 23 or not 0 <= weekday <= 6:
            return jsonify({"error": "Hour must be 0-23 and weekday must be 0-6."}), 400
        if poor_visibility not in (0, 1):
            return jsonify({"error": "Visibility must be 0 (good) or 1 (poor)."}), 400

        profile = _traffic_profile(hour, weekday, festival, event)
        risk = predict_risk(hour, profile["level"], poor_visibility)
        if poor_visibility and str(risk).lower() == "low":
            risk = "Moderate"
        date_label = now.strftime("%d %B %Y")
        return jsonify({
            "risk": str(risk), "hour": datetime.now().replace(hour=hour).strftime("%I:00 %p"),
            "date": date_label, "day": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][weekday],
            "day_type": "Weekend" if weekday >= 5 else "Weekday",
            "traffic_level": profile["level"], "traffic_estimate": profile["label"],
            "traffic_reason": profile["reason"], "poor_visibility": poor_visibility,
            "festival_period": festival, "event_day": event,
            "risk_explanation": f"Estimated {profile['label'].lower()} traffic from {profile['reason']}. Visibility is {'poor' if poor_visibility else 'good or not supplied'}.",
            "note": "Demonstration model trained on synthetic sample data. Traffic is estimated from time/day/event selections, not measured live traffic."
        })
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid prediction input."}), 400
    except Exception:
        app.logger.exception("Risk prediction failed")
        return jsonify({"error": "Risk prediction failed. Check the server log."}), 500

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.")
    return redirect(url_for("login"))
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)