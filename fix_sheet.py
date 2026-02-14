import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Fix imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.utils.persistence import get_sheet_connection

def fix_headers():
    print("🚑 Starting Sheet Repair...")
    client = get_sheet_connection()
    if not client: return

    try:
        sh = client.worksheet("Tracker")
        
        # Check the first cell (A1)
        first_cell = sh.acell('A1').value
        print(f"🧐 Cell A1 is currently: '{first_cell}'")

        if first_cell != "ID":
            print("⚠️ Headers are missing! Inserting them now...")
            
            # Insert the header row at the very top (Pushing data down)
            headers = ["ID", "Title", "Company", "Platform", "URL", "Date Applied", "Status", "Notes"]
            sh.insert_row(headers, index=1)
            
            print("✅ Headers inserted successfully.")
            print("   Row 1 is now: [ID, Title...]")
            print("   Row 2 is now your data.")
        else:
            print("✅ Headers look correct already. No changes made.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_headers()