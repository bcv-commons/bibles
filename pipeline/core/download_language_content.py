#!/usr/bin/env python3
"""
DBT (Bible Brain, Digital Bible Platform, by Faith Comes By Hearing)
text-content fetch — the calls bibles needs from
what was originally MONO's full download/selection pipeline.

Used by fingerprint_versification.py (versification probing) and
scripts/confirm_text_availability.py (content-availability confirmation,
see examples/content-availability-confirmation.md) to fetch a single
book/chapter of plain text and — on failure — classify *why* it failed
(access-restricted vs. genuinely absent vs. network error), so a caller can
distinguish "confirmed absent" from "never checked." Everything else from
the original download_language_content.py — audio/timing fetch, fileset
selection, story-set/template parsing, version-exclude checks, the CLI —
has been removed; nothing in this repo calls any of it.

Requires BIBLE_API_KEY in .env.
"""

import os
import sys
from datetime import datetime
from typing import Dict, Optional

try:
    import requests
    from dotenv import load_dotenv
except ImportError as e:
    print("Error: Required packages not installed.")
    print("Please run: pip install -r requirements.txt")
    print(f"Missing module: {e.name}")
    sys.exit(1)

load_dotenv()

BIBLE_API_KEY = os.getenv("BIBLE_API_KEY", "")
BIBLE_API_BASE_URL = "https://4.dbt.io/api"
API_TIMEOUT = 30

# Module-level record of the most recent API failure, exposed so callers
# (like confirm_text_availability.py) can classify a None return from
# get_text_content() into 403 vs 404 vs network error, instead of lumping
# every failure into one "unknown" bucket.
_LAST_API_ERROR: Optional[Dict[str, object]] = None


def _classify_api_failure() -> str:
    """Return a short status tag for the most recent API failure.

    Call right after a None return from get_text_content()/make_api_request()
    to know WHY, not just THAT.

    "empty_data"          — HTTP 200 but data was empty / unexpected shape
    "http_403_forbidden"  — DBT returned 403 (usually access-restricted bible)
    "http_404_not_found"  — DBT returned 404 (chapter genuinely absent)
    "http_error"          — any other HTTP/network error
    """
    err = _LAST_API_ERROR
    if not err:
        return "empty_data"
    code = err.get("status_code")
    if code == 403:
        return "http_403_forbidden"
    if code == 404:
        return "http_404_not_found"
    return "http_error"


def log(message: str, level: str = "INFO"):
    """Print log message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}", flush=True)


def make_api_request(
    endpoint: str, params: Optional[Dict] = None, use_key_param: bool = False
) -> Optional[Dict]:
    """Make API request with error handling.

    Args:
        endpoint: API endpoint path
        params: Query parameters
        use_key_param: If True, use 'key' query param instead of Bearer token (for timing endpoint)
    """
    if not BIBLE_API_KEY:
        log("BIBLE_API_KEY not set in .env file", "ERROR")
        return None

    url = f"{BIBLE_API_BASE_URL}/{endpoint}"
    request_params = params or {}

    if use_key_param:
        # Some endpoints (like timestamps) require key as query param, not Bearer token
        request_params["key"] = BIBLE_API_KEY
        request_params["v"] = "4"
        headers = {}
    else:
        # Most endpoints use Bearer token
        headers = {"Authorization": f"Bearer {BIBLE_API_KEY}"}

    global _LAST_API_ERROR
    _LAST_API_ERROR = None
    try:
        response = requests.get(
            url, headers=headers, params=request_params, timeout=API_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        _LAST_API_ERROR = {"status_code": status, "url": url, "message": str(e)}
        log(f"API request failed: {e}", "ERROR")
        return None
    except requests.RequestException as e:
        _LAST_API_ERROR = {"status_code": None, "url": url, "message": str(e)}
        log(f"API request failed: {e}", "ERROR")
        return None


def get_text_content(fileset_id: str, book: str, chapter: int) -> Optional[dict]:
    """Get text content from API.

    Returns dict with either:
    - {'type': 'path', 'data': url} for JSON/USX filesets with downloadable files
    - {'type': 'verses', 'data': [verse_data]} for plain text filesets with inline verses
    """
    # Use the correct endpoint format: /bibles/filesets/{fileset_id}/{book}/{chapter}
    endpoint = f"bibles/filesets/{fileset_id}/{book}/{chapter}"

    # This endpoint requires key as query param, not Bearer token
    data = make_api_request(endpoint, use_key_param=True)

    if not data or "data" not in data or not data["data"]:
        return None

    first_item = data["data"][0]

    # Check if this is a downloadable file (JSON/USX format)
    if "path" in first_item:
        return {"type": "path", "data": first_item["path"]}

    # Check if this is inline verse data (plain text format)
    elif "verse_text" in first_item:
        return {"type": "verses", "data": data["data"]}

    return None
