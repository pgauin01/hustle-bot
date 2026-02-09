import feedparser
import ssl
from typing import List, Dict, Any

# Fix for SSL certificate errors on some machines
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

RSS_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

def fetch_weworkremotely(tag: str = None) -> List[Dict[str, Any]]:
    """
    Fetches jobs from WeWorkRemotely RSS feed.
    Note: WWR RSS doesn't support tag filtering directly in the URL, 
    so we fetch all and filter in Python if needed.
    """
    print(f"📡 Connecting to WeWorkRemotely RSS...")
    
    try:
        feed = feedparser.parse(RSS_URL)
        jobs = []
        
        for entry in feed.entries:
            # WWR Title format is usually: "Job Title: Company Name" or similar
            # We will leave cleaning to the normalizer, just grab raw data
            job = {
                "id": entry.id,
                "title": entry.title,
                "link": entry.link,
                "description": entry.description,
                "published": entry.published
            }
            jobs.append(job)
            
        print(f"✅ Retrieved {len(jobs)} raw jobs from WeWorkRemotely.")
        return jobs
        
    except Exception as e:
        print(f"❌ WeWorkRemotely Failed: {e}")
        return []