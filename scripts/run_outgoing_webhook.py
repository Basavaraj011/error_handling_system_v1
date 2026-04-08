# scripts/run_outgoing_webhook.py
import os
import sys
import hmac
import base64
import hashlib
import json
import logging
import re
from collections import defaultdict, deque
import html as html_lib
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, abort
from dotenv import load_dotenv

# Load .env early
load_dotenv()

# Import your ChatBot class (adjust this import if your class lives elsewhere)
from src.plugins.chatbot.bot import ChatBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("teams_outgoing_webhook")

# ── Configuration ──────────────────────────────────────────────────────────────
TEAMS_OUTGOING_HMAC_SECRET = os.getenv("TEAMS_OUTGOING_HMAC_SECRET", "")
PORT = int(os.getenv("PORT", "3978"))

# One ChatBot instance
bot = ChatBot()

# In‑memory, per-conversation rolling history (last 5 exchanges)
HISTORY = defaultdict(lambda: deque(maxlen=5))

app = Flask(__name__)


# ── Security: HMAC verification ────────────────────────────────────────────────
def verify_hmac(raw_body: bytes, auth_header: str) -> bool:
    """
    Teams sends: Authorization: HMAC <base64signature>
    signature = base64( HMACSHA256( raw_body, base64Decode(sharedSecret) ) )
    """
    if not auth_header or not auth_header.startswith("HMAC "):
        logger.error("Missing or invalid Authorization header")
        return False

    provided_sig_b64 = auth_header.split(" ", 1)[1].strip()
    if not TEAMS_OUTGOING_HMAC_SECRET:
        logger.error("TEAMS_OUTGOING_HMAC_SECRET not set")
        return False

    try:
        secret_bin = base64.b64decode(TEAMS_OUTGOING_HMAC_SECRET)
    except Exception:
        logger.exception("Failed to base64-decode webhook secret")
        return False

    mac = hmac.new(secret_bin, raw_body, hashlib.sha256).digest()
    expected_sig_b64 = base64.b64encode(mac).decode("utf-8")

    # constant-time compare
    return hmac.compare_digest(provided_sig_b64, expected_sig_b64)


# ── Helper ─────────────────────────────────────────────────────────────────────
def strip_teams_mention(text: str) -> str:
    """
    Removes a leading @BotName mention (if present) and trims whitespace.
    (HTML <at> tags are handled in extract_text_from_payload.)
    """
    if not text:
        return ""
    t = text.strip()
    if t.startswith("@"):
        parts = t.split(" ", 1)
        t = parts[1].strip() if len(parts) == 2 else ""
    return t


def extract_text_from_payload(payload: dict) -> str:
    """
    Robustly extract text from a Teams Outgoing Webhook payload.
    Priority:
      1) payload['text'] (if present and non-empty)
      2) payload['summary']
      3) payload['value']['text']
      4) First HTML attachment: attachments[0]['content'] (contentType 'text/html')
    Then: HTML-unescape, remove mention <span>, strip tags, collapse whitespace.
    """
    if not isinstance(payload, dict):
        return ""

    txt = payload.get("text")

    if isinstance(txt, str) and txt.strip():
        # Clean HTML inside "text"
        html = html_lib.unescape(txt)
        soup = BeautifulSoup(html, "html.parser")

        for mention in soup.find_all("at"):
            mention.decompose()

        text_only = soup.get_text(" ", strip=True)
        text_only = " ".join(text_only.split())

        print("CLEANED TEXT:", text_only, flush=True)
        return text_only

    sm = payload.get("summary")
    if isinstance(sm, str) and sm.strip():
        return sm.strip()

    val = payload.get("value")
    if isinstance(val, dict):
        vt = val.get("text")
        if isinstance(vt, str) and vt.strip():
            return vt.strip()

    atts = payload.get("attachments")
    if isinstance(atts, list) and atts:
        att = atts[0] or {}
        ctype = att.get("contentType")
        content = att.get("content")
        if (ctype and "text/html" in ctype.lower()) and isinstance(content, str) and content.strip():
            html = html_lib.unescape(content)

            # Use BeautifulSoup to strip ALL HTML cleanly
            soup = BeautifulSoup(html, "html.parser")

            # Remove <at> mention tags cleanly
            for mention in soup.find_all("at"):
                mention.decompose()

            # Extract plain text
            text_only = soup.get_text(" ", strip=True)

            # Normalize excessive whitespace
            text_only = " ".join(text_only.split())

            print("CLEANED TEXT:", text_only, flush=True)

            return text_only

    return ""


# ── Mapper: ChatBot → Teams response ───────────────────────────────────────────
def to_teams_response(result: dict) -> dict:
    """
    Supports:
      - {"type":"text","content":"..."}
      - {"type":"card","content":{...}}
      - {"type":"composite","explanation":"...", "card":{...}}
      - {"type":"composite","explanation":"...", "cards":[{...},{...}], "sql":"..."}
    """
    if not isinstance(result, dict):
        return {"type": "message", "text": "Unexpected bot result."}

    rtype = result.get("type")

    if rtype == "composite":
        explanation = result.get("explanation", "")
        resp = {"type": "message", "text": explanation}
        attachments = []

        if isinstance(result.get("cards"), list):
            for c in result["cards"]:
                if isinstance(c, dict):
                    attachments.append({
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": c
                    })
        elif isinstance(result.get("card"), dict):
            attachments.append({
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": result["card"]
            })

        # Optional inline SQL block; if present we add as a simple Adaptive Card too
        sql_text = result.get("sql")

        print("SQL from bot: ", sql_text)

        if isinstance(sql_text, str) and sql_text.strip():
            attachments.append({
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": "SQL executed", "weight": "Bolder"},
                        {"type": "TextBlock", "wrap": True, "fontType": "Monospace", "text": sql_text}
                    ]
                }
            })

        if attachments:
            resp["attachments"] = attachments
        return resp

    if rtype == "text":
        return {"type": "message", "text": str(result.get("content") or "")}

    if rtype == "card" and isinstance(result.get("content"), dict):
        return {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": result["content"]
            }]
        }
    
    return {
        "type": "message",
        "text": bot.query_executor.GUIDANCE_MESSAGE
    }



# ── Healthcheck ────────────────────────────────────────────────────────────────
@app.get("/healthz")
def health():
    return "ok", 200


# ── Webhook endpoint ───────────────────────────────────────────────────────────
@app.post("/teams/outgoing")
def teams_outgoing():
    raw_body = request.get_data()
    auth_header = request.headers.get("Authorization", "")
    if not verify_hmac(raw_body, auth_header):
        print("❌ HMAC FAILED")
        print("AUTH HEADER:", repr(auth_header))
        print("RAW BODY LEN:", len(raw_body))
        abort(401)

    payload = json.loads(raw_body.decode("utf-8"))
    raw_text = extract_text_from_payload(payload)
    user_text = strip_teams_mention(raw_text or "")

    print("========== TEAMS DEBUG ==========")
    print("RAW FROM TEAMS:", repr(raw_text))
    print("AFTER STRIP  :", repr(user_text))
    print("NORMALIZED   :", repr(user_text.lower().replace('_', ' ')))
    print("==================================")

    try:
        # Use a conversation key to track last 5 turns
        conv_id = ((payload.get("conversation") or {}).get("id")
                   or (payload.get("from") or {}).get("id")
                   or "default")

        prev = list(HISTORY[conv_id])
        if prev:
            ctx = "\n\n[Context: last 5 messages]\n" + "\n".join(
                f"User: {p['user']}\nBot: {p['bot']}" for p in prev
            )
        else:
            ctx = ""

        user_text_with_ctx = (user_text or "") + ctx

        # Call bot
        result = bot.process_message(user_text_with_ctx)
        resp = to_teams_response(result)

        # Store the last turn
        bot_text = ""
        if isinstance(result, dict):
            if result.get("type") == "composite":
                bot_text = (result.get("explanation") or "")[:800]
            elif result.get("type") in ("text", "card"):
                bot_text = str(result.get("content") or "")[:800]

        HISTORY[conv_id].append({"user": user_text, "bot": bot_text})

    except Exception:
        logger.exception("Error processing message")
        resp = {"type": "message", "text": "Sorry, something went wrong."}

    return jsonify(resp), 200


if __name__ == "__main__":
    logger.info(f"Starting Teams Outgoing Webhook on :{PORT} (POST /teams/outgoing)")
    app.run(host="0.0.0.0", port=PORT, debug=False)