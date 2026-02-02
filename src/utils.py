from __future__ import annotations
import re
from datetime import datetime, timezone
from dateutil import parser as dtparser
import requests
from bs4 import BeautifulSoup

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def parse_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = dtparser.parse(value)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None

def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text

def fetch_article_text(url: str, timeout: int = 20) -> str | None:
    """
    Best-effort extraction. If paywalled/blocked, returns None.
    """
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove scripts/styles/nav/footers
        for tag in soup(["script","style","nav","footer","aside","form"]):
            tag.decompose()

        # Prefer <article>
        article = soup.find("article")
        text = article.get_text(" ", strip=True) if article else soup.get_text(" ", strip=True)
        text = clean_text(text)

        # Guard: avoid gigantic or tiny junk
        if len(text) < 400:
            return None
        if len(text) > 20000:
            text = text[:20000]
        return text
    except Exception:
        return None
