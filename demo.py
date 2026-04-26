"""End-to-end demo runner. Runs four scenarios with no SMS account required.

Usage:
    python demo.py
"""
import logging
import os
import sys

os.environ["DEMO_MODE"] = "1"
os.environ.setdefault("USE_REMOTEOK", "0")

import config       # noqa: E402
import pipeline     # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


SCENARIOS = [
    ("Scenario 1: REGISTERED candidate (English, Nigeria) - software developer",
     "+2348012345678",
     """Name: Adaeze Okafor
Disability: Visual impairment
Education: B.Sc Computer Science, University of Lagos; AWS Cloud Practitioner
Skills: Python, Django, JavaScript, Git, SQL
Experience: 2 years intern at Andela; 1 year freelance web dev
Location: Lagos, Nigeria
Job: Junior Software Developer"""),

    ("Scenario 2: NOT-REGISTERED candidate (English, Nigeria) - mechanical tech",
     "+2348099998888",
     """Name: Ifeanyi Obi
Disability: Lower-limb mobility impairment
Education: WAEC SSCE; OND Mechanical Engineering, Yaba College of Tech
Skills: AutoCAD, HVAC, mechanical drawing, hand tools
Experience: 3 years apprenticeship at fabrication workshop
Location: Abuja, Nigeria
Job: Mechanical maintenance technician"""),

    ("Scenario 3: REGISTERED candidate (French, Cameroon) - tailor",
     "+237671234567",
     """Nom: Marie Nguema
Handicap: Mobilité réduite
Education: BEPC; CAP Couture
Competences: couture, patrons, retouches, finitions
Experience: 4 ans atelier de couture à Yaoundé
Lieu: Douala, Cameroun
Emploi: Couturier"""),

    ("Scenario 4: REGISTERED candidate (French, DR Congo) - logistics",
     "+243812345678",
     """Nom: Jean-Paul Mbeki
Handicap: Amputation jambe gauche
Education: Diplôme d'État, Graduat Logistique
Competences: SAP, supply chain, français, anglais
Experience: 3 ans agent logistique au port de Matadi
Lieu: Kinshasa, RDC
Emploi: Coordinateur logistique"""),
]


def banner(t):
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78)


def summarise(r):
    print("\n  status     :", r.get("status"))
    print("  language   :", r.get("language"))
    print("  country    :", r.get("country"))
    print("  registered :", r.get("registered"))
    p = r.get("profile") or {}
    if p.get("occupations"):
        print("  Module 1 - Skills profile:")
        for o in p["occupations"][:3]:
            print("     * {} (ISCO {}) score={:.2f}  matched={}"
                  .format(o["label"], o["isco"], o["score"], ", ".join(o["matched_terms"][:4])))
        print("     ISCED level :", p["isced_level"], "-", p["isced_label"])
        if p.get("skills_missing"):
            print("     skills to grow:", ", ".join(p["skills_missing"][:5]))
    risk = r.get("risk") or {}
    if risk.get("occupations"):
        ro = risk["occupations"][0]
        print("  Module 2 - Automation risk: {:.0%} ({}); adjacent: {}".format(
            ro["automation_risk_lmic"], ro["risk_band"],
            ", ".join(o["label"] for o in ro["adjacent_occupations"][:3])))
        if risk.get("wittgenstein_shift"):
            print("     Wittgenstein 25-35:", risk["wittgenstein_shift"])
    econ = r.get("econ") or {}
    if econ.get("signals"):
        print("  Module 3 - Econ signals:")
        for s in econ["signals"]:
            print("     * {}: {}".format(s["label"], s["value"]))
    if r.get("applied"):
        print("  Top opportunities:")
        for a in r["applied"]:
            j = a["job"]
            comps = a.get("components", {})
            print("     - {:.2f}  {} @ {} ({})  [tfidf={:.2f} loc={:.2f} isco={:.2f} incl={:.2f}]".format(
                a["score"], j.get("title", ""), j.get("company", ""), j.get("location", ""),
                comps.get("tfidf", 0), comps.get("location", 0),
                comps.get("isco", 0), comps.get("inclusion", 0)))


def main():
    # Reset run-state so the demo is reproducible
    for p in [config.CANDIDATES_CSV, config.APPLICATIONS_LOG_CSV]:
        if p.exists():
            p.unlink()
    for p in config.OUTBOX_DIR.glob("*.json"):
        p.unlink()

    print("EquiLink - End-to-End Demo (DEMO_MODE=ON)")
    print("Outbox:", config.OUTBOX_DIR)

    for title, phone, sms in SCENARIOS:
        banner(title)
        print("Inbound SMS from {}:".format(phone))
        for line in sms.splitlines():
            print("    " + line)
        result = pipeline.process_sms(phone, sms, auto_apply=False)
        summarise(result)

    banner("DONE")
    print("Inspect ./data/outbox/    for queued SMS+email payloads.")
    print("Inspect ./data/candidates.csv for stored candidates.")
    print("Inspect ./data/applications_log.csv for the application audit trail.")
    print("Run `python app.py` then open  http://localhost:5000/dashboard/?country=ng")
    print("                                                   ?country=cm")
    print("                                                   ?country=cd")


if __name__ == "__main__":
    sys.exit(main() or 0)
