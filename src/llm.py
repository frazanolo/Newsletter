from __future__ import annotations
import os
import json
from openai import OpenAI

def get_client() -> OpenAI:
    return OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def llm_json(model: str, system: str, user: str) -> dict:
    """
    Returns parsed JSON. Raises if invalid.
    """
    client = get_client()
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    text = resp.output_text
    return json.loads(text)
