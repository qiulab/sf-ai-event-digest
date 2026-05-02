# 🤖 SF AI Event Digest

A daily-curated digest of the top AI & tech events in San Francisco — automatically scraped, scored, and emailed.

**🔗 Live signup form:** https://qiulab.github.io/sf-ai-event-digest/

## What it does

Every morning at 8am Pacific, the pipeline:

1. **Scrapes** upcoming events from `lu.ma/sf`, `lu.ma/ai-sf`, and `cerebralvalley.ai`
2. **Scores** each event 1-10 using **Gemini 2.5 Flash** (free tier), weighted heavily by host reputation — Anthropic, OpenAI, Cursor, Vercel, a16z, Y Combinator, and 30+ other top AI labs/tools/VCs all get bonus points
3. **Tags** events across 10 interest categories (AI/ML · AI Research · Product · Design · Engineering · Founders · Investing · Career/hiring · Policy/safety · Women in Tech)
4. **Filters** to top 7 events (score ≥ 7), sorted by reputation × score
5. **Emails** a beautiful HTML digest to all subscribers via Gmail

The signup form is **fully self-contained** — visitors get personalized top 3 events instantly when they subscribe, no backend round-trip needed.

## Architecture

| Layer | Tech |
|-------|------|
| Frontend | Single-file static HTML (`index.html`) |
| Pipeline | Python (`sf_ai_digest.py`) — runs on a daily schedule |
| LLM scoring | Google Gemini 2.5 Flash (free tier) → Claude → keyword fallback |
| Subscriber list | Google Sheets |
| Email delivery | Gmail |
| Scrape cache | 6-hour TTL, persists in `.workspace/` |
| Hosting | GitHub Pages (free) |

## Optimizations

- **6-hour scrape cache** — 312× faster on cache hits, prevents re-scraping the same data
- **Enrichment capped at 15 events** — only fetches descriptions for top candidates
- **3-tier scoring fallback** — Gemini → Claude → free keyword scorer (never breaks)
- **Parallel scraping** — all 3 sources fetched concurrently

## Local preview

Just open `index.html` in any browser — no build step needed.

## Sources

- [`lu.ma/sf`](https://lu.ma/sf) — General San Francisco events
- [`lu.ma/ai-sf`](https://lu.ma/ai-sf) — AI Events SF (curated by Superscout)
- [`cerebralvalley.ai`](https://cerebralvalley.ai/events) — via their public API

---

Built with [Ready Dash](https://gumloop.com) on Gumloop.
