import pandas as pd
from src.db import get_conn


def load_sales_review_category_combined():
    sql = """
    SELECT
        SalesMonth,
        Category,
        TotalSales,
        TotalTransactions,
        ReviewMonth,
        TotalReviews,
        AvgSentimentScore,
        PositiveReviews,
        NeutralReviews,
        NegativeReviews,
        AvgReviewScore,
        AvgTopicCount,
        ReviewImpactScore
    FROM analytics.sales_review_category_combined
    ORDER BY SalesMonth, Category
    """
    with get_conn() as conn:
        return pd.read_sql(sql, conn)


def clean_data(df):
    df = df.copy()
    df["SalesMonth"] = pd.to_datetime(df["SalesMonth"], errors="coerce")
    df["ReviewMonth"] = pd.to_datetime(df["ReviewMonth"], errors="coerce")
    return df


def get_season(month_number):
    if month_number in [12, 1, 2]:
        return "Winter"
    elif month_number in [3, 4, 5]:
        return "Spring"
    elif month_number in [6, 7, 8]:
        return "Summer"
    else:
        return "Fall"


def add_time_columns(df):
    df = df.copy()
    df["Year"] = df["SalesMonth"].dt.year
    df["MonthNumber"] = df["SalesMonth"].dt.month
    df["MonthName"] = df["SalesMonth"].dt.strftime("%b")
    df["YearMonth"] = df["SalesMonth"].dt.strftime("%Y-%m")
    df["Season"] = df["MonthNumber"].apply(get_season)
    return df


def classify_category_month(row, sales_threshold, sentiment_threshold):
    total_sales = row["TotalSales"]
    avg_sentiment = row["AvgSentimentScore"]

    if pd.isna(total_sales) or pd.isna(avg_sentiment):
        return "Insufficient Data"
    if total_sales >= sales_threshold and avg_sentiment >= sentiment_threshold:
        return "Strong Performer"
    elif total_sales >= sales_threshold and avg_sentiment < sentiment_threshold:
        return "Risk"
    elif total_sales < sales_threshold and avg_sentiment >= sentiment_threshold:
        return "Opportunity"
    else:
        return "Weak"


def segment_by_month(df):
    df = df.copy()
    result_list = []

    for sales_month, group in df.groupby("SalesMonth"):
        month_data = group.copy()
        sales_threshold = month_data["TotalSales"].median()
        sentiment_threshold = month_data["AvgSentimentScore"].median()

        month_data["SalesThreshold"] = sales_threshold
        month_data["SentimentThreshold"] = sentiment_threshold
        month_data["Segment"] = month_data.apply(
            lambda row: classify_category_month(row, sales_threshold, sentiment_threshold),
            axis=1,
        )
        result_list.append(month_data)

    return pd.concat(result_list, ignore_index=True) if result_list else df


def safe_divide(numerator, denominator):
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return None
    return numerator / denominator


def add_kpis(df):
    df = df.copy()
    df["PositiveReviewRatio"] = df.apply(lambda row: safe_divide(row["PositiveReviews"], row["TotalReviews"]), axis=1)
    df["NegativeReviewRatio"] = df.apply(lambda row: safe_divide(row["NegativeReviews"], row["TotalReviews"]), axis=1)
    df["NeutralReviewRatio"] = df.apply(lambda row: safe_divide(row["NeutralReviews"], row["TotalReviews"]), axis=1)
    df["SalesPerTransaction"] = df.apply(lambda row: safe_divide(row["TotalSales"], row["TotalTransactions"]), axis=1)
    df["SalesPerReview"] = df.apply(lambda row: safe_divide(row["TotalSales"], row["TotalReviews"]), axis=1)
    return df


def generate_insight(row):
    month_text = row["YearMonth"]
    category = row["Category"]
    season = row["Season"]
    segment = row["Segment"]

    if segment == "Strong Performer":
        return (
            f"In {month_text}, {category} was a strong performer in {season}. "
            f"It showed high sales and positive customer sentiment compared with other categories in the same month."
        )
    elif segment == "Risk":
        return (
            f"In {month_text}, {category} was classified as risk in {season}. "
            f"It achieved relatively high sales, but customer sentiment was weaker than the monthly benchmark."
        )
    elif segment == "Opportunity":
        return (
            f"In {month_text}, {category} was identified as an opportunity in {season}. "
            f"Customer sentiment was relatively positive, but sales were below the monthly benchmark."
        )
    elif segment == "Weak":
        return (
            f"In {month_text}, {category} was weak in {season}. "
            f"Both sales and customer sentiment were below the monthly benchmark."
        )
    else:
        return f"In {month_text}, {category} did not have enough valid data for business interpretation."


def add_insight(df):
    df = df.copy()
    df["Insight"] = df.apply(generate_insight, axis=1)
    return df


def generate_business_recommendation(row):
    month_text = row["YearMonth"]
    category = row["Category"]
    segment = row["Segment"]
    season = row["Season"]

    if segment == "Strong Performer":
        return (
            f"For {category} in {month_text} ({season}), maintain current strategy, "
            f"protect product availability, and consider stronger promotion during similar seasonal periods."
        )
    elif segment == "Risk":
        return (
            f"For {category} in {month_text} ({season}), review customer feedback, "
            f"investigate possible quality or service issues, and monitor whether weak sentiment affects future sales."
        )
    elif segment == "Opportunity":
        return (
            f"For {category} in {month_text} ({season}), customer response was relatively positive, "
            f"so stronger promotion, better visibility, or targeted campaigns may help improve sales."
        )
    elif segment == "Weak":
        return (
            f"For {category} in {month_text} ({season}), review both commercial performance and customer feedback carefully "
            f"before increasing investment or expanding activity."
        )
    else:
        return f"For {category} in {month_text} ({season}), there is not enough data to generate a reliable recommendation."


def add_business_recommendation(df):
    df = df.copy()
    df["BusinessRecommendation"] = df.apply(generate_business_recommendation, axis=1)
    return df


def ensure_segmentation_table(conn):
    cursor = conn.cursor()
    cursor.execute("""
    IF OBJECT_ID('analytics.monthly_category_segmentation', 'U') IS NULL
    CREATE TABLE analytics.monthly_category_segmentation (
        SalesMonth DATE NULL,
        ReviewMonth DATE NULL,
        [Year] INT NULL,
        MonthNumber INT NULL,
        MonthName NVARCHAR(20) NULL,
        YearMonth NVARCHAR(20) NULL,
        Season NVARCHAR(20) NULL,
        Category NVARCHAR(100) NULL,
        TotalSales FLOAT NULL,
        TotalTransactions FLOAT NULL,
        TotalReviews FLOAT NULL,
        AvgSentimentScore FLOAT NULL,
        PositiveReviews FLOAT NULL,
        NeutralReviews FLOAT NULL,
        NegativeReviews FLOAT NULL,
        AvgReviewScore FLOAT NULL,
        AvgTopicCount FLOAT NULL,
        ReviewImpactScore FLOAT NULL,
        SalesThreshold FLOAT NULL,
        SentimentThreshold FLOAT NULL,
        Segment NVARCHAR(50) NULL,
        PositiveReviewRatio FLOAT NULL,
        NegativeReviewRatio FLOAT NULL,
        NeutralReviewRatio FLOAT NULL,
        SalesPerTransaction FLOAT NULL,
        SalesPerReview FLOAT NULL,
        Insight NVARCHAR(MAX) NULL,
        BusinessRecommendation NVARCHAR(MAX) NULL
    )
    """)
    conn.commit()
    cursor.close()


def save_to_sql(df):
    with get_conn() as conn:
        ensure_segmentation_table(conn)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM analytics.monthly_category_segmentation")

        insert_sql = """
        INSERT INTO analytics.monthly_category_segmentation (
            SalesMonth, ReviewMonth, [Year], MonthNumber, MonthName, YearMonth, Season, Category,
            TotalSales, TotalTransactions, TotalReviews, AvgSentimentScore, PositiveReviews, NeutralReviews,
            NegativeReviews, AvgReviewScore, AvgTopicCount, ReviewImpactScore, SalesThreshold,
            SentimentThreshold, Segment, PositiveReviewRatio, NegativeReviewRatio, NeutralReviewRatio,
            SalesPerTransaction, SalesPerReview, Insight, BusinessRecommendation
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        for _, row in df.iterrows():
            cursor.execute(insert_sql, (
                row["SalesMonth"] if pd.notna(row["SalesMonth"]) else None,
                row["ReviewMonth"] if pd.notna(row["ReviewMonth"]) else None,
                int(row["Year"]) if pd.notna(row["Year"]) else None,
                int(row["MonthNumber"]) if pd.notna(row["MonthNumber"]) else None,
                row["MonthName"],
                row["YearMonth"],
                row["Season"],
                row["Category"],
                float(row["TotalSales"]) if pd.notna(row["TotalSales"]) else None,
                float(row["TotalTransactions"]) if pd.notna(row["TotalTransactions"]) else None,
                float(row["TotalReviews"]) if pd.notna(row["TotalReviews"]) else None,
                float(row["AvgSentimentScore"]) if pd.notna(row["AvgSentimentScore"]) else None,
                float(row["PositiveReviews"]) if pd.notna(row["PositiveReviews"]) else None,
                float(row["NeutralReviews"]) if pd.notna(row["NeutralReviews"]) else None,
                float(row["NegativeReviews"]) if pd.notna(row["NegativeReviews"]) else None,
                float(row["AvgReviewScore"]) if pd.notna(row["AvgReviewScore"]) else None,
                float(row["AvgTopicCount"]) if pd.notna(row["AvgTopicCount"]) else None,
                float(row["ReviewImpactScore"]) if pd.notna(row["ReviewImpactScore"]) else None,
                float(row["SalesThreshold"]) if pd.notna(row["SalesThreshold"]) else None,
                float(row["SentimentThreshold"]) if pd.notna(row["SentimentThreshold"]) else None,
                row["Segment"],
                float(row["PositiveReviewRatio"]) if pd.notna(row["PositiveReviewRatio"]) else None,
                float(row["NegativeReviewRatio"]) if pd.notna(row["NegativeReviewRatio"]) else None,
                float(row["NeutralReviewRatio"]) if pd.notna(row["NeutralReviewRatio"]) else None,
                float(row["SalesPerTransaction"]) if pd.notna(row["SalesPerTransaction"]) else None,
                float(row["SalesPerReview"]) if pd.notna(row["SalesPerReview"]) else None,
                row["Insight"],
                row["BusinessRecommendation"],
            ))

        conn.commit()
        cursor.close()


def run_business_recommendation_pipeline():
    df = load_sales_review_category_combined()
    if df.empty:
        return {"rows_saved": 0}

    df = clean_data(df)
    df = add_time_columns(df)
    df = segment_by_month(df)
    df = add_kpis(df)
    df = add_insight(df)
    df = add_business_recommendation(df)
    save_to_sql(df)
    return {"rows_saved": int(len(df))}


if __name__ == "__main__":
    result = run_business_recommendation_pipeline()
    print(result)
