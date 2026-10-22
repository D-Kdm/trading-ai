from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from app.services.fyers_auth import exchange_auth_code, login_url
from app.services.fyers_service import FyersError
from app.services.market_service import clear_cache, get_market_data
from app.services.strategy_service import generate_signal
from app.services.model_service import predict_latest, get_model_info
from app.models.train_model import train_model

router = APIRouter()

DEFAULT_SYMBOL = "NSE:RELIANCE-EQ"


@router.get("/features")
def get_features(symbol: str = DEFAULT_SYMBOL):
    df, _ = get_market_data(symbol)
    return df.tail(10).to_dict()


@router.get("/signal")
def get_signal(symbol: str = DEFAULT_SYMBOL):
    df, _ = get_market_data(symbol)
    df = generate_signal(df)
    latest = df.iloc[-1]

    return {
        "signal": int(latest['signal']),
        "close": float(latest['close'])
    }


@router.post("/train")
def train(symbol: str = DEFAULT_SYMBOL):
    # Fetch data -> build features -> compare models, backtest, save the best
    df, _ = get_market_data(symbol)
    return train_model(df, symbol)


@router.get("/predict")
def predict(symbol: str = DEFAULT_SYMBOL):
    # Fetch latest data -> build features -> ask this stock's trained model
    df, _ = get_market_data(symbol)
    try:
        return predict_latest(df, symbol)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/backtest")
def backtest(symbol: str = DEFAULT_SYMBOL):
    # Results of the backtest run during the last training
    info = get_model_info(symbol)
    if info is None:
        raise HTTPException(status_code=400, detail=f"No model for {symbol} yet. Call /train first.")
    return info["backtest"]


@router.get("/fyers/login")
def fyers_login():
    # Step 1 of the daily Fyers login: send the browser to Fyers
    try:
        return RedirectResponse(login_url())
    except FyersError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fyers/callback")
def fyers_callback(auth_code: str = None, s: str = None, message: str = None):
    # Step 2: Fyers sends the browser back here with a one-time auth_code
    if s != "ok" or not auth_code:
        raise HTTPException(status_code=400, detail=f"Fyers login failed: {message or s or 'no auth_code'}")
    try:
        exchange_auth_code(auth_code)
    except FyersError as e:
        raise HTTPException(status_code=400, detail=str(e))
    clear_cache()                      # drop demo data so live data loads now
    return RedirectResponse("/?connected=1")


@router.get("/api/dashboard")
def dashboard(symbol: str = DEFAULT_SYMBOL):
    """Everything the web dashboard needs, in one request."""
    df, source = get_market_data(symbol)
    df = generate_signal(df)

    candles = [
        {
            "time": int(row.timestamp),
            "open": float(row.open), "high": float(row.high),
            "low": float(row.low), "close": float(row.close),
            "volume": float(row.volume),
            "ma_10": float(row.ma_10), "ma_20": float(row.ma_20),
            "bb_upper": float(row.bb_upper), "bb_lower": float(row.bb_lower),
            "rsi": float(row.rsi_14), "macd_hist": float(row.macd_hist),
            "returns": float(row.returns), "volatility": float(row.volatility),
            "signal": int(row.signal),
        }
        for row in df.itertuples()
    ]

    try:
        ai = predict_latest(df, symbol)
    except FileNotFoundError:
        ai = None   # model not trained yet - the dashboard shows a "Train" prompt

    return {
        "symbol": symbol,
        "source": source,
        "candles": candles,
        "ai": ai,
        "model": get_model_info(symbol),
    }
