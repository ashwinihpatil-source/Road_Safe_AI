
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

# DEMONSTRATION DATA ONLY — not real accident records.
data = {
    "hour": [
        8, 9, 17, 18, 22, 23, 7, 14, 16, 20,
        10, 11, 13, 15, 19, 21, 6, 12, 18, 22,
        7, 9, 14, 17, 20, 23, 8, 12, 16, 21
    ],
    "traffic_level": [
        3, 3, 3, 3, 2, 1, 3, 2, 3, 2,
        1, 2, 1, 2, 3, 2, 2, 1, 3, 1,
        2, 1, 2, 3, 2, 1, 3, 1, 2, 2
    ],
    "poor_visibility": [
        0, 0, 1, 1, 1, 1, 0, 0, 0, 1,
        0, 0, 0, 0, 1, 1, 0, 0, 0, 1,
        0, 0, 0, 1, 1, 1, 0, 0, 0, 1
    ],
    "risk": [
        "High", "High", "High", "High", "High",
        "Moderate", "High", "Moderate", "High",
        "High", "Low", "Low", "Low", "Moderate",
        "High", "Moderate", "Moderate", "Low",
        "High", "Moderate", "Moderate", "Low",
        "Moderate", "High", "High", "Moderate",
        "High", "Low", "Moderate", "Moderate"
    ]
}

df = pd.DataFrame(data)

features = ["hour", "traffic_level", "poor_visibility"]
X = df[features]
y = df["risk"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

model = RandomForestClassifier(
    n_estimators=100, random_state=42
)
model.fit(X_train, y_train)

predictions = model.predict(X_test)
print("Demonstration model trained.")
print("Test accuracy:", round(accuracy_score(y_test, predictions), 2))
print("IMPORTANT: This score is only for invented demo data.")

joblib.dump(model, "risk_model.pkl")
print("Model saved as risk_model.pkl")