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
# 1. EXPANDED INSTANT BREAKING FLASHES & GLOBAL RSS NETWORK
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip("'").strip('"')
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

CATEGORY_FEEDS = {
    "⚡ Breaking Flashes & Geopolitics": [
        # Real-time X/Twitter mirrors for instant squawk & geopolitical flashes
        "https://xcancel.com/financialjuice/rss",
        "https://xcancel.com/DeitaOne/rss",
        "https://xcancel.com/ForexLive/rss",
        "https://xcancel.com/unusual_whales/rss",
        # Google News real-time wire for quotes & breaking headlines
        "https://news.google.com/rss/search?q=breaking+trump+iran+war+fed+rbi+statement+when:1d&hl=en-US&gl=US&ceid=US:en",
        "https://www.forexlive.com/feed/news",
        "https://www.fxstreet.com/rss/news"
    ],
    "Indian Stock Market": [
        "https://news.google.com/rss/search?q=nifty+sensex+stock+market+india+breaking+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.business-standard.com/rss/markets-106.rss",
        "https://www.financialexpress.com/market/feed/",
        "https://www.livemint.com/rss/markets",
        "https://www.ndtvprofit.com/rss/markets.xml",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
    ],
    "US & Global Markets": [
        "https://news.google.com/rss/search?q=wall+street+nasdaq+sp500+dow+jones+breaking+when:1d&hl=en-US&gl=US&ceid=US:en",
        "https://search.cnbc.com/rs/search/combined:rss?source=cnbc&q=markets",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.investing.com/rss/news_25.rss",
        "https://www.marketwatch.com/rss/topstories"
    ],
    "Forex & Commodities": [
        "https://news.google.com/rss/search?q=crude+oil+gold+usd+inr+forex+breaking+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.dailyfx.com/feeds/market-news",
        "https://www.oilprice.com/rss/main",
        "https://www.kitco.com/rss/news.xml"
    ],
    "Crypto & Global Macro": [
        "https://news.google.com/rss/search?q=bitcoin+ethereum+crypto+fed+interest+rate+when:1d&hl=en-US&gl=US&ceid=US:en",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cointelegraph.com/rss",
        "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best"
    ]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_url(url_str):
    match = re.search(r'https?://[^\s\]\)]+', str(url_str))
    return match.group(0) if match else url_str

# Helper function to extract thumbnail images from RSS entries
def extract_entry_image(entry):
    # 1. Check media_content
    if 'media_content' in entry and entry.media_content:
        for media in entry.media_content:
            if 'url' in media and media['url']:
                return media['url']
    # 2. Check media_thumbnail
    if 'media_thumbnail' in entry and entry.media_thumbnail:
        if isinstance(entry.media_thumbnail, list) and len(entry.media_thumbnail) > 0:
            return entry.media_thumbnail[0].get('url', '')
    # 3. Check enclosures
    if 'enclosures' in entry and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/') and 'href' in enc:
                return enc['href']
    # Fallback market thumbnail
    return "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=150&q=80"

# ==========================================
# 2. INGEST HEADLINES & DEDUPLICATION CHECK
# ==========================================
print("=== Step 1: Ingesting Live Multi-Source Market Feeds ===")
now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
is_weekend = now_ist.weekday() in [5, 6]  # Saturday = 5, Sunday = 6

if is_weekend:
    current_time_str = now_ist.strftime("%b %d, %Y") + " (Weekend Macro Wrap)"
else:
    current_time_str = now_ist.strftime("%I:%M %p IST")

now_utc = datetime.now(timezone.utc)

category_data = {}
all_raw_titles = []
category_images = {}

for cat_name, feed_urls in CATEGORY_FEEDS.items():
    cleaned_titles = []
    cat_img = None
    for feed_url in feed_urls:
        try:
            resp = requests.get(clean_url(feed_url), headers=HEADERS, timeout=8)
            feed = feedparser.parse(resp.content)
            # Scan top 5 entries per feed to avoid missing micro breaking flashes
            for entry in feed.entries[:5]:
                t = re.sub(r'\s*-\s*[^-]+$', '', entry.title)
                t = re.sub(r'\?.*$', '', t).strip()
                if t and t not in cleaned_titles:
                    cleaned_titles.append(t)
                    all_raw_titles.append(t)
                    if not cat_img:
                        cat_img = extract_entry_image(entry)
        except Exception as e:
            print(f"⚠️ Error fetching {cat_name} from {feed_url}: {e}")
            
    if cleaned_titles:
        category_data[cat_name] = cleaned_titles[:4]
        category_images[cat_name] = cat_img or "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=150&q=80"

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
is_duplicate = (current_hash is not None) and (latest_saved_hash == current_hash)

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
You are a senior chief market strategist preparing a 7:00 AM IST Pre-Market Briefing.
Synthesize the headlines into actionable, high-density market analysis. Highlight breaking geopolitical events, crude oil catalysts, and central bank commentary.

Format strictly as HTML inside a single <div> with bullet points:
<p><b>Overall Daily Market Bias: Moderately Bullish / Neutral / Bearish</b></p>
<ul>
  <li><b>⚡ Geopolitics & Macro Flashes:</b> [2 dense sentences highlighting breaking geopolitical quotes or major world events]</li>
  <li><b>Global & US Markets:</b> [2 dense sentences on Wall Street futures, treasury yields, or major tech/macro drivers]</li>
  <li><b>Commodities & Forex:</b> [2 dense sentences on crude oil trends, gold demand, or rupee/dollar levels]</li>
  <li><b>Indian Equities Outlook:</b> [2 dense sentences on Nifty opening cues, institutional flows, or key sector focus]</li>
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
            "<li><b>⚡ Geopolitics & Macro Flashes:</b> Geopolitical headlines remain in focus as energy markets track supply stability in the Middle East.</li>\n"
            "<li><b>Global & US Markets:</b> Wall Street futures trade in controlled ranges as treasury yields stabilize ahead of key inflation data.</li>\n"
            "<li><b>Commodities & Forex:</b> Easing crude oil prices provide margin relief to Asian importers, while USD/INR holds near key support levels.</li>\n"
            "<li><b>Indian Equities Outlook:</b> Nifty 50 and Sensex display positive underlying momentum supported by robust domestic DII buying.</li>\n"
            "</ul>"
        )
        
    morning_briefing_data = {
        "date": now_ist.strftime("%b %d, %Y"),
        "html": briefing_html
    }

# ==========================================
# 4. SYNTHESIZE HIGH-QUALITY COMMENTARY (IF NEW)
# ==========================================
ai_bullets_html = None

if not is_duplicate and category_data:
    print("=== Step 3: Generating Actionable Market Commentary Block ===")
    prompt_text = "\n".join([f"[{cat}]: " + " | ".join(items) for cat, items in category_data.items()])
    
    prompt = f"""
You are an institutional trading desk analyst. Analyze the market headlines and synthesize high-impact commentary.

CRITICAL INSTRUCTIONS:
1. PRIORITIZE BREAKING NEWS: Lead with breaking geopolitical quotes (e.g., statements on war, sanctions, central bank actions, or leader quotes like Trump/Fed/RBI).
2. NO GENERIC FLUFF: Mention specific tickers, commodities, currency pairs, or leaders wherever relevant.
3. BOLD KEY TERMS: Use HTML <b>tags</b> to **bold key stock tickers, levels, leader names, and major catalysts** (e.g., <b>Nifty 50</b>, <b>Trump</b>, <b>Crude Oil</b>, <b>RBI</b>).
4. STRUCTURE: Explain (1) WHAT happened, (2) WHY it happened, and (3) WHAT IT MEANS for immediate market bias.

Output strictly 5 HTML <li> tags formatted as follows:
<li><b>⚡ Breaking Flashes & Geopolitics:</b> [Key breaking quotes, geopolitical developments, or sudden market catalysts]</li>
<li><b>Indian Stock Market:</b> [Specific sector/stock drivers, institutional sentiment, or Nifty/Sensex action]</li>
<li><b>US & Global Markets:</b> [Wall Street/Asian tech action, treasury yields, earnings, or Fed commentary]</li>
<li><b>Forex & Commodities:</b> [USD/INR direction, Crude oil catalysts, Gold/Silver safe-haven demand]</li>
<li><b>Crypto & Global Macro:</b> [BTC/ETH price action, ETF updates, or inflation/policy prints]</li>

Headlines:
{prompt_text}
"""
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