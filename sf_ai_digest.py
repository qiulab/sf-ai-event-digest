"""
SF AI Event Digest Pipeline
Scrapes lu.ma/sf, lu.ma/ai-sf, and cerebralvalley.ai, scores events
(Gemini → Claude → keyword fallback), filters top events, and emails
them to all subscribers.

Optimizations:
- 6-hour scrape cache (skip refetch if recent)
- Cap description enrichment at 15 events
- Free Gemini for LLM scoring (15 req/min, 1500/day free tier)
"""

import os, json, re, time, hashlib, logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from gumcp_client import Client
import requests
import pytz

# Optional LLM clients — only loaded if their API keys are set
try:
    import google.generativeai as genai
except ImportError:
    genai = None
try:
    import anthropic
except ImportError:
    anthropic = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────────────────────
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1qVVEYTHxhRltcTb3N3T8FSgjS04wkaPT0hao4nM0jjM/edit'
LUMA_SOURCES = ['sf', 'ai-sf']
CEREBRAL_VALLEY_ENABLED = True
MIN_SCORE = 7
MAX_EVENTS = 7
MAX_ENRICHMENT = 15  # ⚡ cost optimization: only fetch descriptions for top 15

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# Fallback: load from persistent secrets file in workspace
SECRETS_PATH = '/home/user/.workspace/secrets.json'
if (not GEMINI_API_KEY or not ANTHROPIC_API_KEY) and os.path.exists(SECRETS_PATH):
    try:
        with open(SECRETS_PATH, 'r') as _f:
            _secrets = json.load(_f)
        GEMINI_API_KEY = GEMINI_API_KEY or _secrets.get('GEMINI_API_KEY', '')
        ANTHROPIC_API_KEY = ANTHROPIC_API_KEY or _secrets.get('ANTHROPIC_API_KEY', '')
    except Exception:
        pass

# ─── Cache ───────────────────────────────────────────────────────────────────
CACHE_PATH = '/home/user/.workspace/scrape_cache.json'
CACHE_TTL_HOURS = 6

SF_KEYWORDS = ['san francisco', 'sf,', ' sf ', 'bay area', 'oakland', 'berkeley',
               'palo alto', 'mountain view', 'menlo park', 'sunnyvale', 'redwood city',
               'south san francisco', 'silicon valley', 'soma', 'mission district']

HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}


# ─── Step 1: Scrape Events ───────────────────────────────────────────────────

def extract_events_from_luma_page(slug: str) -> list[dict]:
    """Scrape all event objects from a Luma calendar page."""
    log.info(f"Scraping lu.ma/{slug}...")
    r = requests.get(f'https://lu.ma/{slug}', headers=HTTP_HEADERS, timeout=20)
    r.raise_for_status()

    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if not match:
        log.warning(f"No __NEXT_DATA__ found for lu.ma/{slug}")
        return []

    data = json.loads(match.group(1))
    events = []
    seen_ids = set()

    def walk(obj, depth=0):
        if depth > 15:
            return
        if isinstance(obj, dict):
            if 'event' in obj and isinstance(obj['event'], dict):
                ev = obj['event']
                if 'name' in ev and 'start_at' in ev and ev.get('api_id') not in seen_ids:
                    seen_ids.add(ev.get('api_id'))
                    events.append(ev)
            for v in obj.values():
                walk(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, depth + 1)

    walk(data)
    log.info(f"  → {len(events)} events found on lu.ma/{slug}")
    return events


def get_event_details(event_url: str) -> dict:
    """Fetch description and organizer from an individual event page."""
    try:
        r = requests.get(event_url, headers=HTTP_HEADERS, timeout=10)
        if r.status_code != 200:
            return {}
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if not match:
            return {}
        data = json.loads(match.group(1))

        def find_key(d, key, depth=0):
            if depth > 10:
                return None
            if isinstance(d, dict):
                if key in d:
                    return d[key]
                for v in d.values():
                    result = find_key(v, key, depth + 1)
                    if result is not None:
                        return result
            elif isinstance(d, list):
                for item in d:
                    result = find_key(item, key, depth + 1)
                    if result is not None:
                        return result
            return None

        desc = find_key(data, 'description') or ''
        organizer = (
            find_key(data, 'display_name') or
            find_key(data, 'full_name') or
            find_key(data, 'username') or
            'Unknown'
        )
        return {'description': desc, 'organizer': organizer}
    except Exception as e:
        log.warning(f"Could not fetch {event_url}: {e}")
        return {}


def normalize_event(ev: dict, source: str) -> dict:
    start_at = ev.get('start_at', '')
    try:
        dt = datetime.fromisoformat(start_at.replace('Z', '+00:00'))
        tz = pytz.timezone(ev.get('timezone', 'America/Los_Angeles'))
        dt_local = dt.astimezone(tz)
        date_str = dt_local.strftime('%A, %B %d at %I:%M %p %Z')
        date_epoch = dt.timestamp()
    except Exception:
        date_str = start_at
        date_epoch = 0

    geo = ev.get('geo_address_info', {}) or {}
    location_parts = [geo.get('address', ''), geo.get('city', '')]
    location = ', '.join(p for p in location_parts if p) or 'San Francisco'

    url_slug = ev.get('url', ev.get('api_id', ''))
    url = f"https://lu.ma/{url_slug}" if not url_slug.startswith('http') else url_slug

    return {
        'id': ev.get('api_id', ''),
        'name': ev.get('name', 'Unknown'),
        'date': date_str,
        'date_epoch': date_epoch,
        'organizer': 'Unknown',
        'description': '',
        'url': url,
        'location': location,
        'source': source,
    }


def fetch_cerebral_valley_events() -> list[dict]:
    """Fetch upcoming SF/Bay Area events from Cerebral Valley's public API."""
    log.info("Fetching Cerebral Valley events...")
    all_events = []
    offset = 0
    limit = 50
    start_dt = datetime.now(timezone.utc).strftime('%Y-%m-%dT00:00:00.000Z')
    while True:
        try:
            r = requests.get(
                'https://api.cerebralvalley.ai/v1/public/event/pull',
                params={'approved': 'true', 'startDateTime': start_dt,
                        'limit': limit, 'offset': offset},
                headers={'Accept': 'application/json'}, timeout=15
            )
            if r.status_code != 200:
                break
            events = r.json().get('events', [])
            if not events:
                break
            all_events.extend(events)
            if len(events) < limit:
                break
            offset += limit
            if offset > 500:
                break
        except Exception as e:
            log.warning(f"CV API error at offset {offset}: {e}")
            break

    # Filter to SF/Bay Area + future
    now_utc = datetime.now(timezone.utc)
    sf_events = []
    for ev in all_events:
        location = (ev.get('location', '') or '').lower()
        venue = (ev.get('venue', '') or '').lower()
        if not any(kw in f"{location} {venue}" for kw in SF_KEYWORDS):
            continue
        try:
            dt = datetime.strptime(ev['startDateTime'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            if dt < now_utc - timedelta(hours=1):
                continue
        except Exception:
            continue
        # Normalize to common shape
        try:
            dt_local = dt.astimezone(pytz.timezone('America/Los_Angeles'))
            date_str = dt_local.strftime('%a, %b %d · %I:%M %p %Z')
            date_epoch = dt.timestamp()
        except Exception:
            date_str = ev.get('startDateTime', '')
            date_epoch = 0
        sf_events.append({
            'id': f"cv-{ev.get('id', '')}",
            'name': ev.get('name', 'Unknown'),
            'date': date_str,
            'date_epoch': date_epoch,
            'organizer': ev.get('venue', '') or 'Cerebral Valley',
            'description': ev.get('description', '') or ev.get('descriptionSummary', '') or '',
            'url': ev.get('url', ''),
            'location': ev.get('location', 'San Francisco'),
            'source': 'cerebralvalley.ai',
        })
    log.info(f"  → {len(sf_events)} SF/Bay Area Cerebral Valley events")
    return sf_events



# ─── Cache helpers ───────────────────────────────────────────────────────────

def _load_cache() -> dict | None:
    """Return cached scrape data if it exists and is fresh, else None."""
    try:
        with open(CACHE_PATH, 'r') as f:
            cached = json.load(f)
        cached_at = datetime.fromisoformat(cached['cached_at'])
        if datetime.now(timezone.utc) - cached_at < timedelta(hours=CACHE_TTL_HOURS):
            age_min = int((datetime.now(timezone.utc) - cached_at).total_seconds() / 60)
            log.info(f"✓ Using scrape cache (age: {age_min}m, TTL: {CACHE_TTL_HOURS}h)")
            return cached['events']
        else:
            log.info(f"Cache expired (older than {CACHE_TTL_HOURS}h) — refetching")
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        pass
    return None


def _save_cache(events: list[dict]) -> None:
    """Write scrape results to cache."""
    try:
        with open(CACHE_PATH, 'w') as f:
            json.dump({
                'cached_at': datetime.now(timezone.utc).isoformat(),
                'events': events,
            }, f)
        log.info(f"✓ Saved {len(events)} events to cache")
    except Exception as e:
        log.warning(f"Could not save cache: {e}")


def scrape_all_events(force_refresh: bool = False) -> list[dict]:
    """Scrape Luma sources in parallel + Cerebral Valley API, merge results.

    Uses 6-hour cache to avoid redundant scraping. Pass force_refresh=True to skip cache.
    """
    # Check cache first
    if not force_refresh:
        cached = _load_cache()
        if cached is not None:
            return cached

    raw_by_source = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(extract_events_from_luma_page, slug): slug for slug in LUMA_SOURCES}
        if CEREBRAL_VALLEY_ENABLED:
            futures[pool.submit(fetch_cerebral_valley_events)] = 'cerebralvalley.ai'
        for future in as_completed(futures):
            label = futures[future]
            try:
                raw_by_source[label] = future.result()
            except Exception as e:
                log.error(f"Source {label} failed: {e}")
                raw_by_source[label] = []

    # Normalize and deduplicate (Luma needs normalize, CV is pre-normalized)
    seen = set()
    combined = []
    for slug in LUMA_SOURCES:
        for ev in raw_by_source.get(slug, []):
            normalized = normalize_event(ev, f'lu.ma/{slug}')
            if normalized['id'] not in seen and normalized['name'] not in {e['name'] for e in combined}:
                seen.add(normalized['id'])
                combined.append(normalized)
    if CEREBRAL_VALLEY_ENABLED:
        for ev in raw_by_source.get('cerebralvalley.ai', []):
            # Dedup by name (CV often re-lists Luma events)
            if ev['id'] not in seen and ev['name'] not in {e['name'] for e in combined}:
                seen.add(ev['id'])
                combined.append(ev)

    # Sort by date, keep upcoming only
    now_epoch = datetime.now(timezone.utc).timestamp()
    combined = [e for e in combined if e['date_epoch'] >= now_epoch - 3600]
    combined.sort(key=lambda e: e['date_epoch'])

    # Enrich Luma events with descriptions (CV already has them)
    luma_events = [e for e in combined if e['source'].startswith('lu.ma')][:MAX_ENRICHMENT]
    log.info(f"Enriching top {len(luma_events)} Luma events with details (capped at {MAX_ENRICHMENT})...")

    def enrich(event):
        details = get_event_details(event['url'])
        event['description'] = details.get('description', '')
        event['organizer'] = details.get('organizer', 'Unknown')
        return event

    if luma_events:
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(enrich, luma_events))

    log.info(f"Total events after merge + enrichment: {len(combined)}")
    _save_cache(combined)
    return combined


# ─── Step 2: Score Events with Claude ───────────────────────────────────────

SCORE_PROMPT = """You are curating SF AI/tech events for a general audience interested in the AI ecosystem (builders, founders, PMs, engineers, investors, and curious folks).

Event:
Name: {event_name}
Date: {event_date}
Organizer: {event_organizer}
Description: {event_description}

Score 1-10 weighted heavily by HOST REPUTATION. Top frontier AI labs (Anthropic, OpenAI, Google DeepMind, Mistral, Cohere, xAI), top AI tools (Cursor, Vercel, Hugging Face, Replicate, Together AI, Scale AI, Perplexity), and top VCs (a16z, Sequoia, Founders Fund, Benchmark, Greylock, Y Combinator, Lightspeed, Bessemer) should score 9-10. Generic events with no notable hosts max at 6-7.

Return ONLY valid JSON:
{{
  "score": 8,
  "attend": true,
  "reason": "One general sentence on why this event matters (mention notable hosts if present).",
  "top_hosts": ["Anthropic", "OpenAI"]
}}

Scoring: 9-10 must attend (top hosts/buzzy), 7-8 strong (solid AI community), 5-6 average, 1-4 skip."""


def score_event_with_llm(event: dict, llm_client=None, llm_provider: str = 'gemini') -> dict:
    """Score an event using the configured LLM provider.

    Provider priority: gemini (free) → claude (paid) → keyword fallback.
    """
    prompt = SCORE_PROMPT.format(
        event_name=event['name'],
        event_date=event['date'],
        event_organizer=event.get('organizer', 'Unknown'),
        event_description=(event.get('description') or 'No description available.')[:500],
    )

    raw_text = None
    try:
        if llm_provider == 'gemini' and llm_client is not None:
            import google.generativeai.types as glm
            response = llm_client.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=300,
                    response_mime_type='application/json',
                    response_schema={
                        'type': 'OBJECT',
                        'properties': {
                            'score':  {'type': 'INTEGER'},
                            'attend': {'type': 'BOOLEAN'},
                            'reason': {'type': 'STRING'},
                            'top_hosts': {'type': 'ARRAY', 'items': {'type': 'STRING'}},
                        },
                        'required': ['score', 'attend', 'reason'],
                    }
                ),
            )
            raw_text = response.text.strip()
        elif llm_provider == 'claude' and llm_client is not None:
            msg = llm_client.messages.create(
                model='claude-opus-4-5',
                max_tokens=300,
                messages=[{'role': 'user', 'content': prompt}]
            )
            raw_text = msg.content[0].text.strip()
    except Exception as e:
        log.warning(f"  LLM call failed for '{event['name'][:40]}': {e}")

    if raw_text:
        try:
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                event.update(json.loads(json_match.group()))
                return event
        except Exception:
            pass

    # Fallback to keyword scoring
    event.update(keyword_score_event(event))
    return event


def keyword_score_event(event: dict) -> dict:
    """Free deterministic scorer — used when no LLM key is available."""
    text = (event.get('name', '') + ' ' + event.get('description', '')).lower()
    name_lower = event.get('name', '').lower()

    # Top-host reputation weights
    top_hosts = {
        'anthropic': 3.0, 'openai': 3.0, 'google deepmind': 2.5, 'cursor': 2.5,
        'vercel': 2.5, 'a16z': 3.0, 'andreessen horowitz': 3.0, 'sequoia': 3.0,
        'y combinator': 2.5, 'founders fund': 2.5, 'mistral': 2.0, 'cohere': 2.0,
        'hugging face': 2.0, 'huggingface': 2.0, 'replicate': 2.0, 'together ai': 2.0,
        'scale ai': 2.0, 'perplexity': 2.0, 'nvidia': 2.0, 'databricks': 2.0,
        'figma': 2.0, 'stripe': 2.0, 'notion': 2.0, 'replit': 2.0, 'benchmark': 2.5,
        'greylock': 2.0, 'lightspeed': 2.0, 'bessemer': 2.0, 'index ventures': 2.0,
        'accel': 2.0, 'khosla': 2.0, ' yc ': 2.0, 'aws': 1.5, 'amd': 1.5,
        'github': 1.5, 'workos': 1.5, 'mongodb': 1.5,
    }
    matched_hosts = []
    host_bonus = 0.0
    for host, weight in top_hosts.items():
        if host in text:
            host_bonus += weight
            display = host.strip().title()
            if display not in matched_hosts:
                matched_hosts.append(display)
    host_bonus = min(host_bonus, 4.0)

    ai_kws = ['ai', 'llm', 'machine learning', 'agent', 'gpt', 'claude', 'genai', 'gen ai', 'neural']
    ai_score = min(sum(1 for kw in ai_kws if kw in text) * 0.5, 2.0)
    tech_kws = ['hackathon', 'demo day', 'pitch', 'workshop', 'meetup', 'summit', 'builder', 'founder', 'startup']
    tech_score = min(sum(1 for kw in tech_kws if kw in text) * 0.4, 1.5)
    low_kws = ['hospitality', 'real estate', 'wellness', 'meditation', 'yoga', 'cooking', 'mahjong']
    penalty = sum(1.5 for kw in low_kws if kw in name_lower)

    score = 4.0 + host_bonus + ai_score + tech_score - penalty
    if not any(kw in text for kw in ai_kws):
        score -= 1.5
    score = max(1, min(10, round(score)))

    if matched_hosts:
        host_str = ', '.join(matched_hosts[:2])
        reason = f"Featuring {host_str} — top-tier signal." if score >= 9 else f"Featuring {host_str} — strong AI community presence."
    else:
        reason = "Buzzy AI event with strong builder turnout." if score >= 9 else "Active AI/tech community gathering."

    return {
        'score': score,
        'attend': score >= 7,
        'reason': reason,
        'top_hosts': matched_hosts[:3],
    }


def score_all_events(events: list[dict]) -> list[dict]:
    """Score all events. Tries Gemini (free) → Claude → keyword fallback."""
    # Try Gemini first (free tier: 15 req/min, 1500/day)
    if GEMINI_API_KEY and genai is not None:
        log.info(f"Scoring {len(events)} events with Gemini (free tier)...")
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_client = genai.GenerativeModel('gemini-2.5-flash')
        scored = []
        for i, ev in enumerate(events):
            log.info(f"  [{i+1}/{len(events)}] {ev['name'][:50]}")
            scored.append(score_event_with_llm(ev, gemini_client, 'gemini'))
            time.sleep(0.4)  # 15 req/min = 1 every 4s; 0.4s is safe
        return scored

    # Fallback to Claude if available
    if ANTHROPIC_API_KEY and anthropic is not None:
        log.info(f"Scoring {len(events)} events with Claude...")
        claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        scored = []
        for ev in events:
            scored.append(score_event_with_llm(ev, claude, 'claude'))
            time.sleep(0.3)
        return scored

    # Final fallback: free keyword scoring
    log.info(f"No LLM key set — using free keyword scorer for {len(events)} events")
    for ev in events:
        ev.update(keyword_score_event(ev))
    return events


# ─── Step 3: Filter & Sort ───────────────────────────────────────────────────

def filter_and_sort(events: list[dict]) -> list[dict]:
    eligible = [e for e in events if e.get('score', 0) >= MIN_SCORE]
    eligible.sort(key=lambda e: e.get('score', 0), reverse=True)
    top = eligible[:MAX_EVENTS]
    log.info(f"After filter: {len(eligible)} eligible → keeping top {len(top)}")
    return top


# ─── Step 4: Format Email ────────────────────────────────────────────────────

def format_email_body(events: list[dict], subscriber_name: str) -> tuple[str, str]:
    subject = "Your SF AI Events This Week 🤖"

    lines = [
        f"Hi {subscriber_name},",
        "",
        "Here are this week's top AI events in San Francisco:",
        "",
    ]

    for i, ev in enumerate(events, 1):
        score = ev.get('score', '?')
        attend = "⭐ Must Attend" if score >= 9 else ("✅ Strong Pick" if score >= 7 else "")
        lines.append(f"{i}. {ev['name']} — {ev['date']}  {attend}")
        lines.append(f"   {ev.get('reason', '')}")
        lines.append(f"   Who to meet: {ev.get('networking_angle', '')}")
        lines.append(f"   📍 {ev.get('location', 'San Francisco')}")
        lines.append(f"   🔗 {ev['url']}")
        lines.append("")

    lines += [
        "—",
        "Ready Dash · SF AI Event Digest",
        "Unsubscribe: reply with 'unsubscribe'",
    ]

    return subject, "\n".join(lines)


# ─── Step 5: Send Emails via Gmail ──────────────────────────────────────────

def get_subscribers(gumcp_client) -> list[dict]:
    raw = gumcp_client.call_tool('gsheets__batch-get', {
        'spreadsheet_url': SHEET_URL,
        'ranges': ['subscribers!A:F'],
    })
    result = json.loads(raw[0])
    rows = result.get('valueRanges', [{}])[0].get('values', [])
    if not rows or len(rows) < 2:
        return []

    headers = [h.lower().strip() for h in rows[0]]
    subscribers = []
    for row in rows[1:]:
        if len(row) >= 2 and row[1].strip():
            sub = {}
            for j, h in enumerate(headers):
                sub[h] = row[j] if j < len(row) else ''
            subscribers.append(sub)

    log.info(f"Loaded {len(subscribers)} subscribers")
    return subscribers


def send_digest_to_subscribers(events: list[dict], gumcp_client) -> int:
    subscribers = get_subscribers(gumcp_client)
    if not subscribers:
        log.warning("No subscribers found.")
        return 0

    sent = 0
    for sub in subscribers:
        name = sub.get('name', 'there')
        email = sub.get('email', '').strip()
        if not email:
            continue

        subject, body = format_email_body(events, name)
        try:
            raw = gumcp_client.call_tool('gmail__send_email', {
                'to': email,
                'subject': subject,
                'body': body,
                'body_type': 'plain',
            })
            log.info(f"  Email sent to {email}")
            sent += 1
            time.sleep(0.5)
        except Exception as e:
            log.error(f"  Failed to send to {email}: {e}")

    return sent


# ─── Main Entry Point ────────────────────────────────────────────────────────

def run_digest(single_subscriber_email: str = None):
    """
    Run the full event digest pipeline.
    If single_subscriber_email is provided, only send to that address.
    """
    log.info("=" * 60)
    log.info("SF AI Event Digest — Starting")
    log.info("=" * 60)

    # Step 1: Scrape
    events = scrape_all_events()
    if not events:
        log.error("No events scraped. Aborting.")
        return

    # Step 2: Score
    scored = score_all_events(events)

    # Step 3: Filter
    top_events = filter_and_sort(scored)
    if not top_events:
        log.warning("No events scored above threshold. Aborting.")
        return

    log.info(f"Top {len(top_events)} events selected:")
    for ev in top_events:
        log.info(f"  [{ev.get('score', '?')}] {ev['name']}")

    # Steps 4 & 5: Format and send
    def get_gumcp():
        return Client(
            user_id=os.getenv('GUMCP_USER_ID'),
            gumcp_api_key=os.getenv('GUMCP_ACCESS_TOKEN') or os.getenv('GUMCP_API_KEY'),
            base_url=os.getenv('GUMCP_BASE_URL'),
        )

    with get_gumcp() as gc:
        if single_subscriber_email:
            subject, body = format_email_body(top_events, 'there')
            gc.call_tool('gmail__send_email', {
                'to': single_subscriber_email,
                'subject': subject,
                'body': body,
                'body_type': 'plain',
            })
            log.info(f"Digest sent to {single_subscriber_email}")
        else:
            sent = send_digest_to_subscribers(top_events, gc)
            log.info(f"Digest sent to {sent} subscribers.")

    log.info("SF AI Event Digest — Done ✓")
    return top_events


if __name__ == '__main__':
    run_digest()
