import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import pandas as pd
from datetime import datetime
from ..models.job import Job
from dotenv import load_dotenv  


load_dotenv()

# --- CONNECTION SETUP ---
def get_sheet_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = None
    if os.getenv("GOOGLE_CREDENTIALS_JSON"):
        try: creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
        except: return None
    elif os.path.exists("credentials.json"):
        try: creds_dict = json.load(open("credentials.json"))
        except: return None
    if not creds_dict: return None

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet_url = os.getenv("GOOGLE_SHEET_URL")
        if not sheet_url: return None
        return client.open_by_url(sheet_url)
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

# --- 1. TRACKER ---
def save_application(job_obj, status="Applied"):
    try:
        sh = get_sheet_connection()
        if not sh: return
        try: worksheet = sh.worksheet("Tracker")
        except: worksheet = sh.add_worksheet(title="Tracker", rows="100", cols="10")
        
        # Header Check
        headers = ["ID", "Title", "Company", "Platform", "URL", "Date Applied", "Status", "Notes"]
        vals = worksheet.get_all_values()
        if not vals or vals[0][0] != "ID":
            worksheet.insert_row(headers, index=1)

        if str(job_obj.id) in worksheet.col_values(1): return

        row = [str(job_obj.id), job_obj.title, getattr(job_obj, "company", "Unknown"), job_obj.platform, job_obj.url, datetime.now().strftime("%Y-%m-%d"), status, ""]
        worksheet.append_row(row)
        print(f"✅ Tracked: {job_obj.title}")
    except Exception as e: print(f"❌ Tracker Error: {e}")

def load_applications():
    try:
        sh = get_sheet_connection()
        if not sh: return []
        return sh.worksheet("Tracker").get_all_records()
    except: return []

def update_status(job_id, new_status):
    try:
        sh = get_sheet_connection()
        if not sh: return
        ws = sh.worksheet("Tracker")
        cell = ws.find(str(job_id), in_column=1)
        if cell: ws.update_cell(cell.row, 7, new_status)
    except: pass

# --- 2. MANUAL JOBS (Updated) ---
def save_manual_job(job):
    try:
        sh = get_sheet_connection()
        if not sh: return

        try:
            worksheet = sh.worksheet("Manual_Jobs")
        except:
            worksheet = sh.add_worksheet(title="Manual_Jobs", rows="100", cols="10")

        # ENFORCE HEADERS
        headers = ["ID", "Title", "Company", "Description", "URL", "Score", "Reason", "Gap Analysis"]
        
        # Check first row
        first_row = []
        try: first_row = worksheet.row_values(1)
        except: pass
        
        if not first_row or first_row[0] != "ID":
            print("📝 Adding Headers to Manual_Jobs...")
            worksheet.insert_row(headers, index=1)

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
        print(f"✅ Saved Manual Job: {job.title}")

    except Exception as e:
        print(f"❌ Manual Save Error: {e}")

def load_manual_jobs():
    try:
        sh = get_sheet_connection()
        if not sh: return []
        try: worksheet = sh.worksheet("Manual_Jobs")
        except: return []
        
        data = worksheet.get_all_records()
        jobs = []
        for d in data:
            # Helper to safely get keys (case-insensitive fallback)
            def g(k): return d.get(k) or d.get(k.lower()) or ""
            
            j = Job(id=str(g("ID")), platform="Manual Entry", title=g("Title"), company=g("Company"), description=g("Description"), url=g("URL"), budget_min=0, budget_max=0, is_remote=True)
            try: j.relevance_score = int(float(g("Score")))
            except: j.relevance_score = 0
            j.reasoning = g("Reason")
            j.gap_analysis = g("Gap Analysis")
            jobs.append(j)
        return jobs
    except: return []

def delete_manual_job(job_id):
    try:
        sh = get_sheet_connection()
        if not sh: return
        ws = sh.worksheet("Manual_Jobs")
        cell = ws.find(str(job_id), in_column=1)
        if cell: ws.delete_rows(cell.row)
    except: pass

# --- 3. LETTERS ---
def save_cover_letter(job_id, content): pass
def load_cover_letters(): return {}