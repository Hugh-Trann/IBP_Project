import uuid
from pathlib import Path
import pandas as pd
import numpy as np
from src.db import get_conn


SALES_COL_MAP = {
    "Order ID": "OrderId",
    "Customer Name": "CustomerName",
    "Category": "Category",
    "Sub Category": "SubCategory",
    "City": "City",
    "State": "Province",
    "Region": "Region",
    "Order Date": "OrderDate",
    "Sales": "Sales",
    "Discount": "Discount",
    "Profit": "Profit"
}

REVIEWS_COL_MAP = {
    "productId": "ProductID",
	"Title": "ProductName",
	"userId": "UserID",
	"Time": "ReviewDate",
    "Score": "ReviewScore",
	"Text": "ReviewContent",
	"Cat1":"Category",
	"Cat2":"SubCategory",
	"Cat3":"ProductType"
}

# replace non value in df
def process_non_value(df):
    df = df.astype(object)
    df = df.replace({pd.NA: None, np.nan: None})
    return df

# insert data into SQL
def insert_df(conn, table_name: str, df: pd.DataFrame):
    columns = list(df.columns)
    cols_sql = ",".join(f"[{c}]" for c in columns)
    placeholders = ",".join("?" for _ in columns)
    sql = f"INSERT INTO {table_name} ({cols_sql}) VALUES ({placeholders})"

    rows = list(df.itertuples(index=False, name=None))

    if not rows:
        print("No rows to insert.")
        return

    print("Total rows:", len(rows))
    print("First row:", rows[0])

    cur = conn.cursor()
    cur.fast_executemany = False
    
    for i, row in enumerate(rows):
        try:
            cur.execute(sql, row)
        except Exception as e:
            print("Insert failed at row:", i)
            print("Row data:", row)
            print("Error:", e)
            raise

    print("RAW INSERT COMPLETED.")

def create_batch_and_load_raw(file_path: str, dataset_type: str, dataset_year: int) -> dict:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Uploaded file not found: {file_path}")

    # check file
    if p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
        # print(df.info())
    elif p.suffix.lower() == ".xlsx":
        df = pd.read_excel(p)
    else:
        raise ValueError("Only .csv or .xlsx supported")

    if dataset_type not in ("sales", "reviews"):
        raise ValueError("dataset_type must be 'sales' or 'reviews'")

    batch_uuid = uuid.uuid4()
   
    if dataset_type == "sales":
        col_map = SALES_COL_MAP
        target = "rawT.customer_purchase"
        db_cols = ["OrderId", "CustomerName", "Category", "SubCategory", "City", "Province", "Region", "OrderDate",
        "Sales", "Discount", "Profit", "batch_id"]
    else:
        col_map = REVIEWS_COL_MAP
        target = "rawT.customer_review"
        db_cols = ["ProductID", "ProductName", "UserID", "ReviewDate", "ReviewScore", "ReviewContent", "Category", "SubCategory", "ProductType", "batch_id"] 
    
    # Validate CSV has required headers
    missing = set(col_map.keys()) - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in uploaded file: {sorted(missing)}")

    # Rename CSV columns to DB column names
    df = df.rename(columns=col_map)  

    # Add metadata columns 
    df["batch_id"] = batch_uuid

    df = df[db_cols] 

    # handle non values in df
    df = process_non_value(df)

    with get_conn() as conn:
        try:
            cur = conn.cursor()

            # Insert batch record
            cur.execute("""INSERT INTO dbo.upload_batch (batch_id, dataset_year, dataset_type, original_filename, status)
            VALUES (?, ?, ?, ?, 'uploaded');""", (batch_uuid, int(dataset_year), dataset_type, p.name),)
        
            # Insert raw rows 
            insert_df(conn, target, df)
            
            conn.commit()
        
            # Use a fresh cursor for counts uploaded results
            cur = conn.cursor()

            total_in_table = cur.execute(f"SELECT COUNT(*) FROM {target};").fetchone()[0]
            total_in_batch = cur.execute(f"SELECT COUNT(*) FROM {target} WHERE batch_id = ?;", (batch_uuid,)).fetchone()[0]
        
        except Exception:
            conn.rollback()
            raise

    return {
        "batch_id": str(batch_uuid),
        "dataset_type": dataset_type,
        "dataset_year": int(dataset_year),
        "target_table": target,
        "rows_inserted": int(total_in_batch),
        "table_total_rows": int(total_in_table),
        "source_file": p.name,
    }
