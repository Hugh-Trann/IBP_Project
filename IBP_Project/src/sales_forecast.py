import pandas as pd
import numpy as np
from src.db import get_conn
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import matplotlib.pyplot as plt


def sales_forecast():
    """
    Forecast total monthly sales with Linear Regression trained from cleaned.fact_sales,
    then allocate each forecast month to categories using recent historical category mix.

    Output table:
        analytics.sales_forecast
            - Category
            - SalesMonth
            - Sales

    Why this design:
    - keeps the stronger total-sales Linear Regression model as the source of truth
    - adds Category so Forecast Outlook can use one single table only
    - makes forecast summary and category table consistent with each other
    """

    forecast_months = 12
    category_share_months = 6

    with get_conn() as conn:
        cur = conn.cursor()

        sql_total_sales = """
            SELECT
                DATEFROMPARTS(YEAR(fs.OrderDate), MONTH(fs.OrderDate), 1) AS SalesMonth,
                SUM(fs.Sales) AS TotalSales
            FROM cleaned.fact_sales fs
            WHERE fs.OrderDate IS NOT NULL
            GROUP BY DATEFROMPARTS(YEAR(fs.OrderDate), MONTH(fs.OrderDate), 1)
            ORDER BY SalesMonth;
        """

        sql_category_monthly = """
            SELECT
                fs.Category,
                DATEFROMPARTS(YEAR(fs.OrderDate), MONTH(fs.OrderDate), 1) AS SalesMonth,
                SUM(fs.Sales) AS TotalSales
            FROM cleaned.fact_sales fs
            WHERE fs.OrderDate IS NOT NULL
              AND fs.Category IS NOT NULL
            GROUP BY
                fs.Category,
                DATEFROMPARTS(YEAR(fs.OrderDate), MONTH(fs.OrderDate), 1)
            ORDER BY fs.Category, SalesMonth;
        """

        total_df = pd.read_sql(sql_total_sales, conn)
        category_df = pd.read_sql(sql_category_monthly, conn)

        if total_df.empty:
            print("No source rows found in cleaned.fact_sales.")
            return 0

        total_df["SalesMonth"] = pd.to_datetime(total_df["SalesMonth"], errors="coerce")
        total_df = total_df.dropna(subset=["SalesMonth", "TotalSales"]).copy()
        total_df = total_df.sort_values("SalesMonth").reset_index(drop=True)

        category_df["SalesMonth"] = pd.to_datetime(category_df["SalesMonth"], errors="coerce")
        category_df = category_df.dropna(subset=["Category", "SalesMonth", "TotalSales"]).copy()
        category_df = category_df.sort_values(["Category", "SalesMonth"]).reset_index(drop=True)

        def split_train_test(df):
            working = df.copy()
            working["Year"] = working["SalesMonth"].dt.year
            working["Month"] = working["SalesMonth"].dt.month
            working["Lag1"] = working["TotalSales"].shift(1)
            working["Lag3"] = working["TotalSales"].shift(3)
            working["Lag6"] = working["TotalSales"].shift(6)
            working["Lag12"] = working["TotalSales"].shift(12)
            working["RollingMean3"] = working["TotalSales"].shift(1).rolling(window=3).mean()
            working["RollingMean6"] = working["TotalSales"].shift(1).rolling(window=6).mean()
            working = working.dropna().reset_index(drop=True)

            latest_year = working["SalesMonth"].dt.year.max()
            train_df = working[working["SalesMonth"].dt.year < latest_year].copy()
            test_df = working[working["SalesMonth"].dt.year == latest_year].copy()

            if train_df.empty or test_df.empty:
                split_point = int(len(working) * 0.8)
                train_df = working.iloc[:split_point].copy()
                test_df = working.iloc[split_point:].copy()

            return working, train_df, test_df

        def evaluation_metrics(y_true, y_pred):
            mae = mean_absolute_error(y_true, y_pred)
            mse = mean_squared_error(y_true, y_pred)
            r2 = r2_score(y_true, y_pred) if len(y_true) > 1 else np.nan
            mape = np.mean(np.abs((y_true - y_pred) / y_true) * 100) if np.all(y_true != 0) else np.nan
            return mae, mse, r2, mape

        def sales_predict_plot(test_dates, y_actual, y_pred):
            plt.figure(figsize=(12, 6))
            plt.plot(test_dates, y_actual, label="Actual", marker="o")
            plt.plot(test_dates, y_pred, label="Predicted", marker="o")
            plt.xticks(test_dates, rotation=45)
            plt.title("Actual vs Predicted Total Sales")
            plt.xlabel("Month")
            plt.ylabel("Sales")
            plt.legend()
            plt.tight_layout()
            plt.show()

        _, train_df, test_df = split_train_test(total_df)
        if train_df.empty or test_df.empty:
            print("Not enough rows to train total sales forecast model.")
            return 0

        feature_cols = ["Year", "Month", "Lag1", "Lag3", "Lag6", "Lag12", "RollingMean3", "RollingMean6"]
        target_col = "TotalSales"

        X_train = train_df[feature_cols]
        y_train = train_df[target_col]
        X_test = test_df[feature_cols]
        y_test = test_df[target_col]

        model = LinearRegression()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        mae, mse, r2, mape = evaluation_metrics(y_test.values, y_pred)
        print("\nTOTAL SALES LINEAR REGRESSION MODEL")
        print(f"Train rows: {len(train_df)} | Test rows: {len(test_df)}")
        print(f"MAE : {mae:,.2f}")
        print(f"MSE : {mse:,.2f}")
        print(f"R2  : {r2:,.4f}" if not pd.isna(r2) else "R2  : N/A")
        print(f"MAPE: {mape:,.2f}" if not pd.isna(mape) else "MAPE: N/A")

        sales_predict_plot(test_df["SalesMonth"], y_test.values, y_pred)

        forecast_rows = []
        forecast_history = total_df.copy()

        for _ in range(forecast_months):
            last_month = forecast_history["SalesMonth"].max()
            next_month = last_month + pd.DateOffset(months=1)

            sales_series = forecast_history["TotalSales"]
            lag1 = sales_series.iloc[-1]
            lag3 = sales_series.iloc[-3] if len(sales_series) >= 3 else lag1
            lag6 = sales_series.iloc[-6] if len(sales_series) >= 6 else lag1
            lag12 = sales_series.iloc[-12] if len(sales_series) >= 12 else lag1
            rolling_mean_3 = sales_series.iloc[-3:].mean() if len(sales_series) >= 3 else sales_series.mean()
            rolling_mean_6 = sales_series.iloc[-6:].mean() if len(sales_series) >= 6 else sales_series.mean()

            new_x = pd.DataFrame([{
                "Year": next_month.year,
                "Month": next_month.month,
                "Lag1": lag1,
                "Lag3": lag3,
                "Lag6": lag6,
                "Lag12": lag12,
                "RollingMean3": rolling_mean_3,
                "RollingMean6": rolling_mean_6,
            }])

            predicted_total_sales = float(model.predict(new_x[feature_cols])[0])
            predicted_total_sales = max(0.0, predicted_total_sales)

            forecast_rows.append({
                "SalesMonth": next_month,
                "PredictedTotalSales": predicted_total_sales,
            })

            forecast_history = pd.concat([
                forecast_history,
                pd.DataFrame([{
                    "SalesMonth": next_month,
                    "TotalSales": predicted_total_sales,
                }])
            ], ignore_index=True)

        forecast_total_df = pd.DataFrame(forecast_rows)

        latest_actual_month = category_df["SalesMonth"].max()
        share_start_month = latest_actual_month - pd.DateOffset(months=category_share_months - 1)
        recent_category_df = category_df[category_df["SalesMonth"] >= share_start_month].copy()

        category_share_df = (
            recent_category_df.groupby("Category", as_index=False)["TotalSales"]
            .sum()
            .rename(columns={"TotalSales": "RecentCategorySales"})
        )

        total_recent_sales = float(category_share_df["RecentCategorySales"].sum())
        if total_recent_sales <= 0:
            print("Category sales share could not be calculated.")
            return 0

        category_share_df["SalesShare"] = category_share_df["RecentCategorySales"] / total_recent_sales

        allocated_rows = []
        for forecast_row in forecast_total_df.to_dict(orient="records"):
            month_total = float(forecast_row["PredictedTotalSales"])
            month_date = forecast_row["SalesMonth"]

            for share_row in category_share_df.to_dict(orient="records"):
                allocated_rows.append({
                    "Category": str(share_row["Category"]),
                    "SalesMonth": month_date,
                    "Sales": round(month_total * float(share_row["SalesShare"]), 2),
                })

        forecast_output_df = pd.DataFrame(allocated_rows)
        if forecast_output_df.empty:
            print("No category sales forecast rows generated.")
            return 0

        adjusted_rows = []
        for month, group in forecast_output_df.groupby("SalesMonth", dropna=False):
            working = group.copy().sort_values("Category").reset_index(drop=True)
            target_total = round(float(forecast_total_df.loc[forecast_total_df["SalesMonth"] == month, "PredictedTotalSales"].iloc[0]), 2)
            current_total = round(float(working["Sales"].sum()), 2)
            diff = round(target_total - current_total, 2)
            if len(working) > 0 and diff != 0:
                working.loc[working.index[-1], "Sales"] = round(float(working.loc[working.index[-1], "Sales"]) + diff, 2)
            adjusted_rows.append(working)

        forecast_output_df = pd.concat(adjusted_rows, ignore_index=True)
        forecast_output_df = forecast_output_df.sort_values(["SalesMonth", "Category"]).reset_index(drop=True)

        print("\nFORECAST RESULT")
        print(forecast_output_df.head())

        cur.execute("DELETE FROM analytics.sales_forecast;")
        cur.executemany(
            """
            INSERT INTO analytics.sales_forecast(Category, SalesMonth, Sales)
            VALUES (?, ?, ?);
            """,
            forecast_output_df.itertuples(index=False, name=None)
        )
        conn.commit()

        return int(len(forecast_output_df))


# sales_forecast()
