"""SerpApi google_jobs adapter with on-disk daily caching.

Hides the API key (read from env: SERPAPI_API_KEY).
Caches each (query, location, country, date) tuple in data/serpapi_cache/
so repeated runs the same day cost zero API credits.

Also guards against exhausting the free tier via SERPAPI_MAX_CALLS_PER_DAY.
"""
import datetime as dt
import hashlib
import json
import logging
from pathlib import Path

import config

log = logging.getLogger(__name__)

CACHE_DIR = config.DATA_DIR / "serpapi_cache"
CACHE_DIR.mkdir(exist_ok=True)
COUNTER_FILE = CACHE_DIR / "_call_counter.json"


def _today():
    return dt.datetime.utcnow().strftime("%Y-%m-%d")


def _key(query, location, country_code):
    raw = "|".join([_today(), (query or "").lower().strip(),
                    (location or "").lower().strip(),
                    (country_code or "").lower()])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _cache_path(key):
    return CACHE_DIR / "{}_{}.json".format(_today(), key)


def _read_counter():
    if not COUNTER_FILE.exists():
        return {"date": _today(), "calls": 0}
    try:
        d = json.loads(COUNTER_FILE.read_text(encoding="utf-8"))
        if d.get("date") != _today():
            d = {"date": _today(), "calls": 0}
        return d
    except Exception:
        return {"date": _today(), "calls": 0}


def _bump_counter():
    d = _read_counter()
    d["calls"] += 1
    COUNTER_FILE.write_text(json.dumps(d), encoding="utf-8")
    return d["calls"]


def _normalise_job(item, country_code, country_name):
    """Project the SerpApi google_jobs payload into our JOB_FIELDS shape."""
    ext = item.get("detected_extensions", {}) or {}
    apply_options = item.get("apply_options", []) or []
    apply_url = ""
    if apply_options:
        apply_url = apply_options[0].get("link", "")
    apply_url = apply_url or item.get("share_link", "") or item.get("related_links", [{}])[0].get("link", "")

    description = (item.get("description") or "").replace("\r", " ").replace("\n", " ")[:1500]
    return {
        "job_id": "SERP-" + (item.get("job_id") or hashlib.md5(
            (item.get("title", "") + item.get("company_name", "")).encode("utf-8")).hexdigest()[:10]),
        "title": item.get("title", ""),
        "company": item.get("company_name", ""),
        "location": item.get("location", ""),
        "country": country_name,
        "isco_code": "",
        "inclusive": "",
        "description": description,
        "requirements": ", ".join(item.get("job_highlights", [{}])[0].get("items", [])
                                  if item.get("job_highlights") else []),
        "apply_email": "",
        "apply_url": apply_url,
        "language": "en",
        "source": "serpapi",
        "posted_at": ext.get("posted_at", ""),
    }


def search(query, location, country, max_results=10):
    """Return a list of normalised job dicts, using cache when possible.

    `country` is the country YAML dict (provides country_code, country_name,
    google_domain hints).
    """
    if not config.SERPAPI_ENABLED:
        return []
    if not query:
        return []

    code = country["country_code"].lower()
    key = _key(query, location, code)
    cache_file = _cache_path(key)
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            log.info("SerpApi cache hit (%s) %d jobs", cache_file.name, len(cached))
            return cached
        except Exception:
            cache_file.unlink()

    counter = _read_counter()
    if counter["calls"] >= config.SERPAPI_MAX_CALLS_PER_DAY:
        log.warning("SerpApi daily cap reached (%d) — skipping live call",
                    config.SERPAPI_MAX_CALLS_PER_DAY)
        return []
    if not config.SERPAPI_API_KEY:
        log.warning("SERPAPI_API_KEY not set — skipping")
        return []

    try:
        import requests
    except ImportError:
        log.warning("`requests` not installed — skipping SerpApi")
        return []

    google_domain = {
        "ng": "google.com.ng",
        "cm": "google.cm",
        "cd": "google.cd",
    }.get(code, "google.com")

    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location or country.get("country_name", ""),
        "google_domain": google_domain,
        "hl": country.get("default_language", "en"),
        "gl": code,
        "api_key": config.SERPAPI_API_KEY,
    }

    log.info("SerpApi LIVE call #%d for %r in %r", counter["calls"] + 1, query, location)
    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("SerpApi call failed: %s", e)
        return []
    finally:
        _bump_counter()

    raw = data.get("jobs_results", []) or []
    jobs = [_normalise_job(it, code, country.get("country_name", "")) for it in raw[:max_results]]

    try:
        cache_file.write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning("Could not write SerpApi cache %s: %s", cache_file, e)

    return jobs
