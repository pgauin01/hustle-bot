import json
import os
from datetime import datetime

FILE_PATH = "my_applications.json"

def load_applications():
    if not os.path.exists(FILE_PATH):
        return []
    with open(FILE_PATH, "r") as f:
        return json.load(f)

def save_application(job_obj, status="Applied"):
    apps = load_applications()
    
    # Check if already exists
    for app in apps:
        if app["id"] == job_obj.id:
            return # Already tracked

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
    with open(FILE_PATH, "w") as f:
        json.dump(apps, f, indent=2)

def update_status(job_id, new_status, notes=""):
    apps = load_applications()
    for app in apps:
        if app["id"] == job_id:
            app["status"] = new_status
            if notes: app["notes"] = notes
            break
    with open(FILE_PATH, "w") as f:
        json.dump(apps, f, indent=2)