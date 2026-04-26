"""Policymaker / program-officer dashboard.

Aggregates candidates.csv + jobs.csv + skills taxonomy and surfaces:
  - Distribution of mapped occupations among registered candidates
  - Skill-supply vs skill-demand gap (top under-supplied skills)
  - Automation-risk distribution (low / medium / high) with LMIC calibration
  - Two visible econometric signals per country (median wage + sector growth)
  - Wittgenstein 2025-2035 education shift narrative

Mounted by app.py at /dashboard.
"""
import csv
from collections import Counter

from flask import Blueprint, render_template_string, request

import config
import country_config

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


_TEMPLATE = """
<!doctype html>
<html lang="{{ lang }}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EquiLink - Policymaker dashboard ({{ country.country_name }})</title>
<style>
  html { background: linear-gradient(rgba(255,255,255,0.88), rgba(255,255,255,0.88)),
                     url('/static/wallpaper.png') center/cover fixed no-repeat; min-height: 100%; }
  body { font: 14px/1.45 system-ui, sans-serif; max-width: 1100px; margin: 24px auto; padding: 0 16px; color: #1a1a1a;
         background: linear-gradient(rgba(255,255,255,0.88), rgba(255,255,255,0.88)),
                     url('/static/wallpaper.png') center/cover fixed no-repeat; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  h1 .tagline { font-size: 12px; font-weight: 400; color: #6b7080;
                letter-spacing: 0.02em; display: inline-block; margin-left: 6px; }
  h1 small { display: block; font-size: 13px; font-weight: 500;
             color: #444; margin-top: 4px; }
  .sub { color: #666; margin-bottom: 24px; }
  nav a { margin-right: 12px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; background: #fafafa; }
  .card h2 { font-size: 16px; margin: 0 0 8px; }
  .signal { font-size: 22px; font-weight: 600; }
  .note { color: #666; font-size: 12px; margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eee; }
  .bar { background: #4a90e2; height: 14px; border-radius: 3px; }
  .bar.high { background: #d0021b; }
  .bar.medium { background: #f5a623; }
  .bar.low { background: #7ed321; }
  .small { font-size: 12px; color: #666; }
</style>
</head>
<body>
<h1>EquiLink <span class="tagline">— tackling the UNMAPPED challenge by World Bank</span><br/><small>Policymaker view</small></h1>
<div class="sub">{{ country.country_name }} ({{ country.country_code }}) ·
  default language: {{ country.default_language }} ·
  candidates on file: {{ stats.total_candidates }}</div>

<nav>
  {% for c in all_countries %}
    <a href="?country={{ c.code }}">{{ c.name }}</a>
  {% endfor %}
</nav>

<h2 style="margin-top:24px">Visible econometric signals</h2>
<div class="grid">
  <div class="card">
    <h2>Median monthly wage (entry-level professionals)</h2>
    <div class="signal">{{ country.currency_symbol }}{{ "{:,}".format(country.median_wage_by_isco1["2"]) }} {{ country.currency }}</div>
    <div class="note">Source: NBS / ILOSTAT / INS — ISCO-08 major group 2.</div>
  </div>
  <div class="card">
    <h2>ICT sector employment growth (YoY)</h2>
    <div class="signal">{{ "{:+.1f}".format(country.sector_growth_pct.ICT) }} % / yr</div>
    <div class="note">Source: AfDB AEO 2024.</div>
  </div>
  <div class="card">
    <h2>Returns to tertiary education (per year)</h2>
    <div class="signal">{{ "{:.1f}".format(country.returns_to_education_pct.tertiary) }} %</div>
    <div class="note">Source: Psacharopoulos & Patrinos 2018.</div>
  </div>
  <div class="card">
    <h2>Minimum wage / month</h2>
    <div class="signal">{{ country.currency_symbol }}{{ "{:,}".format(country.minimum_wage_monthly) }} {{ country.currency }}</div>
    <div class="note">National statutory minimum.</div>
  </div>
</div>

<h2 style="margin-top:32px">Wittgenstein 2025-2035 education shift</h2>
<div class="card">{{ shift }}</div>

<div class="grid" style="margin-top:32px">
  <div class="card">
    <h2>Top mapped occupations (candidates)</h2>
    <table>
      <thead><tr><th>ISCO</th><th>Occupation</th><th>#</th></tr></thead>
      <tbody>
      {% for row in stats.top_occupations %}
        <tr><td>{{ row.isco }}</td><td>{{ row.label }}</td><td>{{ row.count }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Automation-risk distribution (LMIC calibrated)</h2>
    <table>
      <tr><td style="width:60px">Low</td>
          <td><div class="bar low" style="width:{{ stats.risk_pct.low }}%"></div></td>
          <td>{{ stats.risk_pct.low }}%</td></tr>
      <tr><td>Medium</td>
          <td><div class="bar medium" style="width:{{ stats.risk_pct.medium }}%"></div></td>
          <td>{{ stats.risk_pct.medium }}%</td></tr>
      <tr><td>High</td>
          <td><div class="bar high" style="width:{{ stats.risk_pct.high }}%"></div></td>
          <td>{{ stats.risk_pct.high }}%</td></tr>
    </table>
    <div class="note">Frey-Osborne probability × {{ country.automation_multiplier }} (LMIC multiplier).</div>
  </div>

  <div class="card">
    <h2>Skill demand vs supply (top gaps)</h2>
    <table>
      <thead><tr><th>Skill</th><th>Job demand</th><th>Candidate supply</th><th>Gap</th></tr></thead>
      <tbody>
      {% for s in stats.skill_gaps %}
        <tr><td>{{ s.skill }}</td><td>{{ s.demand }}</td><td>{{ s.supply }}</td>
            <td style="color: {% if s.gap > 0 %}#d0021b{% else %}#7ed321{% endif %}">{{ s.gap }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
    <div class="note">Gap = demand - supply. Positive = under-supplied.</div>
  </div>

  <div class="card">
    <h2>Disability-inclusive postings</h2>
    <div class="signal">{{ stats.inclusive_pct }} %</div>
    <div class="note">{{ stats.inclusive_count }} of {{ stats.total_jobs }} job postings are tagged inclusive
      (keywords: {{ country.inclusion_keywords|join(", ") }}).</div>
  </div>
</div>

<p class="small" style="margin-top:32px">
  Country-agnostic infrastructure layer. Swap any of these YAML/CSV files in
  <code>config_data/</code> to localize without changing code.
</p>
</body>
</html>
"""


def _load_candidates(country_code):
    rows = []
    if not config.CANDIDATES_CSV.exists():
        return rows
    with open(config.CANDIDATES_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("country_code", "").lower() == country_code.lower():
                rows.append(r)
    return rows


def _load_jobs(country_name):
    rows = []
    if not config.JOBS_CSV.exists():
        return rows
    with open(config.JOBS_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if country_name.split()[0].lower() in r.get("country", "").lower() \
                    or r.get("country", "").lower() == "remote":
                rows.append(r)
    return rows


def _build_stats(country):
    candidates = _load_candidates(country["country_code"])
    jobs = _load_jobs(country["country_name"])

    # Top occupations
    occ_counter = Counter(c["top_occupation"] for c in candidates if c.get("top_occupation"))
    isco_lookup = {row["isco_code"]: row["occupation_label_en"]
                   for row in country_config.load_taxonomy()}
    top_occupations = []
    for label, n in occ_counter.most_common(8):
        isco = next((k for k, v in isco_lookup.items() if v == label), "")
        top_occupations.append({"isco": isco, "label": label, "count": n})

    # Risk distribution
    bands = {"low": 0, "medium": 0, "high": 0}
    for c in candidates:
        try:
            r = float(c.get("automation_risk", "") or 0)
        except ValueError:
            continue
        if r >= 0.7:
            bands["high"] += 1
        elif r >= 0.35:
            bands["medium"] += 1
        else:
            bands["low"] += 1
    total_with_risk = sum(bands.values()) or 1
    risk_pct = {k: round(v * 100 / total_with_risk) for k, v in bands.items()}

    # Skill demand vs supply (using ESCO canonical skills)
    taxonomy = country_config.load_taxonomy()
    all_skills = set()
    for occ in taxonomy:
        all_skills.update(occ["skills_list"])
    demand = Counter()
    for j in jobs:
        text = (j.get("requirements", "") + " " + j.get("description", "")).lower()
        for s in all_skills:
            if s and s in text:
                demand[s] += 1
    supply = Counter()
    for c in candidates:
        text = (c.get("skills", "") + " " + c.get("education", "") + " "
                + c.get("job_history", "")).lower()
        for s in all_skills:
            if s and s in text:
                supply[s] += 1
    gaps = []
    for s, d in demand.most_common(20):
        gaps.append({"skill": s, "demand": d, "supply": supply.get(s, 0),
                     "gap": d - supply.get(s, 0)})
    gaps.sort(key=lambda x: x["gap"], reverse=True)
    skill_gaps = gaps[:10]

    inclusive_count = sum(1 for j in jobs if (j.get("inclusive", "") or "").lower() == "yes")
    inclusive_pct = round(inclusive_count * 100 / len(jobs)) if jobs else 0

    return {
        "total_candidates": len(candidates),
        "total_jobs": len(jobs),
        "top_occupations": top_occupations,
        "risk_pct": risk_pct,
        "skill_gaps": skill_gaps,
        "inclusive_count": inclusive_count,
        "inclusive_pct": inclusive_pct,
    }


@bp.route("/")
def index():
    code = request.args.get("country", "ng").lower()
    country = country_config.load_country(code=code)
    stats = _build_stats(country)
    witt = country_config.load_wittgenstein().get(country["country_code"], {})
    shift = witt.get("shift_summary_en") or witt.get("shift_summary_fr", "")

    all_countries = []
    for c in country_config.list_country_codes():
        cc = country_config.load_country(code=c)
        all_countries.append({"code": c, "name": cc["country_name"]})

    return render_template_string(
        _TEMPLATE, country=country, stats=stats, shift=shift,
        all_countries=all_countries, lang=country.get("default_language", "en")
    )
