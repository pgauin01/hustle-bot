import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime

def get_gspread_client():
    """
    Authenticates with Google Sheets using local file OR GitHub Secret.
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 1. Try Loading from GitHub Secret (String)
    json_creds = os.getenv("GOOGLE_SHEETS_JSON")
    if json_creds:
        creds_dict = json.loads(json_creds)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)

    # 2. Try Loading from Local File
    if os.path.exists("credentials.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        return gspread.authorize(creds)
        
    print("⚠️ No Google Sheets credentials found. Skipping logging.")
    return None

def log_jobs_to_sheet(jobs, sheet_url):
    """
    Appends a list of Job objects to the Google Sheet.
    """
    client = get_gspread_client()
    if not client:
        return

    try:
        # Open by URL
        sheet = client.open_by_url(sheet_url).sheet1
        
        # Check if header exists, if not add it
        if not sheet.get_all_values():
            header = ["Date", "Role", "Company", "Platform", "Score", "Reason", "Link", "Status"]
            sheet.append_row(header)

        # Prepare rows
        rows_to_add = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        print(f"📝 Logging {len(jobs)} jobs to Google Sheets...")

        for job in jobs:
            # Format: [Date, Role, Company, Platform, Score, Reason, Link, Status]
            row = [
                today,
                job.title,
                getattr(job, 'company', 'Unknown'),
                job.platform,
                job.relevance_score,
                job.reasoning,
                job.url,
                "Applied" if job.relevance_score > 90 else "To Review"
            ]
            rows_to_add.append(row)

        # Bulk append (Faster than one by one)
        if rows_to_add:
            sheet.append_rows(rows_to_add)
            print("✅ Successfully logged to Google Sheets.")
            
    except Exception as e:
        # Change this line to use repr(e) to see the full error object
        print(f"❌ Failed to log to Sheets: {repr(e)}")