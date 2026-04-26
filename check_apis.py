"""Quick probe: are the SerpApi + local Ollama (Gemma) integrations live?

Run from the Python 3.11 env:

    conda activate hacknation5-env2
    python check_apis.py
"""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s %(name)s: %(message)s")

import config

print("=" * 72)
print("ENV CHECK")
print("=" * 72)
print("Python:                   ", sys.version.split()[0])
print("DEMO_MODE:                ", os.environ.get("DEMO_MODE", "(unset)"))

# ---- SerpApi --------------------------------------------------------------
print()
print("--- SerpApi ---")
print("SERPAPI_API_KEY set:      ", bool(config.SERPAPI_API_KEY),
      "(len {})".format(len(config.SERPAPI_API_KEY)) if config.SERPAPI_API_KEY else "")
print("SERPAPI_ENABLED:          ", config.SERPAPI_ENABLED)
print("SERPAPI_MAX_CALLS_PER_DAY:", config.SERPAPI_MAX_CALLS_PER_DAY)

import serpapi_jobs
serp_enabled = bool(config.SERPAPI_ENABLED and config.SERPAPI_API_KEY)
print("Adapter enabled:          ", serp_enabled)
print("Calls today (cached):     ", serpapi_jobs._read_counter().get("calls", 0))

if serp_enabled:
    print()
    print("Probing SerpApi: 'software developer' in Lagos, Nigeria ...")
    jobs = serpapi_jobs.search("software developer", "Lagos, Nigeria",
                               country={"country_code": "NG"}, max_results=3)
    print("  -> got {} job(s)".format(len(jobs)))
    for j in jobs[:3]:
        print("     -", j.get("title"), "@", j.get("company"),
              "(", j.get("location"), ")")
    print("  -> calls today now:", serpapi_jobs._read_counter().get("calls", 0))
    print("  (cached on disk under data/serpapi_cache/)")

# ---- Ollama / Gemma --------------------------------------------------------
print()
print("--- Ollama (local LLM) ---")
print("LLM_RERANK_ENABLED:       ", os.environ.get("LLM_RERANK_ENABLED"))
print("LLM_MODEL:                ", os.environ.get("LLM_MODEL", "gemma3:4b"))

try:
    import ollama  # noqa
    print("ollama package installed: yes")
except ImportError:
    print("ollama package installed: NO  (pip install ollama)")

import llm_reasoner
print("Reasoner._enabled():      ", llm_reasoner._enabled())
print("Calls today (cached):     ", llm_reasoner._read_counter().get(
        llm_reasoner._today(), 0))

if llm_reasoner._enabled():
    print()
    print("Direct Ollama probe (raw, not cached) ...")
    try:
        from ollama import chat
        res = chat(
            model=os.environ.get("LLM_MODEL", "gemma3:4b"),
            messages=[{
                "role": "user",
                "content": ('Reply with strict JSON only, exact shape: '
                            '{"verdict":"yes","rationale":"ok"}'),
            }],
            options={"temperature": 0.0},
        )
        print("  OK. content =", repr(res.message.content))
    except Exception as exc:
        import traceback
        print("  FAILED:", type(exc).__name__, "-", exc)
        traceback.print_exc()

    print()
    print("Probing reasoner: visually impaired -> Software Developer ...")
    cand = {
        "disability": "Visual impairment",
        "skills": "Python, Django, SQL",
        "education": "B.Sc Computer Science",
        "job_pref": "Junior Software Developer",
    }
    job = {
        "title": "Junior Software Developer",
        "company": "Andela",
        "description": "Build Django backends. Remote-friendly. Screen-reader compatible workflow.",
        "requirements": "Python, SQL, Git",
    }
    out = llm_reasoner.assess_fit(cand, job, lang="en")
    print("  ->", out)

    print()
    print("Probing reasoner: leg amputee -> Farm Field Worker ...")
    cand2 = {
        "disability": "Lower-limb amputation, wheelchair user",
        "skills": "agriculture, hand tools",
        "education": "Primary",
        "job_pref": "Farm worker",
    }
    job2 = {
        "title": "Farm Field Worker",
        "company": "AgroNigeria",
        "description": "Plant, weed, harvest. Long hours standing in the field.",
        "requirements": "Physical fitness, ability to lift 25kg",
    }
    out2 = llm_reasoner.assess_fit(cand2, job2, lang="en")
    print("  ->", out2)

    print()
    print("Total LLM calls today:", llm_reasoner._read_counter().get(
            llm_reasoner._today(), 0))

print()
print("=" * 72)
print("Done. If both adapters say _enabled() = True and the probe printed")
print("rows / a verdict, your live + local LLM stacks are wired up correctly.")
print("=" * 72)
