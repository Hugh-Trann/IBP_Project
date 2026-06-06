import pandas as pd
import numpy as np
from src.db import get_conn

def run_raw_to_clean_for_batch(batch_id: str) -> dict:
    with get_conn() as conn:
        # Read only this batch
        purchase = pd.read_sql(
            "SELECT * FROM rawT.customer_purchase WHERE batch_id = ?;",
            conn,
            params=[batch_id],
        )
        review = pd.read_sql(
            "SELECT * FROM rawT.customer_review WHERE batch_id = ?;",
            conn,
            params=[batch_id],
        )

        # basic cleaning 
        if not purchase.empty:
            for col in ["OrderId", "CustomerName", "Category", "SubCategory", "City"]:
                if col in purchase.columns:
                    purchase[col] = purchase[col].astype(str).str.strip()
            # featuring
            purchase["CustomerID"] = purchase["CustomerName"] + purchase["City"]
            purchase["CustomerID"] = purchase["CustomerID"].str.replace(r"[\s,.\-_]+", "", regex=True)
            purchase["ProductID"] = purchase["Category"] + purchase["SubCategory"]
            purchase["ProductID"] = purchase["ProductID"].str.replace(r"[\s,.\-_]+", "", regex=True)
            purchase["OderId"] = purchase["OrderId"].astype(str)
            purchase["OrderDate"] = pd.to_datetime(purchase["OrderDate"], errors="coerce")
            purchase["Sales"] = pd.to_numeric(purchase["Sales"], errors="coerce")
            purchase["Discount"] = pd.to_numeric(purchase["Discount"], errors="coerce")
            purchase["Profit"] = pd.to_numeric(purchase["Profit"], errors="coerce")

        if not review.empty:
            for col in ["ProductID", "ProductName", "UserID", "ReviewContent", "Category", "SubCategory", "ProductType"]:
                if col in review.columns:
                    review[col] = review[col].astype(str).str.strip()
            review["ProductID"] = review["ProductID"].str.replace(r"[\s]+", "")
            review["ReviewScore"]= pd.to_numeric(review["ReviewScore"], errors="coerce")
            review["ReviewDate"] = pd.to_datetime(review["ReviewDate"], unit="s", origin="1977-01-01", errors="coerce")
            review["Category"] = review["Category"].str.replace(r"[\s,.\-_]+", "", regex=True)
        
        # create dims from purchase
        dim_customer = pd.DataFrame(columns=["CustomerID", "CustomerName", "City", "OrderDate"])
        dim_customer["batch_id"] = batch_id
        dim_product = pd.DataFrame(columns=["ProductID", "Category", "SubCategory"])
        dim_product["batch_id"] = batch_id
        dim_date = pd.DataFrame(columns=["OrderDate"])

        if not purchase.empty:
            dim_customer = (
                purchase[["CustomerID", "CustomerName", "City", "OrderDate"]]
                .sort_values(["CustomerID", "OrderDate"])
                .drop_duplicates(subset=["CustomerID"], keep="first")
                .copy()
            )

            dim_customer["FirstMonthVisit"] = dim_customer["OrderDate"].dt.to_period("M").dt.to_timestamp()
            dim_customer["batch_id"] = batch_id
            dim_customer = dim_customer.drop(columns=["OrderDate"])

            dim_product = (
                purchase[["ProductID", "Category", "SubCategory"]]
                # .dropna(subset=["ProductID"])
                # .assign(ProductID=lambda d: d["ProductID"].astype(str))
                .sort_values(["ProductID"])
                .drop_duplicates(subset=["ProductID"], keep="first")
            )
            dim_date = purchase[["OrderDate"]].sort_values("OrderDate").drop_duplicates()
            

        # create fact from purchase
        fact_sales = pd.DataFrame()
        if not purchase.empty:
            fact_sales = purchase[["OrderId", "CustomerID", "Category", "ProductID", "OrderDate", "Sales", "Discount", "Profit"]].copy()
            fact_sales["batch_id"] = batch_id
            fact_sales["SalesMonth"] = fact_sales['OrderDate'].dt.to_period("M").dt.to_timestamp()
        cur = conn.cursor()
        cur.fast_executemany = True

        # create fact from review
        SQL_DELETE_NOT_RELEVANT_REVIEW_YEAR = """
            DELETE FROM cleaned.customer_review
            WHERE year(ReviewDate) not in ('2015', '2016', '2017', '2018')
        """

        SQL_DELETE_NOT_RELEVANT_REVIEW_CATEGORY = """
            DELETE FROM cleaned.customer_review
            WHERE Category in ('babyproducts', 'beauty', 'healthpersonalcare', 'petsupplies', 'toysgames')
        """

        fact_review = pd.DataFrame(columns = ["ProductID", "ProductName", "UserID", "ReviewDate", "ReviewScore", "ReviewContent", "Category", "SubCategory",  "ProductType"])
        if not review.empty:
            fact_review = review[["ProductID", "ProductName", "UserID", "ReviewDate", "ReviewScore", "ReviewContent", "Category", "SubCategory", "ProductType"]].copy()
            fact_review["batch_id"] = batch_id
            fact_review = fact_review.replace({pd.NA:None, np.nan:None})
      
            cur.executemany(
                """
                INSERT INTO cleaned.customer_review(ProductID, ProductName, UserID, ReviewDate, ReviewScore, ReviewContent, Category, SubCategory, ProductType, batch_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                fact_review.itertuples(index=False, name=None)
            )

            cur.execute(SQL_DELETE_NOT_RELEVANT_REVIEW_YEAR)
            cur.execute(SQL_DELETE_NOT_RELEVANT_REVIEW_CATEGORY)


        # Customers
        if not dim_customer.empty:
            cur.executemany(
                """
                INSERT INTO cleaned.dim_customer (CustomerID, CustomerName, City, FirstMonthVisit, batch_id)
                SELECT ?, ?, ?, ? ,?
                WHERE NOT EXISTS (SELECT 1 FROM cleaned.dim_customer WHERE CustomerID = ?);
                """,
                [(r.CustomerID, r.CustomerName, r.City, r.FirstMonthVisit, batch_id, r.CustomerID) for r in dim_customer.itertuples(index=False)]
            )

        # Products
        if not dim_product.empty:
            cur.executemany(
                """
                INSERT INTO cleaned.dim_product (ProductID, Category, SubCategory, batch_id)
                SELECT ?, ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM cleaned.dim_product WHERE ProductID = ?);
                """,
                [(r.ProductID, r.Category, r.SubCategory, batch_id, r.ProductID) for r in dim_product.itertuples(index=False)]
            )

        SQL_DIM_DATE = """
            INSERT INTO cleaned.dim_date (SalesDate)
            SELECT DISTINCT
                datefromparts(year(OrderDate), month(OrderDate), 1) AS SalesMonth
            FROM cleaned.fact_sales
            EXCEPT
            SELECT SalesDate
            FROM cleaned.dim_date;
        """  

        SQL_DIM_MONTH = SQL_DIM_MONTH = """
            INSERT INTO cleaned.dim_month (MonthStart, [Year], MonthNumber, MonthName, YearMonth)
            SELECT DISTINCT
                M.MonthStart,
                YEAR(M.MonthStart) AS [Year],
                MONTH(M.MonthStart) AS MonthNumber,
                DATENAME(MONTH, M.MonthStart) AS MonthName,
                CONVERT(char(7), M.MonthStart, 120) AS YearMonth
            FROM (
                SELECT SalesMonth AS MonthStart
                FROM cleaned.fact_sales
                WHERE SalesMonth IS NOT NULL

                UNION

                SELECT ReviewMonth AS MonthStart
                FROM analytics.review_score_category_monthly
                WHERE ReviewMonth IS NOT NULL
            ) M
            WHERE NOT EXISTS (
                SELECT 1
                FROM cleaned.dim_month D
                WHERE D.MonthStart = M.MonthStart
            );
        """   

        # Date
        if not dim_date.empty:
            cur.executemany(
                """
                INSERT INTO cleaned.dim_date (SalesDate)
                VALUES (?); 
                """,
                dim_date.itertuples(index=False, name=None)
            )
            

        conn.commit()

        if not fact_sales.empty:
            cur.executemany(
                """
                INSERT INTO cleaned.fact_sales
                (OrderID, CustomerID, Category,ProductID, OrderDate, Sales, Discount, Profit, batch_id, SalesMonth)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                fact_sales.itertuples(index=False, name=None)
            )
            cur.execute(SQL_DIM_DATE)
            cur.execute(SQL_DIM_MONTH)

        conn.commit()

        return {
            "batch_id": batch_id,
            "fact_sales_rows": int(len(fact_sales)),
            # "fact_review_rows": int(len(fact_review)),
            "dim_customer_count": int(len(dim_customer)),
            "dim_product_count": int(len(dim_product)),
        }
