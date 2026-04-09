from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Trading AI API")


@app.get("/")
def read_root():
    return {
        "message": "Trading AI API is running.",
        "available_endpoints": ["/features", "/docs"],
    }

app.include_router(router)
