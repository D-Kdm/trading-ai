# AI-Based Algorithmic Trading System 🚀

This project is an AI-powered trading system that uses live market data to generate buy/sell signals.

## Features
- Web dashboard: candlestick chart, moving averages, buy/sell markers, AI prediction
- Live stock data integration using Fyers API (falls back to demo data if not connected)
- Rule-based and ML-based trading strategies
- FastAPI-based REST API

## Tech Stack
- Python
- FastAPI
- Pandas, NumPy
- Scikit-learn

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000 for the dashboard, or http://127.0.0.1:8000/docs for the API.

## Connect live Fyers data

Add your access token to `.env`:

```
FYERS_ACCESS_TOKEN=your_token_here
```

Without it, the dashboard shows realistic **demo data** (marked with a yellow "Demo data" badge).

## Test without Fyers

```bash
python test_model.py
```
