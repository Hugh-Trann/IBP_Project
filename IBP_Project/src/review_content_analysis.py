import math
import re

import numpy as np
import pandas as pd
from nltk.sentiment import SentimentIntensityAnalyzer
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from src.db import get_conn


def load_review_data(conn):
    sql = """
        SELECT
            ProductID,
            ProductName,
            UserID,
            ReviewDate,
            ReviewScore,
            ReviewContent,
            Category
        FROM analytics.customer_review_matched
    """
    return pd.read_sql(sql, conn)


def load_sales_data(conn):
    sql = """
        SELECT
            CAST(SalesMonth AS date) AS SalesMonth,
            Category,
            SUM(TotalSales) AS TotalSales,
            SUM(TotalTransactions) AS TotalTransactions
        FROM analytics.products_transactions
        GROUP BY CAST(SalesMonth AS date), Category
        ORDER BY CAST(SalesMonth AS date), Category
    """
    df = pd.read_sql(sql, conn)
    df["SalesMonth"] = pd.to_datetime(df["SalesMonth"], errors="coerce")
    return df


def standardize_category_value(x):
    if pd.isna(x):
        return None
    x = str(x).strip().lower()
    x = x.replace("&", "and")
    x = x.replace(",", "")
    x = re.sub(r"\s+", " ", x)
    return x


def clean_text(text):
    if pd.isna(text):
        return ""
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+|https\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


sia = SentimentIntensityAnalyzer()

TOPIC_LABELS = [
    "Price",
    "Quality",
    "Delivery",
    "Packaging",
    "Customer Service",
    "Usability",
    "Availability",
]

TOPIC_DESCRIPTIONS = [
    "comments about price, cost, expensive, cheap, affordability, value for money",
    "comments about quality, taste, freshness, defect, broken, damaged product",
    "comments about delivery, shipping, late arrival, delay, slow delivery",
    "comments about packaging, box, bottle, leaking, seal, damaged package",
    "comments about customer service, support, refund, return, seller response",
    "comments about using the product, instructions, setup, convenient, easy to use",
    "comments about stock, availability, out of stock, unavailable item",
]

model = SentenceTransformer("all-MiniLM-L6-v2")
topic_embeddings = model.encode(TOPIC_DESCRIPTIONS)


def get_sentiment_score(text):
    if not text:
        return 0.0
    return round(sia.polarity_scores(text)["compound"], 4)


def get_sentiment_label(score):
    if score > 0.05:
        return "Positive"
    if score < -0.05:
        return "Negative"
    return "Neutral"


def classify_topics_bert(text, threshold=0.35, top_n=3):
    if not text:
        return [("Other", 0.0)]

    review_embedding = model.encode([text])
    scores = cosine_similarity(review_embedding, topic_embeddings)[0]

    topic_score_pairs = []
    for label, score in zip(TOPIC_LABELS, scores):
        topic_score_pairs.append((label, round(float(score), 4)))

    topic_score_pairs = sorted(topic_score_pairs, key=lambda x: x[1], reverse=True)
    selected_topics = [pair for pair in topic_score_pairs if pair[1] >= threshold][:top_n]

    if not selected_topics:
        return [("Other", 0.0)]

    return selected_topics


def get_topic_names(topic_score_list):
    return [item[0] for item in topic_score_list]


def get_topic_scores(topic_score_list):
    return [item[1] for item in topic_score_list]


def get_primary_topic(topic_score_list):
    if not topic_score_list:
        return "Other"
    return topic_score_list[0][0]


def get_primary_topic_score(topic_score_list):
    if not topic_score_list:
        return 0.0
    return topic_score_list[0][1]


def analyze_reviews(df):
    df = df.copy()
    df["CleanReviewText"] = df["ReviewContent"].fillna("").astype(str).apply(clean_text)
    df["SentimentScore"] = df["CleanReviewText"].apply(get_sentiment_score)
    df["SentimentLabel"] = df["SentimentScore"].apply(get_sentiment_label)
    df["TopicResults"] = df["CleanReviewText"].apply(
        lambda x: classify_topics_bert(x, threshold=0.35, top_n=3)
    )
    df["Topics"] = df["TopicResults"].apply(get_topic_names)
    df["TopicScores"] = df["TopicResults"].apply(get_topic_scores)
    df["PrimaryTopic"] = df["TopicResults"].apply(get_primary_topic)
    df["PrimaryTopicScore"] = df["TopicResults"].apply(get_primary_topic_score)
    df["TopicsText"] = df["Topics"].apply(lambda x: ", ".join(x))
    df["TopicScoresText"] = df["TopicScores"].apply(lambda x: ", ".join([str(i) for i in x]))
    df["TopicCount"] = df["Topics"].apply(len)
    df["ReviewDate"] = pd.to_datetime(df["ReviewDate"], errors="coerce")
    df["ReviewMonth"] = df["ReviewDate"].dt.to_period("M").dt.to_timestamp()
    df["Category"] = df["Category"].apply(standardize_category_value)
    return df


def explode_review_topics(df_reviews):
    rows = []
    for _, row in df_reviews.iterrows():
        for topic, score in zip(row["Topics"], row["TopicScores"]):
            rows.append({
                "ProductID": row.get("ProductID"),
                "ProductName": row.get("ProductName"),
                "UserID": row.get("UserID"),
                "ReviewDate": row.get("ReviewDate"),
                "ReviewMonth": row.get("ReviewMonth"),
                "ReviewScore": row.get("ReviewScore"),
                "Category": row.get("Category"),
                "ReviewContent": row.get("ReviewContent"),
                "CleanReviewText": row.get("CleanReviewText"),
                "SentimentScore": row.get("SentimentScore"),
                "SentimentLabel": row.get("SentimentLabel"),
                "Topic": topic,
                "TopicSimilarityScore": score,
            })
    return pd.DataFrame(rows)


def create_review_category_monthly(df_reviews):
    df = df_reviews.copy()
    df["ReviewMonth"] = pd.to_datetime(df["ReviewMonth"], errors="coerce")
    df["Category"] = df["Category"].apply(standardize_category_value)

    summary = (
        df.groupby(["ReviewMonth", "Category"], dropna=False)
        .agg(
            TotalReviews=("ReviewContent", "count"),
            AvgSentimentScore=("SentimentScore", "mean"),
            PositiveReviews=("SentimentLabel", lambda x: (x == "Positive").sum()),
            NeutralReviews=("SentimentLabel", lambda x: (x == "Neutral").sum()),
            NegativeReviews=("SentimentLabel", lambda x: (x == "Negative").sum()),
            AvgReviewScore=("ReviewScore", "mean"),
            AvgTopicCount=("TopicCount", "mean"),
        )
        .reset_index()
    )

    summary["AvgSentimentScore"] = summary["AvgSentimentScore"].round(4)
    summary["AvgReviewScore"] = summary["AvgReviewScore"].round(4)
    summary["AvgTopicCount"] = summary["AvgTopicCount"].round(2)
    return summary


def create_review_topic_category_monthly(df_topic):
    df = df_topic.copy()
    df["ReviewMonth"] = pd.to_datetime(df["ReviewMonth"], errors="coerce")
    df["Category"] = df["Category"].apply(standardize_category_value)

    summary = (
        df.groupby(["ReviewMonth", "Category", "Topic"], dropna=False)
        .agg(
            TopicReviewCount=("Topic", "count"),
            AvgTopicSentimentScore=("SentimentScore", "mean"),
            AvgTopicSimilarityScore=("TopicSimilarityScore", "mean"),
            PositiveTopicReviews=("SentimentLabel", lambda x: (x == "Positive").sum()),
            NeutralTopicReviews=("SentimentLabel", lambda x: (x == "Neutral").sum()),
            NegativeTopicReviews=("SentimentLabel", lambda x: (x == "Negative").sum()),
        )
        .reset_index()
    )

    summary["AvgTopicSentimentScore"] = summary["AvgTopicSentimentScore"].round(4)
    summary["AvgTopicSimilarityScore"] = summary["AvgTopicSimilarityScore"].round(4)
    return summary


def merge_sales_review_category_monthly(df_sales, df_review_category_monthly):
    sales = df_sales.copy()
    reviews = df_review_category_monthly.copy()
    sales["SalesMonth"] = pd.to_datetime(sales["SalesMonth"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    reviews["ReviewMonth"] = pd.to_datetime(reviews["ReviewMonth"], errors="coerce").dt.to_period("M").dt.to_timestamp()
    sales["Category"] = sales["Category"].apply(standardize_category_value)
    reviews["Category"] = reviews["Category"].apply(standardize_category_value)

    return pd.merge(
        sales,
        reviews,
        left_on=["Category", "SalesMonth"],
        right_on=["Category", "ReviewMonth"],
        how="left",
    )


def keep_only_matched_rows(df_combined):
    return df_combined[df_combined["ReviewMonth"].notna()].copy()


def create_category_review_impact_score(df):
    df = df.copy()
    df["ReviewImpactScore"] = (
        (df["AvgSentimentScore"].fillna(0) * 0.7) +
        (df["TotalReviews"].fillna(0) * 0.3)
    ) * 100
    df["ReviewImpactScore"] = df["ReviewImpactScore"].round(2)
    return df


def calculate_category_correlations(df_combined):
    df = df_combined.copy()
    feature_cols = [
        "AvgSentimentScore",
        "TotalReviews",
        "NegativeReviews",
        "PositiveReviews",
        "AvgReviewScore",
    ]
    all_results = []

    for category in df["Category"].dropna().unique():
        df_cat = df[df["Category"] == category]
        for col in feature_cols:
            valid_df = df_cat[["TotalSales", col]].dropna()
            corr = round(valid_df["TotalSales"].corr(valid_df[col]), 4) if len(valid_df) > 1 else None
            all_results.append({
                "Category": category,
                "Metric": f"TotalSales_vs_{col}",
                "Correlation": corr,
            })

    return pd.DataFrame(all_results)


def ensure_runtime_tables(conn):
    cursor = conn.cursor()
    cursor.execute("""
    IF OBJECT_ID('analytics.review_processed', 'U') IS NULL
    CREATE TABLE analytics.review_processed (
        ProductID NVARCHAR(50) NULL,
        ProductName NVARCHAR(255) NULL,
        UserID NVARCHAR(50) NULL,
        ReviewDate DATE NULL,
        ReviewMonth DATE NULL,
        ReviewScore FLOAT NULL,
        Category NVARCHAR(100) NULL,
        ReviewContent NVARCHAR(MAX) NULL,
        CleanReviewText NVARCHAR(MAX) NULL,
        SentimentScore FLOAT NULL,
        SentimentLabel NVARCHAR(20) NULL,
        PrimaryTopic NVARCHAR(100) NULL,
        PrimaryTopicScore FLOAT NULL,
        TopicsText NVARCHAR(1000) NULL,
        TopicScoresText NVARCHAR(1000) NULL,
        TopicCount INT NULL
    );

    IF OBJECT_ID('analytics.review_topic_detail', 'U') IS NULL
    CREATE TABLE analytics.review_topic_detail (
        ProductID NVARCHAR(50) NULL,
        ProductName NVARCHAR(255) NULL,
        UserID NVARCHAR(50) NULL,
        ReviewDate DATE NULL,
        ReviewMonth DATE NULL,
        ReviewScore FLOAT NULL,
        Category NVARCHAR(100) NULL,
        ReviewContent NVARCHAR(MAX) NULL,
        CleanReviewText NVARCHAR(MAX) NULL,
        SentimentScore FLOAT NULL,
        SentimentLabel NVARCHAR(20) NULL,
        Topic NVARCHAR(100) NULL,
        TopicSimilarityScore FLOAT NULL
    );

    IF OBJECT_ID('analytics.review_category_monthly', 'U') IS NULL
    CREATE TABLE analytics.review_category_monthly (
        ReviewMonth DATE NULL,
        Category NVARCHAR(100) NULL,
        TotalReviews INT NULL,
        AvgSentimentScore FLOAT NULL,
        PositiveReviews INT NULL,
        NeutralReviews INT NULL,
        NegativeReviews INT NULL,
        AvgReviewScore FLOAT NULL,
        AvgTopicCount FLOAT NULL
    );

    IF OBJECT_ID('analytics.review_topic_category_monthly', 'U') IS NULL
    CREATE TABLE analytics.review_topic_category_monthly (
        ReviewMonth DATE NULL,
        Category NVARCHAR(100) NULL,
        Topic NVARCHAR(100) NULL,
        TopicReviewCount INT NULL,
        AvgTopicSentimentScore FLOAT NULL,
        AvgTopicSimilarityScore FLOAT NULL,
        PositiveTopicReviews INT NULL,
        NeutralTopicReviews INT NULL,
        NegativeTopicReviews INT NULL
    );

    IF OBJECT_ID('analytics.sales_review_category_combined', 'U') IS NULL
    CREATE TABLE analytics.sales_review_category_combined (
        SalesMonth DATE NULL,
        Category NVARCHAR(100) NULL,
        TotalSales FLOAT NULL,
        TotalTransactions FLOAT NULL,
        ReviewMonth DATE NULL,
        TotalReviews INT NULL,
        AvgSentimentScore FLOAT NULL,
        PositiveReviews INT NULL,
        NeutralReviews INT NULL,
        NegativeReviews INT NULL,
        AvgReviewScore FLOAT NULL,
        AvgTopicCount FLOAT NULL,
        ReviewImpactScore FLOAT NULL
    );

    IF OBJECT_ID('analytics.review_sales_correlation', 'U') IS NULL
    CREATE TABLE analytics.review_sales_correlation (
        Category VARCHAR(50) NULL,
        Metric NVARCHAR(200) NULL,
        Correlation FLOAT NULL
    );
    """)
    conn.commit()
    cursor.close()


def clear_runtime_tables(conn):
    cursor = conn.cursor()
    for table in [
        "analytics.review_processed",
        "analytics.review_topic_detail",
        "analytics.review_category_monthly",
        "analytics.review_topic_category_monthly",
        "analytics.sales_review_category_combined",
        "analytics.review_sales_correlation",
    ]:
        cursor.execute(f"DELETE FROM {table};")
    conn.commit()
    cursor.close()


def clean_value_for_sql(x):
    if pd.isna(x):
        return None
    if isinstance(x, pd.Timestamp):
        return x.to_pydatetime()
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        x = float(x)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    return x


def save_dataframe_to_sql(conn, df, table_name):
    cursor = conn.cursor()
    cols = list(df.columns)
    placeholders = ", ".join(["?" for _ in cols])
    col_names = ", ".join(cols)
    insert_sql = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"

    for row in df.itertuples(index=False, name=None):
        clean_row = tuple(clean_value_for_sql(x) for x in row)
        cursor.execute(insert_sql, clean_row)

    conn.commit()
    cursor.close()


def prepare_combined_for_save(df):
    df = df.copy()

    count_cols = ["TotalReviews", "PositiveReviews", "NeutralReviews", "NegativeReviews"]
    float_cols = [
        "TotalSales",
        "TotalTransactions",
        "AvgSentimentScore",
        "AvgReviewScore",
        "AvgTopicCount",
        "ReviewImpactScore",
    ]
    date_cols = ["SalesMonth", "ReviewMonth"]

    for col in count_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df = df.replace([np.inf, -np.inf], np.nan)
    return df


def save_sales_review_category_combined(conn, df):
    cursor = conn.cursor()
    insert_sql = """
    INSERT INTO analytics.sales_review_category_combined (
        SalesMonth, Category, TotalSales, TotalTransactions, ReviewMonth,
        TotalReviews, AvgSentimentScore, PositiveReviews, NeutralReviews,
        NegativeReviews, AvgReviewScore, AvgTopicCount, ReviewImpactScore
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for row in df.itertuples(index=False, name=None):
        clean_row = tuple(clean_value_for_sql(x) for x in row)
        cursor.execute(insert_sql, clean_row)

    conn.commit()
    cursor.close()


def run_review_content_pipeline():
    with get_conn() as conn:
        ensure_runtime_tables(conn)
        clear_runtime_tables(conn)

        df_reviews_raw = load_review_data(conn)
        df_sales = load_sales_data(conn)

        if df_reviews_raw.empty or df_sales.empty:
            return {"review_rows": 0, "combined_rows": 0}

        df_reviews_processed = analyze_reviews(df_reviews_raw)
        df_topic_detail = explode_review_topics(df_reviews_processed)
        df_review_category_monthly = create_review_category_monthly(df_reviews_processed)
        df_topic_category_monthly = create_review_topic_category_monthly(df_topic_detail)
        df_combined = merge_sales_review_category_monthly(df_sales, df_review_category_monthly)
        df_combined = keep_only_matched_rows(df_combined)
        df_combined = create_category_review_impact_score(df_combined)
        df_corr = calculate_category_correlations(df_combined)

        save_dataframe_to_sql(
            conn,
            df_reviews_processed[
                [
                    "ProductID", "ProductName", "UserID", "ReviewDate", "ReviewMonth",
                    "ReviewScore", "Category", "ReviewContent", "CleanReviewText",
                    "SentimentScore", "SentimentLabel", "PrimaryTopic", "PrimaryTopicScore",
                    "TopicsText", "TopicScoresText", "TopicCount",
                ]
            ],
            "analytics.review_processed",
        )

        save_dataframe_to_sql(conn, df_topic_detail, "analytics.review_topic_detail")
        save_dataframe_to_sql(conn, df_review_category_monthly, "analytics.review_category_monthly")
        save_dataframe_to_sql(conn, df_topic_category_monthly, "analytics.review_topic_category_monthly")

        save_cols = [
            "SalesMonth", "Category", "TotalSales", "TotalTransactions", "ReviewMonth",
            "TotalReviews", "AvgSentimentScore", "PositiveReviews", "NeutralReviews",
            "NegativeReviews", "AvgReviewScore", "AvgTopicCount", "ReviewImpactScore",
        ]
        df_combined_save = prepare_combined_for_save(df_combined[save_cols])

        save_sales_review_category_combined(conn, df_combined_save)
        save_dataframe_to_sql(conn, df_corr, "analytics.review_sales_correlation")

        return {
            "review_rows": int(len(df_reviews_processed)),
            "combined_rows": int(len(df_combined_save)),
        }


if __name__ == "__main__":
    print(run_review_content_pipeline())
