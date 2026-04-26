"""Module 2 (lite) - AI Readiness & Displacement Risk Lens.

Inputs: a skills profile (from skills_engine) + a country config.
Outputs: per-occupation automation risk (Frey-Osborne x LMIC multiplier),
         3 adjacent occupations to pivot toward, durable skills to build,
         and the Wittgenstein 2025-2035 education shift narrative.
"""
import country_config


def _band(p):
    if p >= 0.70:
        return "high"
    if p >= 0.35:
        return "medium"
    return "low"


def assess(profile, country, lang="en"):
    frey = country_config.load_frey()
    cal = country_config.load_lmic_calibration()
    mult = float(country.get("automation_multiplier", 0.65))
    threshold = float(cal.get("high_risk_threshold", 0.6))

    occ_risks = []
    for occ in profile["occupations"]:
        rec = frey.get(occ["isco"])
        if not rec:
            continue
        raw = rec["probability"]
        adjusted = round(min(1.0, raw * mult), 3)
        adj_codes = cal.get("adjacencies", {}).get(int(occ["isco"]), [])
        adj_occs = []
        for code in adj_codes:
            row = country_config.occupation_by_isco(code)
            if not row:
                continue
            arec = frey.get(str(code))
            ap = round(min(1.0, arec["probability"] * mult), 3) if arec else None
            adj_occs.append({
                "isco": str(code),
                "label": row["occupation_label_fr"] if lang == "fr" else row["occupation_label_en"],
                "automation_risk": ap,
            })
        occ_risks.append({
            "isco": occ["isco"],
            "label": occ["label"],
            "automation_risk_raw": raw,
            "automation_risk_lmic": adjusted,
            "risk_band": _band(adjusted),
            "is_high_risk": adjusted >= threshold,
            "frey_source": rec["source"],
            "adjacent_occupations": adj_occs,
        })

    durable = list(cal.get("durable_skills_general", []))

    witt = country_config.load_wittgenstein().get(country["country_code"], {})
    shift_key = "shift_summary_fr" if lang == "fr" else "shift_summary_en"
    shift = witt.get(shift_key, "")

    return {
        "occupations": occ_risks,
        "durable_skills": durable,
        "wittgenstein_shift": shift,
        "lmic_multiplier": mult,
        "high_risk_threshold": threshold,
    }
