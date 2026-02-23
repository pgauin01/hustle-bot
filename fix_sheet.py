import time
import gspread
from src.utils.google_sheets import get_sheet_connection
from dotenv import load_dotenv
load_dotenv()

# Define the exact headers the Python dashboard requires
SHEET_SCHEMAS = {
    "New_Matches": ["ID", "Title", "Company", "Platform", "URL", "Date Posted", "Score", "Reasoning"],
    "Manual_Jobs": ["ID", "Title", "Company", "Description", "URL", "Score", "Reason", "Gap Analysis"],
    "Tracker": ["ID", "Title", "Company", "Platform", "URL", "Date Applied", "Status", "Notes"],
    "Cover_Letters": ["Job ID", "Company", "Date Created", "Content"],
    "Run_History": ["Role", "Last_Run_Timestamp"]
}

def fix_all_sheets():
    print("🚀 Connecting to Google Sheets...")
    sh = get_sheet_connection()
    if not sh:
        print("❌ Could not connect to Google Sheets. Check your credentials.")
        return

    for sheet_name, expected_headers in SHEET_SCHEMAS.items():
        print(f"\n🛠️ Inspecting tab: {sheet_name}...")
        
        # 1. Check if tab exists
        try:
            ws = sh.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            print(f"   ➕ Tab doesn't exist. Creating {sheet_name}...")
            ws = sh.add_worksheet(title=sheet_name, rows="100", cols=str(len(expected_headers)))
            ws.append_row(expected_headers)
            continue
            
        # 2. Fetch all current data
        all_values = ws.get_all_values()
        
        if not all_values:
            print(f"   ⚠️ Sheet is completely empty. Inserting headers...")
            ws.insert_row(expected_headers, index=1)
            continue
            
        # 3. Clean up ghost rows at the very top
        rows_deleted = 0
        while all_values and not any(str(cell).strip() for cell in all_values[0]):
            print(f"   🧹 Found blank Row 1. Deleting...")
            ws.delete_rows(1)
            all_values.pop(0)
            rows_deleted += 1
            time.sleep(1) # Prevent API rate limits
            
        if rows_deleted > 0:
            all_values = ws.get_all_values()
            
        # 4. Enforce Correct Headers
        if not all_values or all_values[0][0] != expected_headers[0]:
            print(f"   🚨 Headers missing or corrupted. Forcing correct headers at Row 1...")
            ws.insert_row(expected_headers, index=1)
            time.sleep(1)
        else:
            print(f"   ✅ Row 1 is healthy and contains correct headers.")
            
    print("\n🎉 All sheets have been fixed and standardized!")

if __name__ == "__main__":
    fix_all_sheets()