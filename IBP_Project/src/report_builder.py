from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from src.db import get_conn


TOP_N_CATEGORY_ROWS = 3
RECENT_INSIGHT_MONTHS = 3


def build_report_data(
    year: Optional[int] = None,
    category: str = "All Categories",
    report_type: str = "full",
) -> Dict[str, Any]:
    available_years = get_available_years()
    selected_year = year if year is not None else (max(available_years) if available_years else datetime.now().year)
    selected_category = category or "All Categories"

    metadata = get_report_metadata(selected_year, selected_category, report_type)
    summary_cards = get_summary_cards(selected_year, selected_category)
    sales_section = get_sales_section(selected_year, selected_category)
    summary_cards["sales_growth_pct"] = sales_section["kpis"]["sales_growth_pct"]
    review_section = get_review_section(selected_year, selected_category)
    combined_insight = get_combined_insight(selected_year, selected_category)
    recommendations = get_recommendations(selected_year, selected_category)
    forecast_section = get_forecast_section(selected_year, selected_category)
    executive_summary = generate_executive_summary(
        selected_year,
        selected_category,
        summary_cards,
        sales_section,
        review_section,
        combined_insight,
        forecast_section,
    )
    appendix_tables = get_appendix_tables(
        sales_section,
        review_section,
        combined_insight,
        recommendations,
        forecast_section,
    )

    return {
        "metadata": metadata,
        "summary_cards": summary_cards,
        "executive_summary": executive_summary,
        "sales_section": sales_section,
        "review_section": review_section,
        "combined_insight": combined_insight,
        "recommendations": recommendations,
        "forecast_section": forecast_section,
        "appendix_tables": appendix_tables,
    }


def get_available_years() -> List[int]:
    sql = """
        SELECT DISTINCT YEAR(OrderDate) AS SalesYear
        FROM cleaned.fact_sales
        WHERE OrderDate IS NOT NULL
        ORDER BY SalesYear
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn)

    if df.empty:
        return []
    return [int(v) for v in df["SalesYear"].dropna().tolist()]


def get_available_categories() -> List[str]:
    sql = """
        SELECT DISTINCT Category
        FROM analytics.sales_review_category_combined
        WHERE Category IS NOT NULL
        ORDER BY Category
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn)

    if df.empty:
        return []
    return [str(v) for v in df["Category"].dropna().tolist()]


def get_forecast_year() -> Optional[int]:
    sql = """
        SELECT TOP 1 YEAR(SalesMonth) AS ForecastYear
        FROM analytics.sales_forecast
        WHERE SalesMonth IS NOT NULL
        ORDER BY SalesMonth DESC
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn)

    if df.empty or pd.isna(df.iloc[0]["ForecastYear"]):
        return None
    return int(df.iloc[0]["ForecastYear"])


def get_report_metadata(year: int, category: str, report_type: str) -> Dict[str, Any]:
    forecast_year = get_forecast_year() or (year + 1)

    return {
        "report_title": "Integrated Business Performance Report",
        "report_subtitle": "Sales, Customer Review, Recommendation, and Forecast Analysis",
        "generated_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "report_period_label": f"January {year} to December {year}",
        "selected_year": year,
        "selected_category": category,
        "report_type": report_type,
        "forecast_year": forecast_year,
        "dataset_name": "IBP Uploaded Dataset",
        "batch_id": None,
    }


def _category_filter_sql(column_name: str, category: str) -> tuple[str, list[Any]]:
    if not category or category == "All Categories":
        return "", []
    return f" AND {column_name} = ? ", [category]


def _trend_label(change_pct: Optional[float]) -> str:
    if change_pct is None:
        return "N/A"
    if change_pct >= 5:
        return "Upward"
    if change_pct > 0:
        return "Slight Upward"
    if change_pct <= -5:
        return "Declining"
    if change_pct < 0:
        return "Slight Decline"
    return "Flat"


def _safe_mom_growth(prev_value: float, curr_value: float) -> Optional[float]:
    if prev_value is None or curr_value is None:
        return None
    if pd.isna(prev_value) or pd.isna(curr_value):
        return None
    if prev_value == 0:
        return None
    return ((curr_value - prev_value) / prev_value) * 100.0


def _format_growth_record(record: Dict[str, Any]) -> Dict[str, Any]:
    sales_growth_pct = None if pd.isna(record.get("SalesGrowthPct")) else round(float(record.get("SalesGrowthPct")), 2)
    profit_growth_pct = None if pd.isna(record.get("ProfitGrowthPct")) else round(float(record.get("ProfitGrowthPct")), 2)

    return {
        "category": str(record["Category"]),
        "sales": round(float(record["TotalSales"] or 0), 2),
        "profit": round(float(record["TotalProfit"] or 0), 2),
        "orders": int(record["Orders"] or 0),
        "sales_growth_pct": sales_growth_pct,
        "profit_growth_pct": profit_growth_pct,
        "trend": _trend_label(sales_growth_pct),
    }


def _get_category_sales_performance_df(year: int, category: str) -> pd.DataFrame:
    category_filter_sql, category_filter_params = _category_filter_sql("fs.Category", category)

    sql = f"""
        SELECT
            fs.Category,
            YEAR(fs.OrderDate) AS SalesYear,
            SUM(fs.Sales) AS TotalSales,
            SUM(fs.Profit) AS TotalProfit,
            COUNT(fs.OrderID) AS Orders
        FROM cleaned.fact_sales fs
        WHERE YEAR(fs.OrderDate) IN (?, ?)
        {category_filter_sql}
        GROUP BY fs.Category, YEAR(fs.OrderDate)
        ORDER BY fs.Category, SalesYear
    """

    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params=[year - 1, year] + category_filter_params)

    if df.empty:
        return pd.DataFrame()

    rows: List[Dict[str, Any]] = []

    for cat, group in df.groupby("Category", dropna=False):
        current_row = group[group["SalesYear"] == year]
        previous_row = group[group["SalesYear"] == (year - 1)]

        current_sales = float(current_row["TotalSales"].iloc[0]) if not current_row.empty else 0.0
        previous_sales = float(previous_row["TotalSales"].iloc[0]) if not previous_row.empty else 0.0

        current_profit = float(current_row["TotalProfit"].iloc[0]) if not current_row.empty else 0.0
        previous_profit = float(previous_row["TotalProfit"].iloc[0]) if not previous_row.empty else 0.0

        current_orders = int(current_row["Orders"].iloc[0]) if not current_row.empty else 0

        sales_growth_pct = None if previous_sales == 0 else round(((current_sales - previous_sales) / previous_sales) * 100.0, 2)
        profit_growth_pct = None if previous_profit == 0 else round(((current_profit - previous_profit) / previous_profit) * 100.0, 2)

        rows.append({
            "Category": cat,
            "TotalSales": current_sales,
            "TotalProfit": current_profit,
            "Orders": current_orders,
            "SalesGrowthPct": sales_growth_pct,
            "ProfitGrowthPct": profit_growth_pct,
        })

    return pd.DataFrame(rows)


def get_summary_cards(year: int, category: str) -> Dict[str, Any]:
    sales_filter_sql, sales_filter_params = _category_filter_sql("fs.Category", category)

    sql_sales = f"""
        SELECT
            SUM(fs.Sales) AS TotalSales,
            SUM(fs.Profit) AS TotalProfit,
            COUNT(fs.OrderID) AS TotalOrders,
            CASE
                WHEN COUNT(fs.OrderID) = 0 THEN 0
                ELSE SUM(fs.Sales) * 1.0 / COUNT(fs.OrderID)
            END AS AvgOrderValue
        FROM cleaned.fact_sales fs
        WHERE YEAR(fs.OrderDate) = ?
        {sales_filter_sql}
    """

    review_filter_sql, review_filter_params = _category_filter_sql("rcm.Category", category)

    sql_reviews = f"""
        SELECT
            SUM(rcm.TotalReviews) AS TotalReviews,
            CAST(
                SUM(CAST(rcm.AvgReviewScore * rcm.TotalReviews AS float))
                / NULLIF(SUM(rcm.TotalReviews), 0)
                AS decimal(10,2)
            ) AS AvgReviewScore
        FROM analytics.review_category_monthly rcm
        WHERE YEAR(rcm.ReviewMonth) = ?
        {review_filter_sql}
    """

    forecast_filter_sql, forecast_filter_params = _category_filter_sql("pf.Category", category)

    sql_forecast = f"""
        SELECT
            SUM(pf.ForecastTransactions) AS ForecastTransactions
        FROM analytics.products_forecast pf
        WHERE YEAR(pf.SalesMonth) = (
            SELECT TOP 1 YEAR(SalesMonth)
            FROM analytics.products_forecast
            WHERE SalesMonth IS NOT NULL
            ORDER BY SalesMonth DESC
        )
        {forecast_filter_sql}
    """

    with get_conn() as conn:
        df_sales = pd.read_sql(sql_sales, conn, params=[year] + sales_filter_params)
        df_reviews = pd.read_sql(sql_reviews, conn, params=[year] + review_filter_params)
        df_forecast = pd.read_sql(sql_forecast, conn, params=forecast_filter_params)

    total_sales = float(df_sales.iloc[0]["TotalSales"] or 0) if not df_sales.empty else 0.0
    total_profit = float(df_sales.iloc[0]["TotalProfit"] or 0) if not df_sales.empty else 0.0
    total_orders = int(df_sales.iloc[0]["TotalOrders"] or 0) if not df_sales.empty else 0
    avg_order_value = float(df_sales.iloc[0]["AvgOrderValue"] or 0) if not df_sales.empty else 0.0

    total_reviews = int(df_reviews.iloc[0]["TotalReviews"] or 0) if not df_reviews.empty else 0
    avg_review_score = float(df_reviews.iloc[0]["AvgReviewScore"] or 0) if not df_reviews.empty else 0.0

    forecast_sales = float(df_forecast.iloc[0]["ForecastTransactions"] or 0) if not df_forecast.empty else 0.0
    forecast_growth_pct = round(((forecast_sales - total_orders) / total_orders) * 100, 2) if total_orders else 0.0

    return {
        "total_sales": round(total_sales, 2),
        "total_profit": round(total_profit, 2),
        "total_orders": total_orders,
        "avg_order_value": round(avg_order_value, 2),
        "avg_review_score": round(avg_review_score, 2),
        "total_reviews": total_reviews,
        "forecast_sales": round(forecast_sales, 2),
        "forecast_growth_pct": forecast_growth_pct,
    }


def get_sales_section(year: int, category: str) -> Dict[str, Any]:
    sales_filter_sql, sales_filter_params = _category_filter_sql("fs.Category", category)

    sql_kpis = f"""
        SELECT
            YEAR(fs.OrderDate) AS SalesYear,
            SUM(fs.Sales) AS TotalSales,
            SUM(fs.Profit) AS TotalProfit,
            COUNT(fs.OrderID) AS TotalOrders,
            COUNT(fs.ProductID) AS UnitsSold,
            CASE
                WHEN COUNT(fs.OrderID) = 0 THEN 0
                ELSE SUM(fs.Sales) * 1.0 / COUNT(fs.OrderID)
            END AS AvgOrderValue
        FROM cleaned.fact_sales fs
        WHERE YEAR(fs.OrderDate) IN (?, ?)
        {sales_filter_sql}
        GROUP BY YEAR(fs.OrderDate)
        ORDER BY SalesYear
    """

    with get_conn() as conn:
        df_kpis = pd.read_sql(sql_kpis, conn, params=[year - 1, year] + sales_filter_params)

    current_row = df_kpis[df_kpis["SalesYear"] == year]
    previous_row = df_kpis[df_kpis["SalesYear"] == (year - 1)]

    current = current_row.iloc[0] if not current_row.empty else {}
    previous = previous_row.iloc[0] if not previous_row.empty else {}

    current_sales = float(current.get("TotalSales", 0) or 0)
    previous_sales = float(previous.get("TotalSales", 0) or 0)
    current_profit = float(current.get("TotalProfit", 0) or 0)
    previous_profit = float(previous.get("TotalProfit", 0) or 0)

    overall_sales_growth_pct = round(((current_sales - previous_sales) / previous_sales) * 100, 2) if previous_sales else 0.0
    overall_profit_growth_pct = round(((current_profit - previous_profit) / previous_profit) * 100, 2) if previous_profit else 0.0

    perf_df = _get_category_sales_performance_df(year, category)

    if perf_df.empty:
        top_contributors: List[Dict[str, Any]] = []
        low_contributors: List[Dict[str, Any]] = []
        fastest_growing: List[Dict[str, Any]] = []
        slowest_or_declining: List[Dict[str, Any]] = []
        declining_section_title = "Most Declining Categories"
        insights = ["No category sales performance data is available for the selected filters."]
    else:
        top_contributors = [
            _format_growth_record(r)
            for r in perf_df.sort_values(["TotalSales", "Category"], ascending=[False, True]).head(TOP_N_CATEGORY_ROWS).to_dict(orient="records")
        ]

        low_contributors = [
            _format_growth_record(r)
            for r in perf_df.sort_values(["TotalSales", "Category"], ascending=[True, True]).head(TOP_N_CATEGORY_ROWS).to_dict(orient="records")
        ]

        valid_growth_df = perf_df[perf_df["SalesGrowthPct"].notna()].copy()

        fastest_growing = [
            _format_growth_record(r)
            for r in valid_growth_df.sort_values(["SalesGrowthPct", "Category"], ascending=[False, True]).head(TOP_N_CATEGORY_ROWS).to_dict(orient="records")
        ]

        negative_growth_df = valid_growth_df[valid_growth_df["SalesGrowthPct"] < 0].copy()

        if not negative_growth_df.empty:
            declining_section_title = "Most Declining Categories"
            slowest_or_declining = [
                _format_growth_record(r)
                for r in negative_growth_df.sort_values(["SalesGrowthPct", "Category"], ascending=[True, True]).head(TOP_N_CATEGORY_ROWS).to_dict(orient="records")
            ]
        else:
            declining_section_title = "Slowest Growing Categories"
            slowest_or_declining = [
                _format_growth_record(r)
                for r in valid_growth_df.sort_values(["SalesGrowthPct", "Category"], ascending=[True, True]).head(TOP_N_CATEGORY_ROWS).to_dict(orient="records")
            ]

        best_growth_text = (
            f"{fastest_growing[0]['category']} recorded the strongest year-over-year sales growth at {fastest_growing[0]['sales_growth_pct']:.2f}%."
            if fastest_growing and fastest_growing[0]["sales_growth_pct"] is not None
            else "No valid growth leader is available."
        )

        if declining_section_title == "Most Declining Categories":
            worst_growth_text = (
                f"{slowest_or_declining[0]['category']} recorded the weakest year-over-year sales growth at {slowest_or_declining[0]['sales_growth_pct']:.2f}%."
                if slowest_or_declining and slowest_or_declining[0]["sales_growth_pct"] is not None
                else "No valid declining category is available."
            )
        else:
            worst_growth_text = (
                f"{slowest_or_declining[0]['category']} recorded the slowest year-over-year sales growth at {slowest_or_declining[0]['sales_growth_pct']:.2f}%."
                if slowest_or_declining and slowest_or_declining[0]["sales_growth_pct"] is not None
                else "No valid slow-growth category is available."
            )

        insights = [
            f"Total revenue for {year} reached {current_sales:,.2f}, while total profit reached {current_profit:,.2f}.",
            f"Sales growth and profit growth in this section are calculated year-over-year by comparing {year} against {year - 1}.",
            best_growth_text,
            worst_growth_text,
        ]

    return {
        "kpis": {
            "total_sales": round(current_sales, 2),
            "total_profit": round(current_profit, 2),
            "total_orders": int(current.get("TotalOrders", 0) or 0),
                        "avg_order_value": round(float(current.get("AvgOrderValue", 0) or 0), 2),
            "sales_growth_pct": overall_sales_growth_pct,
            "profit_growth_pct": overall_profit_growth_pct,
        },
        "top_contributors": top_contributors,
        "low_contributors": low_contributors,
        "fastest_growing": fastest_growing,
        "most_declining": slowest_or_declining,
        "declining_section_title": declining_section_title,
        "insights": insights,
    }


def get_review_section(year: int, category: str) -> Dict[str, Any]:
    category_filter_sql, category_filter_params = _category_filter_sql("rcm.Category", category)

    sql_kpis = f"""
        SELECT
            SUM(rcm.TotalReviews) AS TotalReviews,
            CAST(
                SUM(CAST(rcm.AvgReviewScore * rcm.TotalReviews AS float))
                / NULLIF(SUM(rcm.TotalReviews), 0)
                AS decimal(10,2)
            ) AS AvgReviewScore,
            AVG(CAST(rcm.AvgSentimentScore AS float)) AS AvgSentimentScore,
            SUM(rcm.PositiveReviews) AS PositiveReviews,
            SUM(rcm.NeutralReviews) AS NeutralReviews,
            SUM(rcm.NegativeReviews) AS NegativeReviews
        FROM analytics.review_category_monthly rcm
        WHERE YEAR(rcm.ReviewMonth) = ?
        {category_filter_sql}
    """

    sql_topics = """
        SELECT
            rctm.Topic,
            SUM(rctm.TopicReviewCount) AS TopicCount
        FROM analytics.review_topic_category_monthly rctm
        WHERE YEAR(rctm.ReviewMonth) = ?
    """ + (" AND rctm.Category = ? " if category != "All Categories" else "") + """
        GROUP BY rctm.Topic
        ORDER BY SUM(rctm.TopicReviewCount) DESC, rctm.Topic
    """

    sql_category = f"""
        SELECT
            rcm.Category,
            CAST(
                SUM(CAST(rcm.AvgReviewScore * rcm.TotalReviews AS float))
                / NULLIF(SUM(rcm.TotalReviews), 0)
                AS decimal(10,2)
            ) AS AvgReviewScore,
            AVG(CAST(rcm.AvgSentimentScore AS float)) AS AvgSentimentScore,
            SUM(rcm.TotalReviews) AS TotalReviews
        FROM analytics.review_category_monthly rcm
        WHERE YEAR(rcm.ReviewMonth) = ?
        {category_filter_sql}
        GROUP BY rcm.Category
        ORDER BY rcm.Category
    """

    sql_dominant_topic = """
        WITH topic_ranked AS (
            SELECT
                rctm.Category,
                rctm.Topic,
                SUM(rctm.TopicReviewCount) AS TopicCount,
                ROW_NUMBER() OVER (
                    PARTITION BY rctm.Category
                    ORDER BY SUM(rctm.TopicReviewCount) DESC, rctm.Topic
                ) AS rn
            FROM analytics.review_topic_category_monthly rctm
            WHERE YEAR(rctm.ReviewMonth) = ?
        """ + (" AND rctm.Category = ? " if category != "All Categories" else "") + """
            GROUP BY rctm.Category, rctm.Topic
        )
        SELECT Category, Topic
        FROM topic_ranked
        WHERE rn = 1
    """

    with get_conn() as conn:
        df_kpis = pd.read_sql(sql_kpis, conn, params=[year] + category_filter_params)
        df_topics = pd.read_sql(sql_topics, conn, params=[year] + ([] if category == "All Categories" else [category]))
        df_category = pd.read_sql(sql_category, conn, params=[year] + category_filter_params)
        df_dom_topic = pd.read_sql(sql_dominant_topic, conn, params=[year] + ([] if category == "All Categories" else [category]))

    dom_topic_map = dict(zip(df_dom_topic["Category"], df_dom_topic["Topic"])) if not df_dom_topic.empty else {}
    if not df_category.empty:
        df_category["DominantTopic"] = df_category["Category"].map(dom_topic_map).fillna("N/A")

    row = df_kpis.iloc[0] if not df_kpis.empty else {}

    return {
        "kpis": {
            "total_reviews": int(row.get("TotalReviews", 0) or 0),
            "avg_review_score": round(float(row.get("AvgReviewScore", 0) or 0), 2),
            "avg_sentiment_score": round(float(row.get("AvgSentimentScore", 0) or 0), 2),
            "positive_reviews": int(row.get("PositiveReviews", 0) or 0),
            "neutral_reviews": int(row.get("NeutralReviews", 0) or 0),
            "negative_reviews": int(row.get("NegativeReviews", 0) or 0),
        },
        "topics": [
            {"topic": str(r["Topic"]), "count": int(r["TopicCount"] or 0)}
            for r in df_topics.to_dict(orient="records")
        ],
        "category_review_summary": [
            {
                "category": str(r["Category"]),
                "avg_review_score": round(float(r["AvgReviewScore"] or 0), 2),
                "avg_sentiment_score": round(float(r["AvgSentimentScore"] or 0), 2),
                "total_reviews": int(r["TotalReviews"] or 0),
                "dominant_topic": str(r["DominantTopic"]),
            }
            for r in df_category.to_dict(orient="records")
        ],
        "insights": [
            f"Customer reviews totaled {int(row.get('TotalReviews', 0) or 0):,} in {year}.",
            f"The weighted average review score was {float(row.get('AvgReviewScore', 0) or 0):.2f}, with an average sentiment score of {float(row.get('AvgSentimentScore', 0) or 0):.2f}.",
            f"The most discussed topic was {df_topics.iloc[0]['Topic']}." if not df_topics.empty else "No topic discussion data is available.",
        ],
    }


def get_combined_insight(year: int, category: str) -> Dict[str, Any]:
    sql = """
        SELECT
            SalesMonth,
            Category,
            Segment,
            Insight,
            BusinessRecommendation,
            TotalSales,
            AvgSentimentScore
        FROM analytics.monthly_category_segmentation
        WHERE Year = ?
    """
    params: list[Any] = [year]

    if category != "All Categories":
        sql += " AND Category = ? "
        params.append(category)

    sql += " ORDER BY SalesMonth, Category "

    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params=params)

    if df.empty:
        return {
            "window_label": "No recent-period data",
            "strong_zone": [],
            "weak_zone": [],
            "opportunity_zone": [],
            "summary_table": [],
            "insights": ["No combined sales-review insight data is available for the selected filters."],
        }

    df["SalesMonth"] = pd.to_datetime(df["SalesMonth"], errors="coerce")
    recent_months = sorted(df["SalesMonth"].dropna().unique())[-RECENT_INSIGHT_MONTHS:]
    recent_df = df[df["SalesMonth"].isin(recent_months)].copy()

    if recent_df.empty:
        return {
            "window_label": "No recent-period data",
            "strong_zone": [],
            "weak_zone": [],
            "opportunity_zone": [],
            "summary_table": [],
            "insights": ["No combined sales-review insight data is available for the selected filters."],
        }

    month_label = ", ".join(pd.to_datetime(recent_months).strftime("%Y-%m").tolist())

    grouped_rows = []
    for cat, group in recent_df.groupby("Category", dropna=False):
        segment_counts = group["Segment"].value_counts()
        dominant_segment = segment_counts.index[0] if not segment_counts.empty else "Unknown"

        latest_row = group.sort_values("SalesMonth").iloc[-1]
        recommendation_text = str(latest_row["BusinessRecommendation"]) if pd.notna(latest_row["BusinessRecommendation"]) else ""

        grouped_rows.append({
            "category": str(cat),
            "dominant_segment": dominant_segment,
            "suggested_action": recommendation_text,
        })

    result_df = pd.DataFrame(grouped_rows)

    segment_map = {
        "Strong Performer": ("High", "Strong", "Strong recent performance with healthy customer response in the recent period."),
        "Risk": ("High", "Weak", "Sales remain relatively strong, but customer sentiment is weaker and may affect future performance."),
        "Opportunity": ("Moderate", "Strong", "Customer sentiment is relatively positive, but sales are below recent benchmark and may offer growth potential."),
        "Weak": ("Low", "Weak", "Sales and customer sentiment are both weak relative to recent benchmark."),
    }

    summary_table = []
    strong_zone = []
    weak_zone = []
    opportunity_zone = []

    for _, row in result_df.iterrows():
        seg = row["dominant_segment"]
        if seg not in segment_map:
            continue

        sales_performance, review_sentiment, business_insight = segment_map[seg]

        summary_row = {
            "category": row["category"],
            "sales_performance": sales_performance,
            "review_sentiment": review_sentiment,
            "business_insight": business_insight,
            "suggested_action": row["suggested_action"],
        }
        summary_table.append(summary_row)

        zone_item = {
            "category": row["category"],
            "action": row["suggested_action"],
        }

        if seg == "Strong Performer":
            strong_zone.append(zone_item)
        elif seg in ("Risk", "Weak"):
            weak_zone.append(zone_item)
        elif seg == "Opportunity":
            opportunity_zone.append(zone_item)

    insights = [
        f"This section is based on the latest {RECENT_INSIGHT_MONTHS} months of available data: {month_label}.",
        "Using a recent multi-month window gives a more balanced picture than using one month only.",
    ]

    return {
        "window_label": month_label,
        "strong_zone": strong_zone,
        "weak_zone": weak_zone,
        "opportunity_zone": opportunity_zone,
        "summary_table": summary_table,
        "insights": insights,
    }


def get_recommendations(year: int, category: str) -> List[Dict[str, Any]]:
    sql = """
        SELECT
            SalesMonth,
            Category,
            Segment,
            BusinessRecommendation
        FROM analytics.monthly_category_segmentation
        WHERE Year = ?
    """
    params: list[Any] = [year]

    if category != "All Categories":
        sql += " AND Category = ? "
        params.append(category)

    sql += " ORDER BY SalesMonth DESC, Category "

    with get_conn() as conn:
        df = pd.read_sql(sql, conn, params=params)

    if df.empty:
        return []

    latest_month = df["SalesMonth"].max()
    latest_df = df[df["SalesMonth"] == latest_month].copy()

    priority_map = {
        "Risk": "High",
        "Opportunity": "Medium",
        "Weak": "Medium",
        "Strong Performer": "Low",
    }

    expected_map = {
        "Risk": "Protect revenue and improve customer retention",
        "Opportunity": "Unlock growth potential",
        "Weak": "Reduce underperformance risk",
        "Strong Performer": "Sustain growth momentum",
    }

    issue_map = {
        "Risk": "High sales but weak customer sentiment",
        "Opportunity": "Strong sentiment but moderate sales",
        "Weak": "Weak sales and weak customer sentiment",
        "Strong Performer": "Strong performance in both sales and customer response",
    }

    rows = []
    for r in latest_df.to_dict(orient="records"):
        segment = str(r["Segment"])
        rows.append({
            "priority": priority_map.get(segment, "Medium"),
            "category": str(r["Category"]),
            "issue_or_opportunity": issue_map.get(segment, "Business condition review"),
            "recommended_action": str(r["BusinessRecommendation"]),
            "expected_benefit": expected_map.get(segment, "Improve business performance"),
        })

    priority_order = {"High": 1, "Medium": 2, "Low": 3}
    rows.sort(key=lambda x: (priority_order.get(x["priority"], 9), x["category"]))
    return rows


def get_forecast_section(year: int, category: str) -> Dict[str, Any]:
    forecast_year = get_forecast_year()

    if forecast_year is None:
        return {
            "summary": {
                "forecast_period": "N/A",
                "forecast_sales": 0.0,
                "forecast_orders": 0,
                "forecast_growth_pct": 0.0,
            },
            "category_forecast": [],
            "product_forecast": [],
            "insights": ["No forecast data is available."],
        }

    current_filter_sql, current_filter_params = _category_filter_sql("fs.Category", category)
    forecast_filter_sql, forecast_filter_params = _category_filter_sql("sf.Category", category)
    txn_forecast_filter_sql, txn_forecast_filter_params = _category_filter_sql("pf.Category", category)

    sql_current = f"""
        SELECT
            fs.Category,
            SUM(fs.Sales) AS CurrentSales
        FROM cleaned.fact_sales fs
        WHERE YEAR(fs.OrderDate) = ?
        {current_filter_sql}
        GROUP BY fs.Category
    """

    sql_forecast = f"""
        SELECT
            sf.Category,
            SUM(sf.Sales) AS ForecastSales
        FROM analytics.sales_forecast sf
        WHERE YEAR(sf.SalesMonth) = ?
        {forecast_filter_sql}
        GROUP BY sf.Category
    """

    sql_current_txn = f"""
        SELECT
            fs.Category,
            COUNT(DISTINCT fs.OrderID) AS CurrentTransactions
        FROM cleaned.fact_sales fs
        WHERE YEAR(fs.OrderDate) = ?
        {current_filter_sql}
        GROUP BY fs.Category
    """

    sql_forecast_txn = f"""
        SELECT
            pf.Category,
            SUM(pf.ForecastTransactions) AS ForecastTransactions
        FROM analytics.products_forecast pf
        WHERE YEAR(pf.SalesMonth) = ?
        {txn_forecast_filter_sql}
        GROUP BY pf.Category
    """

    with get_conn() as conn:
        df_current = pd.read_sql(sql_current, conn, params=[year] + current_filter_params)
        df_forecast = pd.read_sql(sql_forecast, conn, params=[forecast_year] + forecast_filter_params)
        df_current_txn = pd.read_sql(sql_current_txn, conn, params=[year] + current_filter_params)
        df_forecast_txn = pd.read_sql(sql_forecast_txn, conn, params=[forecast_year] + txn_forecast_filter_params)

    df = pd.merge(df_current, df_forecast, on="Category", how="outer").fillna(0)

    if df.empty:
        return {
            "summary": {
                "forecast_period": str(forecast_year),
                "forecast_sales": 0.0,
                "forecast_orders": 0,
                "forecast_growth_pct": 0.0,
            },
            "category_forecast": [],
            "product_forecast": [],
            "insights": ["No forecast rows are available for the selected filters."],
        }

    df["ForecastChangePct"] = df.apply(
        lambda r: round(((r["ForecastSales"] - r["CurrentSales"]) / r["CurrentSales"]) * 100, 2)
        if float(r["CurrentSales"]) != 0 else (0.0 if float(r["ForecastSales"]) == 0 else 100.0),
        axis=1,
    )
    df["Trend"] = df["ForecastChangePct"].apply(_trend_label)

    forecast_total = round(float(df["ForecastSales"].sum()), 2)
    current_total = round(float(df["CurrentSales"].sum()), 2)
    growth_pct = round(((forecast_total - current_total) / current_total) * 100, 2) if current_total else 0.0

    positive_df = df.sort_values(["ForecastChangePct", "Category"], ascending=[False, True]).reset_index(drop=True)
    negative_df = df.sort_values(["ForecastChangePct", "Category"], ascending=[True, True]).reset_index(drop=True)

    insights = []
    if not positive_df.empty:
        insights.append(
            f"{positive_df.iloc[0]['Category']} shows the strongest forecast improvement at {float(positive_df.iloc[0]['ForecastChangePct']):.2f}%."
        )
    if not negative_df.empty:
        insights.append(
            f"{negative_df.iloc[0]['Category']} shows the weakest forecast direction at {float(negative_df.iloc[0]['ForecastChangePct']):.2f}%."
        )
    insights.append(f"Overall forecast growth for {forecast_year} is {growth_pct:.2f}%.")

    records = []
    for r in df.sort_values(["ForecastSales", "Category"], ascending=[False, True]).to_dict(orient="records"):
        records.append({
            "category": str(r["Category"]),
            "current_sales": round(float(r["CurrentSales"] or 0), 2),
            "forecast_sales": round(float(r["ForecastSales"] or 0), 2),
            "forecast_change_pct": round(float(r["ForecastChangePct"] or 0), 2),
            "trend": str(r["Trend"]),
        })

    txn_df = pd.merge(df_current_txn, df_forecast_txn, on="Category", how="outer").fillna(0)
    txn_df["ForecastChangePct"] = txn_df.apply(
        lambda r: round(((r["ForecastTransactions"] - r["CurrentTransactions"]) / r["CurrentTransactions"]) * 100, 2)
        if float(r["CurrentTransactions"]) != 0 else (0.0 if float(r["ForecastTransactions"]) == 0 else 100.0),
        axis=1,
    )
    txn_df["Trend"] = txn_df["ForecastChangePct"].apply(_trend_label)

    product_records = []
    for r in txn_df.sort_values(["ForecastTransactions", "Category"], ascending=[False, True]).to_dict(orient="records"):
        product_records.append({
            "category": str(r["Category"]),
            "current_transactions": round(float(r["CurrentTransactions"] or 0), 0),
            "forecast_transactions": round(float(r["ForecastTransactions"] or 0), 0),
            "forecast_change_pct": round(float(r["ForecastChangePct"] or 0), 2),
            "trend": str(r["Trend"]),
        })

    forecast_transactions_total = int(round(float(txn_df["ForecastTransactions"].sum()), 0)) if not txn_df.empty else 0

    return {
        "summary": {
            "forecast_period": str(forecast_year),
            "forecast_sales": forecast_total,
            "forecast_orders": forecast_transactions_total,
            "forecast_growth_pct": growth_pct,
        },
        "category_forecast": records,
        "product_forecast": product_records,
        "insights": insights,
    }

def generate_executive_summary(
    year: int,
    category: str,
    summary_cards: Dict[str, Any],
    sales_section: Dict[str, Any],
    review_section: Dict[str, Any],
    combined_insight: Dict[str, Any],
    forecast_section: Dict[str, Any],
) -> List[str]:
    category_text = category if category != "All Categories" else "all categories"
    weak_count = len(combined_insight.get("weak_zone", []))
    opp_count = len(combined_insight.get("opportunity_zone", []))

    top_growth = sales_section.get("fastest_growing", [])
    top_growth_text = (
        f"The strongest growth momentum came from {top_growth[0]['category']} with year-over-year sales growth of {top_growth[0]['sales_growth_pct']:.2f}%."
        if top_growth and top_growth[0]["sales_growth_pct"] is not None
        else "No valid category growth ranking was available."
    )

    return [
        f"In {year}, the business generated total sales of {summary_cards['total_sales']:,.2f} and total profit of {summary_cards['total_profit']:,.2f} for {category_text}.",
        f"Customer review performance remained at an average score of {summary_cards['avg_review_score']:.2f}, based on {summary_cards['total_reviews']:,} reviews.",
        f"The integrated analysis identified {weak_count} weak category group(s) and {opp_count} opportunity category group(s) in the recent period.",
        top_growth_text,
        f"Forecast results indicate an expected change of {forecast_section['summary']['forecast_growth_pct']:.2f}% in the next forecast year.",
    ]


def get_appendix_tables(
    sales_section: Dict[str, Any],
    review_section: Dict[str, Any],
    combined_insight: Dict[str, Any],
    recommendations: List[Dict[str, Any]],
    forecast_section: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "kpi_summary": [
            {"metric": "Total Sales", "value": sales_section["kpis"]["total_sales"]},
            {"metric": "Total Profit", "value": sales_section["kpis"]["total_profit"]},
            {"metric": "Total Orders", "value": sales_section["kpis"]["total_orders"]},
            {"metric": "Average Review Score", "value": review_section["kpis"]["avg_review_score"]},
            {"metric": "Average Sentiment Score", "value": review_section["kpis"]["avg_sentiment_score"]},
        ],
        "category_summary": combined_insight["summary_table"],
        "recommendation_details": recommendations,
        "forecast_details": forecast_section["category_forecast"],
    }