import requests
import json

# Test the forecast API
url = "http://127.0.0.1:8000/api/forecast/forecast/"
headers = {"Content-Type": "application/json"}
data = {"tenant_id": 1, "target_month": 12}

try:
    response = requests.post(url, headers=headers, data=json.dumps(data))
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")