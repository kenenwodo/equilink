# EquiLink

> **EquiLink — tackling the UNMAPPED challenge by World Bank.**
> A multilingual, SMS-first job-matching service for people with
> disabilities across Africa. Submitted to **HackNation #5 ·
> *UNMAPPED Africa* (World Bank)**.

EquiLink lets a candidate send a single SMS from any phone — no
smartphone, no data plan, no CV — and get back a ranked, accommodation-
aware list of live jobs in English or French. National disability
commissions (e.g. **NCPWD** in Nigeria) get a clean referral pipeline
of un-registered citizens. Policymakers get a dashboard of inclusive
jobs, wages, automation risk, and reskilling pathways.

```
SMS  ─►  parse  ─►  country / language detect  ─►  ISCO-08 skills map
        ─►  national disability registry  ─►  Google Jobs (SerpApi)
        ─►  TF-IDF + ISCO + inclusion boosts  ─►  local Gemma 3 rerank
        ─►  block / caution / boost filter  ─►  ranked SMS  +  employer
            email  +  policymaker dashboard
```

---

## Table of contents

- [Quick start (5 minutes, fully offline)](#quick-start-5-minutes-fully-offline)
- [Optional: enable the local LLM rerank](#optional-enable-the-local-llm-rerank)
- [Optional: enable live Google Jobs (SerpApi)](#optional-enable-live-google-jobs-serpapi)
- [Optional: enable real SMS / email](#optional-enable-real-sms--email)
- [Demo personas](#demo-personas)
- [Project structure](#project-structure)
- [Adding a new country](#adding-a-new-country)
- [Where outbound messages go in demo mode](#where-outbound-messages-go-in-demo-mode)
- [License](#license)

---

## Quick start (5 minutes, fully offline)

Requirements:

- **Python 3.11** (Python 3.10 also works). Use a virtualenv or conda.
- macOS, Linux, or WSL on Windows.
- **No** API keys are required for the offline demo.

```bash
# 1. Clone and enter the project
git clone https://github.com/<your-username>/equilink.git
cd equilink

# 2. Create a virtual environment (pick ONE)
python3.11 -m venv .venv && source .venv/bin/activate
# or:  conda create -n equilink python=3.11 -y && conda activate equilink

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy the example environment file (defaults are demo-safe)
cp .env.example .env

# 5. Run the Flask app
python app.py
```

Then open <http://localhost:6034> in your browser. Try the built-in
demo personas:

- <http://localhost:6034/?preset=adaeze> — Lagos, Nigeria, English, blind
- <http://localhost:6034/?preset=patrick> — Kinshasa, DRC, French, wheelchair
- <http://localhost:6034/?preset=marie> — Douala, Cameroon, French, hearing-impaired
- <http://localhost:6034/?preset=jeanpaul> — Kinshasa, DRC, French, mobility-impaired

The policymaker dashboard is at
<http://localhost:6034/dashboard/?country=ng> (also `cm`, `cd`).

> **Demo mode is on by default** (`DEMO_MODE=1` in `.env.example`).
> Nothing is sent over the wire — every SMS and email is written to
> `data/outbox/` as JSON for inspection.

You can also run the offline end-to-end script that walks all four
personas across NG / CM / CD in EN and FR:

```bash
python demo.py
```

---

## Optional: enable the local LLM rerank

EquiLink uses a **local** large language model to rerank the top-N
job matches and explain each fit in the candidate's own language.
There is **no API key** and no third-party call — the model runs
on your machine via [Ollama](https://ollama.com).

```bash
# 1. Install Ollama (macOS/Linux):  https://ollama.com
# 2. Pull the model (~ 3 GB):
ollama pull gemma3:4b

# 3. Make sure the daemon is running, then enable the rerank:
LLM_RERANK_ENABLED=1 DEMO_MODE=1 python app.py
```

Tested on a 16 GB MacBook and a $400 mini-PC. Per-(candidate, job)
results are cached on disk in `data/llm_cache/`, so reruns are free.

---

## Optional: enable live Google Jobs (SerpApi)

To pull live, country-scoped postings from Google Jobs, get a free
[SerpApi](https://serpapi.com/) key (50 searches / month) and set:

```bash
# in .env
SERPAPI_API_KEY=sk-your-key-here
SERPAPI_ENABLED=1
SERPAPI_MAX_CALLS_PER_DAY=10   # protects your quota
```

Without a key, EquiLink falls back to the seed jobs in
`data/jobs.csv` and (optionally) the free RemoteOK feed.

---

## Optional: enable real SMS / email

To send real SMS replies and partner emails, switch out of demo mode
and fill in the relevant credentials in `.env`:

```bash
# in .env
DEMO_MODE=0

# SMS — pick ONE provider
SMS_PROVIDER=africastalking      # or "twilio"
AT_USERNAME=your-username
AT_API_KEY=your-key

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASSWORD=your-app-password
SMTP_FROM="EquiLink <noreply@equilink.africa>"
```

EquiLink ships with provider-agnostic adapters in
[`notifier.py`](notifier.py), so swapping for a different SMS gateway
is a one-function change.

---

## Demo personas

`?preset=` populates the homepage form with one of four built-in
candidates so you can run a full end-to-end flow without typing:

| Preset      | Country | Language | Disability             | Education             |
|-------------|---------|----------|------------------------|-----------------------|
| `adaeze`    | NG      | EN       | Visual impairment      | BSc Computer Science  |
| `patrick`   | CD      | FR       | Wheelchair user        | BSc Informatique      |
| `marie`     | CM      | FR       | Hearing impairment     | BTS                   |
| `jeanpaul`  | CD      | FR       | Mobility impairment    | Diplôme professionnel |

---

## Project structure

```
code/
├─ app.py                  Flask entrypoint (port 6034)
├─ candidate.py            Homepage + result page (Jinja-in-Python)
├─ dashboard.py            Policymaker dashboard blueprint
├─ pipeline.py             End-to-end orchestrator
├─ parser.py               Regex SMS field extractor
├─ country_config.py       Country detection + per-country YAML loader
├─ i18n.py                 EN / FR detection and translations
├─ skills_engine.py        Free-text skills → ISCO-08 + ISCED
├─ jobs_source.py          Merge live + seed job sources
├─ serpapi_jobs.py         Google Jobs via SerpApi (cached)
├─ job_matcher.py          TF-IDF + ISCO / location / inclusion boosts
├─ disability_fit.py       Block / Caution / Boost matrix
├─ llm_reasoner.py         Ollama → Gemma 3 rerank + bilingual rationale
├─ registry.py             National disability registry verifier
├─ notifier.py             SMS (Africa's Talking / Twilio) + SMTP email
├─ econ_signals.py         Wages, sector growth, returns-to-education
├─ risk_lens.py            Frey–Osborne × LMIC automation risk
├─ storage.py              Candidate CSV with masked PII
├─ demo.py                 Offline end-to-end across all personas
├─ check_apis.py           Smoke-test for SerpApi / Ollama / SMTP
├─ config.py               Env-var loader
├─ config_data/
│  ├─ countries/{ng,cm,cd}.yaml
│  ├─ taxonomy/             ISCO / ISCED / ESCO subsets
│  ├─ automation/           Frey–Osborne base + LMIC calibration
│  └─ wittgenstein/         2025-2035 education projections
├─ data/
│  ├─ jobs.csv              Seed inclusive jobs per country
│  ├─ national_registry.csv Demo registry (synthetic data)
│  ├─ llm_cache/            Cached LLM rationales (gitignored)
│  ├─ serpapi_cache/        Cached SerpApi responses (gitignored)
│  ├─ outbox/               Demo-mode SMS / email JSON (gitignored)
│  └─ candidates.csv        Runtime audit log (gitignored)
├─ static/                  Logos and wallpaper
├─ requirements.txt
└─ .env.example             Copy to .env and fill in keys
```

---

## Adding a new country

1. Drop a new YAML at `config_data/countries/<iso2>.yaml` with
   `country_code`, `default_language`, `supported_languages`,
   `currency`, `currency_symbol`, `education_crosswalk`,
   `median_wage_by_isco1`, `minimum_wage_monthly`,
   `sector_growth_pct`, `returns_to_education_pct`,
   `automation_multiplier`, and `inclusion_keywords`.
2. Add the dialing prefix to
   [`country_config.PHONE_PREFIXES`](country_config.py).
3. *(Optional)* extend
   `config_data/wittgenstein/projections.yaml` with the new ISO-2.
4. *(Optional)* add seed jobs to `data/jobs.csv` with the new
   `country` column.

No Python code change required.

---

## Where outbound messages go in demo mode

Every SMS, partner email, and employer application produced in
`DEMO_MODE=1` is written as a JSON payload under `data/outbox/`,
so you can audit the full conversation without sending anything:

```bash
ls data/outbox/                   # one JSON per outbound message
cat data/candidates.csv           # masked-PII candidate audit log
cat data/applications_log.csv    # which jobs each candidate applied to
```

---

## License

Released under the [MIT License](LICENSE) © 2026 EquiLink contributors.

---

## Acknowledgements

By **Kenechukwu Nwodo**.

Built for **HackNation April 25-26 2026**, UNMAPPED challenge by the
**World Bank**.
