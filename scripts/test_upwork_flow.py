"""Simple smoke test for the Upwork fetch flow.

Usage:
  python scripts/test_upwork_flow.py --query "python developer" --rows 5

This script calls the production fetcher and prints a short summary.
It is safe to run without credentials: in that case it should return 0 jobs.
"""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.platforms.upwork import fetch_upwork_api


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Upwork API fetch flow")
    parser.add_argument("--query", default="python developer", help="Search query")
    parser.add_argument("--rows", type=int, default=5, help="Max number of rows to fetch (1-100)")
    args = parser.parse_args()

    rows = max(1, min(args.rows, 100))

    jobs = fetch_upwork_api(query=args.query, rows=rows)

    if not isinstance(jobs, list):
        print("❌ ERROR: fetch_upwork_api did not return a list")
        return 1

    print(f"✅ fetch_upwork_api returned {len(jobs)} jobs")

    for idx, job in enumerate(jobs[:3], start=1):
        title = job.get("title", "Untitled")
        link = job.get("link", "")
        print(f"  {idx}. {title} -> {link}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
