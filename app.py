import os, time, hmac
import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder="static")

# Provayderlar tartibi: birinchisi ishlamasa, keyingisiga o'tadi.
# Kaliti .env/Render'da yo'q provayder o'tkazib yuboriladi.
# Model nomlari o'zgarib turadi: kerak bo'lsa *_MODEL o'zgaruvchisi bilan almashtiring.
PROVIDERS = [
    ("Groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY",
     os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")),
    ("Cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY",
     os.getenv("CEREBRAS_MODEL", "gpt-oss-120b")),
    ("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
     os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
    ("Mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY",
     os.getenv("MISTRAL_MODEL", "mistral-small-latest")),
    ("OpenRouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY",
     os.getenv("OPENROUTER_MODEL", "openrouter/free")),
]

COOLDOWN = 60          # limitga tushgan provayder necha soniya o'tkazib yuboriladi
MAX_HISTORY = 30       # modelga yuboriladigan oxirgi xabarlar soni
cooldown_until = {}    # provayder nomi -> vaqt


def authorized():
    pw = os.getenv("ACCESS_PASSWORD", "")
    if not pw:
        return False  # parol qo'yilmagan bo'lsa, hech kimni kiritmaymiz
    given = request.headers.get("X-Password", "")
    return hmac.compare_digest(given.encode(), pw.encode())


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.post("/api/chat")
def chat():
    if not authorized():
        return jsonify(error="Parol noto'g'ri."), 401

    messages = (request.get_json(silent=True) or {}).get("messages", [])
    messages = [m for m in messages if m.get("role") in ("user", "assistant") and m.get("content")]
    messages = messages[-MAX_HISTORY:]
    if not messages:
        return jsonify(error="Xabar bo'sh."), 400

    tried, now = [], time.time()
    for name, base, env_key, model in PROVIDERS:
        key = os.getenv(env_key)
        if not key:
            continue
        if cooldown_until.get(name, 0) > now:
            tried.append(f"{name}: dam olmoqda")
            continue
        try:
            r = requests.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": messages},
                timeout=60,
            )
            if r.status_code == 200:
                text = r.json()["choices"][0]["message"]["content"]
                if text:
                    return jsonify(reply=text, provider=name, model=model)
            if r.status_code in (402, 429) or r.status_code >= 500:
                cooldown_until[name] = time.time() + COOLDOWN
            tried.append(f"{name}: {r.status_code}")
        except Exception as e:
            cooldown_until[name] = time.time() + COOLDOWN
            tried.append(f"{name}: {type(e).__name__}")

    if not tried:
        return jsonify(error="Hech qanday API kalit sozlanmagan."), 500
    return jsonify(error="Hamma provayderlar band: " + "; ".join(tried)), 503


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", 5000)), debug=True)
