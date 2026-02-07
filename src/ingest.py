from __future__ import annotations
import feedparser
from datetime import datetime, timezone, timedelta
from typing import Iterable, Dict, Any
from .utils import now_utc_iso, parse_date_to_iso, clean_text, fetch_article_text
import ssl

# Disable SSL verification for feedparser (some feeds have cert issues)
ssl._create_default_https_context = ssl._create_unverified_context

def ingest_feed(feed_cfg: dict) -> list[dict]:
    d = feedparser.parse(feed_cfg["url"])
    out: list[dict] = []

    for e in d.entries[:60]:
        title = clean_text(getattr(e, "title", "") or "")
        link = getattr(e, "link", None)
        if not title or not link:
            continue

        published = parse_date_to_iso(getattr(e, "published", None) or getattr(e, "updated", None))
        summary = clean_text(getattr(e, "summary", "") or getattr(e, "description", "") or "")

        # Use summary as content (skip slow article fetch for now)
        content = summary

        out.append({
            "source": feed_cfg["name"],
            "category": feed_cfg.get("category", "unknown"),
            "title": title,
            "url": link,
            "published_at": published,
            "content": content,
            "inserted_at": now_utc_iso(),
        })
    return out
