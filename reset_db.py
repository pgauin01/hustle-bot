import time
import gspread
from src.utils.google_sheets import get_sheet_connection
from dotenv import load_dotenv
load_dotenv()

# The exact headers required for the dashboard to function
SHEET_SCHEMAS = {
    "New_Matches": ["ID", "Title", "Company", "Platform", "URL", "Date Posted", "Score", "Reasoning"],
    "Manual_Jobs": ["ID", "Title", "Company", "Description", "URL", "Score", "Reason", "Gap Analysis"],
    "Tracker": ["ID", "Title", "Company", "Platform", "URL", "Date Applied", "Status", "Notes"],
    "Cover_Letters": ["Job ID", "Company", "Date Created", "Content"],
    "Run_History": ["Role", "Last_Run_Timestamp"]
}

def reset_database():
    print("🚀 Connecting to Google Sheets...")
    sh = get_sheet_connection()
    if not sh:
        print("❌ Could not connect to Google Sheets. Check your credentials.")
        return

    # 🛑 SAFETY LOCK: Prevent accidental deletion
    print("\n⚠️ WARNING: This will permanently DELETE ALL JOBS and HISTORY in your Google Sheets.")
    confirmation = input("Type 'YES' (all caps) to continue: ")
    
    if confirmation != 'YES':
        print("🛑 Operation aborted. Your data is safe.")
        return

    for sheet_name, expected_headers in SHEET_SCHEMAS.items():
        print(f"\n🧹 Resetting tab: {sheet_name}...")
        
        try:
            ws = sh.worksheet(sheet_name)
            # 1. Nuke the entire sheet (clears all data and weird formatting/ghost rows)
            ws.clear()
            print(f"   🗑️ Wiped old data.")
            
            # 2. Inject fresh, clean headers at Row 1
            ws.insert_row(expected_headers, index=1)
            print(f"   ✅ Inserted clean headers.")
            
        except gspread.exceptions.WorksheetNotFound:
            print(f"   ➕ Tab doesn't exist. Creating {sheet_name}...")
            ws = sh.add_worksheet(title=sheet_name, rows="100", cols=str(len(expected_headers)))
            ws.append_row(expected_headers)
            
        # 3. Throttle to prevent Google API from temporarily blocking us
        time.sleep(2) 

    print("\n🎉 Database successfully reset! Your HustleBot is completely fresh.")

if __name__ == "__main__":
    reset_database()