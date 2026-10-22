# Trading AI 🚀

An AI-powered trading research platform for NSE stocks. It pulls 5-minute candles from the Fyers API, engineers technical features, makes five ML models compete under walk-forward validation, and backtests the winner against a rule-based strategy and buy & hold, all on a live web dashboard.

## Features

**Data and features**
- Live 5-minute candles from the Fyers API, cached for 60 s. If Fyers isn't connected, it falls back to realistic demo data.
- Indicators: RSI, MACD, Bollinger Bands, ATR, moving averages, momentum and volume ratio.
- The model only sees ratios and percentages, never raw prices, so what it learns still applies when the price level changes.

**Machine learning**
- Five models compete: Logistic Regression, Random Forest, **LightGBM tuned with Optuna**, an **LSTM neural network (PyTorch)** that reads the last 30 candles, and a **soft-voting ensemble**.
- **Walk-forward validation** (`TimeSeriesSplit` with a gap) means models are always trained on the past and tested on the future.
- A final **20% holdout**, never touched during model selection, gives the reported score.
- Results include accuracy, precision, recall, AUC, a confusion matrix, a naive baseline and **permutation feature importance**.
- Each stock gets its own model.

**Backtesting**
- Compares the AI strategy, the MA-crossover rules and buy & hold on the holdout period.
- There's no look-ahead bias: a decision at candle *t* only earns candle *t+1*'s return.
- Includes trading costs per position change.
- Reports total return, Sharpe ratio, max drawdown, win rate, number of trades, time in market and the equity curve.

**Dashboard**
- Candlestick chart with MA and Bollinger overlays, buy/sell markers, volume and a synced RSI panel.
- AI signal with probability, backtest equity curves, the model comparison table, the confusion matrix and the Optuna results.

## Tech stack

Python · FastAPI · pandas · NumPy · scikit-learn · LightGBM · Optuna · PyTorch · Fyers API · JavaScript · TradingView Lightweight Charts · pytest

## Project structure

```
app/
  api/routes.py               REST endpoints
  models/train_model.py       training pipeline: split, tune, compete, backtest, save
  models/advanced.py          LSTM, ensemble, LightGBM + Optuna
  services/data_service.py    indicators and features
  services/backtest_service.py
  services/market_service.py  Fyers data or demo fallback, with caching
  services/model_service.py   load models and predict
  static/                     dashboard (HTML/CSS/JS)
tests/                        unit tests
scripts/record_demo.py        records a demo video of the dashboard
```

## Setup

```bash
pip install -r requirements.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu   # optional, for the LSTM
uvicorn main:app --reload
```

Open http://127.0.0.1:8000 for the dashboard, or http://127.0.0.1:8000/docs for the API.

## Connect live Fyers data

Add your access token to `.env`:

```
FYERS_ACCESS_TOKEN=your_token_here
```

Without it, the dashboard shows realistic **demo data**, marked with a yellow "Demo data" badge.

## API

| Endpoint | Description |
|---|---|
| `GET /api/dashboard?symbol=` | Everything the dashboard needs |
| `POST /train?symbol=` | Tune, compare, backtest and save the best model |
| `GET /predict?symbol=` | AI signal for the next candle |
| `GET /backtest?symbol=` | Backtest stats and equity curves |
| `GET /signal`, `GET /features` | Rule signal / latest features |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests cover the indicators, the backtest (including a look-ahead check and cost accounting) and an end-to-end train-and-predict run.

## Honest results

On 5-minute candles, all the models land near AUC 0.50, which means they can barely tell up from down. Short-term price moves are close to random, and this project is built to measure that honestly instead of hiding it.

*Educational project, not financial advice.*
