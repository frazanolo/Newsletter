from __future__ import annotations
import os, json, re
from openai import OpenAI

def get_client() -> OpenAI:
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def llm_json(model: str, system: str, user: str) -> dict:
    client = get_client()
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    text = (resp.output_text or "").strip()

    # 1) Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2) Fallback: extract first JSON object/array
    m = re.search(r"(\{.*\}|\[.*\])", text, flags=re.S)
    if not m:
        raise ValueError(f"LLM did not return JSON. Output (truncated):\n{text[:1200]}")
    return json.loads(m.group(1))
