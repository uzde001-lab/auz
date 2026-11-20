import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app, origins=["https://abdulxay.xo.je", "http://abdulxay.xo.je"])


def env(*names):
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return ""


# Modellar nomi o'zgarsa, Render Environment'da GROQ_MODEL va hokazo bilan almashtirasiz
PROVIDERS = {
    "groq": {
        "label": "Groq (Llama)",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": env("GROQ_API_KEY"),
        "model": env("GROQ_MODEL") or "llama-3.3-70b-versatile",
    },
    "gemini": {
        "label": "Gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key": env("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "model": env("GEMINI_MODEL") or "gemini-2.5-flash",
    },
    "openrouter": {
        "label": "OpenRouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": env("OPENROUTER_API_KEY", "OPENROUTER_KEY"),
        "model": env("OPENROUTER_MODEL") or "meta-llama/llama-3.3-70b-instruct:free",
    },
}

SYSTEM_PROMPT = (
    "Sen cheksiz.AI nomli yordamchisan. Foydalanuvchi qaysi tilda yozsa, "
    "shu tilda (asosan o'zbek tilida) aniq va foydali javob ber."
)


@app.after_request
def allow_embedding(resp):
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


@app.route("/providers")
def providers():
    return jsonify([
        {"id": k, "label": v["label"]} for k, v in PROVIDERS.items() if v["key"]
    ])


def ask(name, messages):
    p = PROVIDERS[name]
    r = requests.post(
        p["url"],
        headers={"Authorization": "Bearer " + p["key"], "Content-Type": "application/json"},
        json={
            "model": p["model"],
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "temperature": 0.7,
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    choice = data.get("provider", "auto")

    clean = []
    for m in data.get("messages", [])[-20:]:
        role, content = m.get("role"), str(m.get("content", ""))[:4000]
        if role in ("user", "assistant") and content.strip():
            clean.append({"role": role, "content": content})
    if not clean or clean[-1]["role"] != "user":
        return jsonify(error="Xabar bo'sh"), 400

    available = [k for k, v in PROVIDERS.items() if v["key"]]
    if not available:
        return jsonify(error="Serverda hech qaysi API kalit topilmadi"), 500

    order = [choice] if choice in available else available

    last_err = "Noma'lum xato"
    for name in order:
        try:
            reply = ask(name, clean)
            return jsonify(reply=reply, provider=PROVIDERS[name]["label"])
        except requests.exceptions.HTTPError as e:
            last_err = "%s xatosi (%s)" % (PROVIDERS[name]["label"], e.response.status_code)
        except Exception:
            last_err = "%s bilan bog'lanib bo'lmadi" % PROVIDERS[name]["label"]
    return jsonify(error=last_err), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
