from src.db import get_conn

SQL_DELETE_NEW_CUSTOMER = "DELETE FROM analytics.new_customer;"
SQL_NEW_CUSTOMER = """
    INSERT INTO analytics.new_customer(FirstMonth, NewCustomer)
    SELECT 
        FirstMonthVisit as FirstMonth, 
        Count(*) as NewCustomer
    FROM cleaned.dim_customer
    GROUP BY FirstMonthVisit
"""

SQL_SALES_GROWTH = """
    DELETE FROM analytics.sales_growth;
    
    WITH monthly_sales AS 
    (SELECT        
        datefromparts(year(OrderDate), month(OrderDate), 1) AS SalesMonth,
        sum(Sales) AS TotalSales,
        sum(Profit) AS TotalProfit
    FROM cleaned.fact_sales
    GROUP BY datefromparts(year(OrderDate), month(OrderDate), 1)
    ),
    ranked_sales AS
    (SELECT
        SalesMonth,
        TotalSales,
        TotalProfit,
        ROW_NUMBER() OVER(ORDER BY SalesMonth) as row_sales
    FROM monthly_sales
    )
    INSERT INTO analytics.sales_growth(SalesMonth, TotalSales, TotalProfit, SalesGrowth, ProfitGrowth)
    SELECT
        cur.SalesMonth,
        cur.TotalSales,
        cur.TotalProfit,
        CASE 
            WHEN prev.TotalSales is null OR prev.TotalSales = 0 then null
            ELSE (cur.TotalSales - prev.TotalSales)/prev.TotalSales
        END AS SalesGrowth,
        CASE
            WHEN prev.TotalProfit is null OR prev.TotalProfit = 0 then null
            ELSE (cur.TotalProfit - prev.TotalProfit)/prev.TotalProfit
        END AS ProfitGrowth
    FROM ranked_sales as cur LEFT JOIN ranked_sales as prev
        ON cur.row_sales = prev.row_sales +1;
"""

SQL_DELETE_PRODUCTS_TRANSACTIONS = """DELETE FROM analytics.products_transactions;"""

SQL_PRODUCTS_TRANSACTIONS = """
    INSERT INTO analytics.products_transactions(Category, SalesMonth, TotalSales, TotalTransactions)
    SELECT
        Category,
	    SalesMonth,
        sum(Sales) AS TotalSales,
	    count(Category) AS TotalTransactions
    FROM cleaned.fact_sales
    GROUP BY Category, SalesMonth;
"""

SQL_MATCHING_CUSTOMER_REVIEW = """
    DELETE FROM analytics.customer_review_matched;

    INSERT INTO analytics.customer_review_matched(ProductID, ProductName, UserID, ReviewDate, ReviewScore, ReviewContent, Category, SubCategory)
    SELECT
        ProductID,
        ProductName,
        UserID,
        ReviewDate,
        ReviewScore,
        ReviewContent,
        SubCategory,
        ProductType
    FROM cleaned.customer_review
    WHERE Category = 'grocerygourmetfood'
	AND ProductType in ('breadcrumbs','breads','breadsticks','breakfast bakery','cakes','cookies',
						'fresh baked cookies','packaged breads','pastries','pizza crusts','stuffing','tortillas',
						'cocktail mixers','coconut water','coffee','energy drinks','hot cocoa','juices',
						'powdered drink mixes','soft drinks','sports drinks','tea','water','chicken',
						'eggs','seafood','beef','pork','flours meals','baking powder',
						'dried beans','fresh fruits','fresh vegetables','oil','herbs', 'chocolate assortments',
                        'chocolate bars','chocolate covered fruit','chocolate pretzels', 'chocolate truffles');
"""

SQL_MAPPING_CUSTOMER_REVIEW_CATEGORY = """
    UPDATE analytics.customer_review_matched
    SET Category = CASE
            WHEN Category = 'breads bakery' THEN 'Bakery'
            WHEN Category = 'beverages' THEN 'Beverages'
            WHEN Category IN ('meat seafood', 'dairy eggs', 'meat poultry') THEN 'Eggs, Meat & Fish'
            WHEN Category IN ('cooking baking supplies') THEN 'Food Grains'
            WHEN Category = 'produce' THEN 'Fruits & Veggies'
            WHEN Category = 'pantry staples' THEN 'Oil & Masala'
            WHEN Category = 'candy chocolate' THEN 'Snacks'
            WHEN Category IN ('breads bakery', 'snack food') THEN 'Snacks'
            ELSE Category
        END,
        ReviewDate = CASE
            WHEN year(ReviewDate) IN (2015, 2016, 2017) THEN datefromparts('2018', month(ReviewDate), day(ReviewDate))
            ELSE ReviewDate
        END;
"""

SQL_REVIEW_SCORE_CATEGORY_SUMMARY = """
    DELETE FROM analytics.review_score_category_summary;

    INSERT INTO analytics.review_score_category_summary (
        Category,
        TotalReviews,
        AvgReviewScore,
        PositiveReviews,
        NeutralReviews,
        NegativeReviews
    )
    SELECT
        Category,
        COUNT(*) AS TotalReviews,
        AVG(CAST(ReviewScore AS FLOAT)) AS AvgReviewScore,
        SUM(CASE WHEN ReviewScore >= 4 THEN 1 ELSE 0 END) AS PositiveReviews,
        SUM(CASE WHEN ReviewScore = 3 THEN 1 ELSE 0 END) AS NeutralReviews,
        SUM(CASE WHEN ReviewScore <= 2 THEN 1 ELSE 0 END) AS NegativeReviews
    FROM analytics.customer_review_matched
    GROUP BY Category;
"""

SQL_REVIEW_CATEGORY_MONTHLY = """
    DELETE FROM analytics.review_score_category_monthly;

    INSERT INTO analytics.review_score_category_monthly (
        ReviewMonth,
        Category,
        TotalReviews,
        AvgReviewScore,
        PositiveReviews,
        NeutralReviews,
        NegativeReviews
    )
    SELECT
        DATEFROMPARTS(YEAR(ReviewDate), MONTH(ReviewDate), 1) AS ReviewMonth,
        Category,
        COUNT(*) AS TotalReviews,
        AVG(CAST(ReviewScore AS FLOAT)) AS AvgReviewScore,
        SUM(CASE WHEN ReviewScore >= 4 THEN 1 ELSE 0 END) AS PositiveReviews,
        SUM(CASE WHEN ReviewScore = 3 THEN 1 ELSE 0 END) AS NeutralReviews,
        SUM(CASE WHEN ReviewScore <= 2 THEN 1 ELSE 0 END) AS NegativeReviews
    FROM analytics.customer_review_matched
    WHERE ReviewDate IS NOT NULL
    GROUP BY
        DATEFROMPARTS(YEAR(ReviewDate), MONTH(ReviewDate), 1),
        Category;
"""

SQL_REVIEW_PRODUCT_MONTHLY = """
    DELETE FROM analytics.review_score_product_monthly;

    INSERT INTO analytics.review_score_product_monthly (
        ReviewMonth,
        ProductID,
        ProductName,
        Category,
        TotalReviews,
        AvgReviewScore,
        PositiveReviews,
        NeutralReviews,
        NegativeReviews
    )
    SELECT
        DATEFROMPARTS(YEAR(ReviewDate), MONTH(ReviewDate), 1) AS ReviewMonth,
        ProductID,
        ProductName,
        Category,
        COUNT(*) AS TotalReviews,
        AVG(CAST(ReviewScore AS FLOAT)) AS AvgReviewScore,
        SUM(CASE WHEN ReviewScore >= 4 THEN 1 ELSE 0 END) AS PositiveReviews,
        SUM(CASE WHEN ReviewScore = 3 THEN 1 ELSE 0 END) AS NeutralReviews,
        SUM(CASE WHEN ReviewScore <= 2 THEN 1 ELSE 0 END) AS NegativeReviews
    FROM analytics.customer_review_matched
    WHERE ReviewDate IS NOT NULL
    GROUP BY
        DATEFROMPARTS(YEAR(ReviewDate), MONTH(ReviewDate), 1),
        ProductID,
        ProductName,
        Category;
"""

SQL_SALES_REVIEW_SUMMARY = """
    DELETE FROM analytics.sales_review_score_summary;

    WITH sales_summary AS (
        SELECT
            Category,
            SUM(Sales) AS TotalSales,
            COUNT(OrderID) AS TotalTransactions
        FROM cleaned.fact_sales
        GROUP BY Category
    ),
    review_summary AS (
        SELECT
            Category,
            COUNT(*) AS TotalReviews,
            AVG(CAST(ReviewScore AS FLOAT)) AS AvgReviewScore
        FROM analytics.customer_review_matched
        GROUP BY Category
    )
    INSERT INTO analytics.sales_review_score_summary (
        Category,
        TotalSales,
        TotalTransactions,
        TotalReviews,
        AvgReviewScore
    )
    SELECT
        s.Category,
        s.TotalSales,
        s.TotalTransactions,
        ISNULL(r.TotalReviews, 0) AS TotalReviews,
        ISNULL(r.AvgReviewScore, 0) AS AvgReviewScore
    FROM sales_summary s
    LEFT JOIN review_summary r
       ON s.Category = r.Category;
"""


def rebuild_analytics() -> dict:
   
    with get_conn() as conn:
        cur = conn.cursor()
        try:
            cur.execute(SQL_DELETE_NEW_CUSTOMER)
            cur.execute(SQL_NEW_CUSTOMER)
            cur.execute(SQL_SALES_GROWTH)
            cur.execute(SQL_DELETE_PRODUCTS_TRANSACTIONS)
            cur.execute(SQL_PRODUCTS_TRANSACTIONS)
            cur.execute(SQL_MATCHING_CUSTOMER_REVIEW)
            cur.execute(SQL_MAPPING_CUSTOMER_REVIEW_CATEGORY)
            cur.execute(SQL_REVIEW_CATEGORY_MONTHLY)
            cur.execute(SQL_REVIEW_SCORE_CATEGORY_SUMMARY)
            cur.execute(SQL_REVIEW_PRODUCT_MONTHLY)
            cur.execute(SQL_SALES_REVIEW_SUMMARY)
            conn.commit()

            new_customer_rows = cur.execute("SELECT COUNT(*) FROM analytics.new_customer;").fetchone()[0]

            return {"new_customers": int(new_customer_rows)}
        except Exception:
            conn.rollback()
            raise