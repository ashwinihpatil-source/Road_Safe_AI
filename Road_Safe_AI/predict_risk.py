import joblib
from pathlib import Path
import pandas as pd

# Load our trained demonstration model
model = joblib.load(Path(__file__).resolve().parent / "risk_model.pkl")

def predict_risk(hour, traffic_level, poor_visibility):
    """
    Predict a demonstration risk category.

    hour: 0-23
    traffic_level: 1 (low), 2 (medium), 3 (high)
    poor_visibility: 0 (no), 1 (yes)
    """

    if not 0 <= hour <= 23:
        raise ValueError("Hour must be between 0 and 23.")

    if traffic_level not in (1, 2, 3):
        raise ValueError("Traffic level must be 1, 2, or 3.")

    if poor_visibility not in (0, 1):
        raise ValueError("Poor Road Visibility must be 0 or 1.")

    sample = pd.DataFrame(
        [[hour, traffic_level, poor_visibility]],
        columns=["hour", "traffic_level", "poor_visibility"]
    )

    prediction = model.predict(sample)[0]
    return prediction

if __name__ == "__main__":
    result = predict_risk(
        hour=18,
        traffic_level=3,
        poor_visibility=1
    )

    print("RoadSafe AI demonstration prediction")
    print("Hour: 18 (6 PM)")
    print("Traffic level: High")
    print("Poor Road Visibility: Yes")
    print("Predicted risk:", result)
    print("Note: This is based on invented training data.")