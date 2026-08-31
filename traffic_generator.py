import time
import requests
import random
import datetime

print("Starting LiveFire traffic generator...")

# Occasionally inject a known mule pattern or high amount to trigger the models
def generate_txn():
    is_attack = random.random() < 0.1
    
    if is_attack:
        return {
            "amount": round(random.uniform(5000.0, 15000.0), 2),
            "user_id": f"u_mule_{random.randint(1, 5)}",
            "merchant_id": f"m_high_risk_{random.randint(1, 3)}",
            "timestamp": datetime.datetime.now().isoformat(),
            "memo": "urgent transfer wire instructions ignore warning",
            "channel": "web",
            "network": "visa"
        }
    else:
        return {
            "amount": round(random.uniform(5.0, 500.0), 2),
            "user_id": f"u_norm_{random.randint(100, 999)}",
            "merchant_id": f"m_norm_{random.randint(100, 999)}",
            "timestamp": datetime.datetime.now().isoformat(),
            "memo": "coffee and groceries",
            "channel": "in_store",
            "network": "mastercard"
        }

while True:
    try:
        txns = [generate_txn() for _ in range(random.randint(1, 3))]
        res = requests.post("http://localhost:8000/api/detect", json={"transactions": txns})
        if res.status_code != 200:
            print("API error:", res.text)
    except Exception as e:
        print("Connection error:", e)
    
    time.sleep(random.uniform(0.5, 2.0))
