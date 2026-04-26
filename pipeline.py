"""End-to-end orchestration:
  parse SMS -> detect country/language -> verify registry -> build skills profile (M1)
  -> assess automation risk (M2) -> compute econ signals (M3) -> rank opportunities
  -> (optional) apply -> confirm via SMS.
"""
import logging

import config
import country_config
import disability_fit
import econ_signals
import i18n
import job_matcher
import jobs_source
import notifier
import parser
import registry
import risk_lens
import skills_engine
import storage

log = logging.getLogger(__name__)


def _format_opportunity(item, lang):
    j = item["job"]
    pct = item.get("score_pct", int(round(min(item["score"], 1.0) * 100)))
    return "- {title} @ {company} ({loc}) [{pct}%]".format(
        title=j.get("title", ""), company=j.get("company", ""),
        loc=j.get("location", ""), pct=pct)


def _detect_language_for_country(body, country):
    """Always honour the language the candidate wrote in (en or fr).
    Country default is only a fallback when detection returns nothing."""
    detected = i18n.detect_language(body)
    return detected or country.get("default_language", "en")


def _apply_to_job(candidate_row, item, lang):
    job = item["job"]
    name = candidate_row["full_name"]
    title = job.get("title", "")
    subject = (
        "Candidature via EquiLink : {} - {}".format(name, title)
        if lang == "fr" else
        "Job Application via EquiLink: {} - {}".format(name, title)
    )

    body_en = (
        "Hello {company} hiring team,\n\n"
        "On behalf of our candidate {name}, registered with EquiLink, we are "
        "submitting an application for the position of {title} ({job_id}).\n\n"
        "Candidate summary:\n"
        "  - Mapped occupation: {occ} (ISCO {isco})\n"
        "  - Education: {edu} (ISCED {isced})\n"
        "  - Skills: {skills}\n"
        "  - Experience: {exp}\n"
        "  - Preferred role: {pref}\n"
        "  - Location: {loc}\n"
        "  - Disability / accommodation: {dis}\n"
        "  - Match score: {score:.2f}\n\n"
        "The candidate has consented to this outreach. Please reply to schedule an "
        "interview or contact them via SMS on the number on file.\n\nRegards,\n{from_name}"
    )
    body_fr = (
        "Bonjour équipe RH de {company},\n\n"
        "Au nom de notre candidat·e {name}, enregistré·e auprès d'EquiLink, "
        "nous soumettons une candidature pour le poste de {title} ({job_id}).\n\n"
        "Résumé du candidat :\n"
        "  - Métier mappé : {occ} (CITP {isco})\n"
        "  - Formation : {edu} (CITE {isced})\n"
        "  - Compétences : {skills}\n"
        "  - Expérience : {exp}\n"
        "  - Poste souhaité : {pref}\n"
        "  - Lieu : {loc}\n"
        "  - Handicap / aménagement : {dis}\n"
        "  - Score : {score:.2f}\n\n"
        "Le·la candidat·e a consenti. Merci de répondre pour planifier un entretien.\n\n"
        "Cordialement,\n{from_name}"
    )
    body = (body_fr if lang == "fr" else body_en).format(
        company=job.get("company", ""), name=name, title=title,
        job_id=job.get("job_id", ""),
        occ=candidate_row.get("top_occupation", "—"),
        isco=candidate_row.get("top_isco", "—"),
        edu=candidate_row.get("education", ""),
        isced=candidate_row.get("isced_level", ""),
        skills=candidate_row.get("skills", "") or "—",
        exp=candidate_row.get("job_history", "") or "—",
        pref=candidate_row.get("job_pref", ""),
        loc=candidate_row.get("location", ""),
        dis=candidate_row.get("disability", ""),
        score=item["score"],
        from_name=config.APPLICATION_FROM_NAME,
    )

    apply_email = job.get("apply_email", "").strip()
    if apply_email:
        notifier.send_email(apply_email, subject, body)
        storage.log_application(candidate_row["candidate_id"], job, item["score"], "email", "sent")
        return "email", apply_email
    if (job.get("apply_url") or "").strip():
        storage.log_application(candidate_row["candidate_id"], job, item["score"], "url", "queued-manual")
        return "url", job["apply_url"]
    storage.log_application(candidate_row["candidate_id"], job, item["score"], "none", "no-channel")
    return "none", ""


def process_sms(phone, body, country_code=None, auto_apply=False):
    parsed, missing = parser.parse_sms(body)
    country = country_config.load_country(code=country_code, phone=phone)
    lang = _detect_language_for_country(body, country)

    if missing:
        notifier.send_sms(phone, i18n.t(lang, "parse_error"))
        return {"status": "parse_error", "missing": missing,
                "language": lang, "country": country["country_code"]}

    profile = skills_engine.build_profile(parsed, country, lang=lang)
    risk = risk_lens.assess(profile, country, lang=lang)
    econ = econ_signals.signals_for_profile(profile, country, lang=lang)

    candidate_row = storage.save_candidate(
        phone, parsed, language=lang, consent=True,
        country_code=country["country_code"], profile=profile, risk=risk,
    )
    log.info("Saved %s (%s) -> %s",
             candidate_row["candidate_id"],
             storage.mask_pii(candidate_row["full_name"]),
             candidate_row["top_occupation"])

    notifier.send_sms(phone, i18n.t(lang, "thanks_received", name=candidate_row["full_name"]))
    if profile["occupations"]:
        top = profile["occupations"][0]
        notifier.send_sms(phone, i18n.t(
            lang, "profile_summary",
            name=candidate_row["full_name"],
            occ=top["label"], isco=top["isco"],
            isced_label=profile["isced_label"],
            why=top["explanation"],
        ))

    is_registered, match = registry.verify(
        candidate_row["full_name"], phone, candidate_row["disability"])
    if not is_registered:
        subject = "New candidate not on registry: {}".format(candidate_row["full_name"])
        email_body = (
            "Dear National Disability Registry,\n\n"
            "EquiLink received an application from a candidate who does "
            "not appear on file. Please review and onboard if eligible.\n\n"
            "  Name:       {name}\n"
            "  Phone:      {phone}\n"
            "  Disability: {dis}\n"
            "  Location:   {loc}\n"
            "  Country:    {ctry}\n"
            "  Mapped to:  {occ} (ISCO {isco})\n"
            "  Received:   {ts}\n\n"
            "The candidate has consented to this referral.\n\nEquiLink Talent Desk"
        ).format(
            name=candidate_row["full_name"], phone=phone,
            dis=candidate_row["disability"], loc=candidate_row["location"],
            ctry=country["country_name"],
            occ=candidate_row.get("top_occupation", "—"),
            isco=candidate_row.get("top_isco", "—"),
            ts=candidate_row["received_at"],
        )
        notifier.send_email(config.DISABILITY_REGISTRY_EMAIL, subject, email_body)
        registry_name = (country.get("registry_name_fr") if lang == "fr"
                         else country.get("registry_name_en")) or "National Disability Registry"
        notifier.send_sms(phone, i18n.t(lang, "not_in_registry",
                                        name=candidate_row["full_name"],
                                        registry=registry_name))

    if econ["signals"]:
        s = econ["signals"]
        notifier.send_sms(phone, i18n.t(
            lang, "econ_summary",
            wage_label=s[0]["label"], wage_val=s[0]["value"],
            growth_label=s[1]["label"], growth_val=s[1]["value"],
            ret_label=s[2]["label"] if len(s) > 2 else "—",
            ret_val=s[2]["value"] if len(s) > 2 else "—",
        ))

    if risk["occupations"]:
        r = risk["occupations"][0]
        adj = ", ".join(o["label"] for o in r["adjacent_occupations"][:3]) or "—"
        durable = ", ".join(risk["durable_skills"][:3])
        notifier.send_sms(phone, i18n.t(
            lang, "risk_summary",
            occ=r["label"],
            risk_pct=int(r["automation_risk_lmic"] * 100),
            band=r["risk_band"],
            durable=durable,
            adjacent=adj,
        ))

    all_jobs = jobs_source.load_all_jobs(
        country=country, query=parsed.get("job_pref", ""),
        location=parsed.get("location", ""))
    log.info("Loaded %d jobs (after country fetch)", len(all_jobs))
    ranked = job_matcher.rank_jobs(
        candidate_row, all_jobs, top_n=config.TOP_N_JOBS,
        profile=profile, country=country, lang=lang)

    if not ranked:
        notifier.send_sms(phone, i18n.t(lang, "no_matches",
                                        name=candidate_row["full_name"]))
        return {"status": "no_matches", "candidate": candidate_row,
                "registered": is_registered, "language": lang,
                "profile": profile, "risk": risk, "econ": econ,
                "country": country["country_code"]}

    applied = []
    for item in ranked:
        if auto_apply:
            channel, target = _apply_to_job(candidate_row, item, lang)
        else:
            channel, target = "queued", ""
            storage.log_application(candidate_row["candidate_id"], item["job"],
                                    item["score"], "queued", "awaiting-consent")
        applied.append({**item, "channel": channel, "target": target})

    job_lines = "\n".join(_format_opportunity(a, lang) for a in applied)
    notifier.send_sms(phone, i18n.t(lang, "applied_confirmation",
                                    name=candidate_row["full_name"],
                                    count=len(applied), jobs=job_lines))

    disability_cats, disability_note = disability_fit.summarise_for_candidate(
        candidate_row.get("disability", ""), lang=lang)

    return {
        "status": "ok",
        "candidate": candidate_row,
        "registered": is_registered,
        "registry_match": match,
        "registry_name": (country.get("registry_name_fr") if lang == "fr"
                          else country.get("registry_name_en")) or "National Disability Registry",
        "registry_email": config.DISABILITY_REGISTRY_EMAIL,
        "language": lang,
        "country": country["country_code"],
        "profile": profile,
        "risk": risk,
        "econ": econ,
        "applied": applied,
        "disability": {
            "categories": disability_cats,
            "note": disability_note,
        },
    }
