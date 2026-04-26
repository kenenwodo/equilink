"""Local Gemma (via Ollama) disability + job fit reasoner.

We ask the LLM ONE direct question per (candidate, job) pair:

    "Given this person's disability, skills and education, can they
    realistically perform the core tasks of this job? Answer yes/maybe/no
    plus one short sentence."

The rule-based reasoner in `disability_fit.py` runs first and removes the
clearly-incompatible jobs. The LLM is then only asked about the survivors,
which keeps the call count tiny:

    * top_n results per candidate submission   (default 5)
    * cached per (candidate, job) → reruns are free
    * soft daily cap via `LLM_MAX_CALLS_PER_DAY`

Gated by env: requires `LLM_RERANK_ENABLED=1` and the `ollama` package
plus a running local Ollama daemon with the model pulled. No API key is
needed because the model runs locally.
"""
import hashlib
import json
import logging
import os
import re
from datetime import datetime

import config

log = logging.getLogger(__name__)

CACHE_DIR = config.DATA_DIR / "llm_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
COUNTER_FILE = CACHE_DIR / "_call_counter.json"

MODEL = os.environ.get("LLM_MODEL", "gemma3:4b")
MAX_CALLS_PER_DAY = int(os.environ.get("LLM_MAX_CALLS_PER_DAY", "200"))

# Bump this when the prompt changes so old cached verdicts get refreshed.
PROMPT_VERSION = "v2-encouraging"


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------
def _enabled():
    if os.environ.get("LLM_RERANK_ENABLED", "0").lower() not in ("1", "true", "yes"):
        return False
    try:
        import ollama  # noqa: F401
    except ImportError:
        log.warning("ollama package not installed; LLM rerank disabled. "
                    "Install with `pip install ollama`.")
        return False
    return True


# ---------------------------------------------------------------------------
# Cache + quota
# ---------------------------------------------------------------------------
def _today():
    return datetime.utcnow().strftime("%Y%m%d")


def _key(candidate, job):
    blob = "|".join([
        PROMPT_VERSION,
        (candidate.get("disability") or "").lower(),
        (candidate.get("skills") or "").lower(),
        (candidate.get("education") or "").lower(),
        (candidate.get("job_pref") or "").lower(),
        (job.get("title") or "").lower(),
        (job.get("description") or "")[:400].lower(),
    ])
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def _cache_path(candidate, job):
    return CACHE_DIR / "{}_{}.json".format(_today(), _key(candidate, job))


def _read_counter():
    if not COUNTER_FILE.exists():
        return {}
    try:
        return json.loads(COUNTER_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _bump_counter():
    d = _read_counter()
    today = _today()
    d[today] = d.get(today, 0) + 1
    try:
        COUNTER_FILE.write_text(json.dumps(d), encoding="utf-8")
    except Exception:
        pass
    return d[today]


def _quota_left():
    d = _read_counter()
    return MAX_CALLS_PER_DAY - d.get(_today(), 0)


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------
_PROMPT = """You are a disability-aware, ENCOURAGING job-fit assessor.

Your default stance is supportive: people with disabilities can do most jobs,
often with assistive technology, training or reasonable accommodation. Do NOT
shut a candidate out of an ambitious choice unless their disability makes the
core tasks of the job *physically impossible*.

Decision rule:
- "yes"   = the candidate can perform the core tasks (with screen readers,
             hand controls, reasonable accommodation, training, etc.).
- "maybe" = significant accommodation or upskilling is needed, but the role
             is still achievable. Note what support would help.
- "no"    = ONLY when the disability physically prevents the core tasks
             (e.g. a fully blind person driving a vehicle, an arm amputee
             performing surgery, a deaf person doing phone-only call-centre
             work). Use this verdict sparingly.

Reference examples:
- Visually impaired person + software engineering            -> yes (screen readers).
- Visually impaired person + outdoor field officer           -> maybe (needs guide / support).
- Visually impaired person + photography or driving          -> no (physically impossible).
- Wheelchair user + CAD design / accounting / remote work    -> yes.
- Wheelchair user + driving with adapted vehicle             -> maybe (hand controls).
- Wheelchair user + heavy construction labour                -> no (physically impossible).
- Deaf person + most desk work, software, design             -> yes.
- Deaf person + phone-only call-centre operator              -> no (physically impossible).
- Arm amputee + management / writing / consulting            -> yes.
- Arm amputee + surgery / watchmaking / jewellery            -> no (physically impossible).

Be honest but encouraging. When the answer is "yes" or "maybe", briefly
mention the assistive tech, accommodation or skill that makes it work.

Return STRICT JSON only, no prose, no markdown fences, exact shape:
{{"verdict": "yes" | "maybe" | "no", "rationale": "<one short sentence in {lang_name}>"}}

CANDIDATE
  disability:  {disability}
  skills:      {skills}
  education:   {education}
  preference:  {pref}

JOB
  title:        {title}
  company:      {company}
  description:  {desc}
  requirements: {reqs}

JSON:"""


def _build_prompt(candidate, job, lang):
    return _PROMPT.format(
        lang_name="French" if lang == "fr" else "English",
        disability=candidate.get("disability") or "—",
        skills=candidate.get("skills") or "—",
        education=candidate.get("education") or "—",
        pref=candidate.get("job_pref") or "—",
        title=job.get("title") or "—",
        company=job.get("company") or "—",
        desc=(job.get("description") or "")[:600],
        reqs=(job.get("requirements") or "")[:300],
    )


def _extract_json(text):
    """Pull the first JSON object out of a model response.

    Local models sometimes wrap output in ```json fences or add a stray
    sentence. We grab the first {...} block to be safe.
    """
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def assess_fit(candidate, job, lang="en"):
    """Return {verdict, rationale, source} or None when disabled / quota gone.

    verdict ∈ {"yes", "maybe", "no"}.
    """
    if not _enabled():
        return None

    cp = _cache_path(candidate, job)
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            pass

    if _quota_left() <= 0:
        log.warning("LLM daily quota exhausted (%d calls)", MAX_CALLS_PER_DAY)
        return None

    try:
        from ollama import chat
    except ImportError:
        return None

    prompt = _build_prompt(candidate, job, lang)
    try:
        response = chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
        )
        _bump_counter()
        text = response.message.content
    except Exception as exc:
        log.warning("Ollama call failed: %s", exc)
        return None

    out = _extract_json(text)
    if not out:
        log.warning("LLM returned non-JSON: %r", (text or "")[:200])
        return None

    verdict = (out.get("verdict") or "maybe").strip().lower()
    if verdict not in ("yes", "maybe", "no"):
        verdict = "maybe"
    result = {
        "verdict": verdict,
        "rationale": (out.get("rationale") or "").strip()[:280],
        "source": "ollama:" + MODEL,
    }
    try:
        cp.write_text(json.dumps(result), encoding="utf-8")
    except Exception:
        pass
    return result
