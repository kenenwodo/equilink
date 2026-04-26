"""Pure-Python TF-IDF + cosine similarity job matcher with location/language boosts.

No sklearn required (Python 3.6 friendly).
"""
import math
import re
import unicodedata
from collections import Counter

import disability_fit
import llm_reasoner

# Bilingual stopwords (small list)
STOPWORDS = set("""
a an and are as at be by for from has have i in is it of on or that the to was were will with
le la les un une et des de du en au aux pour par sur dans avec sans est sont a ete etre
""".split())

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ0-9\+\#\.]+")


def tokenize(text):
    if not text:
        return []
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    toks = [t.lower() for t in _TOKEN_RE.findall(text)]
    return [t for t in toks if t not in STOPWORDS and len(t) > 1]


def _tf(tokens):
    c = Counter(tokens)
    total = sum(c.values()) or 1
    return {t: n / total for t, n in c.items()}


def _idf(docs_tokens):
    N = len(docs_tokens) or 1
    df = Counter()
    for toks in docs_tokens:
        for t in set(toks):
            df[t] += 1
    return {t: math.log((N + 1) / (n + 1)) + 1.0 for t, n in df.items()}


def _vec(tf, idf):
    return {t: tf[t] * idf.get(t, 0.0) for t in tf}


def _cosine(a, b):
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _candidate_text(c):
    return " ".join([c.get("education", ""), c.get("skills", ""),
                     c.get("job_history", ""), c.get("job_pref", ""),
                     c.get("location", ""), c.get("disability", "")])


def _job_text(j):
    return " ".join([j.get("title", ""), j.get("description", ""),
                     j.get("requirements", ""), j.get("location", "")])


def _location_boost(candidate_loc, job):
    """+0.15 for same country/city, +0.10 if candidate wants Remote and job is Remote."""
    cand = (candidate_loc or "").lower()
    jloc = (job.get("location", "") + " " + job.get("country", "")).lower()
    if "remote" in cand and ("remote" in jloc or job.get("country", "").lower() == "remote"):
        return 0.15
    boost = 0.0
    for keyword in ["nigeria", "lagos", "abuja", "port harcourt", "kano", "ibadan",
                    "cameroon", "cameroun", "douala", "yaounde", "yaoundé",
                    "congo", "kinshasa", "brazzaville", "kolwezi"]:
        if keyword in cand and keyword in jloc:
            boost = max(boost, 0.15)
    return boost


def _isco_boost(profile, job):
    """Strong boost when the candidate's mapped occupations match the job's ISCO."""
    if not profile or not profile.get("occupations"):
        return 0.0
    job_isco = (job.get("isco_code") or "").strip()
    if not job_isco:
        return 0.0
    for i, occ in enumerate(profile["occupations"]):
        if occ["isco"] == job_isco:
            return 0.30 if i == 0 else 0.20
        # 4-digit unit group match → 3-digit minor group fallback
        if occ["isco"][:3] == job_isco[:3]:
            return 0.10
    return 0.0


def _inclusion_boost(job, country):
    if not country:
        return 0.0
    if (job.get("inclusive") or "").lower() == "yes":
        return 0.10
    text = ((job.get("description", "") + " " + job.get("requirements", ""))).lower()
    for kw in country.get("inclusion_keywords", []):
        if kw.lower() in text:
            return 0.10
    return 0.0


def _is_remote(job):
    txt = (job.get("location", "") + " " + job.get("country", "")
           + " " + job.get("title", "")).lower()
    return any(k in txt for k in ["remote", "à distance", "a distance", "telework", "télétravail", "anywhere"])


def _job_country_matches(job, country):
    if not country:
        return True
    aliases = [a.lower() for a in country.get("country_aliases", [])]
    aliases.append((country.get("country_name", "") or "").lower())
    aliases.append((country.get("country_code", "") or "").lower())
    aliases = [a for a in aliases if a]
    blob = ((job.get("country", "") or "") + " " + (job.get("location", "") or "")).lower()
    # Word-boundary match so short aliases like "ng" / "cd" / "cm" don't
    # match inside words ("co_ng_o", "in_cd_uded", etc).
    for a in aliases:
        if re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", blob):
            return True
    return False


def _candidate_city(candidate_loc):
    """Extract the leading city/state token from 'Lagos, Nigeria' style strings."""
    if not candidate_loc:
        return ""
    head = candidate_loc.split(",")[0].strip().lower()
    return head


def _job_state_matches(candidate_loc, job):
    """When the candidate names a city/state, the job must mention it (or be remote)."""
    cand_city = _candidate_city(candidate_loc)
    if not cand_city:
        return True
    jloc = (job.get("location", "") or "").lower()
    return cand_city in jloc


def _filter_jobs_by_geography(candidate, jobs, country):
    """Hard geography filter — country always wins, even for remote roles.

    Rules:
      * The job must match the candidate's country (alias / name / code).
        A job tagged "Remote" with no country attached is dropped — we will
        not surface a Kenyan or US remote job to a Nigerian candidate.
      * If the job is not remote, the candidate's city/state must also appear
        in the job location.
    """
    cand_loc = candidate.get("location", "")
    out = []
    for j in jobs:
        if not _job_country_matches(j, country):
            continue
        if _is_remote(j):
            out.append(j)
            continue
        if not _job_state_matches(cand_loc, j):
            continue
        out.append(j)
    return out


def rank_jobs(candidate, jobs, top_n=5, profile=None, country=None, lang="en"):
    """Return top_n result dicts ordered by descending score.

    Each result: {job, score, components: {tfidf, location, isco, inclusion,
                  disability_fit}, fit: {band, rationale, demands}}
    Jobs flagged ``incompatible`` for the candidate's disability are dropped.
    """
    if not jobs:
        return []

    jobs = _filter_jobs_by_geography(candidate, jobs, country)
    if not jobs:
        return []

    disability_cats = disability_fit.classify_disability(
        candidate.get("disability", ""))

    cand_text = _candidate_text(candidate)
    job_texts = [_job_text(j) for j in jobs]
    cand_tokens = tokenize(cand_text)
    job_tokens_list = [tokenize(t) for t in job_texts]

    idf = _idf([cand_tokens] + job_tokens_list)
    cand_vec = _vec(_tf(cand_tokens), idf)

    cand_loc = candidate.get("location", "")
    results = []
    for job, jt in zip(jobs, job_tokens_list):
        fit = disability_fit.score_job(disability_cats, job, lang=lang)
        if fit["fit_band"] == "incompatible":
            # Hard refusal — never recommend physically incompatible roles.
            continue
        sim = _cosine(cand_vec, _vec(_tf(jt), idf))
        loc_b = _location_boost(cand_loc, job)
        isco_b = _isco_boost(profile, job)
        inc_b = _inclusion_boost(job, country)
        fit_b = fit["fit_score"]
        score = sim + loc_b + isco_b + inc_b + fit_b
        results.append({
            "job": job,
            "score": score,
            "components": {
                "tfidf": round(sim, 3),
                "location": loc_b,
                "isco": isco_b,
                "inclusion": inc_b,
                "disability_fit": round(fit_b, 3),
            },
            "fit": {
                "band": fit["fit_band"],
                "rationale": fit["rationale"],
                "demands": fit["demands"],
            },
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    results = [r for r in results if r["score"] > 0.05]
    results = results[:top_n]

    # Optional LLM rerank: ask local Gemma (via Ollama) to validate each finalist.
    # Returns None when LLM_RERANK_ENABLED!=1 / no key / SDK missing / quota gone.
    for r in results:
        verdict = llm_reasoner.assess_fit(candidate, r["job"], lang=lang)
        if not verdict:
            continue
        r["llm"] = verdict
        # Let the LLM rationale replace the rule-based one (richer wording).
        if verdict.get("rationale"):
            r["fit"]["rationale"] = verdict["rationale"]
        if verdict["verdict"] == "no":
            r["fit"]["band"] = "incompatible"
            r["score"] -= 0.40
            r["components"]["llm"] = -0.40
        elif verdict["verdict"] == "yes":
            r["score"] += 0.05
            r["components"]["llm"] = 0.05
        else:
            r["components"]["llm"] = 0.0

    # Drop anything the LLM flagged as a hard "no" and re-sort.
    results = [r for r in results if r["fit"]["band"] != "incompatible"]
    results.sort(key=lambda x: x["score"], reverse=True)

    # Normalise raw score -> [0, 1] for candidate-facing display.
    # Raw scores in this system land roughly in [0, ~1.5]; we clamp at 1.5
    # so a perfect rule+LLM stack reads as 100%.
    SCORE_CEIL = 1.5
    for r in results:
        norm = max(0.0, min(1.0, r["score"] / SCORE_CEIL))
        r["score_norm"] = round(norm, 3)
        r["score_pct"] = int(round(norm * 100))

    return results
