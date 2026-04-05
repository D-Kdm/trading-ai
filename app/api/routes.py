from fastapi import APIRouter
from app.services.fyers_service import fetch_historical_data

router = APIRouter()

@router.get("/")
def home():
    return {"message": "Trading AI Running 🚀"}


@router.get("/data")
def get_data():
    data = fetch_historical_data()
    return data