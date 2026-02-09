import requests
import os

def send_telegram_alert(job_title: str, job_url: str, score: int, reasoning: str, proposal: str = None):
    """
    Sends a formatted alert to your Telegram.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("⚠️ Telegram credentials missing. Skipping alert.")
        return

    # Format the message (HTML style)
    emoji = "🔥" if score >= 90 else "✨"
    
    message = (
        f"{emoji} <b>NEW MATCH FOUND!</b> ({score}/100)\n\n"
        f"<b>Role:</b> {job_title}\n"
        f"<b>Reason:</b> {reasoning}\n"
        f"<b>Link:</b> <a href='{job_url}'>Apply Now</a>\n"
    )
    
    if proposal:
        # Truncate proposal for preview
        preview = proposal[:200] + "..."
        message += f"\n<b>📝 Draft Preview:</b>\n<i>{preview}</i>"

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Failed to send Telegram alert: {e}")