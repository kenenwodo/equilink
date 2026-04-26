"""Candidate-facing web app — visualizes the full SMS pipeline as a guided
demo. Same backend as the SMS webhook; just a friendlier surface.

Mounted at "/" by app.py.
"""
from flask import Blueprint, render_template_string, request

import pipeline

bp = Blueprint("candidate", __name__)


_FORM = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EquiLink — Candidate</title>
<style>
  * { box-sizing: border-box; }
  body { font: 15px/1.5 -apple-system, system-ui, sans-serif;
         color: #1a1a1a; margin: 0;
         background: linear-gradient(rgba(246,247,251,0.88), rgba(246,247,251,0.88)),
                     url('/static/wallpaper.png') center/cover fixed no-repeat #f6f7fb; }
  .wrap { max-width: 760px; margin: 0 auto; padding: 32px 20px 80px; }
  h1 { font-size: 26px; margin: 0 0 4px; }
  h1 .tagline { font-size: 13px; font-weight: 400; color: #6b7080;
                letter-spacing: 0.02em; display: inline-block; margin-left: 6px; }
  .tag { display: inline-block; background: #e6f0ff; color: #1559c4;
         padding: 2px 10px; border-radius: 12px; font-size: 12px; margin-right: 6px; }
  .sub { color: #555; margin-bottom: 24px; }
  form { background: #fff; border: 1px solid #e1e4ec; border-radius: 12px;
         padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
  label { display: block; font-weight: 600; margin: 14px 0 4px; font-size: 13px; }
  input { width: 100%; padding: 10px 12px; border: 1px solid #d8dce6;
          border-radius: 8px; font: inherit; background: #fff; }
  .help { font-size: 12px; color: #6b7080; margin-top: 4px; }

  /* Phone-like SMS composer */
  .phone {
    margin: 18px auto 0; max-width: 360px;
    border: 10px solid #1c1c1e; border-radius: 36px; padding: 14px 14px 18px;
    background: #ecebe6; box-shadow: 0 8px 24px rgba(0,0,0,0.10);
  }
  .phone .header { text-align: center; font-size: 11px; color: #888;
                   margin-bottom: 8px; }
  .sms-textarea {
    width: 100%; min-height: 220px; padding: 12px 14px; border: 0;
    border-radius: 18px; background: #fff; color: #111;
    font: 14px/1.55 -apple-system, system-ui, sans-serif;
    resize: vertical; outline: none;
    box-shadow: inset 0 0 0 1px #d8dce6;
  }
  .send {
    margin-top: 22px; width: 100%; background: #1559c4; color: #fff;
    border: 0; padding: 14px; border-radius: 8px; font: 600 15px/1 inherit;
    cursor: pointer;
  }
  .send:hover { background: #0f4aa8; }
  .footer { color: #8a8f9c; font-size: 12px; margin-top: 24px; text-align: center; }
  .footer a { color: #1559c4; }
  .partners { margin-top: 18px; padding: 14px 16px; background: rgba(255,255,255,0.85);
              border: 1px solid #e1e4ec; border-radius: 10px;
              display: flex; align-items: center; gap: 14px; }
  .partners-label { font-size: 12px; color: #6b7080; text-transform: uppercase;
                    letter-spacing: 0.06em; }
  .partners img { height: 44px; width: auto; }
  .corner-mark { position: fixed; top: 18px; right: 18px; width: 96px; height: 96px;
                 border-radius: 14px; overflow: hidden;
                 background: rgba(255,255,255,0.85);
                 border: 1px solid #e1e4ec;
                 box-shadow: 0 6px 20px rgba(20,30,60,0.12);
                 z-index: 50; pointer-events: none; }
  .corner-mark img { width: 100%; height: 100%; object-fit: cover; display: block; }
  @media (max-width: 720px) {
    .corner-mark { width: 64px; height: 64px; top: 12px; right: 12px; border-radius: 10px; }
  }
</style>
</head>
<body>
<div class="corner-mark" aria-hidden="true"><img src="/static/wallpaper.png" alt=""></div>
<div class="wrap">
  <span class="tag">SMS-first</span><span class="tag">Disability-inclusive</span><span class="tag">EN / FR</span>
  <h1>EquiLink <span class="tagline">— tackling the UNMAPPED challenge by World Bank</span></h1>
  <p class="sub">Job matching for people with disabilities, designed for low-bandwidth
    SMS. Type your details below as you would in a text message — we map your
    skills, verify you against your country's disability registry (or notify
    them if you're not yet enrolled), and surface inclusive job opportunities
    nearby.</p>

  <form method="post" action="/apply">
    <label>Phone number
      <input name="phone" required value="{{ defaults.phone }}"
             placeholder="+2348012345678 (NG), +237671234567 (CM), +243812345678 (CD)">
    </label>
    <div class="help">Country detected from the dialing prefix.
      Reply language follows what you write — write in French and we'll reply in French.</div>

    <div class="phone">
      <div class="header">New message · EquiLink</div>
      <textarea name="sms_body" class="sms-textarea" required
        placeholder="Name: Adaeze Okafor&#10;Disability: Visual impairment&#10;Education: B.Sc Computer Science&#10;Skills: Python, Django, SQL&#10;Experience: 2 years intern at Andela&#10;Location: Lagos, Nigeria&#10;Job: Junior Software Developer">{{ defaults.sms_body }}</textarea>
    </div>

    <button class="send" type="submit">Send SMS</button>
  </form>

  <p class="footer">
    Pre-filled with <a href="/?preset=ng">Adaeze (NG)</a> ·
    <a href="/?preset=cd_patrick">Patrick (CD, FR, wheelchair)</a> ·
    <a href="/?preset=cm">Marie (CM, FR)</a> ·
    <a href="/?preset=cd">Jean-Paul (CD, FR)</a> ·
    <a href="/dashboard/?country=ng">Policymaker view →</a>
  </p>
  <div class="partners">
    <span class="partners-label">In partnership with</span>
    <img src="/static/ncpwd_logo.png" alt="National Commission for Persons with Disabilities (NCPWD)" title="National Commission for Persons with Disabilities (NCPWD) — Nigeria">
  </div>
</div>
</body>
</html>
"""


_RESULT = """
<!doctype html>
<html lang="{{ result.language }}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EquiLink — Your application</title>
<style>
  * { box-sizing: border-box; }
  body { font: 15px/1.55 -apple-system, system-ui, sans-serif;
         color: #1a1a1a; margin: 0;
         background: linear-gradient(rgba(246,247,251,0.88), rgba(246,247,251,0.88)),
                     url('/static/wallpaper.png') center/cover fixed no-repeat #f6f7fb; }
  .wrap { max-width: 820px; margin: 0 auto; padding: 32px 20px 80px; }
  h1 { font-size: 24px; margin: 0 0 4px; }
  h1 .tagline { font-size: 12px; font-weight: 400; color: #6b7080;
                letter-spacing: 0.02em; display: inline-block; margin-left: 6px; }
  .sub { color: #555; margin-bottom: 28px; }
  .step { position: relative; background: #fff; border: 1px solid #e1e4ec;
          border-radius: 12px; padding: 18px 22px; margin: 16px 0;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
  .step h2 { font-size: 15px; margin: 0 0 8px; color: #1559c4;
             display: flex; align-items: center; gap: 8px; }
  .step h2 .num { background: #1559c4; color: #fff; width: 24px; height: 24px;
                  border-radius: 50%; display: inline-flex; align-items: center;
                  justify-content: center; font-size: 12px; }
  .ok    { border-left: 4px solid #20a464; }
  .warn  { border-left: 4px solid #e89c1d; }
  .info  { border-left: 4px solid #1559c4; }
  .pill  { display: inline-block; background: #eef2fa; padding: 2px 8px;
           border-radius: 10px; font-size: 12px; margin-right: 4px; color: #324769; }
  .pill.high { background: #fde7ea; color: #b21d1d; }
  .pill.medium { background: #fff3df; color: #97670a; }
  .pill.low { background: #e3f5ec; color: #1c7848; }
  table { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 14px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #f0f1f5; }
  th { font-weight: 600; color: #5a6072; font-size: 12px; text-transform: uppercase; }
  .signal-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 8px; }
  .signal { background: #f8fafd; border: 1px solid #ecf0f7; border-radius: 8px; padding: 10px 12px; }
  .signal .label { font-size: 12px; color: #6b7080; }
  .signal .value { font-size: 18px; font-weight: 600; margin-top: 2px; }
  .sms-bubble { background: #ecf6e5; border-radius: 14px; padding: 10px 14px;
                margin: 6px 0; font-size: 14px; white-space: pre-wrap;
                border: 1px solid #d4e6c5; max-width: 95%; }
  .email-bubble { background: #fff5e6; border-radius: 8px; padding: 10px 14px;
                  border: 1px solid #ecdcb8; font-size: 13px; margin-top: 6px; }
  .status-box { border-radius: 8px; padding: 12px 14px; margin-top: 6px;
                font-size: 14px; border: 1px solid #cfd5e0; background: #f8fafd; }
  .status-box.ok   { background: #e9f7ef; border-color: #b7e0c5; }
  .status-box.warn { background: #fff5e6; border-color: #ecdcb8; }
  .status-box .status-line { margin: 2px 0; }
  .reg-logo { height: 28px; width: auto; vertical-align: middle;
              margin: 0 8px; border-radius: 4px; background: #fff;
              padding: 2px; border: 1px solid #e1e4ec; }
  .small { color: #6b7080; font-size: 12px; }
  .back { display: inline-block; margin-top: 16px; color: #1559c4;
          text-decoration: none; font-weight: 600; }
  .components { color: #6b7080; font-size: 12px; }
  .progress { display: flex; gap: 4px; margin-bottom: 18px; }
  .progress span { flex: 1; height: 6px; background: #e1e4ec; border-radius: 3px; }
  .progress span.done { background: #20a464; }
  details.modules { background: #fff; border: 1px solid #e1e4ec; border-radius: 12px;
                    padding: 4px 22px; margin: 16px 0; }
  details.modules > summary { cursor: pointer; padding: 14px 0; font-weight: 600;
                              color: #1559c4; outline: none; }
  details.modules[open] > summary { border-bottom: 1px solid #f0f1f5; margin-bottom: 8px; }
  .module-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 8px 0 14px; }
  .module-card { background: #f8fafd; border: 1px solid #ecf0f7; border-radius: 8px;
                 padding: 10px 12px; }
  .module-card h3 { font-size: 12px; text-transform: uppercase; color: #5a6072;
                    margin: 0 0 6px; letter-spacing: 0.04em; }
  .verdict { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px;
             font-weight: 600; margin-right: 4px; }
  .verdict.yes { background: #e3f5ec; color: #1c7848; }
  .verdict.maybe { background: #fff3df; color: #97670a; }
  .verdict.no { background: #fde7ea; color: #b21d1d; }
</style>
</head>
<body>
<div class="wrap">
  <h1>{% if result.language == 'fr' %}Bonjour{% else %}Hello{% endif %} {{ result.candidate.full_name }} 👋</h1>
  <p class="sub">Country detected: <b>{{ result.candidate.country_code }}</b> ·
    Language: <b>{{ result.language|upper }}</b> ·
    Candidate ID: <code>{{ result.candidate.candidate_id }}</code></p>

  <!-- Step 1: parse & receipt -->
  <div class="step ok">
    <h2><span class="num">1</span>{% if result.language == 'fr' %}Message reçu{% else %}Message received{% endif %}</h2>
    <div class="sms-bubble">{{ messages[0] }}</div>
  </div>

  <!-- Step 2: registry verification (disability-first) -->
  <div class="step {% if result.registered %}ok{% else %}warn{% endif %}">
    <h2><span class="num">2</span>
      {% if result.country == 'NG' %}<img src="/static/ncpwd_logo.png" alt="NCPWD" class="reg-logo">{% endif %}
      {{ result.registry_name }}</h2>
    <div class="status-box {% if result.registered %}ok{% else %}warn{% endif %}">
      {% if result.registered %}
        <div class="status-line"><b>{% if result.language == 'fr' %}Statut{% else %}Status{% endif %}:</b>
          ✅ {% if result.language == 'fr' %}Enregistré au registre.{% else %}On the registry.{% endif %}</div>
        {% if result.registry_match %}
        <div class="status-line small">{% if result.language == 'fr' %}Correspondance{% else %}Match{% endif %}:
          {{ result.registry_match.full_name }} · {{ result.registry_match.disability }}</div>
        {% endif %}
      {% else %}
        <div class="status-line"><b>{% if result.language == 'fr' %}Statut{% else %}Status{% endif %}:</b>
          ⚠️ {% if result.language == 'fr' %}Pas encore enregistré.{% else %}Not yet on the registry.{% endif %}</div>
        <div class="status-line"><b>{% if result.language == 'fr' %}Action{% else %}Action{% endif %}:</b>
          📧 {% if result.language == 'fr' %}Référence envoyée par e-mail au bureau du registre.{% else %}Referral email sent to the registry office on your behalf.{% endif %}</div>
        {% if email_event %}
        <div class="status-line small"><b>{% if result.language == 'fr' %}Destinataire{% else %}Recipient{% endif %}:</b>
          <code>{{ email_event.to }}</code></div>
        <div class="status-line small"><b>{% if result.language == 'fr' %}Sujet{% else %}Subject{% endif %}:</b>
          {{ email_event.subject }}</div>
        {% else %}
        <div class="status-line small"><b>{% if result.language == 'fr' %}Destinataire{% else %}Recipient{% endif %}:</b>
          <code>{{ result.registry_email }}</code></div>
        {% endif %}
      {% endif %}
    </div>
    {% if result.disability and result.disability.note %}
    <p class="small" style="margin-top:10px">🧠 {{ result.disability.note }}</p>
    {% endif %}
  </div>

  <!-- Step 3: ranked jobs (THE main thing the candidate cares about) -->
  <div class="step ok">
    <h2><span class="num">3</span>{% if result.language == 'fr' %}Opportunités classées{% else %}Ranked opportunities{% endif %}</h2>
    {% if result.applied %}
    <table>
      <thead><tr><th>#</th><th>{% if result.language == 'fr' %}Poste{% else %}Title{% endif %}</th>
        <th>{% if result.language == 'fr' %}Entreprise{% else %}Company{% endif %}</th>
        <th>{% if result.language == 'fr' %}Lieu{% else %}Location{% endif %}</th>
        <th>{% if result.language == 'fr' %}Peut effectuer ?{% else %}Can do this job?{% endif %}</th>
        <th>{% if result.language == 'fr' %}Score{% else %}Score{% endif %}</th></tr></thead>
      <tbody>
      {% for a in result.applied %}
        <tr>
          <td>{{ loop.index }}</td>
          <td><b>{{ a.job.title }}</b>{% if a.job.inclusive == 'yes' %}<br><span class="pill low">inclusive</span>{% endif %}</td>
          <td>{{ a.job.company }}</td>
          <td>{{ a.job.location }}</td>
          <td>
            {% if a.llm %}
              <span class="verdict {{ a.llm.verdict }}">
                {% if result.language == 'fr' %}{% if a.llm.verdict == 'yes' %}oui{% elif a.llm.verdict == 'no' %}non{% else %}peut-être{% endif %}{% else %}{{ a.llm.verdict }}{% endif %}
              </span>
              <span class="small" title="{{ a.llm.source }}">🤖</span>
              <div class="small" style="margin-top:4px">{{ a.fit.rationale }}</div>
            {% elif a.fit %}
              {% set band = a.fit.band %}
              {% set cls = 'low' if band in ['preferred','suitable'] else ('medium' if band == 'caution' else '') %}
              <span class="pill {{ cls }}">{{ band }}</span>
              {% if a.fit.rationale %}<div class="small" style="margin-top:4px">{{ a.fit.rationale }}</div>{% endif %}
            {% else %}—{% endif %}
          </td>
          <td>{{ a.score_pct }}%<br>
              <span class="components">tfidf {{ a.components.tfidf }} · isco {{ a.components.isco }} · loc {{ a.components.location }} · incl {{ a.components.inclusion }} · fit {{ a.components.disability_fit }}{% if a.components.llm is defined %} · llm {{ a.components.llm }}{% endif %} · raw {{ "%.2f"|format(a.score) }}</span></td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
    <p class="small" style="margin-top:8px">
      {% if result.language == 'fr' %}Score = TF-IDF + CITP + localisation + inclusion + adéquation handicap (+ raisonnement LLM si activé). Les postes physiquement incompatibles sont exclus. Aucun envoi automatique — répondez OUI pour postuler.{% else %}Score = TF-IDF + ISCO + location + inclusion + disability fit (+ LLM reasoning if enabled). Physically incompatible roles are filtered out. Nothing auto-applied — reply YES to apply.{% endif %}
    </p>
    <div class="sms-bubble" style="margin-top:10px">{{ jobs_sms }}</div>
    {% else %}
    <p>{% if result.language == 'fr' %}Aucune opportunité au-dessus du seuil aujourd'hui. Nous vous recontacterons.{% else %}No matches above threshold today. We will follow up.{% endif %}</p>
    {% endif %}
  </div>

  <!-- Folded technical modules (matters more to policymakers / the registry than to candidates) -->
  <details class="modules">
    <summary>📊 {% if result.language == 'fr' %}Détails techniques (modules 1 / 2 / 3) — pour les organisations partenaires{% else %}Technical details (Modules 1 / 2 / 3) — mainly for partner organisations{% endif %}</summary>

    <div class="module-grid">
      <!-- Module 1 -->
      <div class="module-card">
        <h3>{% if result.language == 'fr' %}Module 1 · Compétences (CITP / ESCO){% else %}Module 1 · Skills (ISCO / ESCO){% endif %}</h3>
        {% if result.profile.occupations %}
        <p style="margin:0 0 4px"><b>{{ result.profile.occupations[0].label }}</b>
          <span class="pill">ISCO {{ result.profile.occupations[0].isco }}</span></p>
        <p class="small" style="margin:0 0 6px">ISCED {{ result.profile.isced_level }} · {{ result.profile.isced_label }}</p>
        <p class="small" style="margin:0">{{ result.profile.occupations[0].explanation }}</p>
        {% if result.profile.skills_missing %}
        <p class="small" style="margin-top:6px">
          {% if result.language == 'fr' %}À développer{% else %}Skills to grow{% endif %}:
          {% for s in result.profile.skills_missing[:4] %}<span class="pill">{{ s }}</span>{% endfor %}
        </p>
        {% endif %}
        {% endif %}
      </div>

      <!-- Module 3 -->
      <div class="module-card">
        <h3>{% if result.language == 'fr' %}Module 3 · Marché du travail{% else %}Module 3 · Labour market{% endif %}</h3>
        {% for s in result.econ.signals[:3] %}
        <p class="small" style="margin:2px 0">
          <span style="color:#5a6072">{{ s.label }}:</span> <b>{{ s.value }}</b>
        </p>
        {% endfor %}
      </div>

      <!-- Module 2 -->
      {% if result.risk.occupations %}
      {% set r = result.risk.occupations[0] %}
      <div class="module-card" style="grid-column: span 2">
        <h3>{% if result.language == 'fr' %}Module 2 · Risque d'automatisation{% else %}Module 2 · Automation risk{% endif %}</h3>
        <p style="margin:0 0 4px">
          <b>{{ r.label }}</b>:
          <span class="pill {{ r.risk_band }}">{{ "%.0f"|format(r.automation_risk_lmic*100) }}% — {{ r.risk_band }}</span>
          <span class="small">(Frey-Osborne {{ "%.0f"|format(r.automation_risk_raw*100) }}% × LMIC {{ result.risk.lmic_multiplier }})</span>
        </p>
        <p class="small" style="margin:2px 0">
          {% if result.language == 'fr' %}Compétences durables{% else %}Durable skills{% endif %}:
          {% for s in result.risk.durable_skills[:4] %}<span class="pill">{{ s }}</span>{% endfor %}
        </p>
        {% if r.adjacent_occupations %}
        <p class="small" style="margin:2px 0">
          {% if result.language == 'fr' %}Métiers adjacents plus sûrs{% else %}Adjacent safer roles{% endif %}:
          {% for a in r.adjacent_occupations[:3] %}<span class="pill">{{ a.label }}</span>{% endfor %}
        </p>
        {% endif %}
        {% if result.risk.wittgenstein_shift %}
        <p class="small" style="margin-top:6px">📈 {{ result.risk.wittgenstein_shift }}</p>
        {% endif %}
      </div>
      {% endif %}
    </div>

    <p class="small" style="margin-top:4px">
      <a href="/dashboard/?country={{ result.candidate.country_code|lower }}">
        → {% if result.language == 'fr' %}Tableau de bord pour les politiques publiques{% else %}Open the policymaker dashboard{% endif %}
      </a>
    </p>
  </details>

  <a href="/" class="back">← {% if result.language == 'fr' %}Tester un autre profil{% else %}Try another profile{% endif %}</a>
</div>
</body>
</html>
"""


def _sms_body(name, disability, education, skills, job_history, location, job_pref, lang="en"):
    if lang == "fr":
        return ("Nom : {n}\nHandicap : {d}\nEducation : {e}\n"
                "Competences : {s}\nExperience : {x}\nLieu : {l}\nEmploi : {j}").format(
            n=name, d=disability, e=education, s=skills, x=job_history, l=location, j=job_pref)
    return ("Name: {n}\nDisability: {d}\nEducation: {e}\n"
            "Skills: {s}\nExperience: {x}\nLocation: {l}\nJob: {j}").format(
        n=name, d=disability, e=education, s=skills, x=job_history, l=location, j=job_pref)


PRESETS = {
    "ng": {
        "phone": "+2348012345678",
        "sms_body": _sms_body(
            "Adaeze Okafor", "Visual impairment",
            "B.Sc Computer Science, University of Lagos; AWS Cloud Practitioner",
            "Python, Django, JavaScript, Git, SQL",
            "2 years intern at Andela; 1 year freelance web dev",
            "Lagos, Nigeria", "Junior Software Developer"),
    },
    "cd_patrick": {
        "phone": "+243815557722",
        "sms_body": _sms_body(
            "Patrick Kabila",
            "Utilisateur de fauteuil roulant (paraplegie)",
            "Licence en Informatique de Gestion, Université de Kinshasa",
            "Excel, SQL, Python, Power BI, français, anglais professionnel",
            "2 ans assistant analyste de données chez une ONG à Kinshasa",
            "Kinshasa, RDC", "Analyste de données junior", lang="fr"),
    },
    "cm": {
        "phone": "+237671234567",
        "sms_body": _sms_body(
            "Marie Nguema", "Mobilité réduite",
            "BEPC; CAP Couture", "couture, patrons, retouches, finitions",
            "4 ans atelier de couture à Yaoundé",
            "Douala, Cameroun", "Couturier", lang="fr"),
    },
    "cd": {
        "phone": "+243812345678",
        "sms_body": _sms_body(
            "Jean-Paul Mbeki", "Amputation jambe gauche",
            "Diplôme d'État, Graduat Logistique",
            "SAP, supply chain, français, anglais",
            "3 ans agent logistique au port de Matadi",
            "Kinshasa, RDC", "Coordinateur logistique", lang="fr"),
    },
}

EMPTY = {"phone": "", "sms_body": ""}


@bp.route("/", methods=["GET"])
def home():
    preset = request.args.get("preset", "ng")
    return render_template_string(_FORM, defaults=PRESETS.get(preset, EMPTY))


@bp.route("/apply", methods=["POST"])
def apply():
    phone = request.form.get("phone", "").strip()
    body = request.form.get("sms_body", "").strip()
    if not phone or not body:
        return render_template_string(
            "<h2 style='font-family:sans-serif;padding:32px'>"
            "Please provide both a phone number and an SMS body.<br>"
            "<a href='/'>Back</a></h2>"), 400

    result = pipeline.process_sms(phone, body, auto_apply=False)

    if result.get("status") != "ok":
        return render_template_string(
            "<h2 style='font-family:sans-serif;padding:32px'>Could not parse your "
            "message — missing fields: {{ m|join(', ') }}.<br><br>"
            "<a href='/'>Try again</a></h2>", m=result.get("missing", []))

    # Pull the SMS bubbles from i18n exactly as the candidate would see them
    import i18n
    lang = result["language"]
    name = result["candidate"]["full_name"]
    msgs = [
        i18n.t(lang, "thanks_received", name=name),
        i18n.t(lang, "profile_summary",
               name=name, occ=result["profile"]["occupations"][0]["label"],
               isco=result["profile"]["occupations"][0]["isco"],
               isced_label=result["profile"]["isced_label"],
               why=result["profile"]["occupations"][0]["explanation"]),
        i18n.t(lang, "not_in_registry", name=name,
               registry=result.get("registry_name", "National Disability Registry")),
    ]
    s = result["econ"]["signals"]
    econ_sms = i18n.t(
        lang, "econ_summary",
        wage_label=s[0]["label"] if s else "",
        wage_val=s[0]["value"] if s else "",
        growth_label=s[1]["label"] if len(s) > 1 else "—",
        growth_val=s[1]["value"] if len(s) > 1 else "—",
        ret_label=s[2]["label"] if len(s) > 2 else "—",
        ret_val=s[2]["value"] if len(s) > 2 else "—")

    risk_sms = ""
    if result["risk"]["occupations"]:
        r = result["risk"]["occupations"][0]
        risk_sms = i18n.t(
            lang, "risk_summary",
            occ=r["label"],
            risk_pct=int(r["automation_risk_lmic"] * 100),
            band=r["risk_band"],
            durable=", ".join(result["risk"]["durable_skills"][:3]),
            adjacent=", ".join(o["label"] for o in r["adjacent_occupations"][:3]) or "—")

    job_lines = "\n".join(
        "- {t} @ {c} ({l}) [{p}%]".format(
            t=a["job"]["title"], c=a["job"]["company"],
            l=a["job"]["location"],
            p=a.get("score_pct", int(round(min(a["score"], 1.0) * 100))))
        for a in result.get("applied", []))
    jobs_sms = i18n.t(lang, "applied_confirmation",
                      name=name, count=len(result.get("applied", [])),
                      jobs=job_lines)

    # Surface the registry email if one was queued for this candidate
    import config, json
    email_event = None
    if not result["registered"]:
        for p in sorted(config.OUTBOX_DIR.glob("email_*.json"))[-3:]:
            try:
                ev = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if name in ev.get("subject", ""):
                email_event = ev
                break

    return render_template_string(
        _RESULT, result=result, messages=msgs,
        econ_sms=econ_sms, risk_sms=risk_sms, jobs_sms=jobs_sms,
        email_event=email_event)
