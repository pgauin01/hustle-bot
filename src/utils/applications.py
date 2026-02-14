import json
import os
from datetime import datetime

FILE_PATH = "my_applications.json"

def load_applications():
    if not os.path.exists(FILE_PATH):
        return []
    try:
        with open(FILE_PATH, "r", encoding="utf-8") as f:
            apps = json.load(f)
            if isinstance(apps, list):
                return apps
            print(f"❌ Invalid tracker data format in {FILE_PATH}; expected a list.")
            return []
    except json.JSONDecodeError as e:
        print(f"❌ Could not parse {FILE_PATH}: {e}")
        return []
    except Exception as e:
        print(f"❌ Failed to load {FILE_PATH}: {e}")
        return []

def save_application(job_obj, status="Applied"):
    try:
        apps = load_applications()

        # Check if already exists
        for app in apps:
            if str(app.get("id")) == str(job_obj.id):
                return "exists"

        new_app = {
            "id": job_obj.id,
            "title": job_obj.title,
            "company": getattr(job_obj, "company", "Unknown"),
            "platform": job_obj.platform,
            "url": job_obj.url,
            "applied_date": datetime.now().strftime("%Y-%m-%d"),
            "status": status, # Applied, Interview, Offer, Rejected
            "notes": ""
        }

        apps.append(new_app)
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2)
        return "saved"
    except Exception as e:
        print(f"❌ Failed to save tracker entry: {e}")
        return "error"

def update_status(job_id, new_status, notes=""):
    apps = load_applications()
    for app in apps:
        if app["id"] == job_id:
            app["status"] = new_status
            if notes: app["notes"] = notes
            break
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(apps, f, indent=2)
