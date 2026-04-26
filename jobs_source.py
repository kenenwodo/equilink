"""Loads job postings from local CSV + optional live RemoteOK feed."""
import csv
import logging

import config

log = logging.getLogger(__name__)

JOB_FIELDS = ["job_id", "title", "company", "location", "country",
              "description", "requirements", "apply_email", "apply_url",
              "language", "source", "posted_at"]


def load_local_jobs():
    if not config.JOBS_CSV.exists():
        return []
    out = []
    with open(config.JOBS_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(row)
    return out


def load_remoteok_jobs(limit=40):
    """Free public JSON feed: https://remoteok.com/api  (no key required)."""
    if not config.USE_REMOTEOK:
        return []
    try:
        import requests
        r = requests.get("https://remoteok.com/api",
                         headers={"User-Agent": "AbleMatchAfrica/1.0"},
                         timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("RemoteOK fetch failed: %s", e)
        return []

    jobs = []
    for item in data:
        if not isinstance(item, dict) or "id" not in item:
            continue
        jobs.append({
            "job_id": "ROK-" + str(item.get("id", "")),
            "title": item.get("position") or item.get("title", ""),
            "company": item.get("company", ""),
            "location": "Remote",
            "country": "Remote",
            "description": (item.get("description") or "")[:1500],
            "requirements": ", ".join(item.get("tags", []) or []),
            "apply_email": "",
            "apply_url": item.get("url") or item.get("apply_url", ""),
            "language": "en",
            "source": "remoteok",
            "posted_at": item.get("date", ""),
        })
        if len(jobs) >= limit:
            break
    return jobs


def load_all_jobs(country=None, query="", location=""):
    jobs = load_local_jobs()
    if country and query:
        try:
            import serpapi_jobs
            jobs += serpapi_jobs.search(query, location, country, max_results=10)
        except Exception as e:
            log.warning("SerpApi adapter failed: %s", e)
    jobs += load_remoteok_jobs()
    return jobs
