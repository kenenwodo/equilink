"""Flask webhook receiver for inbound SMS + policymaker dashboard.

Africa's Talking sends application/x-www-form-urlencoded with `from` and `text`.
Twilio sends `From` and `Body`. We accept both.
"""
import logging

from flask import Flask, request, jsonify

import candidate
import dashboard
import pipeline

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = Flask(__name__)
app.register_blueprint(candidate.bp)
app.register_blueprint(dashboard.bp)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"service": "EquiLink", "status": "ok",
                    "candidate_app": "/", "dashboard": "/dashboard/?country=ng"})


@app.route("/sms/inbound", methods=["POST"])
def inbound():
    phone = (request.form.get("from") or request.form.get("From")
             or (request.json or {}).get("phone", ""))
    body = (request.form.get("text") or request.form.get("Body")
            or (request.json or {}).get("body", ""))
    if not phone or not body:
        return jsonify({"error": "missing 'from'/'text' or 'From'/'Body'"}), 400

    result = pipeline.process_sms(phone, body)
    # Strip PII from the JSON response so webhook logs stay clean
    safe = {"status": result.get("status"), "language": result.get("language"),
            "registered": result.get("registered"),
            "applied_count": len(result.get("applied", []))}
    return jsonify(safe), 200


if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 6034)), debug=False)
