from __future__ import annotations
import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENAI_API_KEY")  # keep name for compatibility
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

APP_URL = "https://github.com/frazanolo/Newsletter"
APP_NAME = "All-in-One Daily Finance Brief"

def llm_json(model: str, system: str, user: str) -> dict:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENAI_API_KEY (OpenRouter key) is missing")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": APP_URL,   # REQUIRED by OpenRouter
        "X-Title": APP_NAME        # REQUIRED by OpenRouter
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "temperature": 0.2,
        "max_tokens": 300
    }

    resp = requests.post(
        OPENROUTER_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=90
    )

    if resp.status_code != 200:
        raise RuntimeError(
            f"OpenRouter API error {resp.status_code}: {resp.text}"
        )

    data = resp.json()

    # OpenAI-compatible response format
    text = data["choices"][0]["message"]["content"].strip()

    # Strict JSON handling
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
        if not match:
            raise ValueError(
                f"Model did not return JSON. Output:\n{text[:1200]}"
            )
        return json.loads(match.group(1))
