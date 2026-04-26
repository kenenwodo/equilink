"""Disability-aware job fit reasoner.

For each candidate disability + job posting we estimate compatibility using a
small rule base that mimics the kind of reasoning a recruiter (or an LLM)
would do:

    candidate disability  ->  body demands the role places on a worker
            +              ->  +
    job description        ->  same demands inferred from the posting

We refuse to recommend a job whose physical demands are clearly incompatible
with the candidate's disability (e.g. leg amputee farmer / blind driver) and
boost roles that are well-suited (e.g. wheelchair user with engineering
background → seated CAD / software work).

This is deterministic and offline — no LLM call required.  An optional LLM
rerank can be plugged in later via `llm_matcher.py` (env-gated).
"""

import re
import unicodedata


# ---------------------------------------------------------------------------
# Disability categorisation
# ---------------------------------------------------------------------------
# Each category is a structural label we can reason about, plus the EN/FR
# trigger words that map onto it.

DISABILITY_CATEGORIES = {
    "vision": [
        "blind", "blindness", "visual impairment", "low vision", "vision loss",
        "partially sighted", "aveugle", "malvoyant", "deficience visuelle",
        "deficient visuel", "cecite",
    ],
    "hearing": [
        "deaf", "hearing impairment", "hard of hearing", "hearing loss",
        "sourd", "malentendant", "deficience auditive",
    ],
    "mobility_lower": [
        "lower-limb", "lower limb", "leg amputee", "leg amputation",
        "amputation jambe", "amputation de la jambe", "amputee leg",
        "paraplegic", "paraplegia", "wheelchair", "fauteuil roulant",
        "mobilite reduite", "mobility impairment", "polio",
    ],
    "mobility_upper": [
        "upper-limb", "upper limb", "arm amputee", "arm amputation",
        "amputation bras", "amputation du bras", "hand impairment",
        "loss of hand", "amputee arm",
    ],
    "speech": [
        "speech impairment", "mute", "non-verbal", "trouble de la parole",
        "muet", "aphasia",
    ],
    "cognitive": [
        "cognitive", "learning disability", "dyslexia", "autism",
        "intellectual disability", "trouble cognitif", "dyslexie", "autisme",
    ],
}


# ---------------------------------------------------------------------------
# Job-demand classifier
# ---------------------------------------------------------------------------
# We tag each job with the physical / sensory demands its description implies.
# A single job can carry several tags.

JOB_DEMANDS = {
    # Heavy physical / outdoor
    "heavy_physical": [
        "farmer", "farming", "agriculture", "agricultural worker",
        "agronomist", "field worker", "construction", "labourer", "laborer",
        "warehouse", "loader", "porter", "stevedore", "mason", "masonry",
        "welder", "welding", "scaffolder", "scaffolding", "miner", "mining",
        "fabrication", "assembly line", "production line", "lifting",
        "manual labour", "manual labor",
        "ouvrier", "agriculteur", "manutention", "manutentionnaire",
        "maconnerie", "soudeur", "chantier",
    ],
    "standing_long": [
        "cashier", "waiter", "waitress", "server", "retail attendant",
        "retail associate", "store clerk", "shop assistant", "barista",
        "caissier", "serveur", "vendeur",
    ],
    "driving": [
        "driver", "chauffeur", "delivery rider", "taxi", "okada", "trucker",
        "logistics driver", "dispatch rider",
        "livreur", "camionneur",
    ],
    "fieldwork_outdoor": [
        "field officer", "field agent", "field supervisor", "surveyor",
        "extension officer", "outreach worker", "geologist field",
        "agent de terrain", "agent commercial terrain",
    ],
    "vision_intensive": [
        "graphic design", "graphic designer", "photographer", "photography",
        "videographer", "quality inspector", "inspector", "quality control",
        "radiologist", "tailor", "seamstress", "couturier", "couturiere",
        "couture", "embroidery",
        "designer graphique", "photographe", "controleur qualite",
    ],
    "hearing_required": [
        "call center", "call centre", "call-center", "tele-marketer",
        "telemarketer", "telemarketing", "customer service representative",
        "telephone operator", "telephonist", "radio operator",
        "centre d appel", "teleconseiller", "operateur telephonique",
    ],
    "fine_motor": [
        "watchmaker", "watch repair", "jewelry", "jeweller", "jeweler",
        "surgical", "surgeon", "dentist", "tailor", "seamstress",
        "couturier", "couturiere", "couture", "embroidery", "electronics technician",
        "soldering", "horloger", "bijoutier",
    ],
    "desk_seated_computer": [
        "software", "developer", "engineer", "programmer", "data analyst",
        "data scientist", "accountant", "bookkeeper", "auditor",
        "cad", "autocad", "draughtsman", "drafter", "design engineer",
        "mechanical design", "electrical design", "civil design",
        "content writer", "copywriter", "translator", "transcriber",
        "virtual assistant", "remote support", "customer support remote",
        "data entry", "office administrator", "hr officer",
        "developpeur", "ingenieur logiciel", "comptable", "redacteur",
        "traducteur", "assistant virtuel", "saisie de donnees",
    ],
    "voice_only": [
        "radio host", "voice over", "voice-over", "podcast", "narrator",
        "musician", "singer",
        "animateur radio", "chanteur", "musicien",
    ],
}


# Compatibility matrix: which job demands are PHYSICALLY IMPOSSIBLE for a
# disability (block) vs. which the disability actively favours (boost) vs.
# which are challenging-but-possible with accommodation (caution).
#
# Philosophy: do NOT shut a candidate out of an ambitious choice unless they
# are *physically unable* to do the core tasks. Anything that can be done
# with assistive tech, accommodation or training stays on the list with a
# caution note attached so the candidate can make an informed choice.
#
#   key   = disability category
#   value = {"block": [...impossible demand tags...],
#            "caution": [...possible-but-hard demand tags...],
#            "boost":   [...well-suited demand tags...]}
COMPAT = {
    "vision": {
        # Driving a vehicle and visual-precision work (photography, quality
        # inspection, graphic design) genuinely require sight.
        "block":   ["driving", "vision_intensive"],
        "caution": ["heavy_physical", "fieldwork_outdoor"],
        "boost":   ["voice_only", "hearing_required",   # call centres = phone work
                    "desk_seated_computer"],             # screen-reader friendly
    },
    "hearing": {
        # Phone-only call-centre work needs hearing.
        "block":   ["hearing_required"],
        "caution": [],
        "boost":   ["desk_seated_computer", "vision_intensive", "fine_motor"],
    },
    "mobility_lower": {
        # Heavy lifting and all-day standing require functional legs.
        "block":   ["heavy_physical", "standing_long"],
        # Driving can be done with hand controls; outdoor fieldwork can
        # sometimes be wheelchair-accessible — surface as caution, not block.
        "caution": ["driving", "fieldwork_outdoor"],
        "boost":   ["desk_seated_computer", "voice_only", "hearing_required",
                    "fine_motor"],
    },
    "mobility_upper": {
        # Surgery / jewellery / heavy lifting require functional hands+arms.
        "block":   ["fine_motor", "heavy_physical"],
        "caution": [],
        "boost":   ["voice_only", "hearing_required"],
    },
    "speech": {
        # Radio host / phone-based work require speaking.
        "block":   ["voice_only", "hearing_required"],
        "caution": [],
        "boost":   ["desk_seated_computer", "fine_motor"],
    },
    "cognitive": {
        "block":   [],
        "caution": [],
        "boost":   [],   # avoid stereotyping; rely on TF-IDF + skills match
    },
}


_NORM_RE = re.compile(r"[^a-z0-9 ]+")


def _normalise(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _NORM_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def classify_disability(disability_text):
    """Return list of disability categories detected in the candidate's text."""
    norm = _normalise(disability_text)
    cats = []
    for cat, kws in DISABILITY_CATEGORIES.items():
        for kw in kws:
            if kw in norm:
                cats.append(cat)
                break
    return cats


def classify_job_demands(job):
    """Return list of demand tags inferred from the job posting text."""
    blob = _normalise(" ".join([
        job.get("title", "") or "",
        job.get("description", "") or "",
        job.get("requirements", "") or "",
    ]))
    demands = []
    for tag, kws in JOB_DEMANDS.items():
        for kw in kws:
            if kw in blob:
                demands.append(tag)
                break
    return demands


# ---------------------------------------------------------------------------
# Rationale phrasing (EN + FR)
# ---------------------------------------------------------------------------
_DEMAND_PHRASE = {
    "heavy_physical":      ("heavy physical labour",       "travail physique lourd"),
    "standing_long":       ("long periods of standing",    "longues periodes debout"),
    "driving":             ("driving",                     "conduite"),
    "fieldwork_outdoor":   ("outdoor fieldwork",           "travail de terrain en exterieur"),
    "vision_intensive":    ("close, vision-intensive work","travail visuel intense"),
    "hearing_required":    ("phone or audio work",         "travail au telephone"),
    "fine_motor":          ("fine motor / hand precision", "motricite fine des mains"),
    "desk_seated_computer":("seated computer work",        "travail assis sur ordinateur"),
    "voice_only":          ("voice-based work",            "travail base sur la voix"),
}

_DISABILITY_PHRASE = {
    "vision":          ("visual impairment",   "deficience visuelle"),
    "hearing":         ("hearing impairment",  "deficience auditive"),
    "mobility_lower":  ("lower-limb mobility", "mobilite des membres inferieurs"),
    "mobility_upper":  ("upper-limb mobility", "mobilite des membres superieurs"),
    "speech":          ("speech impairment",   "trouble de la parole"),
    "cognitive":       ("cognitive disability","handicap cognitif"),
}


def _phrase(table, key, lang):
    en, fr = table.get(key, (key, key))
    return fr if lang == "fr" else en


def score_job(disability_cats, job, lang="en"):
    """Return {fit_score, fit_band, rationale, demands, blocked, boosted, cautions}.

    fit_band ∈ {incompatible, caution, neutral, suitable, preferred}
    fit_score is in roughly [-0.40, +0.25] and gets added to the matcher score.

    "incompatible" is reserved for jobs the candidate is *physically unable*
    to do (e.g. blind person + driving). Roles that are challenging but
    possible with accommodation are returned as "caution" and stay on the
    candidate's list with an informational note.
    """
    demands = classify_job_demands(job)
    if not disability_cats:
        return {
            "fit_score": 0.0,
            "fit_band": "neutral",
            "rationale": "",
            "demands": demands,
            "blocked": [],
            "boosted": [],
            "cautions": [],
        }

    blocked, boosted, cautions = [], [], []
    for cat in disability_cats:
        rules = COMPAT.get(cat, {})
        for tag in demands:
            if tag in rules.get("block", []):
                blocked.append((cat, tag))
            elif tag in rules.get("caution", []):
                cautions.append((cat, tag))
            elif tag in rules.get("boost", []):
                boosted.append((cat, tag))

    if blocked:
        # Reserved strictly for physical impossibility.
        cat, tag = blocked[0]
        if lang == "fr":
            rationale = "Non recommande : ce poste exige {} qui n'est pas physiquement possible avec {}.".format(
                _phrase(_DEMAND_PHRASE, tag, lang),
                _phrase(_DISABILITY_PHRASE, cat, lang))
        else:
            rationale = "Not recommended: this role requires {} which is not physically possible with {}.".format(
                _phrase(_DEMAND_PHRASE, tag, lang),
                _phrase(_DISABILITY_PHRASE, cat, lang))
        return {
            "fit_score": -0.40,
            "fit_band": "incompatible",
            "rationale": rationale,
            "demands": demands,
            "blocked": blocked,
            "boosted": boosted,
            "cautions": cautions,
        }

    if boosted:
        cat, tag = boosted[0]
        if lang == "fr":
            rationale = "Bonne adequation : ce poste repose sur {} — compatible avec {}.".format(
                _phrase(_DEMAND_PHRASE, tag, lang),
                _phrase(_DISABILITY_PHRASE, cat, lang))
        else:
            rationale = "Strong fit: this role centres on {} — compatible with {}.".format(
                _phrase(_DEMAND_PHRASE, tag, lang),
                _phrase(_DISABILITY_PHRASE, cat, lang))
        score = 0.25 if len(boosted) >= 2 else 0.18
        return {
            "fit_score": score,
            "fit_band": "preferred" if len(boosted) >= 2 else "suitable",
            "rationale": rationale,
            "demands": demands,
            "blocked": blocked,
            "boosted": boosted,
            "cautions": cautions,
        }

    if cautions:
        # Possible with accommodation — keep on the list, just nudge slightly.
        cat, tag = cautions[0]
        if lang == "fr":
            rationale = "Possible avec amenagement : ce poste implique {} — prevoyez du soutien adapte a {}.".format(
                _phrase(_DEMAND_PHRASE, tag, lang),
                _phrase(_DISABILITY_PHRASE, cat, lang))
        else:
            rationale = "Possible with accommodation: this role involves {} — plan for support suited to {}.".format(
                _phrase(_DEMAND_PHRASE, tag, lang),
                _phrase(_DISABILITY_PHRASE, cat, lang))
        return {
            "fit_score": -0.05,
            "fit_band": "caution",
            "rationale": rationale,
            "demands": demands,
            "blocked": [],
            "boosted": boosted,
            "cautions": cautions,
        }

    # No demand tags resolved either way → mildly cautious if we couldn't tell
    if lang == "fr":
        rationale = "Aucune contre-indication detectee dans la description du poste."
    else:
        rationale = "No accessibility blockers detected in the job description."
    return {
        "fit_score": 0.02,
        "fit_band": "neutral",
        "rationale": rationale,
        "demands": demands,
        "blocked": [],
        "boosted": [],
        "cautions": [],
    }


def summarise_for_candidate(candidate_disability, lang="en"):
    """Short human-readable summary of how we will reason for this candidate."""
    cats = classify_disability(candidate_disability)
    if not cats:
        return cats, ""
    phrases = [_phrase(_DISABILITY_PHRASE, c, lang) for c in cats]
    if lang == "fr":
        msg = ("Profil pris en compte : {}. Nous excluons uniquement les postes "
               "physiquement impossibles ; les autres restent accessibles, avec "
               "des recommandations d'amenagement si necessaire.").format(", ".join(phrases))
    else:
        msg = ("Profile considered: {}. We only filter out roles that are "
               "physically impossible — every other path stays open, with "
               "accommodation notes where helpful.").format(", ".join(phrases))
    return cats, msg
