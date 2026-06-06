Project name: "IBP Project - Intelligent Business Performance Analytics and Decision Support Platform For Small Business"

The platform combines data ingestion, analysis, forecasting, recommendations, reporting and user interaction. The expected benefits include better decision-making, earlier identification of performance problems, and a reusable analytics framework that can be applied to different environment.


Initial setups:
* Code editor: Visual Studio Code
* Database management system: SQL Server

Steps to run the demo from VSC's terminal:
1. Create a virtual environment: python -m venv .venv
2. Activate the virtual environment: .\.venv\Scripts\Activate.ps1
3. Install dependencies: pip install -r requirements.txt
4. Start application: uvicorn front_end.main:app
5. Access the platform: http://127.0.0.1:8000
6. Sample data for uploading: ...\W26_4495_S2_HughT\Implementation\data\grocery store

Steps to fix issues of dependencies (if any):
1. Install python packages: pip install pandas polars pyarrow scikit-learn streamlit  matplotlib seaborn uvicorn fastapi pyodbc python-multipart sqlalchemy python-dotenv requests xgboost
2. Generate dependencies file: pip freeze > requirements.txt
3. Re-start application: uvicorn front_end.main:app
4. Access the platform: http://127.0.0.1:8000
