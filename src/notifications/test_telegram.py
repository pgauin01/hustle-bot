import requests

# --- PASTE YOUR KEYS HERE FOR TESTING ---
BOT_TOKEN = "8414765923:AAFeo3t6Xah7AMOiP-u7qyes-qMWNM3sPHk"  # e.g. 7123456:AAH...
CHAT_ID = "7966277270"        # e.g. 987654321

def test_alert():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": "🔥 <b>Test Alert:</b> If you see this, your Job Agent is connected!",
        "parse_mode": "HTML"
    }
    
    print(f"📡 Sending test message to {CHAT_ID}...")
    
    try:
        response = requests.post(url, json=payload)
        res_json = response.json()
        
        if response.status_code == 200 and res_json.get("ok"):
            print("✅ SUCCESS! Check your Telegram app.")
        else:
            print(f"❌ FAILED. API Response: {res_json}")
            print("\nCommon fixes:")
            print("1. Did you search for YOUR bot and click 'Start'?")
            print("2. Is the Chat ID correct? (Use @userinfobot)")
            
    except Exception as e:
        print(f"❌ Network Error: {e}")

if __name__ == "__main__":
    test_alert()