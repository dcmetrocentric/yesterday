#!/usr/bin/env python3
import json, os, re, time
from datetime import datetime, timezone
import requests
import feedparser

# Cities file
CITIES_FILE = "citypacks.json"
OUT_FILE = "citypacks.generated.json"

# Google News RSS query helper
def rss_url(query, hl="en-US", gl="US", ceid="US:en"):
    import urllib.parse
    return ("https://news.google.com/rss/search?q="
            + urllib.parse.quote(query)
            + f"&hl={hl}&gl={gl}&ceid={ceid}")

# Follow redirects to get publisher URL
def resolve_url(url, timeout=15):
    try:
        r = requests.get(url, allow_redirects=True, timeout=timeout, headers={
            "User-Agent":"Mozilla/5.0 (compatible; YesterdayBot/1.0)"
        })
        return r.url
    except Exception:
        return url

# Emoji heuristic
EMOJI_RULES = [
    (re.compile(r"subway|metro|rail|train|airport|flight|transit", re.I), "🚇"),
    (re.compile(r"storm|snow|rain|flood|heat|wildfire|earthquake|hurricane", re.I), "🌧️"),
    (re.compile(r"mayor|council|parliament|congress|government|policy|election", re.I), "🏛️"),
    (re.compile(r"court|judge|trial|lawsuit|legal", re.I), "⚖️"),
    (re.compile(r"music|festival|concert|tour", re.I), "🎶"),
    (re.compile(r"art|museum|exhibit|gallery|theater|theatre|broadway|film", re.I), "🎭"),
    (re.compile(r"soccer|football|nba|nfl|mlb|nhl|win|beat|match|game", re.I), "🏟️"),
    (re.compile(r"restaurant|food|chef|dining", re.I), "🍽️"),
    (re.compile(r"tech|ai|startup|software|chip|cyber", re.I), "💻"),
    (re.compile(r"port|harbor|harbour|ship|cruise", re.I), "⚓️"),
]
def pick_emoji(title):
    for rx, em in EMOJI_RULES:
        if rx.search(title or ""):
            return em
    return "📰"

def clue_from_title(title):
    # Keep "Yesterday..." vibe, no city name included.
    t = title.strip()
    # Avoid quoting the city by removing common patterns like "CityName —"
    t = re.sub(r"^[A-Z][A-Za-z\s\-]+\s+—\s+", "", t)
    starters = [
        "Yesterday, the front page led with: ",
        "Yesterday, everyone was talking about: ",
        "Yesterday, a headline that stood out: ",
        "Yesterday, the biggest buzz was about: ",
    ]
    s = starters[int(time.time()) % len(starters)]
    # Shorten long titles
    if len(t) > 95:
        t = t[:92].rsplit(" ",1)[0] + "…"
    return s + t

def main():
    with open(CITIES_FILE, "r", encoding="utf-8") as f:
        cities = json.load(f)["cities"]

    out_packs=[]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for item in cities:
        city = item["city"]
        # Query is scoped to last ~21 days using Google News' 'when:' operator
        query = f'{city} when:21d'
        feed = feedparser.parse(rss_url(query))
        entries = feed.entries[:8]  # pull a few, then filter
        stories=[]
        for e in entries:
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            if not title or not link:
                continue
            pub_url = resolve_url(link)
            # Skip if still looks like Google News
            if "news.google" in pub_url:
                continue
            source = getattr(e, "source", None)
            src_name = getattr(source, "title", "") if source else ""
            if not src_name:
                # fallback from feedparser fields
                src_name = getattr(e, "publisher", "") or getattr(e, "author", "") or "Source"
            stories.append({
                "headline": title,
                "source": src_name[:40],
                "url": pub_url
            })
            if len(stories) >= 4:
                break

        # If we couldn't resolve 4 direct URLs, allow remaining as RSS link (still works, but not ideal)
        while len(stories) < 4 and len(entries) > len(stories):
            e = entries[len(stories)]
            stories.append({
                "headline": getattr(e,"title","").strip() or "Headline",
                "source": "Google News",
                "url": getattr(e,"link","").strip()
            })

        cards=[{
            "emoji": pick_emoji(s["headline"]),
            "clue": clue_from_title(s["headline"])
        } for s in stories[:4]]

        out_packs.append({
            "city": city,
            # lat/lng can remain in embedded fallback; distance will still work if embedded packs exist.
            "cards": cards,
            "stories": stories[:4]
        })

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"generated_at": now, "packs": out_packs}, f, ensure_ascii=False, indent=2)

    print(f"Wrote {OUT_FILE} with {len(out_packs)} packs")

if __name__ == "__main__":
    main()
