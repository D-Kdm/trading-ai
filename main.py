import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes import router

app = FastAPI(title="Trading AI API")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "app", "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def dashboard_page():
    # The web dashboard (HTML + JS) - it calls /api/dashboard for its data
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/status")
def status():
    return {
        "message": "Trading AI API is running.",
        "available_endpoints": ["/features", "/signal", "/train", "/predict",
                                "/api/dashboard", "/docs"],
    }

app.include_router(router)
