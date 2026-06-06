import pyodbc

SERVER = r"HTTK"
DATABASE = "IBP"
DRIVER = "ODBC Driver 17 for SQL Server"

MASTER_CONN_STR = (
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={SERVER};"
    "DATABASE=master;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

CONN_STR = (
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def get_master_conn():
    return pyodbc.connect(MASTER_CONN_STR, autocommit=True)


def ensure_database():
    with get_master_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
        IF DB_ID('{DATABASE}') IS NULL
        BEGIN
            CREATE DATABASE [{DATABASE}];
        END
        """)

def ensure_schemas_and_core_tables():
    with pyodbc.connect(CONN_STR, autocommit=True) as conn:
        cur = conn.cursor()

        sql = """
        IF SCHEMA_ID('rawT') IS NULL EXEC('CREATE SCHEMA rawT');
        IF SCHEMA_ID('cleaned') IS NULL EXEC('CREATE SCHEMA cleaned');
        IF SCHEMA_ID('analytics') IS NULL EXEC('CREATE SCHEMA analytics');

        IF OBJECT_ID('dbo.upload_batch', 'U') IS NULL
        CREATE TABLE dbo.upload_batch (
            batch_id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
            dataset_year INT NOT NULL,
            dataset_type VARCHAR(20) NOT NULL,
            original_filename NVARCHAR(255) NOT NULL,
            uploaded_at DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
            status VARCHAR(20) NOT NULL DEFAULT 'uploaded'
        );

        IF OBJECT_ID('rawT.customer_purchase', 'U') IS NULL
        CREATE TABLE rawT.customer_purchase (
            OrderId VARCHAR(20) NOT NULL,
            CustomerName VARCHAR(50) NULL,
            Category VARCHAR(50) NULL,
            SubCategory VARCHAR(50) NULL,
            City VARCHAR(50) NULL,
            Province VARCHAR(50) NULL,
            Region VARCHAR(50) NULL,
            OrderDate DATE NOT NULL,
            Sales DECIMAL(10,2) NULL,
            Discount DECIMAL(8,2) NULL,
            Profit DECIMAL(10,2) NULL,
            batch_id UNIQUEIDENTIFIER NULL
        );

        IF OBJECT_ID('rawT.customer_review', 'U') IS NULL
        CREATE TABLE rawT.customer_review (
            ProductID VARCHAR(50) NULL,
            ProductName VARCHAR(MAX) NULL,
            UserID VARCHAR(50) NULL,
            ReviewDate BIGINT NULL,
            ReviewScore INT NULL,
            ReviewContent VARCHAR(MAX) NULL,
            Category VARCHAR(100) NULL,
            SubCategory VARCHAR(100) NULL,
            ProductType VARCHAR(100) NULL,
            batch_id UNIQUEIDENTIFIER NULL
        );

        -- FIXED: match transform_clean.py
        IF OBJECT_ID('cleaned.dim_customer', 'U') IS NULL
        CREATE TABLE cleaned.dim_customer (
            CustomerID VARCHAR(200) NOT NULL PRIMARY KEY,
            CustomerName VARCHAR(100) NULL,
            City VARCHAR(100) NULL,
            FirstMonthVisit DATE NULL,
            batch_id UNIQUEIDENTIFIER NULL,
            created_at DATE NOT NULL DEFAULT CONVERT(date, SYSUTCDATETIME()),
            updated_at DATE NOT NULL DEFAULT CONVERT(date, SYSUTCDATETIME())
        );

        -- FIXED: match transform_clean.py
        IF OBJECT_ID('cleaned.dim_product', 'U') IS NULL
        CREATE TABLE cleaned.dim_product (
            ProductID VARCHAR(200) NOT NULL PRIMARY KEY,
            Category VARCHAR(100) NULL,
            SubCategory VARCHAR(100) NULL,
            batch_id UNIQUEIDENTIFIER NULL,
            created_at DATE NOT NULL DEFAULT CONVERT(date, SYSUTCDATETIME()),
            updated_at DATE NOT NULL DEFAULT CONVERT(date, SYSUTCDATETIME())
        );

        IF OBJECT_ID('cleaned.dim_date', 'U') IS NULL
        CREATE TABLE cleaned.dim_date (
            SalesDate DATE NOT NULL PRIMARY KEY
        );

        IF OBJECT_ID('cleaned.dim_month', 'U') IS NULL
        CREATE TABLE cleaned.dim_month (
            MonthStart DATE PRIMARY KEY,
            [Year] INT NOT NULL,
            MonthNumber INT NOT NULL,
            MonthName VARCHAR(20) NOT NULL,
            YearMonth VARCHAR(7) NOT NULL
        );

        IF OBJECT_ID('cleaned.fact_sales', 'U') IS NULL
        CREATE TABLE cleaned.fact_sales (
            OrderId VARCHAR(20) NOT NULL PRIMARY KEY,
            CustomerID VARCHAR(200) NULL,
            Category VARCHAR(50) NULL,
            ProductID VARCHAR(200) NULL,
            OrderDate DATE NULL,
            Sales FLOAT NULL,
            Discount FLOAT NULL,
            Profit FLOAT NULL,
            batch_id UNIQUEIDENTIFIER NULL,
            SalesMonth DATE NULL,
            created_at DATE NOT NULL DEFAULT CONVERT(date, SYSUTCDATETIME()),
            updated_at DATE NOT NULL DEFAULT CONVERT(date, SYSUTCDATETIME())
        );

        IF OBJECT_ID('cleaned.customer_review', 'U') IS NULL
        CREATE TABLE cleaned.customer_review (
            ProductID VARCHAR(50) NULL,
            ProductName VARCHAR(MAX) NULL,
            UserID VARCHAR(50) NULL,
            ReviewDate DATE NULL,
            ReviewScore INT NULL,
            ReviewContent VARCHAR(MAX) NULL,
            Category VARCHAR(100) NULL,
            SubCategory VARCHAR(100) NULL,
            ProductType VARCHAR(100) NULL,
            batch_id UNIQUEIDENTIFIER NULL
        );

        IF OBJECT_ID('analytics.sales_growth', 'U') IS NULL
        CREATE TABLE analytics.sales_growth (
            SalesMonth DATE NOT NULL PRIMARY KEY,
            TotalSales DECIMAL(10,2) NOT NULL,
            TotalProfit DECIMAL(10,2) NOT NULL,
            SalesGrowth DECIMAL(10,4) NULL,
            ProfitGrowth DECIMAL(10,4) NULL
        );

        IF OBJECT_ID('analytics.new_customer', 'U') IS NULL
        CREATE TABLE analytics.new_customer (
            FirstMonth DATE NOT NULL,
            NewCustomer INT NOT NULL
        );

        IF OBJECT_ID('analytics.sales_forecast', 'U') IS NULL
        CREATE TABLE analytics.sales_forecast (
            Category VARCHAR(100) NULL,
            SalesMonth DATE NULL,
            Sales DECIMAL(12,2) NULL
        );

        IF OBJECT_ID('analytics.products_transactions', 'U') IS NULL
        CREATE TABLE analytics.products_transactions (
            Category VARCHAR(200) NOT NULL,
            SalesMonth DATE NOT NULL,
            TotalSales FLOAT NULL,
            TotalTransactions INT NULL
        );

        IF OBJECT_ID('analytics.products_forecast', 'U') IS NULL
        CREATE TABLE analytics.products_forecast (
            Category VARCHAR(50) NOT NULL,
            SalesMonth DATE NOT NULL,
            ForecastTransactions INT NULL
        );

        IF OBJECT_ID('analytics.customer_review_matched', 'U') IS NULL
        CREATE TABLE analytics.customer_review_matched (
            ProductID VARCHAR(50) NULL,
            ProductName VARCHAR(MAX) NULL,
            UserID VARCHAR(50) NULL,
            ReviewDate DATE NULL,
            ReviewScore INT NULL,
            ReviewContent VARCHAR(MAX) NULL,
            Category VARCHAR(100) NULL,
            SubCategory VARCHAR(100) NULL
        );

        IF OBJECT_ID('analytics.review_score_category_monthly', 'U') IS NULL
        CREATE TABLE analytics.review_score_category_monthly (
            ReviewMonth DATE NOT NULL,
            Category NVARCHAR(255) NOT NULL,
            TotalReviews INT NOT NULL,
            AvgReviewScore FLOAT NULL,
            PositiveReviews INT NOT NULL,
            NeutralReviews INT NOT NULL,
            NegativeReviews INT NOT NULL
        );

        IF OBJECT_ID('analytics.review_score_product_monthly', 'U') IS NULL
        CREATE TABLE analytics.review_score_product_monthly (
            ReviewMonth DATE NOT NULL,
            ProductID NVARCHAR(100) NOT NULL,
            ProductName NVARCHAR(500) NULL,
            Category NVARCHAR(255) NULL,
            TotalReviews INT NOT NULL,
            AvgReviewScore FLOAT NULL,
            PositiveReviews INT NOT NULL,
            NeutralReviews INT NOT NULL,
            NegativeReviews INT NOT NULL
        );

        IF OBJECT_ID('analytics.sales_review_score_summary', 'U') IS NULL
        CREATE TABLE analytics.sales_review_score_summary (
            Category NVARCHAR(255) NULL,
            TotalSales FLOAT NULL,
            TotalTransactions INT NULL,
            TotalReviews INT NOT NULL,
            AvgReviewScore FLOAT NULL
        );

        IF OBJECT_ID('analytics.review_score_category_summary', 'U') IS NULL
        CREATE TABLE analytics.review_score_category_summary (
            Category NVARCHAR(255) NOT NULL,
            TotalReviews INT NOT NULL,
            AvgReviewScore FLOAT NULL,
            PositiveReviews INT NOT NULL,
            NeutralReviews INT NOT NULL,
            NegativeReviews INT NOT NULL
        );

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
        );
        """
        cur.execute(sql)
        conn.commit()

def ensure_database_ready():
    ensure_database()
    ensure_schemas_and_core_tables()


def get_conn():
    try:
        return pyodbc.connect(CONN_STR)

    except pyodbc.InterfaceError as e:
        msg = str(e)

        if "Cannot open database" in msg or "(4060)" in msg:
            print("Database IBP does not exist yet. Creating it now...")
            ensure_database_ready()
            return pyodbc.connect(CONN_STR)

        raise