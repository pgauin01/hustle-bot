import os
import sys
from src.utils.persistence import load_applications, get_sheet_connection

def debug_tracker():
    print("\n🔍 --- DEBUGGING TRACKER ---")
    
    # 1. Test Connection
    print("\n1️⃣ Testing Connection...")
    client = get_sheet_connection()
    if not client:
        print("❌ Connection Failed. check credentials.")
        return
    print("✅ Connection Successful.")

    # 2. Inspect the Sheet Directly
    print("\n2️⃣ Inspecting 'Tracker' Tab...")
    try:
        sheet = client.worksheet("Tracker")
        data = sheet.get_all_values()
        
        if not data:
            print("❌ Sheet is completely empty (No headers, nothing).")
        else:
            print(f"✅ Found {len(data)} rows (including header).")
            print(f"   Header Row: {data[0]}")
            if len(data) > 1:
                print(f"   First Row Data: {data[1]}")
            else:
                print("⚠️ Sheet has headers but NO DATA rows.")
    except Exception as e:
        print(f"❌ Error accessing tab: {e}")

    # 3. Test the Load Function
    print("\n3️⃣ Testing load_applications()...")
    try:
        apps = load_applications()
        print(f"   Function returned: {type(apps)}")
        print(f"   Item count: {len(apps)}")
        if len(apps) > 0:
            print(f"   First Item: {apps[0]}")
        else:
            print("❌ Function returned empty list []")
    except Exception as e:
        print(f"❌ Function Crashed: {e}")

if __name__ == "__main__":
    # Fix imports to allow running from root
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    debug_tracker()