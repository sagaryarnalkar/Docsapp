import requests
import json

DEEPSEEK_R1_API = "https://api.deepseek.com/generate_embedding"
DEEPSEEK_API_KEY = "sk-54cd5e49a0a24fa6a9ff77c8a4ceb6f8"

def generate_document_embedding(text):
    """
    Calls DeepSeek R1 API to generate a semantic embedding vector.
    """
    payload = {"text": text[:3000]}  # Truncate to avoid extra API cost
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}

    response = requests.post(DEEPSEEK_R1_API, json=payload, headers=headers)

    if response.status_code == 200:
        return json.dumps(response.json().get("embedding", []))
    else:
        print(f"❌ DeepSeek API Error: {response.text}")
        return None
