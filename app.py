import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="static")

# Saytingiz manzillari (iframe va to'g'ridan-to'g'ri so'rovlar uchun)
ALLOWED_SITES = ["https://abdulxay.xo.je", "http://abdulxay.xo.je"]
CORS(app, origins=ALLOWED_SITES)

API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
API_URL = "https://api.mistral.ai/v1/chat/completions"

SYSTEM_PROMPT = (
    "Sen cheksiz.AI nomli yordamchisan. Foydalanuvchi qaysi tilda yozsa, "
    "shu tilda (asosan o'zbek tilida) aniq, qisqa va foydali javob ber."
)


@app.after_request
def allow_embedding(resp):
    # abdulxay.xo.je saytida iframe ichida ochilishiga ruxsat
    resp.headers["Content-Security-Policy"] = (
        "frame-ancestors 'self' https://abdulxay.xo.je http://abdulxay.xo.je"
    )
    resp.headers.pop("X-Frame-Options", None)
    return resp


@app.route("/")
def index():
    return send_from_directory("static", "index.htm")


@app.route("/health")
def health():
    return "ok", 200


@app.route("/chat", methods=["POST"])
def chat():
    if not API_KEY:
        return jsonify(error="Serverda MISTRAL_API_KEY o'rnatilmagan"), 500

    data = request.get_json(silent=True) or {}
    history = data.get("messages", [])

    clean = []
    for m in history[-20:]:
        role = m.get("role")
        content = str(m.get("content", ""))[:4000]
        if role in ("user", "assistant") and content.strip():
            clean.append({"role": role, "content": content})

    if not clean or clean[-1]["role"] != "user":
        return jsonify(error="Xabar bo'sh"), 400

    try:
        r = requests.post(
            API_URL,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + clean,
                "temperature": 0.7,
            },
            timeout=60,
        )
        r.raise_for_status()
        reply = r.json()["choices"][0]["message"]["content"]
        return jsonify(reply=reply)
    except requests.exceptions.HTTPError:
        return jsonify(error=f"AI xatosi ({r.status_code})"), 502
    except Exception:
        return jsonify(error="Server bilan bog'lanib bo'lmadi"), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
