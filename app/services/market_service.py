"""
One place to get market data: real Fyers data if possible, demo data otherwise.
Results are cached for a short time so the dashboard doesn't hit Fyers on every click.
"""
import time
from config import CACHE_SECONDS
from app.services.fyers_service import fetch_historical_data
from app.services.demo_service import generate_demo_response
from app.services.data_service import convert_to_dataframe, add_features

_cache = {}   # symbol -> (time fetched, DataFrame, source)


def get_market_data(symbol):
    """Returns (features DataFrame, source info)."""
    cached = _cache.get(symbol)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1].copy(), cached[2]

    try:
        raw = fetch_historical_data(symbol)
        source = {"type": "live", "detail": "Fyers"}
    except Exception as e:
        raw = generate_demo_response(symbol)
        source = {"type": "demo", "detail": str(e)}

    df = add_features(convert_to_dataframe(raw))
    _cache[symbol] = (time.time(), df, source)
    return df.copy(), source
