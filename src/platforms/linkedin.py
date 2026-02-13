import requests
from bs4 import BeautifulSoup
import time
import random

def fetch_linkedin_jobs(query="Python", location="Remote"):
    """
    Fetches jobs from LinkedIn's Guest API.
    :param query: Job role (e.g. "Python")
    :param location: "India", "Remote", "United States", etc.
    """
    base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    params = {
        "keywords": query,
        "location": location,
        "start": 0
    }

    print(f"   ...Contacting LinkedIn Guest API for '{query}' in '{location}'...")
    
    jobs = []
    try:
        # We fetch the first 25 jobs per location
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"   ⚠️ LinkedIn returned status {response.status_code}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        job_cards = soup.find_all("li")

        for card in job_cards:
            try:
                title_tag = card.find("h3", class_="base-search-card__title")
                company_tag = card.find("h4", class_="base-search-card__subtitle")
                loc_tag = card.find("span", class_="job-search-card__location")
                anchor_tag = card.find("a", class_="base-card__full-link")
                date_tag = card.find("time")

                if title_tag and anchor_tag:
                    # Clean up URL (remove tracking params)
                    clean_url = anchor_tag.get("href").split("?")[0]
                    
                    job = {
                        "id": clean_url, 
                        "title": title_tag.text.strip(),
                        "company": company_tag.text.strip() if company_tag else "Unknown",
                        "location": loc_tag.text.strip() if loc_tag else location,
                        "url": clean_url,
                        "date": date_tag.get("datetime") if date_tag else None,
                        "description": "LinkedIn Job - Click link to view full details." 
                    }
                    jobs.append(job)
            except Exception:
                continue
                
    except Exception as e:
        print(f"   ❌ LinkedIn Fetch Error: {e}")

    return jobs