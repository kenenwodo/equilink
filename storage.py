"""CSV-based storage for candidates and application logs. Privacy-aware."""
import csv
import hashlib
import os
from datetime import datetime
from pathlib import Path

import config

CANDIDATE_FIELDS = [
    "candidate_id", "received_at", "phone_hash", "phone_e164",
    "full_name", "disability", "education", "skills", "job_history",
    "location", "job_pref", "country_code",
    "isced_level", "top_isco", "top_occupation",
    "automation_risk", "language", "consent",
]

APPLICATION_FIELDS = [
    "logged_at", "candidate_id", "job_id", "job_title", "company",
    "score", "channel", "status",
]


def _ensure_csv(path: Path, fields):
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def hash_phone(phone):
    """One-way hash for audit logs / dedup. Reversal requires the salt."""
    h = hashlib.sha256()
    h.update((config.PII_HASH_SALT + "|" + (phone or "")).encode("utf-8"))
    return h.hexdigest()[:16]


def make_candidate_id(phone):
    return "C-" + hash_phone(phone)[:10].upper()


def save_candidate(phone, parsed, language="en", consent=True,
                   country_code="", profile=None, risk=None):
    _ensure_csv(config.CANDIDATES_CSV, CANDIDATE_FIELDS)
    top_isco = ""
    top_occupation = ""
    automation_risk = ""
    isced_level = ""
    if profile and profile.get("occupations"):
        top_isco = profile["occupations"][0]["isco"]
        top_occupation = profile["occupations"][0]["label_en"]
        isced_level = str(profile.get("isced_level", ""))
    if risk and risk.get("occupations"):
        automation_risk = "{:.3f}".format(risk["occupations"][0]["automation_risk_lmic"])

    row = {
        "candidate_id": make_candidate_id(phone),
        "received_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "phone_hash": hash_phone(phone),
        "phone_e164": phone,
        "full_name": parsed.get("full_name", ""),
        "disability": parsed.get("disability", ""),
        "education": parsed.get("education", ""),
        "skills": parsed.get("skills", ""),
        "job_history": parsed.get("job_history", ""),
        "location": parsed.get("location", ""),
        "job_pref": parsed.get("job_pref", ""),
        "country_code": country_code,
        "isced_level": isced_level,
        "top_isco": top_isco,
        "top_occupation": top_occupation,
        "automation_risk": automation_risk,
        "language": language,
        "consent": "yes" if consent else "no",
    }
    with open(config.CANDIDATES_CSV, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS).writerow(row)
    try:
        os.chmod(config.CANDIDATES_CSV, 0o600)
    except OSError:
        pass
    return row


def log_application(candidate_id, job, score, channel, status):
    _ensure_csv(config.APPLICATIONS_LOG_CSV, APPLICATION_FIELDS)
    row = {
        "logged_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "candidate_id": candidate_id,
        "job_id": job.get("job_id", ""),
        "job_title": job.get("title", ""),
        "company": job.get("company", ""),
        "score": "{:.4f}".format(score),
        "channel": channel,
        "status": status,
    }
    with open(config.APPLICATIONS_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=APPLICATION_FIELDS).writerow(row)


def mask_pii(value, keep=2):
    if not value:
        return ""
    parts = value.split()
    return " ".join(p[:keep] + "***" for p in parts)
