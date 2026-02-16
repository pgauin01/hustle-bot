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

# --- 3. COVER LETTERS (UPDATED) ---
def save_cover_letter(job_id, content, company="Unknown"):
    """Saves letter with Company Name."""
    try:
        sh = get_sheet_connection()
        if not sh: return

        try: worksheet = sh.worksheet("Cover_Letters")
        except: worksheet = sh.add_worksheet(title="Cover_Letters", rows="100", cols="5")
            
        # UPDATE: Check for 4 columns now
        first_row = []
        try: first_row = worksheet.row_values(1)
        except: pass
        
        # Force Header Update if missing or old format
        if not first_row or first_row[1] != "Company":
            # If header[1] is "Date Created", it's the old format!
            if first_row and first_row[1] == "Date Created":
                print("⚠️ Detected old Cover Letter sheet. Inserting Company column...")
                worksheet.insert_cols([["Company"] * len(worksheet.col_values(1))], col=2)
                worksheet.update_cell(1, 2, "Company") # Fix header
            else:
                worksheet.insert_row(["Job ID", "Company", "Date Created", "Content"], index=1)

        cell = worksheet.find(str(job_id), in_column=1)
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        if cell:
            # Update: Col 2=Company, Col 3=Date, Col 4=Content
            worksheet.update_cell(cell.row, 2, company)
            worksheet.update_cell(cell.row, 3, date_str)
            worksheet.update_cell(cell.row, 4, content)
            print(f"✅ Updated Draft for {company}")
        else:
            row = [str(job_id), company, date_str, content]
            worksheet.append_row(row)
            print(f"✅ Saved New Draft for {company}")

    except Exception as e:
        print(f"❌ Cover Letter Save Error: {e}")

def load_cover_letters():
    """Returns dict: {job_id: {'company': X, 'date': Y, 'content': Z}}"""
    try:
        sh = get_sheet_connection()
        if not sh: return {}
        try: worksheet = sh.worksheet("Cover_Letters")
        except: return {}

        data = worksheet.get_all_records()
        letters = {}
        for d in data:
            # Helper for keys
            def g(k): return str(d.get(k) or d.get(k.lower()) or "")
            
            jid = g("Job ID")
            if jid:
                letters[jid] = {
                    "company": g("Company") or "Unknown",
                    "date": g("Date Created"),
                    "content": g("Content")
                }
        return letters
    except Exception as e:
        print(f"❌ Error loading letters: {e}")
        return {}
    

def delete_cover_letter(job_id):
    """
    Deletes the cover letter row for the given Job ID.
    """
    try:
        sh = get_sheet_connection()
        if not sh: return False
        
        ws = sh.worksheet("Cover_Letters")
        cell = ws.find(str(job_id), in_column=1)
        
        if cell:
            ws.delete_rows(cell.row)
            print(f"✅ Deleted Cover Letter for {job_id}")
            return True
        else:
            print(f"⚠️ Cover Letter {job_id} not found to delete.")
            return False
            
    except Exception as e:
        print(f"❌ Error deleting cover letter: {e}")
        return False    