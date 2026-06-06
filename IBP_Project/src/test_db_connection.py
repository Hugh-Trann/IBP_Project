import pyodbc


SERVER = r"HTTK"        
DATABASE = "IBP"
DRIVER = "ODBC Driver 17 for SQL Server"

conn_str = (
    f"DRIVER={{{DRIVER}}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

try:
    with pyodbc.connect(conn_str) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SYSTEM_USER, DB_NAME();")
        user, db = cursor.fetchone()
        print("Connected as:", user)
        print("Database:", db)
except Exception as e:
    print("Connection failed:", e)