import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import pandas as pd
from ..models.job import Job
from dotenv import load_dotenv  
from datetime import datetime, timedelta
from .date_utils import parse_any_date, to_us_date



load_dotenv()

# --- CONNECTION SETUP ---
def get_sheet_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = None
    
    # 1. Check for Cloud Secrets (GitHub Actions)
    creds_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_env:
        try:
            # strict=False helps parse slightly messy JSON strings from Cloud environments
            creds_dict = json.loads(creds_env, strict=False)
        except Exception as e:
            print(f"❌ CRITICAL: Failed to parse GOOGLE_CREDENTIALS_JSON. Is it formatted correctly in GitHub Secrets? Error: {e}")
            return None
            
    # 2. Check for Local File
    elif os.path.exists("credentials.json"):
        try: 
            creds_dict = json.load(open("credentials.json"))
        except Exception as e:
            print(f"❌ CRITICAL: Failed to read local credentials.json file. Error: {e}")
            return None
            
    if not creds_dict: 
        print("❌ CRITICAL: No Google Credentials found at all!")
        return None

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet_url = os.getenv("GOOGLE_SHEET_URL")
        if not sheet_url: 
            print("❌ CRITICAL: GOOGLE_SHEET_URL is missing!")
            return None
        return client.open_by_url(sheet_url)
    except Exception as e:
        print(f"❌ CRITICAL: Failed to connect to Google Sheets API: {e}")
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



def log_job_hunt(role):
    """Logs the timestamp of a job hunt to prevent redundant automated runs."""
    try:
        sh = get_sheet_connection()
        if not sh: return
        
        # 1. Try to open the history sheet, or create it if it doesn't exist
        try:
            ws = sh.worksheet("Run_History")
        except:
            ws = sh.add_worksheet(title="Run_History", rows="100", cols="2")
            ws.append_row(["Role", "Last_Run_Timestamp"])
            
        now_str = datetime.utcnow().isoformat()
        
        # 2. Update the time if the role exists, or append a new row
        try:
            cell = ws.find(role, in_column=1)
            ws.update_cell(cell.row, 2, now_str)
        except:
            ws.append_row([role, now_str])
            
        print(f"📝 Logged '{role}' search to history.")
    except Exception as e:
        print(f"⚠️ Failed to log run history: {e}")

def should_skip_run(role, hours_cooldown=12):
    """Checks if a role was searched manually or automatically in the last X hours."""
    try:
        sh = get_sheet_connection()
        if not sh: return False
        
        try:
            ws = sh.worksheet("Run_History")
        except:
            return False # Sheet doesn't exist yet, so don't skip
            
        try:
            cell = ws.find(role, in_column=1)
            last_run_str = ws.cell(cell.row, 2).value
            last_run = datetime.fromisoformat(last_run_str)
            
            # If the time since the last run is LESS than our cooldown, SKIP IT
            if datetime.utcnow() - last_run < timedelta(hours=hours_cooldown):
                return True
        except:
            pass # Role not found in sheet, safe to run
            
        return False
    except:
        return False    


def save_dismissed_job(job):
    """Saves a dismissed job to the Graveyard so the bot never fetches it again."""
    try:
        sh = get_sheet_connection()
        if not sh: return
        
        try:
            ws = sh.worksheet("Dismissed_Jobs")
        except:
            # Create the Graveyard if it doesn't exist
            ws = sh.add_worksheet(title="Dismissed_Jobs", rows="100", cols="4")
            ws.insert_row(["ID", "Title", "Company", "Date Dismissed"], index=1)
        
        existing_ids = set(ws.col_values(1))
        if str(job.id) not in existing_ids:
            from datetime import datetime
            ws.append_row([
                str(job.id), 
                job.title, 
                getattr(job, "company", "Unknown"), 
                datetime.now().strftime("%Y-%m-%d")
            ])
            print(f"👻 Sent '{job.title}' to the Graveyard.")
            
    except Exception as e:
        print(f"❌ Error dismissing job: {e}")

def get_already_saved_ids():
    """Reads all known job IDs from every sheet, including the Graveyard."""
    try:
        sh = get_sheet_connection()
        if not sh: return set()
        
        ids = set()
        # 🛡️ Look at all sheets so we never re-process old data
        sheets_to_check = ["New_Matches", "Tracker", "Manual_Jobs", "Dismissed_Jobs"]
        
        for s_name in sheets_to_check:
            try:
                ws = sh.worksheet(s_name)
                col_vals = ws.col_values(1)
                if len(col_vals) > 1:
                    ids.update(col_vals[1:]) # Skip the header row
            except:
                pass # Tab doesn't exist yet, skip it
                
        return ids
    except Exception as e:
        print(f"❌ Error fetching saved IDs: {e}")
        return set()
    
def clear_graveyard():
    """Wipes all dismissed jobs from the Graveyard tab."""
    try:
        sh = get_sheet_connection()
        if not sh: return False
        
        try:
            ws = sh.worksheet("Dismissed_Jobs")
            ws.clear() # Nuke all the data
            
            # Re-inject the clean headers
            ws.insert_row(["ID", "Title", "Company", "Date Dismissed"], index=1)
            print("🗑️ Graveyard successfully cleared.")
            return True
        except:
            # If the tab doesn't exist yet, it's already "clear"!
            return True 
            
    except Exception as e:
        print(f"❌ Error clearing graveyard: {e}")
        return False
    

def save_new_matches(jobs):
    """Saves jobs using text dates in M/D/YYYY to avoid Google serial conversion."""
    try:
        sh = get_sheet_connection()
        if not sh: return
        
        try:
            ws = sh.worksheet("New_Matches")
        except:
            ws = sh.add_worksheet(title="New_Matches", rows="100", cols="8")
            ws.append_row(["ID", "Title", "Company", "Platform", "URL", "Date Posted", "Score", "Reasoning"])

        # 1. Current day for fallback and daily cap checks
        # today = datetime.now().date()
        # 1. Get current date for comparison
        today_str = datetime.now().strftime("%Y-%m-%d")

        # 🛡️ 2. CHECK GLOBAL DAILY LIMIT (Checking Column 6: Date Posted)
        all_rows = ws.get_all_values()
        today_count = 0
        
        if len(all_rows) > 1:
            # We look at index 5 (Column 6) which is where 'Date Posted' is stored
            # We use 'in' to handle cases where the date has a single quote prefix
            today_count = sum(1 for row in all_rows if len(row) >= 6 and today_str in str(row[5]))

        if today_count >= 15:
            print(f"🛑 [SAFETY VALVE] Already saved {today_count}/15 jobs today. Skipping.")
            return

        # 3. CALCULATE REMAINING CAPACITY
        slots_left = 15 - today_count
        to_save = jobs[:slots_left]

        # 🛡️ 2. CHECK SHEET FOR EXISTING IDs (Preventing duplicates)
        existing_ids = set(ws.col_values(1))
        existing_url = set(ws.col_values(5)) # Also track URLs to prevent duplicates if IDs are missing

        for job in to_save:
            if saved_now >= slots_left: break
            
            # Skip if url already exists in sheet
            if str(job.url) in existing_url:
                continue

            # Standardize to M/D/YYYY and write as RAW text.
            date_val = to_us_date(job.posted_at, fallback_today=True)
            
            row = [
                str(job.id),
                job.title,
                getattr(job, "company", "Unknown"),
                job.platform,
                job.url,
                date_val,                 # Column 6: Date Posted
                str(job.relevance_score),  # Column 7: Score
                job.reasoning              # Column 8: Reasoning
            ]
            ws.append_row(row, value_input_option="RAW")
            existing_ids.add(str(job.id))
            saved_now += 1
            print(f"✅ Saved Elite Match: {job.title} (Date: {date_val})")

    except Exception as e:
        print(f"❌ Persistence Save Error: {e}")

def delete_new_match(job_id):
    """Deletes a specific job from the New_Matches sheet."""
    try:
        sh = get_sheet_connection()
        if not sh: return
        ws = sh.worksheet("New_Matches")
        cell = ws.find(str(job_id), in_column=1)
        if cell: 
            ws.delete_rows(cell.row)
            print(f"🗑️ Deleted job {job_id} from New_Matches")
    except Exception as e:
        print(f"❌ Error deleting match: {e}")


def load_new_matches():
    """Loads all jobs and normalizes Date Posted to M/D/YYYY."""
    try:
        sh = get_sheet_connection()
        if not sh: return []
        ws = sh.worksheet("New_Matches")
        data = ws.get_all_records()
        
        jobs = []
        for d in data:
            # Helper to safely get keys (case-insensitive)
            def g(k): return d.get(k) or d.get(k.lower()) or ""
            
            j = Job(
                id=str(g("ID")), 
                platform=g("Platform"), 
                title=g("Title"), 
                company=g("Company"), 
                description="", 
                url=g("URL")
            )
            
            j.posted_at = to_us_date(g("Date Posted"))
            if not j.posted_at:
                j.posted_at = "Recently Found"

            try: 
                j.relevance_score = int(float(g("Score")))
            except: 
                j.relevance_score = 0
                
            j.reasoning = g("Reasoning")
            jobs.append(j)
            
        return jobs
    except Exception as e:
        print(f"❌ Error loading matches: {e}")
        return []


def normalize_new_matches_dates():
    """Converts existing New_Matches date cells to M/D/YYYY text format."""
    try:
        sh = get_sheet_connection()
        if not sh:
            return 0

        ws = sh.worksheet("New_Matches")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return 0

        updates = 0
        for i, row in enumerate(rows[1:], start=2):
            if len(row) < 6:
                continue

            current_raw = str(row[5]).replace("'", "").strip()
            normalized = to_us_date(current_raw)
            if not normalized:
                continue

            if current_raw != normalized:
                ws.update_cell(i, 6, normalized)
                updates += 1

        return updates
    except Exception as e:
        print(f"❌ Error normalizing dates: {e}")
        return 0
