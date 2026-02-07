from __future__ import annotations
import json
from .db import connect, fetch_recent, upsert_item
from .ingest import ingest_feed
from .llm import llm_json
from .templates import DAILY_TEMPLATE
import os
from pathlib import Path
import yaml
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

SYSTEM_CLUSTER = """You are a strict news desk editor.
You will ONLY use the items provided. Do not add facts, do not browse.
Your goal: deduplicate and cluster items into themes for a finance/geopolitics daily brief.
Return valid JSON only."""

SYSTEM_DRAFT = """You are writing an English daily finance brief for students/investors.
Rules:
- Use ONLY the provided source items (titles + content + URLs).
- No investment advice, no buy/sell, no price targets.
- No invented numbers. If not present, say 'not specified'.
- Be neutral, concise, high-signal.
Return valid JSON only (schema provided)."""

def run_ingest(db_path: str, sources_cfg: dict, root: Path) -> dict:
    conn = connect(db_path)
    inserted = 0
    total = 0
    for feed in sources_cfg["feeds"]:
        items = ingest_feed(feed)
        total += len(items)
        for it in items:
            if upsert_item(conn, it):
                inserted += 1
    
    # Check threshold AFTER all feeds are processed
    if total < 5:
        today = datetime.now(timezone.utc).date().isoformat()
        out_path = root / "drafts" / f"{today}_draft.md"
        out_path.write_text(
            f"# Daily Brief — {today}\n\n"
            "⚠️ Not enough items ingested to generate a reliable brief today.\n\n"
            f"- Items found: {total}\n"
            "- Action: check RSS sources in config/sources.yaml\n",
            encoding="utf-8"
        )
        print("Not enough items; wrote stub draft and exiting cleanly.")
        return {"total_fetched": total, "inserted": inserted}
    return {"total_fetched": total, "inserted": inserted}

def run_cluster_and_select(items: list[dict], model: str) -> dict:
    # Keep payload small: send only essential fields
    compact = [
        {
            "id": it["id"],
            "category": it["category"],
            "source": it["source"],
            "title": it["title"],
            "url": it["url"],
            "published_at": it["published_at"],
        }
        for it in items
    ]

    user = json.dumps({
        "task": "cluster_and_score",
        "items": compact,
        "scoring": {
            "axes": ["expectation_impact","tail_risk","market_sensitivity"],
            "scale": "0-5 integers"
        },
        "output_schema": {
            "clusters": [
                {
                    "cluster_id": "string",
                    "label": "short theme name",
                    "summary": "2-3 sentences",
                    "item_ids": ["int"],
                    "scores": {
                        "expectation_impact": 0,
                        "tail_risk": 0,
                        "market_sensitivity": 0
                    }
                }
            ]
        },
        "constraints": [
            "Aim for 10-18 clusters max",
            "Deduplicate near-identical stories into one cluster",
            "Prefer clusters with primary sources"
        ]
    }, ensure_ascii=False)

    return llm_json(model=model, system=SYSTEM_CLUSTER, user=user)

def run_draft(items: list[dict], clusters: dict, picks: dict, model: str, date_str: str) -> str:
    # Build selected source pack
    by_id = {it["id"]: it for it in items}

    selected_ids = set(picks["top_story_cluster_ids"])
    selected_clusters = [c for c in clusters["clusters"] if c["cluster_id"] in selected_ids]

    # Expand item_ids to full info for selected clusters + quick hits
    selected_item_ids = set()
    for c in selected_clusters:
        selected_item_ids.update(c["item_ids"])
    selected_item_ids.update(picks.get("quick_hit_item_ids", []))
    selected_item_ids.update(picks.get("crypto_item_ids", []))

    source_pack = []
    for iid in selected_item_ids:
        it = by_id.get(iid)
        if not it:
            continue
        source_pack.append({
            "id": it["id"],
            "category": it["category"],
            "source": it["source"],
            "title": it["title"],
            "url": it["url"],
            "published_at": it["published_at"],
            "content": (it["content"] or "")[:3500]
        })

    user = json.dumps({
        "task": "draft_daily_brief",
        "date": date_str,
        "template_rules": {
            "length_target_words": [900, 1200],
            "top_stories": 3,
            "quick_hits": [6, 10],
            "crypto_items": [2, 3]
        },
        "selected_clusters": selected_clusters,
        "selected_items": source_pack,
        "output_schema": {
            "dashboard": {
                "rates": "string",
                "inflation": "string",
                "energy": "string",
                "fx": "string",
                "risk": "string"
            },
            "stories": [
                {
                    "title": "string",
                    "what_happened": "string",
                    "why_it_matters": "string",
                    "what_to_watch_next": "string",
                    "sources": ["url"]
                }
            ],
            "quick_hits": [{"text":"string","sources":["url"]}],
            "crypto_block": [{"title":"string","body":"string","sources":["url"]}],
            "watchlist": ["string"],
            "all_sources": ["url"]
        }
    }, ensure_ascii=False)

    draft = llm_json(model=model, system=SYSTEM_DRAFT, user=user)

    # Render markdown
    def fmt_sources(urls): 
        return ", ".join(urls)

    stories = draft["stories"][:3]
    quick_hits_md = "\n".join([f"- {q['text']} ({fmt_sources(q['sources'])})" for q in draft["quick_hits"]])
    crypto_md = "\n".join([f"- **{c['title']}** — {c['body']} ({fmt_sources(c['sources'])})" for c in draft["crypto_block"]])
    watch_md = "\n".join([f"- {w}" for w in draft["watchlist"]])
    all_sources_md = "\n".join([f"{i+1}) {u}" for i, u in enumerate(draft["all_sources"])])

    md = DAILY_TEMPLATE.format(
        date=date_str,
        s1_title=stories[0]["title"], s1_what=stories[0]["what_happened"], s1_why=stories[0]["why_it_matters"], s1_watch=stories[0]["what_to_watch_next"], s1_sources=fmt_sources(stories[0]["sources"]),
        s2_title=stories[1]["title"], s2_what=stories[1]["what_happened"], s2_why=stories[1]["why_it_matters"], s2_watch=stories[1]["what_to_watch_next"], s2_sources=fmt_sources(stories[1]["sources"]),
        s3_title=stories[2]["title"], s3_what=stories[2]["what_happened"], s3_why=stories[2]["why_it_matters"], s3_watch=stories[2]["what_to_watch_next"], s3_sources=fmt_sources(stories[2]["sources"]),
        quick_hits=quick_hits_md,
        crypto_block=crypto_md,
        watchlist=watch_md,
        all_sources=all_sources_md
    )
    return md

def default_picks_from_clusters(clusters: dict, items: list[dict]) -> dict:
    # naive default: pick top 3 clusters by max score
    def cluster_priority(c):
        s = c["scores"]
        return max(s["expectation_impact"], s["tail_risk"], s["market_sensitivity"])
    ranked = sorted(clusters["clusters"], key=cluster_priority, reverse=True)
    top3 = [c["cluster_id"] for c in ranked[:3]]

    # quick hits: pick some diverse items not in top clusters
    top_item_ids = set()
    for c in clusters["clusters"]:
        if c["cluster_id"] in top3:
            top_item_ids.update(c["item_ids"])

    remaining = [it for it in items if it["id"] not in top_item_ids]
    quick = [it["id"] for it in remaining[:10]]

    # crypto items: anything tagged crypto/crypto_policy
    crypto = [it["id"] for it in items if it["category"] in ("crypto","crypto_policy")][:3]

    return {
        "top_story_cluster_ids": top3,
        "quick_hit_item_ids": quick[:10],
        "crypto_item_ids": crypto[:3],
    }

def main():
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / "config" / "sources.yaml").read_text(encoding="utf-8"))

    db_path = str(root / "data" / "news.sqlite")
    (root / "drafts").mkdir(exist_ok=True)
    (root / "data").mkdir(exist_ok=True)

    model = os.environ.get("OPENAI_MODEL", "openai/gpt-4-turbo")

    ingest_stats = run_ingest(db_path, cfg, root)

    # pull last ~36h of ingested items (gives evening brief coverage)
    conn = connect(db_path)
    since = (datetime.now(timezone.utc) - timedelta(hours=36)).isoformat()
    items = fetch_recent(conn, since_iso=since)
    
    # Limit to first 10 items to conserve tokens
    items = items[:10]

    # cluster + score
    clusters = run_cluster_and_select(items, model=model)

    # save candidates for transparency
    today = datetime.now(timezone.utc).date().isoformat()
    candidates_path = root / "drafts" / f"{today}_candidates.json"
    candidates_path.write_text(
        json.dumps({"ingest": ingest_stats, "clusters": clusters}, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    # picks file (optional)
    picks_path = root / "drafts" / f"{today}_picks.json"
    if picks_path.exists():
        picks = json.loads(picks_path.read_text(encoding="utf-8"))
    else:
        picks = default_picks_from_clusters(clusters, items)
        picks_path.write_text(json.dumps(picks, indent=2, ensure_ascii=False), encoding="utf-8")

    # draft markdown
    md = run_draft(items, clusters, picks, model=model, date_str=today)
    out_path = root / "drafts" / f"{today}_draft.md"
    out_path.write_text(md, encoding="utf-8")

    print(f"OK: wrote {out_path} and {candidates_path}")

if __name__ == "__main__":
    main()
