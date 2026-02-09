import os
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

import requests

from ..graph.state import JobState


def _normalize_cx(raw_cx: str) -> str:
    """
    Accept either a plain CX ID or a full Programmable Search URL and
    return only the CX ID expected by the API.
    """
    if not raw_cx:
        return ""

    value = raw_cx.strip()

    if "://" in value:
        parsed = urlparse(value)
        cx_values = parse_qs(parsed.query).get("cx", [])
        if cx_values and cx_values[0].strip():
            return cx_values[0].strip()
        return value

    if "cx=" in value:
        # Handles strings like "cx=...".
        cx_values = parse_qs(value).get("cx", [])
        if cx_values and cx_values[0].strip():
            return cx_values[0].strip()

    return value


def _print_google_api_error(message: str) -> None:
    lowered = message.lower()

    if "custom search api has not been used" in lowered or "it is disabled" in lowered:
        print("Google API Error: Custom Search API is disabled for this API key's project.")
        print("Fix: enable 'Custom Search API' in Google Cloud Console, then retry in a few minutes.")
        return

    if "invalid value" in lowered and "cx" in lowered:
        print("Google API Error: invalid GOOGLE_SEARCH_CX.")
        print("Fix: use only the CX ID (for example: 0123456789abcdef), not the full cse.google.com URL.")
        return

    print(f"Google API Error: {message}")


def fetch_from_google(query: str, site: str) -> List[Dict[str, Any]]:
    api_key = os.getenv("GOOGLE_API_KEY")
    raw_cx = os.getenv("GOOGLE_SEARCH_CX", "")
    cx = _normalize_cx(raw_cx)

    if not api_key or not cx:
        print("Warning: GOOGLE_API_KEY or GOOGLE_SEARCH_CX is missing.")
        return []

    search_term = f'site:{site} "{query}"'
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": search_term,
        "gl": os.getenv("GOOGLE_SEARCH_GL", "us"),
    }

    try:
        response = requests.get(url, params=params, timeout=20)

        try:
            data = response.json()
        except ValueError:
            print(f"Google Search Failed for {site}: non-JSON response (HTTP {response.status_code}).")
            return []

        if response.status_code >= 400 or "error" in data:
            error_message = data.get("error", {}).get("message", f"HTTP {response.status_code}")
            _print_google_api_error(error_message)
            return []

        items = data.get("items", [])
        print(f"   Found {len(items)} results on {site}")

        jobs: List[Dict[str, Any]] = []
        for item in items:
            jobs.append(
                {
                    "id": item.get("link"),
                    "title": item.get("title"),
                    "company": site,
                    "url": item.get("link"),
                    "description": item.get("snippet", ""),
                    "date": "Recent",
                }
            )

        return jobs

    except requests.RequestException as exc:
        print(f"Google Search Failed for {site}: {exc}")
        return []
    except Exception as exc:
        print(f"Unexpected Google Search error for {site}: {exc}")
        return []


def fetch_google_jobs(state: JobState):
    query = state.get("search_query", "python")
    sites_to_scan = state.get("google_search_sites", ["linkedin.com/jobs", "naukri.com"])

    print(f"Scanning {len(sites_to_scan)} sites via Google...")

    all_jobs: List[Dict[str, Any]] = []
    for site in sites_to_scan:
        all_jobs.extend(fetch_from_google(query, site))

    results_wrapper = [{"source": "google_search", "payload": job} for job in all_jobs]
    return {"raw_results": results_wrapper}
