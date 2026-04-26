"""Parses incoming SMS body into a structured Candidate dict.

Accepted format (English or French, case-insensitive, any line order):

    Name: ...           | Nom: ...
    Disability: ...     | Handicap: ...
    Education: ...      | Education: ...        (degrees + certificates)
    Skills: ...         | Competences: ...
    Experience: ...     | Experience: ...       (job history)
    Location: ...       | Lieu: ...
    Job: ...            | Emploi: ...

Separator can be ":" or "-". Fields can be split across lines or by ";".
Required fields: name, disability, education, location, job. Skills and
experience are optional but strongly improve matching quality.
"""
import re

FIELD_ALIASES = {
    "full_name":   ["name", "full name", "legal name", "nom", "nom complet"],
    "disability":  ["disability", "registered disability", "handicap"],
    "education":   ["education", "certificates", "education and certificates",
                    "éducation", "education et certificats", "diplomes",
                    "diplômes", "formation", "qualifications"],
    "skills":      ["skills", "competences", "compétences", "savoir-faire",
                    "abilities", "capabilities"],
    "job_history": ["experience", "expérience", "work experience",
                    "job history", "experiences", "historique professionnel",
                    "parcours"],
    "location":    ["location", "job location", "lieu", "lieu de travail", "ville"],
    "job_pref":    ["job", "job preference", "preferred job", "emploi",
                    "preference emploi", "préférence d'emploi", "poste"],
}

LABEL_TO_FIELD = {}
for field, labels in FIELD_ALIASES.items():
    for lbl in labels:
        LABEL_TO_FIELD[lbl] = field

_LABELS_PATTERN = "|".join(sorted({re.escape(l) for l in LABEL_TO_FIELD},
                                  key=len, reverse=True))
_LINE_RE = re.compile(
    r"(?P<label>" + _LABELS_PATTERN + r")\s*[:\-]\s*(?P<value>.+?)"
    r"(?=(?:\s*(?:" + _LABELS_PATTERN + r")\s*[:\-])|$)",
    re.IGNORECASE | re.DOTALL,
)

REQUIRED = ["full_name", "disability", "education", "location", "job_pref"]
OPTIONAL = ["skills", "job_history"]


def parse_sms(body):
    """Return (candidate_dict, missing_required_list)."""
    if not body:
        return {}, list(REQUIRED)

    text = body.replace(";", "\n").replace("\r", "\n")
    out = {}
    for m in _LINE_RE.finditer(text):
        label = m.group("label").strip().lower()
        value = m.group("value").strip().strip(".").strip()
        value = re.sub(r"\s+", " ", value)
        field = LABEL_TO_FIELD.get(label)
        if field and field not in out and value:
            out[field] = value

    for f in OPTIONAL:
        out.setdefault(f, "")

    missing = [f for f in REQUIRED if not out.get(f)]
    return out, missing
