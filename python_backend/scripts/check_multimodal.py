import requests

try:
    response = requests.get("http://127.0.0.1:8011/api/multimodal/supported-formats")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
