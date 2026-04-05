from fyers_apiv3 import fyersModel
from config import FYERS_CLIENT_ID

def get_fyers_client():
    # NOTE: You will need access_token (manual step first time)
    access_token = "YOUR_ACCESS_TOKEN"
    
    fyers = fyersModel.FyersModel(
        client_id=FYERS_CLIENT_ID,
        token=access_token,
        log_path=""
    )
    return fyers


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

    response = fyers.history(data)
    return response