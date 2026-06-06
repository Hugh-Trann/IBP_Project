import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

PBI_ACCESS_TOKEN = os.getenv("PBI_ACCESS_TOKEN", "")
PBI_WORKSPACE_ID = os.getenv("PBI_WORKSPACE_ID", "")
PBI_DATASET_ID = os.getenv("PBI_DATASET_ID", "")


def trigger_powerbi_refresh(max_retries=2, retry_delay=120):
    if not PBI_ACCESS_TOKEN:
        return False, "Missing PBI_ACCESS_TOKEN"
    if not PBI_WORKSPACE_ID:
        return False, "Missing PBI_WORKSPACE_ID"
    if not PBI_DATASET_ID:
        return False, "Missing PBI_DATASET_ID"

    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/"
        f"{PBI_WORKSPACE_ID}/datasets/{PBI_DATASET_ID}/refreshes"
    )

    headers = {
        "Authorization": f"Bearer {PBI_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    for attempt in range(max_retries + 1):
        try:
            print(">>> CALLING POWER BI REFRESH API")
            print(">>> URL:", url)
            print(f">>> ATTEMPT: {attempt + 1}")

            response = requests.post(url, headers=headers, json={})

            print(">>> REFRESH API STATUS CODE:", response.status_code)
            print(">>> REFRESH API RESPONSE:", response.text)

            if response.status_code == 202:
                return True, "Power BI refresh started successfully."

            if response.status_code == 429:
                if attempt < max_retries:
                    print(f">>> RATE LIMITED. WAITING {retry_delay} SECONDS BEFORE RETRY...")
                    time.sleep(retry_delay)
                    continue
                return False, f"Power BI API rate limit exceeded after retries. Please retry later."

            return False, f"Refresh failed to start: {response.status_code} - {response.text}"

        except Exception as e:
            return False, f"Error calling Power BI API: {str(e)}"

    return False, "Unknown refresh error."