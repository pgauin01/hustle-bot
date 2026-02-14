import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import pandas as pd
from datetime import datetime
from ..models.job import Job
from dotenv import load_dotenv  


load_dotenv()

# --- GOOGLE SHEETS SETUP ---
def get_sheet_connection():
    """Connects to Google Sheets using credentials from Environment or JSON."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. Try Loading from GitHub Secret/Env Var (String)
    creds_dict = None
    if os.getenv("GOOGLE_CREDENTIALS_JSON"):
        try:
            creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
        except json.JSONDecodeError:
            print("❌ Error: GOOGLE_CREDENTIALS_JSON is not valid JSON.")
            return None

    # 2. Try Loading from Local File
    elif os.path.exists("credentials.json"):
        try:
            creds_dict = json.load(open("credentials.json"))
        except json.JSONDecodeError:
            print("❌ Error: credentials.json is corrupted.")
            return None
        
    if not creds_dict:
        print("❌ No Google Sheet credentials found.")
        return None

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet_url = os.getenv("GOOGLE_SHEET_URL")
        if not sheet_url:
            print("❌ GOOGLE_SHEET_URL is missing from settings.")
            return None
            
        return client.open_by_url(sheet_url)
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None

# --- 1. TRACKER (Self-Healing) ---
def save_application(job_obj, status="Applied"):
    try:
        sh = get_sheet_connection()
        if not sh: return

        # 1. Get or Create "Tracker" tab
        try:
            worksheet = sh.worksheet("Tracker")
        except gspread.exceptions.WorksheetNotFound:
            print("⚠️ 'Tracker' tab not found. Creating it now...")
            worksheet = sh.add_worksheet(title="Tracker", rows="100", cols="10")
        
        # 2. Ensure Headers Exist
        if not worksheet.get_all_values():
            worksheet.append_row(["ID", "Title", "Company", "Platform", "URL", "Date Applied", "Status", "Notes"])

        # 3. Check for duplicates (Column A is ID)
        existing_ids = worksheet.col_values(1)
        job_id_str = str(job_obj.id).strip()
        
        if job_id_str in existing_ids:
            print(f"⚠️ Job {job_id_str} is already tracked.")
            return 

        # 4. Append the Data
        row = [
            job_id_str,
            job_obj.title,
            getattr(job_obj, "company", "Unknown"),
            job_obj.platform,
            job_obj.url,
            datetime.now().strftime("%Y-%m-%d"),
            status,
            ""
        ]
        worksheet.append_row(row)
        print(f"✅ Successfully tracked: {job_obj.title}")
        
    except Exception as e:
        print(f"❌ Tracker Save Error: {e}")

def load_applications():
    try:
        sh = get_sheet_connection()
        if not sh: return []
        
        worksheet = sh.worksheet("Tracker")
        records = worksheet.get_all_records()
        return records
    except:
        return []

def update_status(job_id, new_status):
    try:
        sh = get_sheet_connection()
        if not sh: return
        
        worksheet = sh.worksheet("Tracker")
        
        # IMPROVEMENT: Search ONLY in Column 1 (The ID Column)
        # This prevents bugs where it finds the ID in a URL or description
        cell = worksheet.find(str(job_id), in_column=1)
        
        if cell:
            # Status is Column 7 (G)
            worksheet.update_cell(cell.row, 7, new_status)
            print(f"✅ Updated status for {job_id} to {new_status}")
        else:
            print(f"⚠️ Could not find Job ID: {job_id} in Tracker sheet.")
            
    except Exception as e:
        print(f"❌ Update Error: {e}")

# --- 2. MANUAL JOBS (Self-Healing) ---
def save_manual_job(job):
    try:
        sh = get_sheet_connection()
        if not sh: return

        # 1. Get or Create "Manual_Jobs" tab
        try:
            worksheet = sh.worksheet("Manual_Jobs")
        except gspread.exceptions.WorksheetNotFound:
            print("⚠️ 'Manual_Jobs' tab not found. Creating it now...")
            worksheet = sh.add_worksheet(title="Manual_Jobs", rows="100", cols="10")

        # 2. Ensure Headers Exist
        if not worksheet.get_all_values():
            worksheet.append_row(["ID", "Title", "Company", "Description", "URL", "Score", "Reason", "Gap Analysis"])

        # 3. Append Data
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
        
        try:
            worksheet = sh.worksheet("Manual_Jobs")
        except gspread.exceptions.WorksheetNotFound:
            return [] # No manual jobs yet

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
                budget_min=0, budget_max=0,
                is_remote=True
            )
            # Safe conversion in case Score is empty/string
            try:
                j.relevance_score = int(float(d["Score"])) if d["Score"] else 0
            except:
                j.relevance_score = 0
                
            j.reasoning = d["Reason"]
            j.gap_analysis = d["Gap Analysis"]
            jobs.append(j)
        return jobs
    except Exception as e:
        print(f"Error loading manual jobs: {e}")
        return []

def delete_manual_job(job_id):
    try:
        sh = get_sheet_connection()
        if not sh: return
        
        worksheet = sh.worksheet("Manual_Jobs")
        cell = worksheet.find(str(job_id), in_column=1)
        if cell:
            worksheet.delete_rows(cell.row)
    except: pass

# --- 3. COVER LETTERS ---
def save_cover_letter(job_id, content):
    pass 

def load_cover_letters():
    return {}