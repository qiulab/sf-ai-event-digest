# 🤖 SF AI Event Digest

A daily-curated digest of the top AI & tech events in San Francisco.

**🔗 Live:** https://qiulab.github.io/sf-ai-event-digest/

## What it does

- Scrapes upcoming AI events from `lu.ma/sf`, `lu.ma/ai-sf`, and `cerebralvalley.ai`
- Scores each event 1-10, weighted heavily by **host reputation** (Anthropic, OpenAI, Cursor, Vercel, a16z, Y Combinator, etc.)
- Tags events across 10 interest categories (AI/ML, AI Research, Product, Design, Engineering, Founders, Investing, Career/hiring, Policy/safety, Women in Tech)
- Lets visitors subscribe and **instantly see** their top 3 personalized events
- Sends a daily HTML email digest at 8am Pacific to all subscribers

## How it works

| Layer | Tech |
|-------|------|
| Frontend | Single-file static HTML (this file) — runs anywhere |
| Scraping & scoring | Python pipeline running on a daily schedule |
| Subscriber list | Google Sheets |
| Email delivery | Gmail |

The form is fully self-contained with embedded events JSON, refreshed daily by the pipeline.

## Local preview

Just open `index.html` in any browser — no build step needed.

---

Built with [Ready Dash](https://gumloop.com) on Gumloop.
