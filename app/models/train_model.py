"""
Trains the AI models, compares them, backtests the best one, and saves it.

The question we ask:  "Given the features NOW, will the NEXT 5-min candle
close higher?"  -> target 1 = up, 0 = down.

Steps
  1. Split the data by time:  [ development 80% ][ holdout 20% ]
     The holdout is never touched until the very end - it plays the role of
     "the future" so we get an honest score.
  2. Tune LightGBM with Optuna (on development data only).
  3. Compare 5 models with WALK-FORWARD validation (train on the past, test
     on the next block, slide forward, repeat) and pick the best AUC:
       Logistic Regression | Random Forest | LightGBM | LSTM | Ensemble
  4. Score it on the holdout, and backtest it there against the rules
     strategy and plain buy & hold (with trading costs).
  5. Retrain the winner on ALL data and save it for live predictions.

Run directly:   python -m app.models.train_model
"""
import os
import re
import time
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import OPTUNA_TRIALS
from app.models.advanced import TORCH_AVAILABLE, EnsembleClassifier, LSTMClassifier, tune_lightgbm
from app.services.backtest_service import ai_positions, run_backtest
from app.services.strategy_service import generate_signal

# The columns the model looks at (all ratios / percentages - see data_service.py)
FEATURES = [
    "returns", "returns_3", "dist_ma10", "ma_spread", "volatility", "body_pct",
    "momentum_pct", "rsi_14", "macd_hist_pct", "bb_pct", "bb_width", "atr_pct", "vol_ratio",
]

MODELS_DIR = os.path.dirname(__file__)
HOLDOUT_SHARE = 0.2
CV_SPLITS = 5


def model_path(symbol):
    """One saved model per stock, e.g. app/models/NSE_RELIANCE_EQ.pkl (*.pkl is git-ignored)."""
    return os.path.join(MODELS_DIR, re.sub(r"[^A-Za-z0-9]+", "_", symbol).strip("_") + ".pkl")


ENSEMBLE = "Ensemble (soft voting)"


def base_models(X_dev, y_dev):
    """The individual models. Returns (models, LightGBM tuning info)."""
    lightgbm, tuning = tune_lightgbm(X_dev, y_dev, n_trials=OPTUNA_TRIALS)
    models = {
        # Simple straight-line model - the baseline. Needs scaled features.
        "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)),
        # Many shallow trees voting. min_samples_leaf stops it memorising noise.
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=5, min_samples_leaf=20, random_state=42, n_jobs=-1),
        # Gradient boosting: trees built one after another, each fixing the last one's mistakes
        "LightGBM (Optuna)": lightgbm,
    }
    if TORCH_AVAILABLE:
        # Neural network that reads the last 30 candles as a sequence
        models["LSTM (PyTorch)"] = LSTMClassifier()
    return models, tuning


def create_target(df):
    """Add the 'target' column: 1 if the next candle's close is higher, else 0."""
    df = df.copy()
    # shift(-1) moves the next row's close up into the current row
    df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)
    # The last row has no "next candle", so we can't know its answer -> drop it
    return df.iloc[:-1]


def score(y_true, prob):
    pred = (prob > 0.5).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y_true, pred)), 4),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        # AUC: 0.5 = coin flip, 1.0 = perfect. Doesn't depend on the 0.5 cut-off.
        "auc": round(float(roc_auc_score(y_true, prob)), 4),
    }


def walk_forward_probs(model, X, y):
    """Out-of-sample P(up) for each of CV_SPLITS train-on-past / test-on-next-block rounds."""
    # gap=1: the last training row's target peeks at the next candle, so skip one row
    folds = TimeSeriesSplit(n_splits=CV_SPLITS, gap=1).split(X)
    return [
        (test_idx, clone(model).fit(X.iloc[train_idx], y.iloc[train_idx]).predict_proba(X.iloc[test_idx])[:, 1])
        for train_idx, test_idx in folds
    ]


def average_score(y, fold_probs):
    scores = [score(y.iloc[idx], prob) for idx, prob in fold_probs]
    return {k: round(float(np.mean([s[k] for s in scores])), 4) for k in scores[0]}


def train_model(df, symbol):
    started = time.time()
    df = create_target(df)
    X, y = df[FEATURES], df["target"]

    # ---- 1. time split (one-row gap so the boundary target doesn't leak) ----
    split = int(len(df) * (1 - HOLDOUT_SHARE))
    X_dev, y_dev = X.iloc[:split - 1], y.iloc[:split - 1]
    X_hold, y_hold = X.iloc[split:], y.iloc[split:]

    # ---- 2. tune LightGBM, build the models ----
    models, tuning = base_models(X_dev, y_dev)

    # ---- 3. compare models, pick the best by walk-forward AUC ----
    fold_probs, holdout_probs = {}, {}
    for name, model in models.items():
        fold_probs[name] = walk_forward_probs(model, X_dev, y_dev)
        fitted = clone(model).fit(X_dev, y_dev)
        holdout_probs[name] = (fitted, pd.Series(fitted.predict_proba(X_hold)[:, 1], index=X_hold.index))

    # The ensemble just averages the other models' probabilities - no extra training needed
    names = list(models)
    fold_probs[ENSEMBLE] = [
        (idx, np.mean([fold_probs[n][i][1] for n in names], axis=0))
        for i, (idx, _) in enumerate(fold_probs[names[0]])
    ]
    ensemble = EnsembleClassifier(members=list(models.values()))
    ensemble.classes_, ensemble.fitted_ = np.array([0, 1]), [holdout_probs[n][0] for n in names]
    holdout_probs[ENSEMBLE] = (ensemble, sum(holdout_probs[n][1] for n in names) / len(names))

    comparison = [
        {"name": name, "cv": average_score(y_dev, fold_probs[name]), "holdout": score(y_hold, prob)}
        for name, (_, prob) in holdout_probs.items()
    ]
    best = max(comparison, key=lambda r: r["cv"]["auc"])
    best_name = best["name"]
    best_model, best_prob = holdout_probs[best_name]
    for row in comparison:
        row["best"] = row["name"] == best_name

    # ---- 4a. honest score on the holdout ----
    pred = (best_prob > 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_hold, pred, labels=[0, 1]).ravel()

    # Which features mattered? Shuffle one feature at a time and see how much AUC drops.
    imp = permutation_importance(best_model, X_hold, y_hold, scoring="roc_auc",
                                 n_repeats=5, random_state=42)
    importance = dict(sorted(
        {f: round(float(v), 4) for f, v in zip(FEATURES, imp.importances_mean)}.items(),
        key=lambda kv: kv[1], reverse=True))

    # ---- 4b. backtest on the holdout period ----
    hold_df = df.loc[X_hold.index]
    close = hold_df["close"]
    strategies = {
        "ai": ai_positions(best_prob),
        "rules": generate_signal(hold_df.copy())["signal"],
        "buy_hold": pd.Series(1, index=close.index),
    }
    backtest, curves = {}, {}
    for key, position in strategies.items():
        backtest[key], curves[key] = run_backtest(close, position)

    equity = [
        {"time": int(t), **{k: round(float(curves[k].iloc[i]), 5) for k in curves}}
        for i, t in enumerate(hold_df["timestamp"])
    ]

    # ---- 5. retrain the winner on everything and save ----
    final_model = (EnsembleClassifier(members=list(models.values())) if best_name == ENSEMBLE
                   else clone(models[best_name])).fit(X, y)

    metrics = {
        "symbol": symbol,
        "best_model": best_name,
        "trained_at": datetime.now().strftime("%d %b %Y, %H:%M"),
        "train_rows": len(X_dev),
        "test_rows": len(X_hold),
        "test_accuracy": best["holdout"]["accuracy"],
        "holdout": best["holdout"],
        # Baseline: always guess the more common direction. The model must beat this.
        "baseline": round(float(max(y_hold.mean(), 1 - y_hold.mean())), 4),
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "comparison": comparison,
        "tuning": tuning,
        "training_seconds": round(time.time() - started, 1),
        "feature_importance": importance,
    }
    bundle = {
        "model": final_model,
        "features": FEATURES,
        "metrics": metrics,
        "backtest": {"stats": backtest, "equity": equity},
    }
    joblib.dump(bundle, model_path(symbol))

    return metrics


if __name__ == "__main__":
    from app.services.market_service import get_market_data

    symbol = "NSE:RELIANCE-EQ"
    df, source = get_market_data(symbol)
    print("Data source:", source)
    m = train_model(df, symbol)
    for row in m["comparison"]:
        print(f"{row['name']:<20} CV AUC {row['cv']['auc']:.3f}   holdout acc {row['holdout']['accuracy']:.3f}"
              + ("   <- best" if row["best"] else ""))
