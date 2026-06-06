from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse

from src.db import ensure_database_ready, get_conn
from src.load_raw import create_batch_and_load_raw
from src.transform_clean import run_raw_to_clean_for_batch
from src.build_analytics import rebuild_analytics
from src.review_content_analysis import run_review_content_pipeline
from src.business_recommendation import run_business_recommendation_pipeline
from src.sales_forecast import sales_forecast
from src.product_forecast import product_forecast
from src.powerbi_service import trigger_powerbi_refresh

router = APIRouter()

UPLOAD_DIR = Path("front_end/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

JOBS: dict[str, dict] = {}


class JobCancelledError(Exception):
    pass


def allowed_file(filename: str) -> bool:
    ext = filename.lower().rsplit(".", 1)[-1]
    return ext in {"csv", "xlsx"}


def set_job(job_id: str, **kwargs):
    if job_id in JOBS:
        JOBS[job_id].update(kwargs)


def check_cancel_requested(job_id: str):
    job = JOBS.get(job_id, {})
    if job.get("cancel_requested"):
        raise JobCancelledError("Upload cancelled by user. Changes were rolled back.")


def update_batch_status(batch_id: str, status: str):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE dbo.upload_batch SET status = ? WHERE batch_id = ?",
            (status, batch_id),
        )
        conn.commit()


def has_sales_data() -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cleaned.fact_sales")
        row = cur.fetchone()
        return bool(row and row[0] > 0)


def has_review_data() -> bool:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cleaned.customer_review")
        row = cur.fetchone()
        return bool(row and row[0] > 0)


def rollback_batch_data(batch_id: str):
    """
    Remove only rows related to the current batch, then clean orphan dimensions,
    then rebuild derived tables from remaining source data.
    """
    with get_conn() as conn:
        cur = conn.cursor()

        # delete fact/raw rows by batch
        cur.execute("DELETE FROM cleaned.fact_sales WHERE batch_id = ?", (batch_id,))
        cur.execute("DELETE FROM cleaned.customer_review WHERE batch_id = ?", (batch_id,))
        cur.execute("DELETE FROM rawT.customer_purchase WHERE batch_id = ?", (batch_id,))
        cur.execute("DELETE FROM rawT.customer_review WHERE batch_id = ?", (batch_id,))

        # delete dimension rows carrying batch_id
        try:
            cur.execute("DELETE FROM cleaned.dim_customer WHERE batch_id = ?", (batch_id,))
        except Exception:
            pass

        try:
            cur.execute("DELETE FROM cleaned.dim_product WHERE batch_id = ?", (batch_id,))
        except Exception:
            pass

        # clean orphan dates
        try:
            cur.execute("""
                DELETE FROM cleaned.dim_date
                WHERE SalesDate NOT IN (
                    SELECT DISTINCT CAST(OrderDate AS date)
                    FROM cleaned.fact_sales
                    WHERE OrderDate IS NOT NULL
                )
            """)
        except Exception:
            pass

        # clean orphan months
        try:
            cur.execute("""
                DELETE FROM cleaned.dim_month
                WHERE MonthStart NOT IN (
                    SELECT DISTINCT SalesMonth
                    FROM cleaned.fact_sales
                    WHERE SalesMonth IS NOT NULL
                )
            """)
        except Exception:
            pass

        # mark rolled back
        cur.execute(
            "UPDATE dbo.upload_batch SET status = ? WHERE batch_id = ?",
            ("rolled_back", batch_id),
        )

        conn.commit()

    # rebuild all derived outputs from remaining data
    rebuild_analytics()

    if has_review_data():
        run_review_content_pipeline()

    if has_sales_data() and has_review_data():
        run_business_recommendation_pipeline()

    if has_sales_data():
        sales_forecast()
        product_forecast()


@router.post("/api/upload")
async def api_upload(file: UploadFile = File(...)) -> JSONResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Only .csv or .xlsx files are allowed.")

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Max file size is 50 MB.")

    file_id = str(uuid.uuid4())
    stored_name = f"{file_id}__{Path(file.filename).name}"
    save_path = UPLOAD_DIR / stored_name
    save_path.write_bytes(content)

    return JSONResponse(
        {
            "file_id": file_id,
            "original_name": file.filename,
            "stored_name": stored_name,
            "size_bytes": len(content),
        }
    )


@router.get("/api/preview")
def api_preview(file_id: str, rows: int = 20) -> JSONResponse:
    matches = list(UPLOAD_DIR.glob(f"{file_id}__*"))
    if not matches:
        raise HTTPException(status_code=404, detail="File not found.")

    file_path = matches[0]

    try:
        if file_path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        elif file_path.suffix.lower() == ".xlsx":
            df = pd.read_excel(file_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    df = df.head(max(1, min(rows, 100)))
    preview_rows = df.where(pd.notnull(df), None).to_dict(orient="records")

    return JSONResponse(
        {
            "columns": list(df.columns),
            "rows": preview_rows,
            "row_count": len(df),
        }
    )


def run_pipeline_job(job_id: str, uploaded_path: str, dataset_type: str, dataset_year: int):
    batch_id = None

    try:
        JOBS[job_id] = {
            "status": "running",
            "progress": 5,
            "message": "Initializing database...",
            "cancel_requested": False,
        }

        ensure_database_ready()
        check_cancel_requested(job_id)

        # Step 1: raw load
        set_job(job_id, progress=15, message=f"Loading {dataset_type} raw data...")
        raw_result = create_batch_and_load_raw(uploaded_path, dataset_type, dataset_year)
        batch_id = raw_result["batch_id"]
        update_batch_status(batch_id, "raw_loaded")
        check_cancel_requested(job_id)

        # Step 2: clean transform
        set_job(job_id, progress=35, message=f"Transforming {dataset_type} clean data...")
        clean_result = run_raw_to_clean_for_batch(batch_id)
        update_batch_status(batch_id, "clean_loaded")
        check_cancel_requested(job_id)

        analytics_result = None
        review_content_result = None
        business_result = None
        sales_result = None
        product_result = None

        # SALES PIPELINE
        if dataset_type == "sales":
            set_job(job_id, progress=55, message="Building sales analytics...")
            analytics_result = rebuild_analytics()
            check_cancel_requested(job_id)

            set_job(job_id, progress=75, message="Running sales forecast...")
            sales_result = sales_forecast()
            check_cancel_requested(job_id)

            set_job(job_id, progress=88, message="Running product forecast...")
            product_result = product_forecast()
            check_cancel_requested(job_id)

            # refresh combined outputs only if reviews exist
            if has_review_data():
                set_job(job_id, progress=94, message="Refreshing combined review insights...")
                review_content_result = run_review_content_pipeline()
                check_cancel_requested(job_id)

                set_job(job_id, progress=97, message="Refreshing business recommendations...")
                business_result = run_business_recommendation_pipeline()
                check_cancel_requested(job_id)

        # REVIEW PIPELINE
        elif dataset_type == "reviews":
            set_job(job_id, progress=55, message="Building review analytics...")
            analytics_result = rebuild_analytics()
            check_cancel_requested(job_id)

            set_job(job_id, progress=75, message="Running customer review analysis...")
            review_content_result = run_review_content_pipeline()
            check_cancel_requested(job_id)

            # only build recommendations if sales data exists
            if has_sales_data():
                set_job(job_id, progress=90, message="Building business recommendations...")
                business_result = run_business_recommendation_pipeline()
                check_cancel_requested(job_id)

        else:
            raise ValueError(f"Unsupported dataset_type: {dataset_type}")

        enable_pbi_refresh = os.getenv("ENABLE_PBI_REFRESH", "false").lower() == "true"

        if enable_pbi_refresh:
            set_job(job_id, progress=97, message="Starting Power BI refresh...")
            refresh_ok, refresh_msg = trigger_powerbi_refresh()
            final_status = "completed" if refresh_ok else "warning"
            final_message = (
                "Upload completed. Selected pipeline finished and Power BI refresh started."
                if refresh_ok
                else "Upload completed, but Power BI refresh failed to start."
            )
        else:
            refresh_ok = True
            refresh_msg = "Skipped Power BI refresh (disabled)."
            final_status = "completed"
            final_message = f"{dataset_type.capitalize()} pipeline completed successfully."

        if batch_id:
            update_batch_status(batch_id, "completed")

        JOBS[job_id] = {
            "status": final_status,
            "progress": 100,
            "message": final_message,
            "batch_id": batch_id,
            "dataset_type": dataset_type,
            "raw_result": raw_result,
            "clean_result": clean_result,
            "analytics_result": analytics_result,
            "review_content_result": review_content_result,
            "business_recommendation_result": business_result,
            "sales_forecast_result": sales_result,
            "product_forecast_result": product_result,
            "powerbi_refresh_ok": refresh_ok,
            "powerbi_refresh_msg": refresh_msg,
            "cancel_requested": False,
        }

    except JobCancelledError as e:
        if batch_id:
            try:
                update_batch_status(batch_id, "cancel_requested")
                rollback_batch_data(batch_id)
                update_batch_status(batch_id, "cancelled")
            except Exception as rollback_err:
                JOBS[job_id] = {
                    "status": "failed",
                    "progress": 100,
                    "message": f"Cancel requested, but rollback failed: {rollback_err}",
                    "batch_id": batch_id,
                    "cancel_requested": True,
                }
                return

        JOBS[job_id] = {
            "status": "cancelled",
            "progress": 0,
            "message": str(e),
            "batch_id": batch_id,
            "cancel_requested": True,
        }

    except Exception as e:
        if batch_id:
            try:
                update_batch_status(batch_id, "failed")
                rollback_batch_data(batch_id)
            except Exception as rollback_err:
                JOBS[job_id] = {
                    "status": "failed",
                    "progress": 100,
                    "message": f"Upload failed: {e}. Rollback also failed: {rollback_err}",
                    "batch_id": batch_id,
                    "cancel_requested": False,
                }
                return

        JOBS[job_id] = {
            "status": "failed",
            "progress": 0,
            "message": f"Upload failed and changes were rolled back: {e}",
            "batch_id": batch_id,
            "cancel_requested": False,
        }


@router.post("/api/run")
def api_run(
    background_tasks: BackgroundTasks,
    file_id: str = Form(...),
    dataset_type: str = Form(...),
    dataset_year: int = Form(...),
):
    matches = list(UPLOAD_DIR.glob(f"{file_id}__*"))
    if not matches:
        raise HTTPException(status_code=404, detail="File not found.")

    uploaded_path = str(matches[0])
    job_id = str(uuid.uuid4())

    JOBS[job_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Pipeline queued.",
        "cancel_requested": False,
    }

    background_tasks.add_task(
        run_pipeline_job,
        job_id,
        uploaded_path,
        dataset_type,
        dataset_year,
    )

    return JSONResponse(
        {
            "job_id": job_id,
            "status": "queued",
            "message": "Pipeline started.",
        }
    )


@router.post("/api/cancel/{job_id}")
def api_cancel(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = JOBS[job_id]
    if job["status"] not in {"queued", "running"}:
        return JSONResponse(
            {
                "job_id": job_id,
                "status": job["status"],
                "message": "Job is no longer running.",
            }
        )

    job["cancel_requested"] = True
    job["message"] = "Cancel requested. Rolling back changes..."

    return JSONResponse(
        {
            "job_id": job_id,
            "status": "cancelling",
            "message": "Cancel request received.",
        }
    )


@router.get("/api/status/{job_id}")
def api_status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JSONResponse(JOBS[job_id])