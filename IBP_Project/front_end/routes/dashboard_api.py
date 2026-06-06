from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from collections import defaultdict
import pandas as pd
from src.db import get_conn

router = APIRouter()

@router.get("/api/home/quarterly-sales-profit")
def get_quarterly_sales_profit():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        sql = """
            SELECT
                YEAR(fs.OrderDate) AS SalesYear,
                DATEPART(QUARTER, fs.OrderDate) AS SalesQuarter,
                SUM(fs.Sales) AS TotalSales,
                SUM(fs.Profit) AS TotalProfit
            FROM cleaned.fact_sales fs
            GROUP BY
                YEAR(fs.OrderDate),
                DATEPART(QUARTER, fs.OrderDate)
            ORDER BY
                YEAR(fs.OrderDate),
                DATEPART(QUARTER, fs.OrderDate)
        """

        cursor.execute(sql)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "year": int(row[0]),
                "quarter": int(row[1]),
                "sales": float(row[2] or 0),
                "profit": float(row[3] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/home/yearly-summary")
def get_yearly_summary():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        sql = """
            SELECT
                YEAR(fs.OrderDate) AS SalesYear,
                SUM(fs.Sales) AS TotalRevenue,
                SUM(fs.Profit) AS TotalProfit,
                CASE
                    WHEN SUM(fs.Sales) = 0 THEN 0
                    ELSE (SUM(fs.Profit) * 100.0 / SUM(fs.Sales))
                END AS ProfitMargin
            FROM cleaned.fact_sales fs
            GROUP BY YEAR(fs.OrderDate)
            ORDER BY YEAR(fs.OrderDate)
        """

        cursor.execute(sql)
        rows = cursor.fetchall()

        data = []
        total_revenue = 0
        total_profit = 0

        for row in rows:
            revenue = float(row[1] or 0)
            profit = float(row[2] or 0)
            margin = float(row[3] or 0)

            total_revenue += revenue
            total_profit += profit

            data.append({
                "year": int(row[0]),
                "revenue": revenue,
                "profit": profit,
                "margin": round(margin, 2)
            })

        total_margin = round((total_profit * 100.0 / total_revenue), 2) if total_revenue else 0

        return JSONResponse({
            "rows": data,
            "total_revenue": round(total_revenue, 2),
            "total_profit": round(total_profit, 2),
            "total_margin": total_margin
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/home/top-profit-products")
def get_top_profit_products():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        sql = """
            SELECT TOP 5
                fs.ProductID,
                SUM(fs.Profit) AS TotalProfit
            FROM cleaned.fact_sales fs
            GROUP BY fs.ProductID
            ORDER BY SUM(fs.Profit) DESC
        """

        cursor.execute(sql)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "product": str(row[0]),
                "profit": float(row[1] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/home/top-best-sellers")
def get_top_best_sellers():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        sql = """
            SELECT TOP 5
                fs.ProductID,
                COUNT(*) AS TotalTransactions
            FROM cleaned.fact_sales fs
            GROUP BY fs.ProductID
            ORDER BY COUNT(*) DESC
        """

        cursor.execute(sql)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "product": str(row[0]),
                "transactions": int(row[1] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/home/top-customers")
def get_top_customers():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        sql = """
            SELECT TOP 5
                dc.CustomerName,
                COUNT(*) AS TotalTransactions
            FROM cleaned.fact_sales fs
            INNER JOIN cleaned.dim_customer dc
                ON fs.CustomerID = dc.CustomerID
            GROUP BY dc.CustomerName
            ORDER BY COUNT(*) DESC, dc.CustomerName
        """

        cursor.execute(sql)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "customer": row[0],
                "transactions": int(row[1] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def _append_in_filter(conditions, params, expr, values):
    if values:
        placeholders = ",".join(["?"] * len(values))
        conditions.append(f"{expr} IN ({placeholders})")
        params.extend(values)


def build_sales_where(years=None, months=None, days=None, include_days=True):
    conditions = []
    params = []

    years = years or []
    months = months or []
    days = days or []

    _append_in_filter(conditions, params, "YEAR(fs.OrderDate)", years)
    _append_in_filter(conditions, params, "MONTH(fs.OrderDate)", months)

    if include_days:
        _append_in_filter(conditions, params, "DAY(fs.OrderDate)", days)

    where_sql = ""
    if conditions:
        where_sql = "WHERE " + " AND ".join(conditions)

    return where_sql, params


@router.get("/api/sales/filter-options")
def get_sales_filter_options(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                YEAR(MAX(OrderDate)) AS LatestYear,
                MONTH(MAX(OrderDate)) AS LatestMonth,
                DAY(MAX(OrderDate)) AS LatestDay
            FROM cleaned.fact_sales
        """)
        latest_row = cursor.fetchone()
        latest_year = int(latest_row[0]) if latest_row and latest_row[0] else None
        latest_month = int(latest_row[1]) if latest_row and latest_row[1] else None
        latest_day = int(latest_row[2]) if latest_row and latest_row[2] else None

        cursor.execute("""
            SELECT DISTINCT YEAR(OrderDate) AS SalesYear
            FROM cleaned.fact_sales
            ORDER BY SalesYear
        """)
        years = [int(row[0]) for row in cursor.fetchall()]

        month_conditions = []
        month_params = []
        if year:
            _append_in_filter(month_conditions, month_params, "YEAR(OrderDate)", year)

        month_where = ""
        if month_conditions:
            month_where = "WHERE " + " AND ".join(month_conditions)

        cursor.execute(f"""
            SELECT DISTINCT MONTH(OrderDate) AS SalesMonth
            FROM cleaned.fact_sales
            {month_where}
            ORDER BY SalesMonth
        """, month_params)

        months = [
            {"value": int(row[0]), "label": MONTH_NAMES.get(int(row[0]), str(row[0]))}
            for row in cursor.fetchall()
        ]

        day_conditions = []
        day_params = []
        if year:
            _append_in_filter(day_conditions, day_params, "YEAR(OrderDate)", year)
        if month:
            _append_in_filter(day_conditions, day_params, "MONTH(OrderDate)", month)

        day_where = ""
        if day_conditions:
            day_where = "WHERE " + " AND ".join(day_conditions)

        cursor.execute(f"""
            SELECT DISTINCT DAY(OrderDate) AS SalesDay
            FROM cleaned.fact_sales
            {day_where}
            ORDER BY SalesDay
        """, day_params)

        days = [int(row[0]) for row in cursor.fetchall()]

        return JSONResponse({
            "years": years,
            "months": months,
            "days": days,
            "defaults": {
                "year": latest_year,
                "month": latest_month,
                "day": latest_day,
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/daily/summary")
def get_daily_summary(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
    day: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, day, include_days=True)

        sql = f"""
            SELECT
                fs.Category,
                SUM(fs.Sales) AS TotalSales,
                SUM(fs.Profit) AS TotalProfit,
                COUNT(*) AS NoTransactions
            FROM cleaned.fact_sales fs
            {where_sql}
            GROUP BY fs.Category
            ORDER BY SUM(fs.Sales) DESC
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        data = []
        total_sales = 0
        total_profit = 0
        total_transactions = 0

        for row in rows:
            sales = float(row[1] or 0)
            profit = float(row[2] or 0)
            transactions = int(row[3] or 0)

            total_sales += sales
            total_profit += profit
            total_transactions += transactions

            data.append({
                "category": row[0],
                "sales": sales,
                "profit": profit,
                "transactions": transactions
            })

        return JSONResponse({
            "rows": data,
            "total_sales": round(total_sales, 2),
            "total_profit": round(total_profit, 2),
            "total_transactions": total_transactions
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/daily/avg-transaction")
def get_daily_avg_transaction(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
    day: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, day, include_days=True)

        sql = f"""
            SELECT
                CASE
                    WHEN COUNT(*) = 0 THEN 0
                    ELSE SUM(fs.Sales) * 1.0 / COUNT(*)
                END AS AvgTransactionValue
            FROM cleaned.fact_sales fs
            {where_sql}
        """

        cursor.execute(sql, params)
        row = cursor.fetchone()

        return JSONResponse({
            "avg_transaction_value": round(float(row[0] or 0), 2)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/daily/orders-by-category")
def get_daily_orders_by_category(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
    day: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, day, include_days=True)

        sql = f"""
            SELECT
                fs.Category,
                COUNT(*) AS OrderCount
            FROM cleaned.fact_sales fs
            {where_sql}
            GROUP BY fs.Category
            ORDER BY COUNT(*) DESC
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "category": row[0],
                "orders": int(row[1] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/daily/sales-by-category")
def get_daily_sales_by_category(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
    day: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, day, include_days=True)

        sql = f"""
            SELECT
                fs.Category,
                SUM(fs.Sales) AS TotalSales
            FROM cleaned.fact_sales fs
            {where_sql}
            GROUP BY fs.Category
            ORDER BY SUM(fs.Sales) DESC
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "category": row[0],
                "sales": float(row[1] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/daily/profit-by-category")
def get_daily_profit_by_category(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
    day: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, day, include_days=True)

        sql = f"""
            SELECT
                fs.Category,
                SUM(fs.Profit) AS TotalProfit
            FROM cleaned.fact_sales fs
            {where_sql}
            GROUP BY fs.Category
            ORDER BY SUM(fs.Profit) DESC
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "category": row[0],
                "profit": float(row[1] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/monthly/top-profit")
def get_monthly_top_profit(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, days=None, include_days=False)

        sql = f"""
            SELECT TOP 7
                dp.SubCategory,
                SUM(fs.Profit) AS TotalProfit
            FROM cleaned.fact_sales fs
            INNER JOIN cleaned.dim_product dp
                ON fs.ProductID = dp.ProductID
            {where_sql}
            GROUP BY dp.SubCategory
            ORDER BY SUM(fs.Profit) DESC, dp.SubCategory
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "product": row[0],
                "profit": float(row[1] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/monthly/top-best-sellers")
def get_monthly_top_best_sellers(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, days=None, include_days=False)

        sql = f"""
            SELECT TOP 7
                dp.SubCategory,
                COUNT(fs.ProductID) AS NoTransactions
            FROM cleaned.fact_sales fs
            INNER JOIN cleaned.dim_product dp
                ON fs.ProductID = dp.ProductID
            {where_sql}
            GROUP BY dp.SubCategory
            ORDER BY COUNT(fs.ProductID) DESC, dp.SubCategory
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "product": row[0],
                "transactions": int(row[1] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/monthly/top-customers")
def get_monthly_top_customers(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, days=None, include_days=False)

        sql = f"""
            SELECT TOP 7
                dc.CustomerName,
                COUNT(fs.OrderID) AS NoTransactions
            FROM cleaned.fact_sales fs
            INNER JOIN cleaned.dim_customer dc
                ON fs.CustomerID = dc.CustomerID
            {where_sql}
            GROUP BY dc.CustomerName
            ORDER BY COUNT(fs.OrderID) DESC, dc.CustomerName
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "customer": row[0],
                "transactions": int(row[1] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/monthly/revenue-profit-by-day")
def get_monthly_revenue_profit_by_day(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, days=None, include_days=False)

        sql = f"""
            SELECT
                DAY(fs.OrderDate) AS DayNo,
                SUM(fs.Sales) AS TotalSales,
                SUM(fs.Profit) AS TotalProfit
            FROM cleaned.fact_sales fs
            {where_sql}
            GROUP BY DAY(fs.OrderDate)
            ORDER BY DAY(fs.OrderDate)
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                "day": int(row[0]),
                "sales": float(row[1] or 0),
                "profit": float(row[2] or 0)
            })

        return JSONResponse(data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/monthly/kpis")
def get_monthly_kpis(
    year: list[int] = Query(default=None),
    month: list[int] = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        where_sql, params = build_sales_where(year, month, days=None, include_days=False)

        sql = f"""
            SELECT
                SUM(fs.Sales) AS TotalRevenue,
                SUM(fs.Profit) AS TotalProfit,
                CASE
                    WHEN SUM(fs.Sales) = 0 THEN 0
                    ELSE (SUM(fs.Profit) * 100.0 / SUM(fs.Sales))
                END AS ProfitMargin,
                COUNT(DISTINCT fs.CustomerID) AS CustomerVisit
            FROM cleaned.fact_sales fs
            {where_sql}
        """

        cursor.execute(sql, params)
        row = cursor.fetchone()

        return JSONResponse({
            "total_revenue": round(float(row[0] or 0), 2),
            "total_profit": round(float(row[1] or 0), 2),
            "profit_margin": round(float(row[2] or 0), 2),
            "customer_visit": int(row[3] or 0)
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/comparison/options")
def get_sales_comparison_options():
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT YEAR(OrderDate) AS SalesYear
            FROM cleaned.fact_sales
            ORDER BY SalesYear
        """)
        years = [int(row[0]) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT DISTINCT MONTH(OrderDate) AS SalesMonth
            FROM cleaned.fact_sales
            ORDER BY SalesMonth
        """)
        months = [
            {"value": int(row[0]), "label": MONTH_NAMES.get(int(row[0]), str(row[0]))}
            for row in cursor.fetchall()
        ]

        latest_year = years[-1] if years else None
        previous_year = years[-2] if len(years) >= 2 else latest_year

        return JSONResponse({
            "years": years,
            "months": months,
            "defaults": {
                "mode": "yoy",
                "year1": previous_year,
                "year2": latest_year,
                "month1": 1,
                "month2": 1
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/sales/comparison")
def get_sales_comparison(
    mode: str = Query(..., pattern="^(yoy|mom)$"),
    period1_year: int = Query(...),
    period2_year: int = Query(...),
    period1_month: int | None = Query(default=None),
    period2_month: int | None = Query(default=None),
):
    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        if mode == "yoy":
            sql = """
                SELECT
                    YEAR(fs.OrderDate) AS SalesYear,
                    MONTH(fs.OrderDate) AS SalesMonth,
                    SUM(fs.Sales) AS TotalSales,
                    SUM(fs.Profit) AS TotalProfit
                FROM cleaned.fact_sales fs
                WHERE YEAR(fs.OrderDate) IN (?, ?)
                GROUP BY YEAR(fs.OrderDate), MONTH(fs.OrderDate)
                ORDER BY YEAR(fs.OrderDate), MONTH(fs.OrderDate)
            """
            cursor.execute(sql, [period1_year, period2_year])
            rows = cursor.fetchall()

            labels = []
            month_seen = set()
            year1_map_sales = {}
            year2_map_sales = {}
            year1_map_profit = {}
            year2_map_profit = {}

            for row in rows:
                year_no = int(row[0])
                month_no = int(row[1])
                sales = float(row[2] or 0)
                profit = float(row[3] or 0)

                if month_no not in month_seen:
                    month_seen.add(month_no)
                    labels.append(MONTH_NAMES.get(month_no, str(month_no)))

                if year_no == period1_year:
                    year1_map_sales[month_no] = sales
                    year1_map_profit[month_no] = profit
                elif year_no == period2_year:
                    year2_map_sales[month_no] = sales
                    year2_map_profit[month_no] = profit

            ordered_months = sorted(set(list(year1_map_sales.keys()) + list(year2_map_sales.keys())))
            labels = [MONTH_NAMES.get(m, str(m)) for m in ordered_months]

            sales_series = [
                {
                    "label": str(period1_year),
                    "data": [round(year1_map_sales.get(m, 0), 2) for m in ordered_months]
                },
                {
                    "label": str(period2_year),
                    "data": [round(year2_map_sales.get(m, 0), 2) for m in ordered_months]
                }
            ]

            profit_series = [
                {
                    "label": str(period1_year),
                    "data": [round(year1_map_profit.get(m, 0), 2) for m in ordered_months]
                },
                {
                    "label": str(period2_year),
                    "data": [round(year2_map_profit.get(m, 0), 2) for m in ordered_months]
                }
            ]

            return JSONResponse({
                "mode": "yoy",
                "labels": labels,
                "sales_series": sales_series,
                "profit_series": profit_series,
                "title_suffix": f"({period1_year} vs {period2_year})"
            })

        if period1_month is None or period2_month is None:
            raise HTTPException(status_code=400, detail="Month values are required for month-to-month comparison.")

        sql = """
            SELECT
                YEAR(fs.OrderDate) AS SalesYear,
                MONTH(fs.OrderDate) AS SalesMonth,
                DAY(fs.OrderDate) AS SalesDay,
                SUM(fs.Sales) AS TotalSales,
                SUM(fs.Profit) AS TotalProfit
            FROM cleaned.fact_sales fs
            WHERE
                (YEAR(fs.OrderDate) = ? AND MONTH(fs.OrderDate) = ?)
                OR
                (YEAR(fs.OrderDate) = ? AND MONTH(fs.OrderDate) = ?)
            GROUP BY YEAR(fs.OrderDate), MONTH(fs.OrderDate), DAY(fs.OrderDate)
            ORDER BY YEAR(fs.OrderDate), MONTH(fs.OrderDate), DAY(fs.OrderDate)
        """
        cursor.execute(sql, [period1_year, period1_month, period2_year, period2_month])
        rows = cursor.fetchall()

        period1_sales = {}
        period2_sales = {}
        period1_profit = {}
        period2_profit = {}
        ordered_days = []

        for row in rows:
            year_no = int(row[0])
            month_no = int(row[1])
            day_no = int(row[2])
            sales = float(row[3] or 0)
            profit = float(row[4] or 0)

            if day_no not in ordered_days:
                ordered_days.append(day_no)

            if year_no == period1_year and month_no == period1_month:
                period1_sales[day_no] = sales
                period1_profit[day_no] = profit
            elif year_no == period2_year and month_no == period2_month:
                period2_sales[day_no] = sales
                period2_profit[day_no] = profit

        ordered_days = sorted(set(ordered_days))
        labels = [str(day) for day in ordered_days]

        label_1 = f"{MONTH_NAMES.get(period1_month, period1_month)} {period1_year}"
        label_2 = f"{MONTH_NAMES.get(period2_month, period2_month)} {period2_year}"

        return JSONResponse({
            "mode": "mom",
            "labels": labels,
            "sales_series": [
                {
                    "label": label_1,
                    "data": [round(period1_sales.get(day, 0), 2) for day in ordered_days]
                },
                {
                    "label": label_2,
                    "data": [round(period2_sales.get(day, 0), 2) for day in ordered_days]
                }
            ],
            "profit_series": [
                {
                    "label": label_1,
                    "data": [round(period1_profit.get(day, 0), 2) for day in ordered_days]
                },
                {
                    "label": label_2,
                    "data": [round(period2_profit.get(day, 0), 2) for day in ordered_days]
                }
            ],
            "title_suffix": f"({label_1} vs {label_2})"
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


@router.get("/api/reviews/filters")
def get_review_filters():
    conn = get_conn()

    sql_month = """
        SELECT DISTINCT
            YEAR(ReviewMonth) AS [Year],
            MONTH(ReviewMonth) AS MonthNumber,
            DATENAME(MONTH, ReviewMonth) AS MonthName
        FROM analytics.review_category_monthly
        WHERE ReviewMonth IS NOT NULL
        ORDER BY [Year], MonthNumber
    """

    sql_category = """
        SELECT DISTINCT Category
        FROM analytics.review_category_monthly
        WHERE Category IS NOT NULL
        ORDER BY Category
    """

    df_month = pd.read_sql(sql_month, conn)
    df_category = pd.read_sql(sql_category, conn)

    months_by_year = {}
    for year in sorted(df_month["Year"].dropna().unique().tolist()):
        year_int = int(year)
        year_rows = df_month[df_month["Year"] == year].sort_values("MonthNumber")

        months_by_year[str(year_int)] = [
            {
                "month_number": int(row["MonthNumber"]),
                "month_name": str(row["MonthName"])
            }
            for _, row in year_rows.iterrows()
        ]

    years = [int(y) for y in sorted(df_month["Year"].dropna().unique().tolist())]
    categories = [str(c) for c in df_category["Category"].dropna().tolist()]

    return {
        "years": years,
        "months_by_year": months_by_year,
        "categories": categories
    }


@router.get("/api/reviews/summary")
def get_review_summary(
    year: int = Query(...),
    month: list[int] = Query(default=[]),
    category: list[str] = Query(default=[]),
):
    conn = get_conn()

    sql = """
        SELECT
            Category,
            SUM(PositiveReviews) AS PositiveReviews,
            SUM(NeutralReviews) AS NeutralReviews,
            SUM(NegativeReviews) AS NegativeReviews,
            SUM(TotalReviews) AS TotalReviews,
            CAST(
                SUM(CAST(AvgReviewScore * TotalReviews AS float))
                / NULLIF(SUM(TotalReviews), 0)
                AS decimal(10,2)
            ) AS AvgReviewScore
        FROM analytics.review_category_monthly
        WHERE YEAR(ReviewMonth) = ?
    """

    params = [year]

    if month:
        placeholders = ",".join(["?"] * len(month))
        sql += f" AND MONTH(ReviewMonth) IN ({placeholders}) "
        params.extend(month)

    if category:
        placeholders = ",".join(["?"] * len(category))
        sql += f" AND Category IN ({placeholders}) "
        params.extend(category)

    sql += """
        GROUP BY Category
        ORDER BY Category
    """

    df = pd.read_sql(sql, conn, params=params)

    if df.empty:
        return {
            "cards": {
                "total_reviews": 0,
                "avg_review_score": 0,
                "positive_reviews": 0,
                "negative_reviews": 0
            },
            "tables": {
                "positive": [],
                "neutral": [],
                "negative": []
            }
        }

    df["PositiveReviews"] = df["PositiveReviews"].fillna(0).astype(int)
    df["NeutralReviews"] = df["NeutralReviews"].fillna(0).astype(int)
    df["NegativeReviews"] = df["NegativeReviews"].fillna(0).astype(int)
    df["TotalReviews"] = df["TotalReviews"].fillna(0).astype(int)
    df["AvgReviewScore"] = df["AvgReviewScore"].fillna(0).astype(float)
    df["Category"] = df["Category"].astype(str)

    total_positive = int(df["PositiveReviews"].sum())
    total_negative = int(df["NegativeReviews"].sum())
    total_reviews = int(df["TotalReviews"].sum())

    weighted_avg_review = round(
        float((df["AvgReviewScore"] * df["TotalReviews"]).sum()) / total_reviews, 2
    ) if total_reviews else 0

    positive_rows = [
        {"Category": str(row["Category"]), "Total": int(row["PositiveReviews"])}
        for _, row in df.sort_values("PositiveReviews", ascending=False).iterrows()
    ]

    neutral_rows = [
        {"Category": str(row["Category"]), "Total": int(row["NeutralReviews"])}
        for _, row in df.sort_values("NeutralReviews", ascending=False).iterrows()
    ]

    negative_rows = [
        {"Category": str(row["Category"]), "Total": int(row["NegativeReviews"])}
        for _, row in df.sort_values("NegativeReviews", ascending=False).iterrows()
    ]

    return {
        "cards": {
            "total_reviews": total_reviews,
            "avg_review_score": float(weighted_avg_review),
            "positive_reviews": total_positive,
            "negative_reviews": total_negative
        },
        "tables": {
            "positive": positive_rows,
            "neutral": neutral_rows,
            "negative": negative_rows
        }
    }


@router.get("/api/reviews/summary-direction")
def get_review_summary_direction(
    year: int = Query(...),
    category: list[str] = Query(default=[]),
):
    conn = get_conn()

    sql = """
        SELECT
            MONTH(ReviewMonth) AS MonthNumber,
            DATENAME(MONTH, ReviewMonth) AS MonthName,
            SUM(PositiveReviews) AS PositiveReviews,
            SUM(NeutralReviews) AS NeutralReviews,
            SUM(NegativeReviews) AS NegativeReviews
        FROM analytics.review_category_monthly
        WHERE YEAR(ReviewMonth) = ?
    """

    params = [year]

    if category:
        placeholders = ",".join(["?"] * len(category))
        sql += f" AND Category IN ({placeholders}) "
        params.extend(category)

    sql += """
        GROUP BY MONTH(ReviewMonth), DATENAME(MONTH, ReviewMonth)
        ORDER BY MonthNumber
    """

    df = pd.read_sql(sql, conn, params=params)

    if df.empty:
        return []

    return [
        {
            "MonthNumber": int(row["MonthNumber"]),
            "MonthName": str(row["MonthName"]),
            "PositiveReviews": int(row["PositiveReviews"] or 0),
            "NeutralReviews": int(row["NeutralReviews"] or 0),
            "NegativeReviews": int(row["NegativeReviews"] or 0)
        }
        for _, row in df.iterrows()
    ]


@router.get("/api/reviews/score")
def get_score_review(
    year: int = Query(...),
    month: list[int] = Query(default=[]),
    category: list[str] = Query(default=[]),
):
    conn = get_conn()

    sql = """
        SELECT
            SalesMonth,
            Category,
            SUM(TotalSales) AS TotalSales,
            SUM(TotalTransactions) AS TotalTransactions,
            SUM(TotalReviews) AS TotalReviews,
            CAST(
                SUM(CAST(AvgReviewScore * TotalReviews AS float))
                / NULLIF(SUM(TotalReviews), 0)
                AS decimal(10,2)
            ) AS AvgReviewScore
        FROM analytics.sales_review_category_combined
        WHERE YEAR(SalesMonth) = ?
    """

    params = [year]

    if month:
        placeholders = ",".join(["?"] * len(month))
        sql += f" AND MONTH(SalesMonth) IN ({placeholders}) "
        params.extend(month)

    if category:
        placeholders = ",".join(["?"] * len(category))
        sql += f" AND Category IN ({placeholders}) "
        params.extend(category)

    sql += """
        GROUP BY SalesMonth, Category
        ORDER BY SalesMonth, Category
    """

    df = pd.read_sql(sql, conn, params=params)

    if df.empty:
        return {
            "cards": {
                "total_sales": 0,
                "total_transactions": 0,
                "total_reviews": 0,
                "avg_review_score": 0
            },
            "monthly_chart": [],
            "category_chart": []
        }

    df["TotalSales"] = df["TotalSales"].fillna(0).astype(float)
    df["TotalTransactions"] = df["TotalTransactions"].fillna(0).astype(int)
    df["TotalReviews"] = df["TotalReviews"].fillna(0).astype(int)
    df["AvgReviewScore"] = df["AvgReviewScore"].fillna(0).astype(float)
    df["Category"] = df["Category"].astype(str)
    df["SalesMonth"] = pd.to_datetime(df["SalesMonth"])

    total_sales = round(float(df["TotalSales"].sum()), 2)
    total_transactions = int(df["TotalTransactions"].sum())
    total_reviews = int(df["TotalReviews"].sum())

    avg_review_score = round(
        float((df["AvgReviewScore"] * df["TotalReviews"]).sum()) / total_reviews, 2
    ) if total_reviews else 0

    monthly_df = df.groupby("SalesMonth", as_index=False).agg({
        "TotalSales": "sum",
        "TotalReviews": "sum",
        "AvgReviewScore": "mean"
    })
    monthly_df["MonthLabel"] = monthly_df["SalesMonth"].dt.strftime("%B")

    category_df = df.groupby("Category", as_index=False).agg({
        "TotalSales": "sum",
        "TotalReviews": "sum",
        "AvgReviewScore": "mean"
    }).sort_values("TotalSales", ascending=False)

    monthly_chart = [
        {
            "MonthLabel": str(row["MonthLabel"]),
            "TotalSales": float(row["TotalSales"]),
            "AvgReviewScore": float(round(row["AvgReviewScore"], 2))
        }
        for _, row in monthly_df.iterrows()
    ]

    category_chart = [
        {
            "Category": str(row["Category"]),
            "TotalSales": float(row["TotalSales"]),
            "AvgReviewScore": float(round(row["AvgReviewScore"], 2))
        }
        for _, row in category_df.iterrows()
    ]

    return {
        "cards": {
            "total_sales": total_sales,
            "total_transactions": total_transactions,
            "total_reviews": total_reviews,
            "avg_review_score": float(avg_review_score)
        },
        "monthly_chart": monthly_chart,
        "category_chart": category_chart
    }


@router.get("/api/reviews/sentiment")
def get_sentiment_review(
    year: int = Query(...),
    month: list[int] = Query(default=[]),
    category: list[str] = Query(default=[]),
):
    conn = get_conn()

    sql = """
        SELECT
            SalesMonth,
            Category,
            SUM(TotalSales) AS TotalSales,
            SUM(TotalTransactions) AS TotalTransactions,
            SUM(TotalReviews) AS TotalReviews,
            AVG(CAST(AvgSentimentScore AS float)) AS AvgSentimentScore
        FROM analytics.sales_review_category_combined
        WHERE YEAR(SalesMonth) = ?
    """

    params = [year]

    if month:
        placeholders = ",".join(["?"] * len(month))
        sql += f" AND MONTH(SalesMonth) IN ({placeholders}) "
        params.extend(month)

    if category:
        placeholders = ",".join(["?"] * len(category))
        sql += f" AND Category IN ({placeholders}) "
        params.extend(category)

    sql += """
        GROUP BY SalesMonth, Category
        ORDER BY SalesMonth, Category
    """

    df = pd.read_sql(sql, conn, params=params)

    if df.empty:
        return {
            "cards": {
                "total_sales": 0,
                "total_transactions": 0,
                "total_reviews": 0,
                "avg_sentiment_score": 0
            },
            "monthly_chart": [],
            "category_chart": []
        }

    df["TotalSales"] = df["TotalSales"].fillna(0).astype(float)
    df["TotalTransactions"] = df["TotalTransactions"].fillna(0).astype(int)
    df["TotalReviews"] = df["TotalReviews"].fillna(0).astype(int)
    df["AvgSentimentScore"] = df["AvgSentimentScore"].fillna(0).astype(float)
    df["Category"] = df["Category"].astype(str)
    df["SalesMonth"] = pd.to_datetime(df["SalesMonth"])

    total_sales = round(float(df["TotalSales"].sum()), 2)
    total_transactions = int(df["TotalTransactions"].sum())
    total_reviews = int(df["TotalReviews"].sum())
    avg_sentiment_score = round(float(df["AvgSentimentScore"].mean()), 2)

    monthly_df = df.groupby("SalesMonth", as_index=False).agg({
        "TotalSales": "sum",
        "AvgSentimentScore": "mean"
    })
    monthly_df["MonthLabel"] = monthly_df["SalesMonth"].dt.strftime("%B")

    category_df = df.groupby("Category", as_index=False).agg({
        "TotalSales": "sum",
        "AvgSentimentScore": "mean"
    }).sort_values("TotalSales", ascending=False)

    monthly_chart = [
        {
            "MonthLabel": str(row["MonthLabel"]),
            "TotalSales": float(row["TotalSales"]),
            "AvgSentimentScore": float(round(row["AvgSentimentScore"], 2))
        }
        for _, row in monthly_df.iterrows()
    ]

    category_chart = [
        {
            "Category": str(row["Category"]),
            "TotalSales": float(row["TotalSales"]),
            "AvgSentimentScore": float(round(row["AvgSentimentScore"], 2))
        }
        for _, row in category_df.iterrows()
    ]

    return {
        "cards": {
            "total_sales": total_sales,
            "total_transactions": total_transactions,
            "total_reviews": total_reviews,
            "avg_sentiment_score": float(avg_sentiment_score)
        },
        "monthly_chart": monthly_chart,
        "category_chart": category_chart
    }


@router.get("/api/reviews/topic")
def get_review_topic(
    year: int = Query(...),
    month: list[int] = Query(default=[]),
    category: list[str] = Query(default=[]),
):
    conn = get_conn()

    sql = """
        SELECT
            Topic,
            SUM(TopicReviewCount) AS TopicReviewCount,
            AVG(CAST(AvgTopicSentimentScore AS float)) AS AvgTopicSentimentScore
        FROM analytics.review_topic_category_monthly
        WHERE YEAR(ReviewMonth) = ?
    """

    params = [year]

    if month:
        placeholders = ",".join(["?"] * len(month))
        sql += f" AND MONTH(ReviewMonth) IN ({placeholders}) "
        params.extend(month)

    if category:
        placeholders = ",".join(["?"] * len(category))
        sql += f" AND Category IN ({placeholders}) "
        params.extend(category)

    sql += """
        GROUP BY Topic
        ORDER BY TopicReviewCount DESC, Topic
    """

    df = pd.read_sql(sql, conn, params=params)

    if df.empty:
        return {
            "topic_count_chart": [],
            "topic_sentiment_chart": []
        }

    df["Topic"] = df["Topic"].astype(str)
    df["TopicReviewCount"] = df["TopicReviewCount"].fillna(0).astype(int)
    df["AvgTopicSentimentScore"] = df["AvgTopicSentimentScore"].fillna(0).astype(float)

    topic_count_chart = [
        {
            "Topic": str(row["Topic"]),
            "TopicReviewCount": int(row["TopicReviewCount"])
        }
        for _, row in df.sort_values("TopicReviewCount", ascending=False).iterrows()
    ]

    topic_sentiment_chart = [
        {
            "Topic": str(row["Topic"]),
            "AvgTopicSentimentScore": float(round(row["AvgTopicSentimentScore"], 2))
        }
        for _, row in df.sort_values("AvgTopicSentimentScore", ascending=False).iterrows()
    ]

    return {
        "topic_count_chart": topic_count_chart,
        "topic_sentiment_chart": topic_sentiment_chart
    }

@router.get("/api/forecast/filters")
def get_forecast_filters():
    conn = get_conn()

    sql_year = """
        SELECT TOP 1 ForecastYear
        FROM (
            SELECT YEAR(SalesMonth) AS ForecastYear FROM analytics.sales_forecast
            UNION
            SELECT YEAR(SalesMonth) AS ForecastYear FROM analytics.products_forecast
        ) x
        WHERE ForecastYear IS NOT NULL
        ORDER BY ForecastYear DESC
    """

    sql_months = """
        SELECT DISTINCT
            MONTH(SalesMonth) AS MonthNumber,
            DATENAME(MONTH, SalesMonth) AS MonthName
        FROM (
            SELECT SalesMonth FROM analytics.sales_forecast
            UNION
            SELECT SalesMonth FROM analytics.products_forecast
        ) x
        WHERE SalesMonth IS NOT NULL
          AND YEAR(SalesMonth) = (
              SELECT TOP 1 ForecastYear
              FROM (
                  SELECT YEAR(SalesMonth) AS ForecastYear FROM analytics.sales_forecast
                  UNION
                  SELECT YEAR(SalesMonth) AS ForecastYear FROM analytics.products_forecast
              ) y
              WHERE ForecastYear IS NOT NULL
              ORDER BY ForecastYear DESC
          )
        ORDER BY MonthNumber
    """

    sql_categories = """
        SELECT DISTINCT Category
        FROM (
            SELECT Category, SalesMonth FROM analytics.sales_forecast
            UNION
            SELECT Category, SalesMonth FROM analytics.products_forecast
        ) x
        WHERE Category IS NOT NULL
          AND YEAR(SalesMonth) = (
              SELECT TOP 1 ForecastYear
              FROM (
                  SELECT YEAR(SalesMonth) AS ForecastYear FROM analytics.sales_forecast
                  UNION
                  SELECT YEAR(SalesMonth) AS ForecastYear FROM analytics.products_forecast
              ) y
              WHERE ForecastYear IS NOT NULL
              ORDER BY ForecastYear DESC
          )
        ORDER BY Category
    """

    df_year = pd.read_sql(sql_year, conn)
    df_months = pd.read_sql(sql_months, conn)
    df_categories = pd.read_sql(sql_categories, conn)

    forecast_year = None
    if not df_year.empty:
        forecast_year = int(df_year.iloc[0]["ForecastYear"])

    months = []
    if not df_months.empty:
        months = [
            {
                "month_number": int(row["MonthNumber"]),
                "month_name": str(row["MonthName"])
            }
            for _, row in df_months.iterrows()
        ]

    categories = []
    if not df_categories.empty:
        categories = [str(row["Category"]) for _, row in df_categories.iterrows()]

    return {
        "forecast_year": forecast_year,
        "months": months,
        "categories": categories
    }

@router.get("/api/forecast/sales")
def get_sales_forecast(
    month: list[int] = Query(default=[]),
    category: list[str] = Query(default=[]),
):
    conn = get_conn()

    forecast_year_sql = """
        SELECT TOP 1 YEAR(SalesMonth) AS ForecastYear
        FROM analytics.sales_forecast
        WHERE SalesMonth IS NOT NULL
        ORDER BY SalesMonth DESC
    """
    df_year = pd.read_sql(forecast_year_sql, conn)
    if df_year.empty:
        return {
            "chart": [],
            "table": [],
            "category_pie": [],
            "total_sales": 0
        }

    forecast_year = int(df_year.iloc[0]["ForecastYear"])

    chart_sql = """
        SELECT
            sf.SalesMonth,
            SUM(sf.Sales) AS Sales
        FROM analytics.sales_forecast sf
        WHERE YEAR(sf.SalesMonth) = ?
    """
    chart_params = [forecast_year]

    if month:
        placeholders = ",".join(["?"] * len(month))
        chart_sql += f" AND MONTH(sf.SalesMonth) IN ({placeholders}) "
        chart_params.extend(month)

    if category:
        placeholders = ",".join(["?"] * len(category))
        chart_sql += f" AND sf.Category IN ({placeholders}) "
        chart_params.extend(category)

    chart_sql += """
        GROUP BY sf.SalesMonth
        ORDER BY sf.SalesMonth
    """

    pie_sql = """
        SELECT
            sf.Category,
            SUM(sf.Sales) AS Sales
        FROM analytics.sales_forecast sf
        WHERE YEAR(sf.SalesMonth) = ?
    """
    pie_params = [forecast_year]

    if month:
        placeholders = ",".join(["?"] * len(month))
        pie_sql += f" AND MONTH(sf.SalesMonth) IN ({placeholders}) "
        pie_params.extend(month)

    if category:
        placeholders = ",".join(["?"] * len(category))
        pie_sql += f" AND sf.Category IN ({placeholders}) "
        pie_params.extend(category)

    pie_sql += """
        GROUP BY sf.Category
        ORDER BY SUM(sf.Sales) DESC, sf.Category
    """

    df_chart = pd.read_sql(chart_sql, conn, params=chart_params)
    df_pie = pd.read_sql(pie_sql, conn, params=pie_params)

    if df_chart.empty and df_pie.empty:
        return {
            "chart": [],
            "table": [],
            "category_pie": [],
            "total_sales": 0
        }

    if not df_chart.empty:
        df_chart["SalesMonth"] = pd.to_datetime(df_chart["SalesMonth"])
        df_chart["Sales"] = df_chart["Sales"].fillna(0).astype(float)
        df_chart["MonthLabel"] = df_chart["SalesMonth"].dt.strftime("%B")
    else:
        df_chart = pd.DataFrame(columns=["SalesMonth", "Sales", "MonthLabel"])

    if not df_pie.empty:
        df_pie["Category"] = df_pie["Category"].astype(str)
        df_pie["Sales"] = df_pie["Sales"].fillna(0).astype(float)
    else:
        df_pie = pd.DataFrame(columns=["Category", "Sales"])

    chart_rows = [
        {
            "MonthLabel": str(row["MonthLabel"]),
            "Sales": float(round(row["Sales"], 2))
        }
        for _, row in df_chart.iterrows()
    ]

    table_rows = [
        {
            "Month": str(row["MonthLabel"]),
            "Sales": float(round(row["Sales"], 2))
        }
        for _, row in df_chart.iterrows()
    ]

    pie_rows = [
        {
            "Category": str(row["Category"]),
            "Sales": float(round(row["Sales"], 2))
        }
        for _, row in df_pie.iterrows()
    ]

    total_sales = round(float(df_chart["Sales"].sum()), 2) if not df_chart.empty else 0

    return {
        "chart": chart_rows,
        "table": table_rows,
        "category_pie": pie_rows,
        "total_sales": total_sales
    }


@router.get("/api/forecast/category")
def get_category_forecast(
    month: list[int] = Query(default=[]),
    category: list[str] = Query(default=[]),
):
    conn = get_conn()

    forecast_year_sql = """
        SELECT TOP 1 YEAR(SalesMonth) AS ForecastYear
        FROM analytics.products_forecast
        WHERE SalesMonth IS NOT NULL
        ORDER BY SalesMonth DESC
    """
    df_year = pd.read_sql(forecast_year_sql, conn)
    if df_year.empty:
        return {
            "chart": [],
            "table": [],
            "pie": []
        }

    forecast_year = int(df_year.iloc[0]["ForecastYear"])

    sql = """
        SELECT
            pf.Category,
            SUM(pf.ForecastTransactions) AS ForecastTransactions
        FROM analytics.products_forecast pf
        WHERE YEAR(pf.SalesMonth) = ?
    """

    params = [forecast_year]

    if month:
        placeholders = ",".join(["?"] * len(month))
        sql += f" AND MONTH(pf.SalesMonth) IN ({placeholders}) "
        params.extend(month)

    if category:
        placeholders = ",".join(["?"] * len(category))
        sql += f" AND pf.Category IN ({placeholders}) "
        params.extend(category)

    sql += """
        GROUP BY pf.Category
        ORDER BY SUM(pf.ForecastTransactions) DESC, pf.Category
    """

    df = pd.read_sql(sql, conn, params=params)

    if df.empty:
        return {
            "chart": [],
            "table": [],
            "pie": []
        }

    df["Category"] = df["Category"].astype(str)
    df["ForecastTransactions"] = df["ForecastTransactions"].fillna(0).astype(float)

    rows = [
        {
            "Category": str(row["Category"]),
            "ForecastTransactions": float(round(row["ForecastTransactions"], 2))
        }
        for _, row in df.iterrows()
    ]

    return {
        "chart": rows,
        "table": rows,
        "pie": rows
    }