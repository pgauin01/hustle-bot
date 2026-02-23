import os
import requests

def send_telegram_alert(job):
    """
    Sends a highly formatted HTML message to your Telegram app.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("⚠️ Telegram credentials missing. Skipping notification.")
        return False

    # 1. Dynamic Emoji based on your AI Score
    score = getattr(job, "relevance_score", 0)
    if score >= 90:
        badge = "🔥 <b>UNICORN MATCH</b> 🔥"
    elif score >= 80:
        badge = "🚀 <b>HIGH MATCH</b>"
    else:
        badge = "✅ <b>GOOD MATCH</b>"

    # 2. Build the HTML Message
    # We use getattr() safely in case a job board didn't provide a company name
    message = f"""
{badge}

💼 <b>Role:</b> {job.title}
🏢 <b>Company:</b> {getattr(job, 'company', 'Unknown')}
📍 <b>Source:</b> <i>{job.platform}</i>

🎯 <b>Score:</b> {score}/100

🧠 <b>AI Reasoning:</b>
{getattr(job, 'reasoning', 'No reasoning provided.')}

🔗 <a href="{job.url}">View & Apply Here</a>
    """

    # 3. Send to Telegram API
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True  # <--- PRO TIP: Keeps your chat clean by hiding the massive website preview box
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"📲 Telegram alert sent for: {job.title}")
            return True
        else:
            print(f"❌ Telegram API Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Telegram Crash: {e}")
        return False