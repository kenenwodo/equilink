"""SMS + email senders. In DEMO_MODE, messages are written to data/outbox/ instead."""
import json
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import config


def _outbox_write(kind, payload):
    config.OUTBOX_DIR.mkdir(exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    path = config.OUTBOX_DIR / "{}_{}.json".format(kind, ts)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


# --------------------------------------------------------------------- SMS
def send_sms(to_phone, body):
    payload = {"to": to_phone, "body": body, "provider": config.SMS_PROVIDER,
               "demo_mode": config.DEMO_MODE, "timestamp": datetime.utcnow().isoformat() + "Z"}

    if config.DEMO_MODE or config.SMS_PROVIDER == "none":
        path = _outbox_write("sms", payload)
        print("[SMS-DEMO] -> {}  (saved {})".format(to_phone, path.name))
        print("           " + body.replace("\n", "\n           "))
        return {"status": "queued-demo", "outbox": str(path)}

    if config.SMS_PROVIDER == "africastalking":
        import africastalking
        africastalking.initialize(config.AT_USERNAME, config.AT_API_KEY)
        sms = africastalking.SMS
        kwargs = {"message": body, "recipients": [to_phone]}
        if config.AT_SENDER_ID:
            kwargs["sender_id"] = config.AT_SENDER_ID
        resp = sms.send(**kwargs)
        return {"status": "sent", "provider_response": resp}

    if config.SMS_PROVIDER == "twilio":
        from twilio.rest import Client
        client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(body=body, from_=config.TWILIO_FROM_NUMBER, to=to_phone)
        return {"status": "sent", "sid": msg.sid}

    raise RuntimeError("Unknown SMS_PROVIDER: " + config.SMS_PROVIDER)


# --------------------------------------------------------------------- Email
def send_email(to_email, subject, body, reply_to=None):
    payload = {"to": to_email, "subject": subject, "body": body,
               "reply_to": reply_to, "demo_mode": config.DEMO_MODE,
               "timestamp": datetime.utcnow().isoformat() + "Z"}

    if config.DEMO_MODE or not config.SMTP_USER:
        path = _outbox_write("email", payload)
        print("[EMAIL-DEMO] -> {}  subject='{}'  (saved {})".format(to_email, subject, path.name))
        return {"status": "queued-demo", "outbox": str(path)}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
        s.starttls()
        s.login(config.SMTP_USER, config.SMTP_PASSWORD)
        s.sendmail(config.SMTP_FROM, [to_email], msg.as_string())
    return {"status": "sent"}
