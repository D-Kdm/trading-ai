from fastapi import APIRouter
from app.services.fyers_service import fetch_historical_data
from app.services.data_service import convert_to_dataframe, add_features
from app.services.strategy_service import generate_signal

router = APIRouter()

@router.get("/features")
def get_features():
    raw = fetch_historical_data()
    df = convert_to_dataframe(raw)
    df = add_features(df)

    return df.tail(10).to_dict()

@router.get("/signal")
def get_signal():
    raw = fetch_historical_data()
    df = convert_to_dataframe(raw)
    df = add_features(df)
    df = generate_signal(df)

    latest = df.iloc[-1]

    return {
        "signal": int(latest['signal']),
        "close": float(latest['close'])
    }