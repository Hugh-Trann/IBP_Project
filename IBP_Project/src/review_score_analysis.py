import pandas as pd
from src.db import get_conn


def load_review_category_monthly():
    sql = """
    SELECT ReviewMonth, Category, TotalReviews, AvgReviewScore, PositiveReviews, NeutralReviews, NegativeReviews
    FROM analytics.review_score_category_monthly
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn)
    df["ReviewMonth"] = pd.to_datetime(df["ReviewMonth"], errors="coerce")
    for col in ["TotalReviews", "AvgReviewScore", "PositiveReviews", "NeutralReviews", "NegativeReviews"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_review_product_monthly():
    sql = """
    SELECT ReviewMonth, ProductID, ProductName, Category, TotalReviews, AvgReviewScore, PositiveReviews, NeutralReviews, NegativeReviews
    FROM analytics.review_score_product_monthly
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn)
    df["ReviewMonth"] = pd.to_datetime(df["ReviewMonth"], errors="coerce")
    for col in ["TotalReviews", "AvgReviewScore", "PositiveReviews", "NeutralReviews", "NegativeReviews"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_sales_review_summary():
    sql = """
    SELECT Category, TotalSales, TotalTransactions, TotalReviews, AvgReviewScore
    FROM analytics.sales_review_score_summary
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn)
    for col in ["TotalSales", "TotalTransactions", "TotalReviews", "AvgReviewScore"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_review_category_summary():
    sql = """
    SELECT Category, TotalReviews, AvgReviewScore, PositiveReviews, NeutralReviews, NegativeReviews
    FROM analytics.review_score_category_summary
    """
    with get_conn() as conn:
        df = pd.read_sql(sql, conn)
    for col in ["TotalReviews", "AvgReviewScore", "PositiveReviews", "NeutralReviews", "NegativeReviews"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def add_sentiment_percentages_to_category(df):
    df = df.copy()
    df["PositivePct"] = (df["PositiveReviews"] / df["TotalReviews"] * 100).round(2)
    df["NeutralPct"] = (df["NeutralReviews"] / df["TotalReviews"] * 100).round(2)
    df["NegativePct"] = (df["NegativeReviews"] / df["TotalReviews"] * 100).round(2)
    return df


def add_sentiment_percentages_to_product_monthly(df):
    df = df.copy()
    df["PositivePct"] = (df["PositiveReviews"] / df["TotalReviews"] * 100).round(2)
    df["NeutralPct"] = (df["NeutralReviews"] / df["TotalReviews"] * 100).round(2)
    df["NegativePct"] = (df["NegativeReviews"] / df["TotalReviews"] * 100).round(2)
    return df


def analyze_category_summary(df):
    df = add_sentiment_percentages_to_category(df)
    return {
        "category_summary_with_pct": df,
        "best_categories": df.sort_values(by=["AvgReviewScore", "TotalReviews"], ascending=[False, False]).reset_index(drop=True),
        "worst_categories": df.sort_values(by=["AvgReviewScore", "TotalReviews"], ascending=[True, False]).reset_index(drop=True),
        "most_reviewed_categories": df.sort_values(by="TotalReviews", ascending=False).reset_index(drop=True),
        "highest_negative_categories": df.sort_values(by=["NegativePct", "TotalReviews"], ascending=[False, False]).reset_index(drop=True),
    }


def analyze_category_monthly_trend(df):
    df = add_sentiment_percentages_to_category(df)
    monthly_overall = (
        df.groupby("ReviewMonth", as_index=False)
        .agg(TotalReviews=("TotalReviews", "sum"), PositiveReviews=("PositiveReviews", "sum"), NeutralReviews=("NeutralReviews", "sum"), NegativeReviews=("NegativeReviews", "sum"), AvgReviewScore=("AvgReviewScore", "mean"))
        .sort_values("ReviewMonth")
    )
    monthly_overall["AvgReviewScore"] = monthly_overall["AvgReviewScore"].round(2)
    monthly_overall["PositivePct"] = (monthly_overall["PositiveReviews"] / monthly_overall["TotalReviews"] * 100).round(2)
    monthly_overall["NegativePct"] = (monthly_overall["NegativeReviews"] / monthly_overall["TotalReviews"] * 100).round(2)
    top_category_by_month = df.sort_values(by=["ReviewMonth", "AvgReviewScore", "TotalReviews"], ascending=[True, False, False]).groupby("ReviewMonth", as_index=False).first()
    worst_category_by_month = df.sort_values(by=["ReviewMonth", "AvgReviewScore", "TotalReviews"], ascending=[True, True, False]).groupby("ReviewMonth", as_index=False).first()
    return {"monthly_overall": monthly_overall, "top_category_by_month": top_category_by_month, "worst_category_by_month": worst_category_by_month}


def analyze_product_monthly_summary(df, min_reviews=5):
    df = add_sentiment_percentages_to_product_monthly(df)
    filtered_df = df[df["TotalReviews"] >= min_reviews].copy()
    return {
        "product_monthly_with_pct": filtered_df,
        "best_products": filtered_df.sort_values(by=["AvgReviewScore", "TotalReviews"], ascending=[False, False]).reset_index(drop=True),
        "worst_products": filtered_df.sort_values(by=["AvgReviewScore", "TotalReviews"], ascending=[True, False]).reset_index(drop=True),
        "most_reviewed_products": filtered_df.sort_values(by="TotalReviews", ascending=False).reset_index(drop=True),
        "highest_negative_products": filtered_df.sort_values(by=["NegativePct", "TotalReviews"], ascending=[False, False]).reset_index(drop=True),
    }


def summarize_product_performance_across_months(df, min_total_reviews=10):
    summary = df.groupby(["ProductID", "ProductName", "Category"], as_index=False).agg(TotalReviews=("TotalReviews", "sum"), PositiveReviews=("PositiveReviews", "sum"), NeutralReviews=("NeutralReviews", "sum"), NegativeReviews=("NegativeReviews", "sum"), AvgReviewScore=("AvgReviewScore", "mean"))
    summary = summary[summary["TotalReviews"] >= min_total_reviews].copy()
    summary["PositivePct"] = (summary["PositiveReviews"] / summary["TotalReviews"] * 100).round(2)
    summary["NegativePct"] = (summary["NegativeReviews"] / summary["TotalReviews"] * 100).round(2)
    return {"summary": summary, "best_products_overall": summary.sort_values(by=["AvgReviewScore", "TotalReviews"], ascending=[False, False]).reset_index(drop=True), "worst_products_overall": summary.sort_values(by=["AvgReviewScore", "TotalReviews"], ascending=[True, False]).reset_index(drop=True)}


def analyze_sales_review_relationship(df):
    working_df = df.copy().dropna(subset=["TotalSales", "TotalTransactions", "TotalReviews", "AvgReviewScore"])
    sales_review_corr = working_df["TotalSales"].corr(working_df["AvgReviewScore"]) if len(working_df) > 1 else None
    transaction_review_corr = working_df["TotalTransactions"].corr(working_df["AvgReviewScore"]) if len(working_df) > 1 else None
    sales_reviews_count_corr = working_df["TotalSales"].corr(working_df["TotalReviews"]) if len(working_df) > 1 else None
    result = {
        "Sales_vs_ReviewScore_Correlation": None if sales_review_corr is None else round(float(sales_review_corr), 4),
        "Transactions_vs_ReviewScore_Correlation": None if transaction_review_corr is None else round(float(transaction_review_corr), 4),
        "Sales_vs_TotalReviews_Correlation": None if sales_reviews_count_corr is None else round(float(sales_reviews_count_corr), 4),
    }
    low_score_high_sales_products = working_df[(working_df["AvgReviewScore"] <= 3.0) & (working_df["TotalSales"] > working_df["TotalSales"].median())].sort_values(by=["TotalSales", "AvgReviewScore"], ascending=[False, True]).reset_index(drop=True)
    return {"correlations": result, "low_score_high_sales_products": low_score_high_sales_products}


def build_review_kpi_summary(review_category_df, sales_review_df):
    total_reviews = int(review_category_df["TotalReviews"].sum()) if not review_category_df.empty else 0
    total_positive = int(review_category_df["PositiveReviews"].sum()) if not review_category_df.empty else 0
    total_neutral = int(review_category_df["NeutralReviews"].sum()) if not review_category_df.empty else 0
    total_negative = int(review_category_df["NegativeReviews"].sum()) if not review_category_df.empty else 0
    total_sales = round(float(sales_review_df["TotalSales"].sum()), 2) if not sales_review_df.empty else 0.0
    total_transaction = int(sales_review_df["TotalTransactions"].sum()) if not sales_review_df.empty else 0
    weighted_avg_score = 0.0
    if not review_category_df.empty and total_reviews:
        weighted_avg_score = round(float((review_category_df["AvgReviewScore"] * review_category_df["TotalReviews"]).sum()) / total_reviews, 2)
    positive_pct = round((total_positive / total_reviews) * 100, 2) if total_reviews else 0.0
    negative_pct = round((total_negative / total_reviews) * 100, 2) if total_reviews else 0.0
    return {"TotalReviews": total_reviews, "WeightedAvgReviewScore": weighted_avg_score, "PositiveReviews": total_positive, "NeutralReviews": total_neutral, "NegativeReviews": total_negative, "PositivePct": positive_pct, "NegativePct": negative_pct, "TotalSales": total_sales, "TotalTransactions": total_transaction}


def run_review_summary_analysis():
    review_category_monthly_df = load_review_category_monthly()
    review_product_monthly_df = load_review_product_monthly()
    sales_review_df = load_sales_review_summary()
    review_category_df = load_review_category_summary()
    category_summary_results = analyze_category_summary(review_category_df)
    category_monthly_results = analyze_category_monthly_trend(review_category_monthly_df)
    product_monthly_results = analyze_product_monthly_summary(review_product_monthly_df, min_reviews=5)
    product_overall_results = summarize_product_performance_across_months(review_product_monthly_df, min_total_reviews=10)
    sales_review_results = analyze_sales_review_relationship(sales_review_df)
    kpi_summary = build_review_kpi_summary(review_category_df, sales_review_df)
    return {"kpi_summary": kpi_summary, "category_summary_results": category_summary_results, "category_monthly_results": category_monthly_results, "product_monthly_results": product_monthly_results, "product_overall_results": product_overall_results, "sales_review_results": sales_review_results}


if __name__ == "__main__":
    results = run_review_summary_analysis()
    print(results["kpi_summary"])
