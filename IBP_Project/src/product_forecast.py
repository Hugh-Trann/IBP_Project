import pandas as pd
import numpy as np
from src.db import get_conn
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import matplotlib.pyplot as plt


def product_forecast():
    """
    Forecast category-level monthly transactions trained from cleaned.fact_sales.

    Output table:
        analytics.products_forecast
            - Category
            - SalesMonth
            - ForecastTransactions

    Notes:
    - This table is for transaction analysis only.
    - Forecast Outlook in the report should use analytics.sales_forecast only.
    """

    forecast_months = 12
    min_training_rows = 12

    with get_conn() as conn:
        cur = conn.cursor()

        sql = """
            SELECT
                fs.Category,
                DATEFROMPARTS(YEAR(fs.OrderDate), MONTH(fs.OrderDate), 1) AS SalesMonth,
                COUNT(DISTINCT fs.OrderID) AS Transactions
            FROM cleaned.fact_sales fs
            WHERE fs.OrderDate IS NOT NULL
              AND fs.Category IS NOT NULL
            GROUP BY
                fs.Category,
                DATEFROMPARTS(YEAR(fs.OrderDate), MONTH(fs.OrderDate), 1)
            ORDER BY fs.Category, SalesMonth;
        """

        df = pd.read_sql(sql, conn)
        if df.empty:
            print("No source rows found in cleaned.fact_sales.")
            return 0

        df["SalesMonth"] = pd.to_datetime(df["SalesMonth"], errors="coerce")
        df = df.dropna(subset=["Category", "SalesMonth", "Transactions"]).copy()
        df = df.sort_values(["Category", "SalesMonth"]).reset_index(drop=True)

        feature_cols = ["Year", "Month", "Lag1", "Lag3", "RollingMean3"]
        forecast_rows = []
        metrics_rows = []

        def build_features(category_df):
            working = category_df.sort_values("SalesMonth").copy()
            working["Year"] = working["SalesMonth"].dt.year
            working["Month"] = working["SalesMonth"].dt.month
            working["Lag1"] = working["Transactions"].shift(1)
            working["Lag3"] = working["Transactions"].shift(3)
            working["RollingMean3"] = working["Transactions"].shift(1).rolling(window=3).mean()
            return working.dropna().reset_index(drop=True)

        def split_train_test(feature_df):
            latest_year = feature_df["SalesMonth"].dt.year.max()
            train_df = feature_df[feature_df["SalesMonth"].dt.year < latest_year].copy()
            test_df = feature_df[feature_df["SalesMonth"].dt.year == latest_year].copy()
            if train_df.empty or test_df.empty:
                split_point = int(len(feature_df) * 0.8)
                train_df = feature_df.iloc[:split_point].copy()
                test_df = feature_df.iloc[split_point:].copy()
            return train_df, test_df

        def evaluation_metrics(y_true, y_pred):
            mae = mean_absolute_error(y_true, y_pred)
            mse = mean_squared_error(y_true, y_pred)
            r2 = r2_score(y_true, y_pred) if len(y_true) > 1 else np.nan
            mape = np.mean(np.abs((y_true - y_pred) / y_true) * 100) if np.all(y_true != 0) else np.nan
            return mae, mse, r2, mape

        def products_predict_plot(test_dates, y_actual, y_pred, category):
            plt.figure(figsize=(12, 6))
            plt.plot(test_dates, y_actual, label="Actual", marker="o")
            plt.plot(test_dates, y_pred, label="Predicted", marker="o")
            plt.xticks(test_dates, rotation=45)
            plt.title(f"Actual vs Predicted Transactions - {category}")
            plt.xlabel("Month")
            plt.ylabel("Transactions")
            plt.legend()
            plt.tight_layout()
            plt.show()

        for category, group in df.groupby("Category", dropna=False):
            history_df = group.sort_values("SalesMonth").reset_index(drop=True).copy()
            feature_df = build_features(history_df)

            if len(feature_df) < min_training_rows:
                print(f"Skip {category}: not enough rows after feature engineering ({len(feature_df)} rows).")
                continue

            train_df, test_df = split_train_test(feature_df)
            if train_df.empty or test_df.empty:
                print(f"Skip {category}: train/test split is empty.")
                continue

            X_train = train_df[feature_cols]
            y_train = train_df["Transactions"]
            X_test = test_df[feature_cols]
            y_test = test_df["Transactions"]

            model = XGBRegressor(
                n_estimators=400,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
            )
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            mae, mse, r2, mape = evaluation_metrics(y_test.values, y_pred)
            metrics_rows.append({
                "Category": category,
                "MAE": float(mae),
                "MSE": float(mse),
                "R2": None if pd.isna(r2) else float(r2),
                "MAPE": None if pd.isna(mape) else float(mape),
            })

            print(f"\nCategory: {category}")
            print(f"Train rows: {len(train_df)} | Test rows: {len(test_df)}")
            print(f"MAE : {mae:,.2f}")
            print(f"MSE : {mse:,.2f}")
            print(f"R2  : {r2:,.4f}" if not pd.isna(r2) else "R2  : N/A")
            print(f"MAPE: {mape:,.2f}" if not pd.isna(mape) else "MAPE: N/A")

            products_predict_plot(test_df["SalesMonth"], y_test.values, y_pred, category)

            rolling_history = history_df.copy()
            for _ in range(forecast_months):
                last_month = rolling_history["SalesMonth"].max()
                next_month = last_month + pd.DateOffset(months=1)

                txn_series = rolling_history["Transactions"]
                lag1 = txn_series.iloc[-1] if len(txn_series) >= 1 else 0
                lag3 = txn_series.iloc[-3] if len(txn_series) >= 3 else lag1
                rolling_mean_3 = txn_series.iloc[-3:].mean() if len(txn_series) >= 3 else txn_series.mean()

                new_x = pd.DataFrame([{
                    "Year": next_month.year,
                    "Month": next_month.month,
                    "Lag1": lag1,
                    "Lag3": lag3,
                    "RollingMean3": rolling_mean_3,
                }])

                predicted_transactions = float(model.predict(new_x[feature_cols])[0])
                predicted_transactions = max(0.0, predicted_transactions)

                forecast_rows.append({
                    "Category": category,
                    "SalesMonth": next_month,
                    "ForecastTransactions": round(predicted_transactions, 2),
                })

                rolling_history = pd.concat([
                    rolling_history,
                    pd.DataFrame([{
                        "Category": category,
                        "SalesMonth": next_month,
                        "Transactions": predicted_transactions,
                    }])
                ], ignore_index=True)

        forecast_df = pd.DataFrame(forecast_rows)
        metrics_df = pd.DataFrame(metrics_rows)

        print("\nFORECAST RESULT")
        print(forecast_df.head())
        print("\nMODEL METRICS")
        print(metrics_df)

        if forecast_df.empty:
            print("No product forecast rows generated.")
            return 0

        forecast_df = forecast_df.sort_values(["SalesMonth", "Category"]).reset_index(drop=True)

        cur.execute("DELETE FROM analytics.products_forecast;")
        cur.executemany(
            """
            INSERT INTO analytics.products_forecast(Category, SalesMonth, ForecastTransactions)
            VALUES (?, ?, ?);
            """,
            forecast_df.itertuples(index=False, name=None)
        )
        conn.commit()

        return int(len(forecast_df))


# product_forecast()
