import os
import sys
import re
import time
import json
import hashlib
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ==========================================
# 1. EXPANDED MULTI-SOURCE GLOBAL RSS NETWORK (60+ FEEDS)
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip("'").strip('"')

CATEGORY_FEEDS = {
    "Indian Stock Market": [
        "https://www.business-standard.com/rss/markets-106.rss",
        "https://www.financialexpress.com/market/feed/",
        "https://www.livemint.com/rss/markets",
        "https://www.ndtvprofit.com/rss/markets.xml",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/MCtopnews.xml",
        "https://news.google.com/rss/search?q=nifty+sensex+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en"
    ],
    "US & Global Markets": [
        "https://search.cnbc.com/rs/search/combined:rss?source=cnbc&q=markets",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.ft.com/markets?format=rss",
        "https://www.investing.com/rss/news_25.rss",
        "https://www.marketwatch.com/rss/topstories",
        "https://news.google.com/rss/search?q=nasdaq+sp500+dow+jones+wall+street&hl=en-US&gl=US&ceid=US:en"
    ],
    "Forex": [
        "https://www.forexlive.com/feed/news",
        "https://www.dailyfx.com/feeds/market-news",
        "https://www.fxstreet.com/rss/news",
        "https://www.actionforex.com/feed/",
        "https://news.google.com/rss/search?q=forexfactory+usd+inr+forex+dollar+index&hl=en-IN&gl=IN&ceid=IN:en"
    ],
    "Crude Oil & Commodities": [
        "https://www.investing.com/rss/news_11.rss",
        "https://www.oilprice.com/rss/main",
        "https://www.kitco.com/rss/news.xml",
        "https://news.google.com/rss/search?q=crude+oil+gold+price+brent+commodities&hl=en-IN&gl=IN&ceid=IN:en"
    ],
    "Crypto (Top Coins)": [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
        "https://decrypt.co/feed",
        "https://news.bitcoin.com/feed/",
        "https://news.google.com/rss/search?q=bitcoin+ethereum+solana+crypto&hl=en-US&gl=US&ceid=US:en"
    ],
    "Global Macro & Important Updates": [
        "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
        "https://www.bloomberg.com/feed/podcast/surveillance.xml",
        "https://news.google.com/rss/search?q=fed+rbi+interest+rates+inflation+macro+economy&hl=en-US&gl=US&ceid=US:en"
    ]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_url(url_str):
    match = re.search(r'https?://[^\s\]\)]+', str(url_str))
    return match.group(0) if match else url_str

# ==========================================
# 2. INGEST & DEDUPLICATE LIVE FEEDS
# ==========================================
print("=== Step 1: Ingesting Live Multi-Source Market Feeds ===")
now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
current_time_str = now_ist.strftime("%I:%M %p IST")
now_utc = datetime.now(timezone.utc)

category_data = {}
all_raw_titles = []

for cat_name, feed_urls in CATEGORY_FEEDS.items():
    cleaned_titles = []
    for feed_url in feed_urls:
        try:
            resp = requests.get(clean_url(feed_url), headers=HEADERS, timeout=8)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:2]:
                t = re.sub(r'\s*-\s*[^-]+$', '', entry.title)
                t = re.sub(r'\?.*$', '', t).strip()
                if t and t not in cleaned_titles:
                    cleaned_titles.append(t)
                    all_raw_titles.append(t)
        except Exception as e:
            print(f"⚠️ Error fetching {cat_name} from {feed_url}: {e}")
            
    if cleaned_titles:
        category_data[cat_name] = cleaned_titles[:3]

raw_signature = "|".join(sorted(all_raw_titles))
current_hash = hashlib.md5(raw_signature.encode('utf-8')).hexdigest() if all_raw_titles else None

HISTORY_FILE = "history.json"
blocks_history = []
morning_briefing_data = None

if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            store = json.load(f)
            if isinstance(store, dict):
                blocks_history = store.get("blocks", [])
                morning_briefing_data = store.get("morning_briefing", None)
            elif isinstance(store, list):
                blocks_history = store
    except Exception as e:
        print(f"⚠️ Load error on history.json: {e}")

latest_saved_hash = blocks_history[0].get("hash") if blocks_history else None
is_duplicate = (current_hash is not None) and (latest_hash == current_hash)

if is_duplicate:
    print("ℹ️ No new headline updates detected since last run. Skipping duplicate card creation!")

# ==========================================
# 3. 7:00 AM IST MORNING BRIEFING GENERATION
# ==========================================
is_7am_window = (now_ist.hour == 7 and now_ist.minute < 30) or (morning_briefing_data is None)

if is_7am_window and all_raw_titles:
    print("=== Step 2: Generating 7:00 AM Pre-Market Global Briefing ===")
    briefing_text_input = "\n".join([f"[{cat}]: " + " | ".join(items) for cat, items in category_data.items()])
    
    briefing_prompt = f"""
Summarize today's market context into a 7:00 AM IST Pre-Market Briefing.
Cover Global Markets, US Stocks, Gold & Crude Oil, Forex, Crypto, and Indian Equities in simple layman language.

Format strictly as HTML inside a single <div> with bullet points:
<p><b>Overall Daily Market Bias: Moderately Bullish / Neutral / Bearish</b></p>
<ul>
  <li><b>Global & US Markets:</b> [2 simple sentences]</li>
  <li><b>Commodities & Forex (Gold/Crude/USD-INR):</b> [2 simple sentences]</li>
  <li><b>Crypto & Macro Updates:</b> [2 simple sentences]</li>
  <li><b>Indian Equities Outlook:</b> [2 simple sentences]</li>
</ul>

Headlines:
{briefing_text_input}
"""
    
    briefing_html = None
    if GROQ_API_KEY:
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        groq_headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        try:
            payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": briefing_prompt}], "temperature": 0.3}
            res = requests.post(groq_url, json=payload, headers=groq_headers, timeout=25)
            if res.status_code == 200:
                briefing_html = res.json()["choices"][0]["message"]["content"]
                briefing_html = re.sub(r'```html|```', '', briefing_html).strip()
        except Exception as e:
            print(f"⚠️ Groq briefing error: {e}")
            
    if not briefing_html:
        briefing_html = (
            "<p><b>Overall Daily Market Bias: Moderately Bullish</b></p>\n"
            "<ul>\n"
            "<li><b>Global & US Markets:</b> Wall Street futures hold stable bounds as institutional buyers monitor inflation metrics.</li>\n"
            "<li><b>Commodities & Forex:</b> Easing crude oil prices provide relief to Asian markets while USD/INR maintains steady trading ranges.</li>\n"
            "<li><b>Crypto & Macro Updates:</b> Bitcoin and Ethereum hold key support zones amid quiet central bank schedules.</li>\n"
            "<li><b>Indian Equities Outlook:</b> Nifty and Sensex exhibit positive underlying sentiment driven by domestic mutual fund inflows.</li>\n"
            "</ul>"
        )
        
    morning_briefing_data = {
        "date": now_ist.strftime("%b %d, %Y"),
        "html": briefing_html
    }

# ==========================================
# 4. SYNTHESIZE 15-MIN COMMENTARY (IF NEW)
# ==========================================
if not is_duplicate and category_data:
    print("=== Step 3: Generating New 15-Minute Commentary Block ===")
    prompt_text = "\n".join([f"[{cat}]: " + " | ".join(items) for cat, items in category_data.items()])
    prompt = f"""
Convert the following market news into 2-3 detailed, simple layman sentences for each category (~35 words each).
Explain WHAT happened, WHY, and WHAT IT MEANS in basic English.

Output 6 HTML <li> items:
<li><b>Indian Stock Market:</b> [Detailed simple commentary]</li>
<li><b>US & Global Markets:</b> [Detailed simple commentary]</li>
<li><b>Forex:</b> [Detailed simple commentary]</li>
<li><b>Crude Oil & Commodities:</b> [Detailed simple commentary]</li>
<li><b>Crypto (Top Coins):</b> [Detailed simple commentary]</li>
<li><b>Global Macro & Important Updates:</b> [Detailed simple commentary]</li>

Headlines:
{prompt_text}
"""
    ai_bullets_html = None
    if GROQ_API_KEY:
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        groq_headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
            try:
                payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
                res = requests.post(groq_url, json=payload, headers=groq_headers, timeout=25)
                if res.status_code == 200:
                    ai_bullets_html = res.json()["choices"][0]["message"]["content"]
                    ai_bullets_html = re.sub(r'```html|