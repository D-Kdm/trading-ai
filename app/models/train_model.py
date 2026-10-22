"""
Trains the AI model.

The idea:
  - Each row of our data is one 5-minute candle with features
    (returns, moving averages, volatility, momentum...).
  - We ask the model: "Given these features NOW, will the NEXT candle
    close higher than this one?"  -> 1 = yes (up), 0 = no (down).
  - A Random Forest learns patterns from past candles where we already
    know the answer, then we save it to a file so the API can use it.

Run directly to train:   python -m app.models.train_model
"""
import os
from datetime import datetime
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# The columns the model looks at. Must be the same at training and prediction time.
FEATURES = ["returns", "ma_10", "ma_20", "volatility", "price_diff", "momentum"]

# Where the trained model is saved (*.pkl is ignored by git).
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")


def create_target(df):
    """Add the 'target' column: 1 if the next candle's close is higher, else 0."""
    df = df.copy()
    # shift(-1) moves the next row's close up into the current row
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
    # The last row has no "next candle", so we can't know its answer -> drop it
    return df.iloc[:-1]


def train_model(df, symbol=None):
    """Train on a feature DataFrame (from add_features), save the model, return metrics."""
    df = create_target(df)
    X = df[FEATURES]   # inputs
    y = df["target"]   # correct answers

    # Split by time, NOT randomly: train on the first 80%, test on the last 20%.
    # Random splitting would let the model "see the future", giving fake-good accuracy.
    split = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split], X.iloc[split:]
    y_train, y_test = y.iloc[:split], y.iloc[split:]

    # 100 decision trees vote together. max_depth limits how complex each tree
    # gets, which reduces overfitting (memorising noise instead of patterns).
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X_train, y_train)

    # Check how often it's right on data it has never seen.
    accuracy = accuracy_score(y_test, model.predict(X_test))

    metrics = {
        "symbol": symbol,
        "trained_at": datetime.now().strftime("%d %b %Y, %H:%M"),
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "test_accuracy": round(float(accuracy), 4),
        # Baseline: accuracy if you always guessed the more common direction.
        # The model is only useful if it beats this.
        "baseline": round(float(max(y_test.mean(), 1 - y_test.mean())), 4),
        # How much each feature helped the model decide (all add up to 1)
        "feature_importance": {
            f: round(float(v), 4) for f, v in zip(FEATURES, model.feature_importances_)
        },
    }

    # Save the model AND its stats together in one file
    joblib.dump({"model": model, "metrics": metrics}, MODEL_PATH)

    return metrics


if __name__ == "__main__":
    from app.services.market_service import get_market_data

    df, source = get_market_data("NSE:RELIANCE-EQ")
    print("Data source:", source)
    print(train_model(df, "NSE:RELIANCE-EQ"))
