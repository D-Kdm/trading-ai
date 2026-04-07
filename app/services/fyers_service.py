from fyers_apiv3 import fyersModel
from config import FYERS_CLIENT_ID

ACCESS_TOKEN = "PASTE_YOUR_TOKEN_HERE"

def get_fyers_client():
    return fyersModel.FyersModel(
        client_id=FYERS_CLIENT_ID,
        token=ACCESS_TOKEN,
        log_path=""
    )


def fetch_historical_data(symbol="NSE:RELIANCE-EQ"):
    fyers = get_fyers_client()

    data = {
        "symbol": symbol,
        "resolution": "5",
        "date_format": "1",
        "range_from": "2024-03-01",
        "range_to": "2024-03-10",
        "cont_flag": "1"
    }

    return fyers.history(data)