import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import pandas as pd
from datetime import datetime
from ..models.job import Job

# --- GOOGLE SHEETS SETUP ---
def get_sheet_connection():
    """Connects to Google Sheets using credentials from Environment or JSON."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Check for credentials in Streamlit Secrets (Best for Cloud)
    # OR Environment Variables
    creds_dict = None
    if os.getenv("GOOGLE_CREDENTIALS_JSON"):
        creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    elif os.path.exists("credentials.json"):
        creds_dict = json.load(open("credentials.json"))
        
    if not creds_dict:
        return None # Fail gracefully

    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet_url = os.getenv("GOOGLE_SHEET_URL")
    return client.open_by_url(sheet_url)

# --- 1. TRACKER (Replaces my_applications.json) ---
def save_application(job_obj, status="Applied"):
    try:
        sh = get_sheet_connection()
        
        # Try to open "Tracker" tab. If missing, create it!
        try:
            worksheet = sh.worksheet("Tracker")
        except gspread.exceptions.WorksheetNotFound:
            print("⚠️ 'Tracker' tab not found. Creating it now...")
            worksheet = sh.add_worksheet(title="Tracker", rows="100", cols="10")
            # Add Headers
            worksheet.append_row(["ID", "Title", "Company", "Platform", "URL", "Date Applied", "Status", "Notes"])

        # Check for duplicates (Column A is ID)
        try:
            existing_ids = worksheet.col_values(1)
            if str(job_obj.id) in existing_ids:
                print(f"⚠️ Job {job_obj.id} is already tracked.")
                return # Skip duplicate
        except: pass # If sheet is empty, col_values might fail, just continue

        # Append the Data
        row = [
            str(job_obj.id),
            job_obj.title,
            getattr(job_obj, "company", "Unknown"),
            job_obj.platform,
            job_obj.url,
            datetime.now().strftime("%Y-%m-%d"),
            status,
            "" # Empty Notes
        ]
        worksheet.append_row(row)
        print(f"✅ Successfully tracked: {job_obj.title}")
        
    except Exception as e:
        print(f"❌ Tracker Save Error: {e}")

def load_applications():
    try:
        sh = get_sheet_connection()
        worksheet = sh.worksheet("Tracker")
        records = worksheet.get_all_records()
        return records
    except:
        return []

def update_status(job_id, new_status):
    try:
        sh = get_sheet_connection()
        worksheet = sh.worksheet("Tracker")
        
        # Find row with Job ID
        cell = worksheet.find(str(job_id))
        if cell:
            # Status is Column 7 (G)
            worksheet.update_cell(cell.row, 7, new_status)
    except Exception as e:
        print(f"Update Error: {e}")

# --- 2. MANUAL JOBS (Replaces manual_jobs.json) ---
def save_manual_job(job):
    try:
        sh = get_sheet_connection()
        worksheet = sh.worksheet("Manual_Jobs")
        
        row = [
            str(job.id),
            job.title,
            getattr(job, "company", "Unknown"),
            job.description,
            job.url,
            str(job.relevance_score),
            job.reasoning,
            getattr(job, "gap_analysis", "")
        ]
        worksheet.append_row(row)
    except Exception as e:
        print(f"Manual Save Error: {e}")

def load_manual_jobs():
    try:
        sh = get_sheet_connection()
        worksheet = sh.worksheet("Manual_Jobs")
        data = worksheet.get_all_records()
        
        jobs = []
        for d in data:
            j = Job(
                id=str(d["id"]),
                platform="Manual Entry",
                title=d["title"],
                company=d["company"],
                description=d["description"],
                url=d["url"],
                budget_min=0, budget_max=0
            )
            j.relevance_score = int(d["relevance_score"])
            j.reasoning = d["reasoning"]
            j.gap_analysis = d["gap_analysis"]
            jobs.append(j)
        return jobs
    except:
        return []

def delete_manual_job(job_id):
    try:
        sh = get_sheet_connection()
        worksheet = sh.worksheet("Manual_Jobs")
        cell = worksheet.find(str(job_id))
        if cell:
            worksheet.delete_rows(cell.row)
    except: pass

# --- 3. COVER LETTERS (Replaces drafted_letters.json) ---
# NOTE: Storing huge text in cells is risky. 
# For v1, we can stick to session state (non-persistent) or add a 'Letters' tab.
# Let's use session state for now to keep it simple, or return empty dict.
def save_cover_letter(job_id, content):
    pass # Skipped for simplicity in v1 Cloud

def load_cover_letters():
    return {}