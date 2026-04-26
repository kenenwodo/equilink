# EquiLink — Technical Documentation

This document is the engineering companion to [README.md](README.md). It
explains how the three UNMAPPED modules are wired together, the data
contracts, and how to extend the system.

---

## 1. Architecture

```
+--------+       +-------------+      +-------------------+
|  SMS   | ----> | app.py /sms | ---> | pipeline.process_sms |
+--------+       +-------------+      +----------+--------+
                                                 |
                       +--------+--------+-------+--------+--------+
                       |        |        |                |        |
                       v        v        v                v        v
                   parser   country_   skills_       risk_lens   econ_
                            config     engine        (Module 2)  signals
                                       (Module 1)                (Module 3)
                                                 |
                                                 v
                                           job_matcher
                                           (Module 3)
                                                 |
                                                 v
                                           registry +
                                           notifier +
                                           storage
+----------+       +-------------------+
|  Browser | --->  | app.py /dashboard | --> dashboard.py (aggregate views)
+----------+       +-------------------+
```

Two surfaces share the same Flask app:

* `POST /sms` — Africa's Talking / Twilio webhook → candidate experience
* `GET  /dashboard/?country=<iso2>` — policymaker / program-officer view

---

## 2. Module 1 — Skills Signal Engine (`skills_engine.py`)

**Input:** parsed candidate dict + country YAML + language code.

**Algorithm**

1. Build a candidate text bag: `job_pref + skills + job_history + education + disability`.
2. Tokenise (lowercased, accent-insensitive).
3. For every ISCO-08 occupation in `config_data/taxonomy/esco_subset.csv`, score:
   * +2.5 if the EN occupation label appears in the candidate text
   * +2.0 if the localised label or any ESCO `alt_label` appears
   * +1.0 per canonical-skill substring or token match (single- or multi-word)
4. Pick top-k (default 3) occupations.
5. Map education to **ISCED 2011** level via the country's `education_crosswalk`
   (highest-matching level wins).
6. Compute `skills_supplied` ∩ `canonical_skills` of the top occupation, and
   `skills_missing` = `canonical_skills − skills_supplied` (the personalised
   "skills to grow" list).
7. Generate a bilingual `explanation` string ("Profile mapped to X (ISCO Y)
   because you mentioned: …").

**Output keys:** `occupations[]`, `isced_level`, `isced_label`,
`canonical_skills`, `skills_supplied`, `skills_missing`, `explanation`.

---

## 3. Module 2 — AI Readiness Lens lite (`risk_lens.py`)

**Sources**

* `config_data/automation/frey_osborne.csv` — baseline automation probability
  per ISCO-08 code (mapped from Frey & Osborne 2013 SOC tables).
* `config_data/automation/lmic_calibration.yaml`
  * `durable_skills_general` — durable cross-cutting skills surfaced to every
    candidate.
  * `adjacencies` — for each high-risk ISCO, three lower-risk occupations the
    candidate could pivot to with realistic skill overlap.
* `country.automation_multiplier` (NG 0.65, CM 0.55, CD 0.45) — discounts
  Frey–Osborne for routine-task adoption rates in LMICs (Nedelkoska & Quintini
  rationale).

**Bands**

* `high`   ≥ 0.70 (post-multiplier)
* `medium` 0.35 – 0.70
* `low`    < 0.35

**Output:** per-occupation `automation_risk_raw`, `automation_risk_lmic`,
`risk_band`, `is_high_risk`, `frey_source`, `adjacent_occupations[]`,
plus `durable_skills`, `wittgenstein_shift`, `lmic_multiplier`.

---

## 4. Module 3 — Opportunity Matching + Visible Signals

### 4.1 Econometric signals (`econ_signals.py`)

Returns 3-4 visible signals per profile, all bilingual:

1. **Median monthly wage** for the candidate's top-mapped occupation, looked
   up in `country.median_wage_by_isco1` by 1-digit ISCO group, formatted with
   the country currency symbol.
2. **Sector growth** — `country.sector_growth_pct[<sector>]` matched to the
   ESCO occupation's sector tag (default ICT if none).
3. **Returns to education** — `country.returns_to_education_pct[<level>]`
   keyed by ISCED bracket (primary / secondary / tertiary).
4. **vs. minimum wage** — multiplier above national minimum (when wage is
   available).

### 4.2 Job ranking (`job_matcher.py`)

Final score = `tfidf_cosine + location_boost + isco_boost + inclusion_boost`

* `tfidf_cosine` — pure-Python TF-IDF cosine between the candidate text bag
  and the job's `title + requirements + description`.
* `location_boost` = `+0.15` if candidate location appears in job location.
* `isco_boost` = `+0.30 / +0.20 / +0.10` if job's ISCO code matches the
  candidate's 1st / 2nd / 3rd mapped occupation, with `+0.10` for a 3-digit
  prefix match.
* `inclusion_boost` = `+0.10` when job is tagged `inclusive=yes` or its text
  contains any country `inclusion_keywords`.

Each ranked item carries a `components` breakdown so the policymaker
dashboard and demo can show exactly *why* a job ranked where it did.

---

## 5. Data contracts

### 5.1 `config_data/countries/<iso2>.yaml`

```yaml
country_code: NG
country_name: Nigeria
default_language: en
supported_languages: [en]
currency: NGN
currency_symbol: ₦
automation_multiplier: 0.65
minimum_wage_monthly: 70000
inclusion_keywords: [inclusive, disability, accessible, accommodation, PWD]
education_crosswalk:
  - { match: "phd|doctorate", isced: 8, label: "Doctorate" }
  - { match: "masters|m\\.sc|msc", isced: 7, label: "Master's" }
  - ...
median_wage_by_isco1:
  "1": 350000
  "2": 220000
  ...
sector_growth_pct:
  ICT: 7.4
  Manufacturing: 1.8
  ...
returns_to_education_pct:
  primary: 6.4
  secondary: 9.1
  tertiary: 17.0
opportunity_types: [private_sector, public_sector, ngo]
```

### 5.2 `config_data/taxonomy/esco_subset.csv`

Columns: `isco_code, esco_uri, occupation_label_en, occupation_label_fr,
alt_labels, canonical_skills, sector, physical_demand,
disability_friendly_notes`.

### 5.3 `data/jobs.csv`

Columns: `job_id, title, company, country, location, sector, isco_code,
inclusive (yes/no), description, requirements, apply_email, apply_url,
posted_at`.

### 5.4 Stored candidate (`data/candidates.csv`)

`candidate_id, received_at, full_name, phone_hash, language, country_code,
disability, education, isced_level, skills, job_history, location, job_pref,
top_isco, top_occupation, automation_risk, consent`.

The phone number is **never** persisted in plaintext — only `SHA-256(salt ||
phone)`. The CSV is created with `chmod 600`. Logs mask PII via
`storage.mask_pii()`.

---

## 6. Adding new content

| Goal | What to edit |
|---|---|
| New country | `config_data/countries/<iso2>.yaml` + `country_config.PHONE_PREFIXES` |
| New occupation | `config_data/taxonomy/esco_subset.csv` and (optionally) `config_data/automation/frey_osborne.csv` |
| New jobs | append rows to `data/jobs.csv` |
| New disabled candidate on registry | append to `data/disability_registry.csv` |
| New language | extend `i18n.MESSAGES` and the country YAML's `supported_languages` |

---

## 7. Privacy & safety

* Salted SHA-256 phone hashing; salt loaded from `PHONE_HASH_SALT` env var.
* `chmod 600` on `candidates.csv` and `applications_log.csv`.
* Logs print masked names ("Adae*** Oka***") via `storage.mask_pii`.
* `auto_apply=False` by default — opportunities are queued with status
  `awaiting-consent`; the candidate must reply YES.
* Disability registry verification is name + phone-hash + condition fuzzy
  match; non-matches trigger an email referral, not silent rejection.
* `DEMO_MODE=1` short-circuits all outbound network calls and writes
  payloads to `data/outbox/`.

---

## 8. Limits and roadmap

See the **Honest about limits** section in [README.md](README.md). Concretely:

* Replace TF-IDF with multilingual sentence embeddings once the deployment
  target supports modern Python.
* Ingest the full ESCO classification (≈3000 occupations) and the full
  ISCO-08 skill mappings.
* Wire `country_config.load_country` to live NSO endpoints (NBS, INS-CM,
  INS-RDC) for current wage and growth data.
* Replace Frey-Osborne with a routine-task-intensity score derived from
  local task surveys.
* Two-way SMS state machine for "Reply YES to apply" — currently logged as
  `queued/awaiting-consent` and intended to be picked up by a follow-up
  webhook handler.
