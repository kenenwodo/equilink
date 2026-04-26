"""Tiny English/French message catalogue."""

STRINGS = {
    "en": {
        "welcome": (
            "Welcome to EquiLink. Reply with this format:\n"
            "Name: <full legal name>\n"
            "Disability: <registered disability>\n"
            "Education: <degrees / certificates>\n"
            "Skills: <skills, separated by commas>\n"
            "Experience: <past jobs / years>\n"
            "Location: <city, country or Remote>\n"
            "Job: <job preference>"
        ),
        "thanks_received": "Thank you {name}. We received your details and are building your skills profile.",
        "parse_error": (
            "Sorry, we could not read your message. Please send these lines:\n"
            "Name: ...\nDisability: ...\nEducation: ...\nSkills: ...\n"
            "Experience: ...\nLocation: ...\nJob: ..."
        ),
        "not_in_registry": (
            "Hi {name}, you are not yet on the {registry}. "
            "We have notified them on your behalf. Your job matching continues."
        ),
        "profile_summary": (
            "Hi {name}. Profile mapped to: {occ} (ISCO {isco}).\n"
            "Education level: {isced_label}.\n"
            "Why: {why}"
        ),
        "econ_summary": (
            "Local labour market signals:\n"
            "  - {wage_label}: {wage_val}\n"
            "  - {growth_label}: {growth_val}\n"
            "  - {ret_label}: {ret_val}"
        ),
        "risk_summary": (
            "Automation risk for {occ}: {risk_pct}% ({band}). "
            "Durable skills to grow: {durable}. "
            "Adjacent safer roles: {adjacent}."
        ),
        "applied_confirmation": (
            "Hi {name}, we surfaced {count} reachable opportunity(ies) for you:\n{jobs}\n"
            "Reply YES to apply or call our hotline."
        ),
        "no_matches": "Hi {name}, we could not find suitable jobs right now. We will keep searching and contact you soon.",
    },
    "fr": {
        "welcome": (
            "Bienvenue chez EquiLink. Répondez avec ce format :\n"
            "Nom : <nom légal complet>\n"
            "Handicap : <handicap enregistré>\n"
            "Education : <diplômes / certificats>\n"
            "Competences : <compétences, séparées par virgules>\n"
            "Experience : <emplois passés / années>\n"
            "Lieu : <ville, pays ou À distance>\n"
            "Emploi : <préférence d'emploi>"
        ),
        "thanks_received": "Merci {name}. Nous avons reçu vos informations et construisons votre profil de compétences.",
        "parse_error": (
            "Désolé, nous n'avons pas compris. Envoyez ces lignes :\n"
            "Nom : ...\nHandicap : ...\nEducation : ...\nCompetences : ...\n"
            "Experience : ...\nLieu : ...\nEmploi : ..."
        ),
        "not_in_registry": (
            "Bonjour {name}, vous n'êtes pas encore au {registry}. "
            "Nous les avons informés. Votre recherche d'emploi continue."
        ),
        "profile_summary": (
            "Bonjour {name}. Profil mappé à : {occ} (CITP {isco}).\n"
            "Niveau éducation : {isced_label}.\n"
            "Pourquoi : {why}"
        ),
        "econ_summary": (
            "Signaux du marché du travail local :\n"
            "  - {wage_label} : {wage_val}\n"
            "  - {growth_label} : {growth_val}\n"
            "  - {ret_label} : {ret_val}"
        ),
        "risk_summary": (
            "Risque d'automatisation pour {occ} : {risk_pct}% ({band}). "
            "Compétences durables à développer : {durable}. "
            "Métiers adjacents plus sûrs : {adjacent}."
        ),
        "applied_confirmation": (
            "Bonjour {name}, nous avons identifié {count} opportunité(s) réelle(s) pour vous :\n{jobs}\n"
            "Répondez OUI pour postuler ou appelez notre ligne d'assistance."
        ),
        "no_matches": "Bonjour {name}, aucun emploi adapté pour le moment. Nous continuons à chercher.",
    },
}


def t(lang, key, **kwargs):
    lang = lang if lang in STRINGS else "en"
    return STRINGS[lang][key].format(**kwargs)


def detect_language(text):
    """Very small heuristic: French if any FR field label or accent appears."""
    if not text:
        return "en"
    lo = text.lower()
    fr_markers = ["nom :", "nom:", "handicap", "education :", "education:",
                  "éducation", "lieu", "emploi", "à distance", "bonjour", "merci"]
    en_markers = ["name:", "disability", "location", "job:", "remote", "hello"]
    fr = sum(1 for m in fr_markers if m in lo)
    en = sum(1 for m in en_markers if m in lo)
    return "fr" if fr > en else "en"
