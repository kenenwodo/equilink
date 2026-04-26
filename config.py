"""Central configuration loader. Reads .env (if present) and exposes typed settings."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTBOX_DIR = DATA_DIR / "outbox"
DATA_DIR.mkdir(exist_ok=True)
OUTBOX_DIR.mkdir(exist_ok=True)

CANDIDATES_CSV = DATA_DIR / "candidates.csv"
REGISTRY_CSV = DATA_DIR / "national_registry.csv"
JOBS_CSV = DATA_DIR / "jobs.csv"
APPLICATIONS_LOG_CSV = DATA_DIR / "applications_log.csv"

DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "none").lower()

AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY = os.getenv("AT_API_KEY", "")
AT_SENDER_ID = os.getenv("AT_SENDER_ID", "")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "AbleMatch Africa <noreply@ablematch.africa>")

DISABILITY_REGISTRY_EMAIL = os.getenv("DISABILITY_REGISTRY_EMAIL", "registry-demo@example.org")
APPLICATION_FROM_NAME = os.getenv("APPLICATION_FROM_NAME", "AbleMatch Africa Talent Desk")

PII_HASH_SALT = os.getenv("PII_HASH_SALT", "dev-salt-change-me")
USE_REMOTEOK = os.getenv("USE_REMOTEOK", "1") == "1"

# SerpApi google_jobs (live job feed). Free tier ~50 calls/month —
# the adapter caches per (query, location, day) to stay well under quota.
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
SERPAPI_ENABLED = os.getenv("SERPAPI_ENABLED", "1") == "1" and bool(SERPAPI_API_KEY)
SERPAPI_MAX_CALLS_PER_DAY = int(os.getenv("SERPAPI_MAX_CALLS_PER_DAY", "10"))

TOP_N_JOBS = 5
