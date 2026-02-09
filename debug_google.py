import os
import requests
import re
from dotenv import load_dotenv

# Load keys
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
CX_ID = os.getenv("GOOGLE_SEARCH_CX")

print("\n--- 🕵️ Google Project Detective ---")

if not API_KEY:
    print("❌ Error: GOOGLE_API_KEY is missing.")
    exit()

print(f"🔑 Testing Key: {API_KEY[:5]}...{API_KEY[-5:]}")

# We try a request. If it works, great. If it fails, we analyze why.
url = "https://www.googleapis.com/customsearch/v1"
params = {
    "key": API_KEY,
    "cx": CX_ID if CX_ID else "test", # Use dummy if missing to force key check
    "q": "test"
}

try:
    response = requests.get(url, params=params)
    data = response.json()
    
    # ---------------------------------------------------------
    # SCENARIO 1: Success (Key is Good!)
    # ---------------------------------------------------------
    if response.status_code == 200:
        print("\n✅ SUCCESS: This API Key is working perfectly!")
        print("   (Since it works, we can't see the Project ID in an error,")
        print("    but you don't need it because it's working!)")

    # ---------------------------------------------------------
    # SCENARIO 2: Failure (We extract the Clue)
    # ---------------------------------------------------------
    else:
        error_msg = data.get('error', {}).get('message', '')
        print(f"\n❌ Request Failed (Code {response.status_code})")
        print(f"⚠️ Google Message: '{error_msg}'")
        
        # Detective Work: Regex to find the Project Number
        match = re.search(r'project (\d+)', error_msg)
        if match:
            project_number = match.group(1)
            print(f"\n🔎 FOUND IT! This Key belongs to Project Number: {project_number}")
            print(f"👉 Go here to find this project: https://console.cloud.google.com/welcome?project={project_number}")
        else:
            print("\n🤷 Could not find Project Number in error message.")
            if response.status_code == 403:
                print("💡 Hint: This usually means the API is disabled or restricted.")

except Exception as e:
    print(f"❌ Error: {e}")