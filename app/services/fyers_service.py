from datetime import date, timedelta
from fyers_apiv3 import fyersModel
from config import FYERS_CLIENT_ID, FYERS_ACCESS_TOKEN, HISTORY_DAYS


class FyersError(Exception):
    """Raised when Fyers refuses a request (bad token, wrong symbol, ...)."""


def get_fyers_client():
    return fyersModel.FyersModel(
        client_id=FYERS_CLIENT_ID,
        token=FYERS_ACCESS_TOKEN,
        log_path=""
    )


def fetch_historical_data(symbol="NSE:RELIANCE-EQ", days=HISTORY_DAYS):
    if not FYERS_ACCESS_TOKEN:
        raise FyersError("No FYERS_ACCESS_TOKEN in .env")

    fyers = get_fyers_client()

    data = {
        "symbol": symbol,
        "resolution": "5",                  # 5-minute candles
        "date_format": "1",                 # dates as yyyy-mm-dd
        "range_from": (date.today() - timedelta(days=days)).isoformat(),
        "range_to": date.today().isoformat(),
        "cont_flag": "1"
    }

    response = fyers.history(data)

    # Fyers answers {"s": "ok", "candles": [...]} on success,
    # or {"s": "error", "message": "..."} on failure
    if response.get("s") != "ok" or not response.get("candles"):
        raise FyersError(response.get("message", "No candles returned"))

    return response
