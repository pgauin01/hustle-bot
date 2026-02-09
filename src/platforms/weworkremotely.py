import feedparser
import ssl
from typing import List, Dict, Any

# Fix for SSL certificate errors
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

RSS_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

def fetch_weworkremotely(tag: str = None) -> List[Dict[str, Any]]:
    print(f"📡 Connecting to WeWorkRemotely RSS...")
    
    try:
        feed = feedparser.parse(RSS_URL)
        jobs = []
        
        for entry in feed.entries:
            # 1. Attempt to extract Company Name
            company = "Unknown"
            
            # Strategy A: Check 'author' field (Common in RSS)
            if hasattr(entry, 'author') and entry.author:
                company = entry.author
            
            # Strategy B: Check if Title is "Company: Role"
            elif ":" in entry.title:
                parts = entry.title.split(":")
                # Heuristic: Company is usually the shorter part at the start
                if len(parts[0]) < 50:
                    company = parts[0].strip()

            job = {
                "id": entry.id,
                "title": entry.title,
                "company": company,  # <--- Storing it here
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