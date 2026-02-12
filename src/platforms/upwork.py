import os
import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
GRAPHQL_URL = "https://api.upwork.com/graphql"
DEFAULT_ROWS = 25
MAX_RETRIES = 4

PUBLIC_JOB_SEARCH_QUERY = """
query publicMarketplaceJobPostingsSearch($marketPlaceJobFilter: PublicMarketplaceJobPostingsSearchFilter!) {
  publicMarketplaceJobPostingsSearch(marketPlaceJobFilter: $marketPlaceJobFilter) {
    jobs {
      title
      description
      ciphertext
      createdDateTime
      type
      engagement
      duration
      hourlyBudgetMin
      hourlyBudgetMax
      skills {
        name
        prettyName
      }
    }
    paging {
      total
      offset
      count
    }
  }
}
"""


def _requests_session() -> requests.Session:
    """Create a resilient HTTP session for Upwork endpoints."""
    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
        raise_on_status=False,
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": "HustleBot/1.0 (+https://github.com/yourusername/hustle-bot)",
            "Accept": "application/json",
        }
    )
    return session


def _get_access_token() -> Optional[str]:
    """Return an Upwork access token from env or refresh token exchange."""
    env_access_token = os.getenv("UPWORK_ACCESS_TOKEN")
    if env_access_token:
        return env_access_token

    client_id = os.getenv("UPWORK_CLIENT_ID")
    client_secret = os.getenv("UPWORK_CLIENT_SECRET")
    refresh_token = os.getenv("UPWORK_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        print(
            "⚠️ Upwork skipped: set UPWORK_ACCESS_TOKEN or "
            "UPWORK_CLIENT_ID + UPWORK_CLIENT_SECRET + UPWORK_REFRESH_TOKEN."
        )
        return None

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    session = _requests_session()

    try:
        # Preferred OAuth2 mode: client auth via HTTP Basic.
        response = session.post(
            TOKEN_URL,
            data=payload,
            auth=(client_id, client_secret),
            timeout=20,
        )

        # Compatibility fallback for apps expecting client credentials in form payload.
        if response.status_code in (400, 401):
            fallback_payload = {
                **payload,
                "client_id": client_id,
                "client_secret": client_secret,
            }
            response = session.post(TOKEN_URL, data=fallback_payload, timeout=20)

        response.raise_for_status()
        token_data = response.json()
    except Exception as exc:
        print(f"❌ Upwork token request failed: {exc}")
        return None

    access_token = token_data.get("access_token")
    new_refresh_token = token_data.get("refresh_token")

    if not access_token:
        print("❌ Upwork token response did not include access_token.")
        return None

    if new_refresh_token and new_refresh_token != refresh_token:
        print(
            "⚠️ Upwork returned a new refresh token. "
            "Update UPWORK_REFRESH_TOKEN in your .env."
        )

    return access_token


def _build_upwork_job_url(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    token = ciphertext if ciphertext.startswith("~") else f"~{ciphertext}"
    return f"https://www.upwork.com/jobs/{token}"


def fetch_upwork_api(query: str = "python developer", rows: int = DEFAULT_ROWS) -> List[Dict[str, Any]]:
    print(f"🌍 Connecting to Upwork API (query='{query}')...")

    access_token = _get_access_token()
    if not access_token:
        return []

    # Polite pacing to avoid bursty API traffic patterns.
    request_delay_s = float(os.getenv("UPWORK_REQUEST_DELAY_SECONDS", "0.5"))
    if request_delay_s > 0:
        time.sleep(request_delay_s)

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    tenant_id = os.getenv("UPWORK_TENANT_ID")
    if tenant_id:
        headers["X-Upwork-API-TenantId"] = tenant_id

    variables = {
        "marketPlaceJobFilter": {
            "searchExpression_eq": query,
            "pagination": {
                "offset": 0,
                "count": max(1, min(rows, 100)),
            },
        }
    }

    payload = {
        "query": PUBLIC_JOB_SEARCH_QUERY,
        "variables": variables,
    }

    session = _requests_session()

    try:
        response = session.post(GRAPHQL_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        print(f"❌ Upwork GraphQL request failed: {exc}")
        return []

    if body.get("errors"):
        first_error = body["errors"][0]
        message = first_error.get("message", "Unknown GraphQL error")
        print(f"❌ Upwork GraphQL error: {message}")
        return []

    jobs_data = (
        body.get("data", {})
        .get("publicMarketplaceJobPostingsSearch", {})
        .get("jobs", [])
    )

    jobs: List[Dict[str, Any]] = []
    for item in jobs_data:
        ciphertext = item.get("ciphertext") or ""
        skills = [
            (skill.get("prettyName") or skill.get("name"))
            for skill in (item.get("skills") or [])
            if (skill.get("prettyName") or skill.get("name"))
        ]

        jobs.append(
            {
                "id": ciphertext or item.get("title", ""),
                "title": item.get("title", "Untitled"),
                "description": item.get("description", ""),
                "link": _build_upwork_job_url(ciphertext),
                "published": item.get("createdDateTime"),
                "budget_min": float(item.get("hourlyBudgetMin") or 0.0),
                "budget_max": float(item.get("hourlyBudgetMax") or 0.0),
                "skills": skills,
                "location": "Unknown",
            }
        )

    print(f"✅ Retrieved {len(jobs)} raw jobs from Upwork API.")
    return jobs
