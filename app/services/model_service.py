"""
Uses the trained AI model (one per stock) to make predictions.
"""
import os
import joblib
from config import AI_BUY_THRESHOLD, AI_SELL_THRESHOLD
from app.models.train_model import model_path


def load_bundle(symbol):
    """Load the saved {model, features, metrics, backtest} bundle for this stock."""
    path = model_path(symbol)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No model for {symbol} yet. Call /train first.")
    return joblib.load(path)


def get_model_info(symbol):
    """Metrics + backtest saved at training time, or None if not trained yet."""
    try:
        bundle = load_bundle(symbol)
    except FileNotFoundError:
        return None
    return {**bundle["metrics"], "backtest": bundle["backtest"]}


def predict_latest(df, symbol):
    """Predict whether the candle after the latest one will close higher."""
    bundle = load_bundle(symbol)
    # Give the model recent history (the LSTM reads the last 30 candles), use the last answer
    recent = df[bundle["features"]].iloc[-64:]

    # predict_proba gives [chance of 0 (down), chance of 1 (up)] for each row
    prob_up = float(bundle["model"].predict_proba(recent)[-1][1])

    # Only act when the model is confident enough (same rule as the backtest)
    if prob_up > AI_BUY_THRESHOLD:
        action = "BUY"
    elif prob_up < AI_SELL_THRESHOLD:
        action = "SELL"
    else:
        action = "HOLD"

    return {
        "prediction": "UP" if prob_up >= 0.5 else "DOWN",
        "probability_up": round(prob_up, 4),
        "action": action,
        "model": bundle["metrics"]["best_model"],
        "close": float(df["close"].iloc[-1]),
    }
