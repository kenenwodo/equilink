"""Module 1 - Skills Signal Engine.

Maps a candidate's free-text education / certificates / skills / job history /
job preference into a portable, human-readable skills profile keyed against
the ESCO/ISCO-08 taxonomy.

Output (`build_profile`):
    {
      "isced_level": 6,
      "isced_label": "Bachelor's",
      "occupations": [
          {"isco": "2512", "label": "Software developer", "score": 0.71,
           "matched_terms": ["python", "b.sc computer science"],
           "explanation": "We mapped you to ... because you mentioned ..."},
          ...
      ],
      "canonical_skills": ["python", "sql", "git", ...],
      "skills_supplied": ["python", "django", "git"],
      "skills_missing": ["sql", "testing"],
      "explanation_en": "...",
      "explanation_fr": "..."
    }

Pure Python; no ML deps.
"""
import re
import unicodedata

import country_config


def _norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.lower()).strip()


def _tokens(s):
    return set(re.findall(r"[a-z0-9\+\#\.]{2,}", _norm(s)))


# ---- education level -----------------------------------------------------
def map_education_level(education_text, country):
    text = _norm(education_text)
    best = None
    for entry in country.get("education_crosswalk", []):
        for kw in entry["match"]:
            if _norm(kw) in text:
                # higher ISCED wins (highest qualification mentioned)
                if not best or entry["isced"] > best["isced"]:
                    best = entry
    if not best:
        return {"isced": 3, "label": "Unknown / assumed Upper-secondary"}
    return {"isced": best["isced"], "label": best["label"]}


# ---- occupation matching --------------------------------------------------
def _score_occupation(cand_tokens, cand_text_norm, occ):
    matched_terms = []
    score = 0.0

    for label in occ["alt_labels_list"]:
        if label and label in cand_text_norm:
            score += 2.0
            matched_terms.append(label)
    if _norm(occ["occupation_label_en"]) in cand_text_norm:
        score += 2.5
        matched_terms.append(occ["occupation_label_en"])

    for skill in occ["skills_list"]:
        if not skill:
            continue
        # multi-word skill: substring match; single word: token match
        if " " in skill:
            if skill in cand_text_norm:
                score += 1.0
                matched_terms.append(skill)
        else:
            if skill in cand_tokens:
                score += 1.0
                matched_terms.append(skill)

    return score, matched_terms


def _explain(occ, matched_terms, lang):
    label = occ["occupation_label_fr"] if lang == "fr" else occ["occupation_label_en"]
    terms = ", ".join(sorted(set(matched_terms))[:5]) or "—"
    if lang == "fr":
        return ("Profil mappé à {label} (CITP {isco}) car vous avez mentionné : {terms}.").format(
            label=label, isco=occ["isco_code"], terms=terms)
    return ("Mapped to {label} (ISCO {isco}) because you mentioned: {terms}.").format(
        label=label, isco=occ["isco_code"], terms=terms)


def build_profile(candidate, country, lang="en", top_k=3):
    """candidate is a dict with full_name, education, skills, job_history, job_pref."""
    parts = [candidate.get(k, "") for k in
             ("education", "skills", "job_history", "job_pref", "disability")]
    cand_text_norm = _norm(" ".join(parts))
    cand_tokens = _tokens(" ".join(parts))

    scored = []
    for occ in country_config.load_taxonomy():
        s, matched = _score_occupation(cand_tokens, cand_text_norm, occ)
        if s > 0:
            scored.append((s, matched, occ))
    scored.sort(key=lambda x: x[0], reverse=True)

    occupations = []
    canon = []
    for s, matched, occ in scored[:top_k]:
        occupations.append({
            "isco": occ["isco_code"],
            "label_en": occ["occupation_label_en"],
            "label_fr": occ["occupation_label_fr"],
            "label": occ["occupation_label_fr"] if lang == "fr" else occ["occupation_label_en"],
            "sector": occ.get("sector", ""),
            "physical_demand": occ.get("physical_demand", ""),
            "disability_friendly_notes": occ.get("disability_friendly_notes", ""),
            "score": round(min(1.0, s / 10.0), 3),
            "matched_terms": sorted(set(matched))[:6],
            "explanation": _explain(occ, matched, lang),
            "canonical_skills": occ["skills_list"],
        })
        canon.extend(occ["skills_list"])

    canonical_skills = sorted(set(canon))
    skills_supplied = [t for t in cand_tokens if t in set(canonical_skills)]
    skills_missing = [s for s in canonical_skills if s not in cand_tokens][:8]

    edu = map_education_level(candidate.get("education", ""), country)

    overall_explanation = (
        "Education level: {edu_label} (ISCED {edu_lvl}).\n".format(
            edu_label=edu["label"], edu_lvl=edu["isced"]) +
        "\n".join(o["explanation"] for o in occupations)
    )

    return {
        "isced_level": edu["isced"],
        "isced_label": edu["label"],
        "occupations": occupations,
        "canonical_skills": canonical_skills,
        "skills_supplied": sorted(set(skills_supplied)),
        "skills_missing": skills_missing,
        "explanation": overall_explanation,
        "language": lang,
        "country": country.get("country_code"),
    }
