"""
Uses the trained AI model to make predictions.
"""
import os
import joblib
from app.models.train_model import FEATURES, MODEL_PATH


def load_model():
    """Load the saved {"model", "metrics"} bundle. Fails clearly if not trained yet."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model not trained yet. Call /train first.")
    return joblib.load(MODEL_PATH)


def get_model_info():
    """The stats saved at training time, or None if there is no model yet."""
    try:
        return load_model()["metrics"]
    except FileNotFoundError:
        return None


def predict_latest(df):
    """Predict whether the candle after the latest one will close higher."""
    model = load_model()["model"]
    latest = df[FEATURES].iloc[[-1]]  # double brackets keep it a 1-row DataFrame

    prediction = int(model.predict(latest)[0])
    # predict_proba gives [chance of 0 (down), chance of 1 (up)]
    prob_up = float(model.predict_proba(latest)[0][1])

    return {
        "prediction": "UP" if prediction == 1 else "DOWN",
        "probability_up": round(prob_up, 4),
        "close": float(df["close"].iloc[-1]),
    }
