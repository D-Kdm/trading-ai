from fastapi import APIRouter
from app.services.fyers_service import fetch_historical_data
from app.services.data_service import convert_to_dataframe

router = APIRouter()

@router.get("/")
def root():
    return {
        "status": "ok",
        "message": "Trading AI API is running.",
        "available_routes": ["/data"],
    }

@router.get("/data")
def get_data():
    raw = fetch_historical_data()
    df = convert_to_dataframe(raw)

    return df.tail(10).to_dict()
