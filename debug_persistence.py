import os
import sys
from src.models.job import Job
from src.utils.persistence import save_application, save_manual_job, get_sheet_connection

# --- FAKE JOB DATA ---
fake_job = Job(
    id="debug_test_123",
    platform="Debug Script",
    title="Test Job Title",
    company="Test Company",
    description="This is a test description.",
    url="https://google.com",
    budget_min=0,
    budget_max=0,
    is_remote=True
)
fake_job.relevance_score = 99
fake_job.reasoning = "Test Reasoning"
fake_job.gap_analysis = "Test Gap Analysis"

def run_debug():
    print("\n🔍 --- DEBUGGING PERSISTENCE.PY ---")
    
    # 1. Test Connection Directly
    print("\n1️⃣ Testing Connection...")
    client = get_sheet_connection()
    if not client:
        print("❌ get_sheet_connection() returned None!")
        print("   -> Check your credentials.json or Environment Variables.")
        return
    else:
        print("✅ Connection Successful!")

    # 2. Test Manual Jobs Save
    print("\n2️⃣ Testing 'save_manual_job'...")
    try:
        save_manual_job(fake_job)
        print("   (Check your 'Manual_Jobs' tab now)")
    except Exception as e:
        print(f"❌ CRITICAL ERROR in save_manual_job: {e}")

    # 3. Test Tracker Save
    print("\n3️⃣ Testing 'save_application'...")
    try:
        save_application(fake_job, status="Debug_Applied")
        print("   (Check your 'Tracker' tab now)")
    except Exception as e:
        print(f"❌ CRITICAL ERROR in save_application: {e}")

if __name__ == "__main__":
    # Ensure we can import from src
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    run_debug()