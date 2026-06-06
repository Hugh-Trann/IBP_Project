from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.report_builder import build_report_data, get_available_categories, get_available_years

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _empty_report_data(year: Optional[int], category: str, report_type: str):
    selected_year = year or 0
    return {
        "metadata": {
            "report_title": "Integrated Business Performance Report",
            "report_subtitle": "Sales, Customer Review, Recommendation, and Forecast Analysis",
            "generated_on": "",
            "report_period_label": "",
            "selected_year": selected_year,
            "selected_category": category,
            "report_type": report_type,
            "forecast_year": None,
            "dataset_name": "IBP Uploaded Dataset",
            "batch_id": None,
        },
        "summary_cards": {
            "total_sales": 0.0,
            "total_profit": 0.0,
            "total_orders": 0,
            "avg_order_value": 0.0,
            "avg_review_score": 0.0,
            "total_reviews": 0,
            "forecast_sales": 0.0,
            "forecast_growth_pct": 0.0,
            "sales_growth_pct": 0.0,
        },
        "executive_summary": ["No report data is available yet. Please upload and process data first."],
        "sales_section": {"kpis": {"total_sales": 0.0, "total_profit": 0.0, "total_orders": 0, "avg_order_value": 0.0, "sales_growth_pct": 0.0, "profit_growth_pct": 0.0}, "top_contributors": [], "low_contributors": [], "fastest_growing": [], "most_declining": [], "declining_section_title": "Most Declining Categories", "insights": []},
        "review_section": {"kpis": {"total_reviews": 0, "avg_review_score": 0.0, "avg_sentiment_score": 0.0, "positive_reviews": 0, "neutral_reviews": 0, "negative_reviews": 0}, "topics": [], "category_review_summary": [], "insights": []},
        "combined_insight": {"window_label": "No recent-period data", "strong_zone": [], "weak_zone": [], "opportunity_zone": [], "summary_table": [], "insights": []},
        "recommendations": [],
        "forecast_section": {"summary": {"forecast_period": "N/A", "forecast_sales": 0.0, "forecast_orders": 0, "forecast_growth_pct": 0.0}, "category_forecast": [], "product_forecast": [], "insights": ["No forecast data is available."]},
        "appendix_tables": {"kpi_summary": [], "category_summary": [], "recommendation_details": [], "forecast_details": []},
    }


def _build_report_context(request: Request, page_title: str, active_page: str, template_name: str, year: Optional[int], category: str, report_type: str):
    available_years = get_available_years()
    available_categories = get_available_categories()

    if year is None and available_years:
        year = max(available_years)
    if category not in ["All Categories"] + available_categories:
        category = "All Categories"
    if report_type not in {"full", "summary", "category"}:
        report_type = "full"

    try:
        report_data = build_report_data(year=year, category=category, report_type=report_type)
    except Exception as e:
        print(f">>> REPORT PAGE ERROR ({template_name}):", e)
        report_data = _empty_report_data(year, category, report_type)

    return templates.TemplateResponse(template_name, {
        "request": request,
        "page_title": page_title,
        "active_page": active_page,
        "report_data": report_data,
        "available_years": available_years,
        "available_categories": available_categories,
        "selected_year": year,
        "selected_category": category,
        "report_type": report_type,
    })


@router.get("/overview", response_class=HTMLResponse)
def overview(request: Request):
    return templates.TemplateResponse("overview.html", {
        "request": request,
        "page_title": "Overview",
        "active_page": "overview",
        "pbi_overview_embed_url": getattr(request.app.state, "pbi_overview_embed_url", ""),
    })


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request, "page_title": "Home", "active_page": "home"})


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request, "page_title": "Upload Data", "active_page": "upload"})


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "page_title": "Dashboard", "active_page": "dashboard"})


@router.get("/analysis/sales", response_class=HTMLResponse)
def sales_page(request: Request):
    return templates.TemplateResponse("sales.html", {"request": request, "page_title": "Sales Performance", "active_page": "sales"})


@router.get("/analysis/reviews", response_class=HTMLResponse)
def review_page(request: Request):
    return templates.TemplateResponse("reviews.html", {"request": request, "page_title": "Customer Review", "active_page": "reviews"})


@router.get("/analysis/forecast", response_class=HTMLResponse)
def forecast_page(request: Request):
    return templates.TemplateResponse("forecast.html", {"request": request, "page_title": "Forecast", "active_page": "forecast"})


@router.get("/report/view", response_class=HTMLResponse)
def view_report_page(request: Request, year: Optional[int] = Query(default=None), category: str = Query(default="All Categories"), report_type: str = Query(default="full")):
    return _build_report_context(request, "View Report", "view_report", "view_report.html", year, category, report_type)


@router.get("/report/download", response_class=HTMLResponse)
def download_report_page(request: Request, year: Optional[int] = Query(default=None), category: str = Query(default="All Categories"), report_type: str = Query(default="full")):
    return _build_report_context(request, "Download Report", "download_report", "report_download.html", year, category, report_type)
