from fastapi import APIRouter
from app.services.fyers_service import fetch_historical_data
from app.services.data_service import convert_to_dataframe, add_features

router = APIRouter()

@router.get("/features")
def get_features():
    raw = fetch_historical_data()
    df = convert_to_dataframe(raw)
    df = add_features(df)

    return df.tail(10).to_dict()