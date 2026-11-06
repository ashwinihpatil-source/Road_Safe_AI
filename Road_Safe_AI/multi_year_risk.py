"""Combine Bengaluru Traffic Police station-wise accident files (2018-2025)
into one multi-year station risk table used by the route planner.

Recent years carry more weight. Station names differ slightly between
files (e.g. "Yelahanka" vs "Yalahanka"), so they are matched to the names
in station_coordinates.csv with an alias table plus fuzzy matching.
"""
import re
import difflib
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = BASE_DIR / "roadsafe_multi_year_risk.csv"

YEAR_WEIGHTS = {2018: 0.4, 2019: 0.45, 2020: 0.35, 2021: 0.5, 2022: 0.6,
                2023: 0.75, 2024: 0.9, 2025: 1.0}

ALIASES = {
    "yelahanka": "Yalahanka", "chikjala": "Chikkajala", "chikkajala": "Chikkajala",
    "kia": "Int. Aiport", "intairport": "Int. Aiport", "devanahalli": "Int. Aiport",
    "krpuram": "K R Puram", "highgrounds": "H.Grounds", "hgrounds": "H.Grounds",
    "wilsongarden": "W.Garden", "wgarden": "W.Garden", "ulsoorgate": "U.Gate",
    "ugate": "U.Gate", "sadashivanagar": "S.S.Nagar", "ssnagar": "S.S.Nagar",
    "kgnagar": "K G Halli", "kghalli": "K G Halli", "ksl": "K S Layout",
    "kslayout": "K S Layout", "rtnagar": "R T Nagar", "ecity": "Electronic City",
    "electroniccity": "Electronic City", "hal": "Airport", "halairport": "Airport",
    "halasur": "Halasooru", "ulsoor": "Halasooru", "bellandur": "Bellanduru",
    "hebbal": "Hebbala", "hennur": "Hennuru", "yeshwanthpur": "Yashawanthapura",
    "yeshwanthapura": "Yashawanthapura", "talaghattapura": "Thalagattapura",
    "malleshwaram": "Malleshwaram", "mico": "Micolayout", "micolayout": "Micolayout",
    "chamarajpete": "Chamarajpet",
    "bpura": "Bytarayanapura", "ftown": "Pulikeshinagar", "kswamylyt": "K S Layout",
    "ypura": "Yashawanthapura", "chickpete": "Chickpet",
}


def _key(name):
    return re.sub(r"[^a-z]", "", str(name).lower())


def _match(name, known):
    k = _key(name)
    if k in ALIASES:
        return ALIASES[k]
    keys = {_key(s): s for s in known}
    if k in keys:
        return keys[k]
    close = difflib.get_close_matches(k, keys.keys(), n=1, cutoff=0.78)
    return keys[close[0]] if close else None


def _read(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    return df


def _num(series):
    return pd.to_numeric(series.astype(str).str.replace(",", ""), errors="coerce").fillna(0)


def load_yearly_records():
    """Return long table: station_raw, year, fatal, total."""
    rows = []
    for path in sorted(DATA_DIR.glob("btp_*_station_wise.csv")):
        df = _read(path)
        for year in YEAR_WEIGHTS:
            cols = [c for c in df.columns if c.startswith(str(year))]
            if not cols:
                continue
            fatal = next((c for c in cols if "fatal" in c.lower() and "non" not in c.lower()), None)
            total = next((c for c in cols if "total" in c.lower()), None)
            if not fatal or not total:
                continue
            part = pd.DataFrame({
                "station_raw": df["Station"].astype(str).str.strip(),
                "zone": df.get("Zone", ""),
                "year": year,
                "fatal": _num(df[fatal]),
                "total": _num(df[total]),
            })
            part = part[~part["station_raw"].str.lower().str.contains("total|nan")]
            rows.append(part)
    return pd.concat(rows, ignore_index=True)


def build_multi_year_risk():
    coords = pd.read_csv(BASE_DIR / "station_coordinates.csv")
    known = coords["station"].dropna().tolist()
    records = load_yearly_records()
    records["station"] = records["station_raw"].apply(lambda s: _match(s, known))
    records = records.dropna(subset=["station"])
    records["w"] = records["year"].map(YEAR_WEIGHTS)
    records["w_fatal"] = records["fatal"] * records["w"]
    records["w_total"] = records["total"] * records["w"]

    g = records.groupby("station").agg(
        weighted_fatal=("w_fatal", "sum"), weighted_total=("w_total", "sum"),
        weight=("w", "sum"), years=("year", "nunique"),
        latest_total=("total", "last"))
    g["fatal_rate"] = g["weighted_fatal"] / g["weight"]
    g["crash_rate"] = g["weighted_total"] / g["weight"]

    # Trend: last two years vs. earlier average (rising stations get a bump).
    recent = records[records["year"] >= 2024].groupby("station")["total"].mean()
    older = records[records["year"] < 2024].groupby("station")["total"].mean()
    g["trend"] = ((recent / older).reindex(g.index).fillna(1.0)).clip(0.5, 2.0)

    score = (0.45 * g["fatal_rate"] / g["fatal_rate"].max()
             + 0.40 * g["crash_rate"] / g["crash_rate"].max()
             + 0.15 * (g["trend"] - 0.5) / 1.5) * 100
    g["risk_score"] = score.round(2)
    g["risk_category"] = pd.cut(g["risk_score"], [-1, 40, 65, 1000],
                                labels=["Lower", "Moderate", "High"]).astype(str)
    out = coords.merge(g.reset_index(), on="station", how="inner")
    out["latitude"] = pd.to_numeric(out["latitude"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["longitude"], errors="coerce")
    out = out.dropna(subset=["latitude", "longitude"])
    return out.sort_values("risk_score", ascending=False).reset_index(drop=True)


if __name__ == "__main__":
    df = build_multi_year_risk()
    df.to_csv(OUTPUT_FILE, index=False)
    print(df[["station", "years", "crash_rate", "fatal_rate", "trend", "risk_score", "risk_category"]].to_string())
    recs = load_yearly_records()
    coords = pd.read_csv(BASE_DIR / "station_coordinates.csv")["station"].tolist()
    print("Unmatched:", sorted({s for s in recs["station_raw"] if not _match(s, coords)}))
