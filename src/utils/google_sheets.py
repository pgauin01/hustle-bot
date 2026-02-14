import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import pandas as pd
from datetime import datetime
from ..models.job import Job # <--- Need this to convert dicts back to Job objects

def get_sheet_connection(sheet_url=None):
    if not sheet_url:
        sheet_url = os.getenv("GOOGLE_SHEET_URL")
        if not sheet_url: return None

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    creds_dict = None
    if os.getenv("GOOGLE_CREDENTIALS_JSON"):
        try: creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
        except: pass
    elif os.path.exists("credentials.json"):
        try: creds_dict = json.load(open("credentials.json"))
        except: pass
        
    if not creds_dict: return None

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open_by_url(sheet_url)
    except: return None

def log_jobs_to_sheet(jobs, sheet_url):
    """Logs a list of Job objects to the 'New_Matches' tab."""
    if not jobs: return

    try:
        sh = get_sheet_connection(sheet_url)
        if not sh: return

        try:
            worksheet = sh.worksheet("New_Matches")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title="New_Matches", rows="100", cols="10")

        # ENFORCE HEADERS
        headers = ["ID", "Title", "Company", "Platform", "URL", "Date Posted", "Score", "Reasoning"]
        first_row = []
        try: first_row = worksheet.row_values(1)
        except: pass
        
        if not first_row or first_row[0] != "ID":
            worksheet.insert_row(headers, index=1)

        # Append Unique Jobs
        existing_ids = set(worksheet.col_values(1))
        new_rows = []
        for job in jobs:
            if str(job.id) not in existing_ids:
                row = [
                    str(job.id),
                    job.title,
                    getattr(job, "company", "Unknown"),
                    job.platform,
                    job.url,
                    str(job.posted_at) if job.posted_at else datetime.now().strftime("%Y-%m-%d"),
                    str(job.relevance_score),
                    job.reasoning
                ]
                new_rows.append(row)
        
        if new_rows:
            worksheet.append_rows(new_rows)
            print(f"✅ Logged {len(new_rows)} jobs to 'New_Matches'.")

    except Exception as e:
        print(f"❌ Google Sheets Error: {e}")

# --- NEW FUNCTIONS ---

def load_new_matches():
    """Reads all jobs from 'New_Matches' tab and returns Job objects."""
    try:
        sh = get_sheet_connection()
        if not sh: return []
        
        try:
            worksheet = sh.worksheet("New_Matches")
        except: return [] # Tab doesn't exist yet

        data = worksheet.get_all_records()
        jobs = []
        
        for d in data:
            # Helper to safely get keys (handles case sensitivity issues)
            def g(k): return str(d.get(k) or d.get(k.lower()) or "")

            j = Job(
                id=g("ID"),
                platform=g("Platform") or "Unknown",
                title=g("Title"),
                company=g("Company"),
                description="Loaded from Sheet (Desc unavailable)", # We don't save full desc to sheet to save space
                url=g("URL"),
                budget_min=0, budget_max=0
            )
            try: j.relevance_score = int(float(g("Score")))
            except: j.relevance_score = 0
            j.reasoning = g("Reasoning")
            j.posted_at = g("Date Posted")
            
            jobs.append(j)
            
        return jobs
    except Exception as e:
        print(f"Error loading matches: {e}")
        return []

def delete_new_match(job_id):
    """Deletes a job from 'New_Matches' tab."""
    try:
        sh = get_sheet_connection()
        if not sh: return
        
        worksheet = sh.worksheet("New_Matches")
        cell = worksheet.find(str(job_id), in_column=1)
        
        if cell:
            worksheet.delete_rows(cell.row)
            print(f"✅ Deleted ID {job_id} from New_Matches")
    except Exception as e:
        print(f"❌ Delete Error: {e}")