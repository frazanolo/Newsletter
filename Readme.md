# All-in-One Daily Finance Brief (draft generator)

## What it does
- Ingests news from RSS feeds into SQLite
- Clusters + scores using an LLM (only using ingested content)
- Generates a Markdown draft in `drafts/YYYY-MM-DD_draft.md`
- Commits results back to repo via GitHub Actions

## Setup
1) Add `OPENAI_API_KEY` as a GitHub Actions secret
2) Edit `config/sources.yaml` to choose feeds
3) Run locally:
   ```bash
   pip install -r requirements.txt
   export OPENAI_API_KEY="..."
   python -m src.pipeline