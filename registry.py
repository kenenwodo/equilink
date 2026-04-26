"""Lookup against the (sample) National Disability Registry."""
import csv
import re
import unicodedata

import config


def _norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _name_tokens(name):
    return set(_norm(name).split())


def _disability_match(a, b):
    """Soft match: any shared meaningful token (>=4 chars), or substring."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na in nb or nb in na:
        return True
    ta = {t for t in na.split() if len(t) >= 4}
    tb = {t for t in nb.split() if len(t) >= 4}
    return bool(ta & tb)


def verify(full_name, phone, disability):
    """Return (is_registered, matched_row_or_None).

    Matching rule: at least 2 shared name tokens AND a disability soft-match.
    Phone match is a strong override (exact E.164).
    """
    if not config.REGISTRY_CSV.exists():
        return False, None

    cand_tokens = _name_tokens(full_name)
    with open(config.REGISTRY_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if phone and row.get("phone") and phone.strip() == row["phone"].strip():
                if _disability_match(disability, row.get("disability", "")):
                    return True, row
            shared = cand_tokens & _name_tokens(row.get("full_name", ""))
            if len(shared) >= 2 and _disability_match(disability, row.get("disability", "")):
                return True, row
    return False, None
