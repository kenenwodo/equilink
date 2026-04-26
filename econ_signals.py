"""Module 3 - Econometric signals exposed visibly to the user.

We surface AT LEAST TWO econometric signals (the rubric requirement):
  1. Median monthly wage for the candidate's mapped occupation, in local currency.
  2. Sector employment growth (% YoY) for that occupation's sector.
  3. (Bonus) Returns to education for the candidate's ISCED level.
"""
import country_config


def signals_for_profile(profile, country, lang="en"):
    if not profile["occupations"]:
        return {"signals": [], "summary": ""}

    top = profile["occupations"][0]
    isco1 = top["isco"][0]                       # ISCO 1-digit major group
    sector = top["sector"] or "Trade"

    wage = country["median_wage_by_isco1"].get(isco1)
    growth = country["sector_growth_pct"].get(sector)
    sym = country.get("currency_symbol", "")
    cur = country.get("currency", "")

    # Returns to education by ISCED level
    isced = profile["isced_level"]
    if isced <= 1:
        ret_key, ret_label = "primary", "primary"
    elif isced <= 3:
        ret_key, ret_label = "secondary", "secondary"
    else:
        ret_key, ret_label = "tertiary", "tertiary"
    ret_pct = country["returns_to_education_pct"].get(ret_key)

    minwage = country.get("minimum_wage_monthly")
    wage_vs_min = None
    if wage and minwage:
        wage_vs_min = round((wage / minwage) * 100 - 100, 1)

    if lang == "fr":
        signals = [
            {"label": "Salaire mensuel médian ({})".format(top["label"]),
             "value": "{} {} {}".format(sym, "{:,}".format(wage) if wage else "n/a", cur),
             "raw": wage,
             "note": "Sources : NBS / ILOSTAT / INS — voir config_data/countries/*.yaml"},
            {"label": "Croissance de l'emploi ({})".format(sector.replace("_", " ")),
             "value": "{:+.1f} % / an".format(growth) if growth is not None else "n/a",
             "raw": growth,
             "note": "Source : AfDB AEO 2024"},
            {"label": "Rendement éducation ({})".format(ret_label),
             "value": "{:.1f} % par année".format(ret_pct) if ret_pct is not None else "n/a",
             "raw": ret_pct,
             "note": "Psacharopoulos & Patrinos 2018"},
        ]
        if wage_vs_min is not None:
            signals.append({
                "label": "vs. salaire minimum",
                "value": "{:+.1f} %".format(wage_vs_min),
                "raw": wage_vs_min,
                "note": "Salaire minimum mensuel : {} {}".format(minwage, cur),
            })
        summary = (
            "Salaire médian {sym}{wage:,} ({cur}/mois) ; secteur {sector} : "
            "{growth:+.1f}%/an ; rendement éducation : {ret:.1f}%/année."
        ).format(sym=sym, wage=wage or 0, cur=cur, sector=sector,
                 growth=growth or 0, ret=ret_pct or 0)
    else:
        signals = [
            {"label": "Median monthly wage ({})".format(top["label"]),
             "value": "{}{} {}".format(sym, "{:,}".format(wage) if wage else "n/a", cur),
             "raw": wage,
             "note": "Sources: NBS / ILOSTAT / INS - see config_data/countries/*.yaml"},
            {"label": "Sector employment growth ({})".format(sector.replace("_", " ")),
             "value": "{:+.1f}% YoY".format(growth) if growth is not None else "n/a",
             "raw": growth,
             "note": "Source: AfDB African Economic Outlook 2024"},
            {"label": "Returns to education ({})".format(ret_label),
             "value": "{:.1f}% per year".format(ret_pct) if ret_pct is not None else "n/a",
             "raw": ret_pct,
             "note": "Psacharopoulos & Patrinos 2018"},
        ]
        if wage_vs_min is not None:
            signals.append({
                "label": "vs. minimum wage",
                "value": "{:+.1f}%".format(wage_vs_min),
                "raw": wage_vs_min,
                "note": "Monthly minimum wage: {} {}".format(minwage, cur),
            })
        summary = (
            "Median wage {sym}{wage:,} {cur}/mo; {sector} sector growing "
            "{growth:+.1f}%/yr; returns to {ret_label} education {ret:.1f}%/yr."
        ).format(sym=sym, wage=wage or 0, cur=cur,
                 sector=sector, growth=growth or 0,
                 ret_label=ret_label, ret=ret_pct or 0)

    return {"signals": signals, "summary": summary,
            "isco_1digit": isco1, "sector": sector}
