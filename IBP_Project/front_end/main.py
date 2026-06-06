from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from front_end.routes import dashboard_api, pages, upload_api

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="IBP Platform")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.state.pbi_overview_embed_url = os.getenv("PBI_OVERVIEW_EMBED_URL", "")
app.state.pbi_sales_embed_url = os.getenv("PBI_SALES_EMBED_URL", "")
app.state.pbi_reviews_embed_url = os.getenv("PBI_REVIEWS_EMBED_URL", "")
app.state.pbi_forecast_embed_url = os.getenv("PBI_FORECAST_EMBED_URL", "")

app.include_router(pages.router)
app.include_router(upload_api.router)
app.include_router(dashboard_api.router)