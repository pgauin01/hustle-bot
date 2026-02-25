from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from ..models.job import Job
import time
import hashlib
import re
import asyncio
import sys


def _switch_to_proactor_policy_for_playwright():
    """
    On Windows, Playwright sync mode needs subprocess-capable event loops.
    Streamlit/Tornado may force Selector policy, which causes NotImplementedError.
    """
    if sys.platform != "win32":
        return None

    selector_policy_cls = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    proactor_policy_cls = getattr(asyncio, "WindowsProactorEventLoopPolicy", None)
    if not selector_policy_cls or not proactor_policy_cls:
        return None

    previous_policy = asyncio.get_event_loop_policy()
    if isinstance(previous_policy, selector_policy_cls):
        asyncio.set_event_loop_policy(proactor_policy_cls())
        return previous_policy

    return None

def fetch_ycombinator_jobs(query, max_jobs=15):
    """
    Scrapes Y Combinator using resilient URL-based routing, 
    and deep-fetches the actual job descriptions.
    """
    print(f"🔍 [YCombinator] Hunting for: {query}...")
    jobs_found = []
    seen_urls = set()

    formatted_query = query.replace(" ", "%20")
    url = f"https://www.workatastartup.com/companies?query={formatted_query}"

    previous_policy = _switch_to_proactor_policy_for_playwright()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })

            # --- PHASE 1: COLLECT JOB LINKS ---
            page.goto(url, wait_until="networkidle")
            time.sleep(4) 
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2)

            html_content = page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            job_links = soup.find_all("a", href=True)
            
            for link in job_links:
                href = link['href']
                
                if "/jobs/" in href and href not in seen_urls:
                    if len(jobs_found) >= max_jobs:
                        break
                        
                    seen_urls.add(href)
                    
                    job_title = link.get_text(separator=" ", strip=True) or "Startup Engineer"
                    company_name = "YC Startup" 
                    
                    card = link
                    for _ in range(5):
                        if card.parent:
                            card = card.parent
                            
                    if card:
                        company_link = card.find("a", href=lambda h: h and "/companies/" in h)
                        if company_link:
                            extracted_name = company_link.get_text(strip=True)
                            if extracted_name:
                                company_name = extracted_name
                            else:
                                img = company_link.find("img")
                                if img and img.get("alt"):
                                    company_name = img.get("alt").replace(" logo", "")

                    full_url = href if href.startswith("http") else "https://www.workatastartup.com" + href
                    unique_str = f"yc_{job_title}_{full_url}".lower().replace(" ", "")
                    job_id = hashlib.md5(unique_str.encode()).hexdigest()[:10]

                    job = Job(
                        id=job_id,
                        platform="YCombinator",
                        title=job_title,
                        company=company_name,
                        description="Pending...", # Placeholder for now
                        url=full_url,
                        budget_min=0,
                        budget_max=0,
                        is_remote=True
                    )
                    jobs_found.append(job)

            # --- PHASE 2: DEEP FETCH DESCRIPTIONS ---
            if jobs_found:
                print(f"📖 [YCombinator] Deep fetching descriptions for {len(jobs_found)} jobs...")
                for job in jobs_found:
                    try:
                        # Navigate to the specific job page
                        page.goto(job.url, wait_until="domcontentloaded")
                        time.sleep(2) # Give React a second to render the text
                        
                        # Grab all text on the page
                        page_text = page.locator("body").inner_text()
                        
                        if page_text:
                            # Clean up messy whitespace/newlines so the LLM can read it easily
                            clean_text = re.sub(r'\n+', '\n', page_text).strip()
                            job.description = clean_text
                        else:
                            job.description = "Could not extract text from page."
                            
                    except Exception as e:
                        print(f"   ⚠️ Failed to fetch {job.url}: {e}")
                        job.description = "Fetch failed."

            browser.close()

    except Exception as e:
        print(f"❌ [YCombinator] Playwright Error: {e!r}")
    finally:
        if previous_policy is not None:
            asyncio.set_event_loop_policy(previous_policy)

    print(f"✅ [YCombinator] Successfully processed {len(jobs_found)} jobs.")
    return jobs_found

if __name__ == "__main__":
    test_jobs = fetch_ycombinator_jobs("AI Engineer", max_jobs=2)
    for j in test_jobs:
        print(f"\n🚀 {j.title} @ {j.company}")
        print(f"🔗 {j.url}")
        print("📝 FULL DESCRIPTION:")
        print("-" * 40)
        # Printing the whole thing instead of just the snippet
        print(j.description) 
        print("-" * 40)
