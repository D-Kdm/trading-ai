"""
One place to get market data: real Fyers data if possible, demo data otherwise.
"""
from app.services.fyers_service import fetch_historical_data
from app.services.demo_service import generate_demo_response
from app.services.data_service import convert_to_dataframe, add_features


def get_market_data(symbol):
    """Returns (features DataFrame, source info)."""
    try:
        raw = fetch_historical_data(symbol)
        source = {"type": "live", "detail": "Fyers"}
    except Exception as e:
        raw = generate_demo_response(symbol)
        source = {"type": "demo", "detail": str(e)}

    df = add_features(convert_to_dataframe(raw))
    return df, source
