"""Loads per-country YAML configs and shared taxonomy/automation data.

Country selection priority:
  1. explicit country_code argument
  2. derived from candidate phone E.164 prefix
  3. NG default
"""
import csv
from pathlib import Path

import yaml

import config

_CONFIG_DIR = config.BASE_DIR / "config_data"
COUNTRIES_DIR = _CONFIG_DIR / "countries"
TAXONOMY_PATH = _CONFIG_DIR / "taxonomy" / "esco_subset.csv"
FREY_PATH = _CONFIG_DIR / "automation" / "frey_osborne.csv"
LMIC_CAL_PATH = _CONFIG_DIR / "automation" / "lmic_calibration.yaml"
WITTGENSTEIN_PATH = _CONFIG_DIR / "wittgenstein" / "projections.yaml"

_PHONE_TO_CODE = {"+234": "ng", "+237": "cm", "+243": "cd", "+242": "cd"}


def country_from_phone(phone):
    if not phone:
        return None
    for prefix, code in _PHONE_TO_CODE.items():
        if phone.strip().startswith(prefix):
            return code
    return None


_country_cache = {}


def load_country(code=None, phone=None):
    code = (code or country_from_phone(phone) or "ng").lower()
    if code in _country_cache:
        return _country_cache[code]
    path = COUNTRIES_DIR / "{}.yaml".format(code)
    if not path.exists():
        path = COUNTRIES_DIR / "ng.yaml"
        code = "ng"
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["_code"] = code
    _country_cache[code] = data
    return data


def list_country_codes():
    return sorted(p.stem for p in COUNTRIES_DIR.glob("*.yaml"))


# ---- shared taxonomy ------------------------------------------------------
_taxonomy_cache = None


def load_taxonomy():
    global _taxonomy_cache
    if _taxonomy_cache is not None:
        return _taxonomy_cache
    rows = []
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            r["alt_labels_list"] = [s.strip().lower() for s in r["alt_labels"].split(";") if s.strip()]
            r["skills_list"] = [s.strip().lower() for s in r["canonical_skills"].split(";") if s.strip()]
            rows.append(r)
    _taxonomy_cache = rows
    return rows


def occupation_by_isco(isco_code):
    for row in load_taxonomy():
        if row["isco_code"] == str(isco_code):
            return row
    return None


# ---- automation data ------------------------------------------------------
_frey_cache = None


def load_frey():
    global _frey_cache
    if _frey_cache is not None:
        return _frey_cache
    out = {}
    with open(FREY_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["isco_code"]] = {
                "label": r["occupation_label"],
                "probability": float(r["frey_osborne_probability"]),
                "source": r["source_note"],
            }
    _frey_cache = out
    return out


_lmic_cache = None


def load_lmic_calibration():
    global _lmic_cache
    if _lmic_cache is None:
        with open(LMIC_CAL_PATH, encoding="utf-8") as f:
            _lmic_cache = yaml.safe_load(f)
    return _lmic_cache


_witt_cache = None


def load_wittgenstein():
    global _witt_cache
    if _witt_cache is None:
        with open(WITTGENSTEIN_PATH, encoding="utf-8") as f:
            _witt_cache = yaml.safe_load(f)
    return _witt_cache
