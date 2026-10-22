from fastapi import APIRouter, HTTPException
from app.services.market_service import get_market_data
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
    # Fetch data -> build features -> train the AI model and save it
    df, _ = get_market_data(symbol)
    return train_model(df, symbol)


@router.get("/predict")
def predict(symbol: str = DEFAULT_SYMBOL):
    # Fetch latest data -> build features -> ask the trained model
    df, _ = get_market_data(symbol)
    try:
        return predict_latest(df)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
            "returns": float(row.returns), "volatility": float(row.volatility),
            "momentum": float(row.momentum),
            "signal": int(row.signal),
        }
        for row in df.itertuples()
    ]

    try:
        ai = predict_latest(df)
    except FileNotFoundError:
        ai = None   # model not trained yet - the dashboard shows a "Train" prompt

    return {
        "symbol": symbol,
        "source": source,
        "candles": candles,
        "ai": ai,
        "model": get_model_info(),
    }
