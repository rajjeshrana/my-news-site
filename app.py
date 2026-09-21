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
# 1. EXPANDED FINANCIAL SOURCES NETWORK
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip("'").strip('"')
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip().strip("'").strip('"')
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip().strip("'").strip('"')

# GREEN-API WHATSAPP CREDENTIALS
GREENAPI_INSTANCE_ID = os.getenv("GREENAPI_INSTANCE_ID", "").strip().strip("'").strip('"')
GREENAPI_API_TOKEN = os.getenv("GREENAPI_API_TOKEN", "").strip().strip("'").strip('"')
GREENAPI_CHAT_ID = os.getenv("GREENAPI_CHAT_ID", "").strip().strip("'").strip('"')

CATEGORY_FEEDS = {
    "🎯 Breakout Stock Setups": [
        "https://news.google.com/rss/search?q=top+stocks+to+buy+today+target+stoploss+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=stock+market+recommendations+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.business-standard.com/rss/markets-106.rss",
        "https://www.financialexpress.com/market/feed/",
        "https://www.livemint.com/rss/markets"
    ],
    "⚡ Breaking Flashes & Geopolitics": [
        "https://news.google.com/rss/search?q=site:twitter.com+OR+site:x.com+breaking+news+when:2d&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=financialjuice+OR+ForexLive+breaking+when:2d&hl=en-US&gl=US&ceid=US:en",
        "https://www.forexlive.com/feed/news",
        "https://www.fxstreet.com/rss/news"
    ],
    "Indian Stock Market": [
        "https://news.google.com/rss/search?q=Nifty+Sensex+stock+market+India+breaking+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.ndtvprofit.com/rss/markets.xml",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/MCtopnews.xml"
    ],
    "US & Global Markets": [
        "https://news.google.com/rss/search?q=Wall+Street+Nasdaq+SP500+breaking+news+when:2d&hl=en-US&gl=US&ceid=US:en",
        "https://search.cnbc.com/rs/search/combined:rss?source=cnbc&q=markets",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
    ],
    "Forex & Commodities": [
        "https://news.google.com/rss/search?q=Crude+Oil+Gold+USD+INR+forex+breaking+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.dailyfx.com/feeds/market-news",
        "https://www.oilprice.com/rss/main"
    ]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

FALLBACK_IMAGE = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80"

def clean_url(url_str):
    match = re.search(r'https?://[^\s\]\)]+', str(url_str))
    return match.group(0) if match else url_str

# ==========================================
# 2. INGEST HEADLINES & DEDUPLICATION CHECK
# ==========================================
print("=== Step 1: Ingesting Live Multi-Source Market Feeds ===")
now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
is_weekend = now_ist.weekday() in [5, 6]
formatted_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")

if is_weekend:
    current_time_str = f"{formatted_time} (Weekend Stock & Macro Radar)"
else:
    current_time_str = f"{formatted_time} (Live Market Stream)"

now_utc = datetime.now(timezone.utc)

HISTORY_FILE = "history.json"
seen_headline_hashes = set()

if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            store = json.load(f)
            if isinstance(store, dict):
                seen_headline_hashes = set(store.get("seen_hashes", []))
    except Exception as e:
        print(f"⚠️ Load error on history.json: {e}")

category_data = {}

for cat_name, feed_urls in CATEGORY_FEEDS.items():
    cleaned_titles = []
    for feed_url in feed_urls:
        try:
            resp = requests.get(clean_url(feed_url), headers=HEADERS, timeout=8)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:6]:
                t = re.sub(r'\s*-\s*[^-]+$', '', entry.title)
                t = re.sub(r'\?.*$', '', t).strip()
                if not t:
                    continue
                
                h_hash = hashlib.md5(t.lower().encode('utf-8')).hexdigest()
                if t not in cleaned_titles:
                    cleaned_titles.append(t)
                    seen_headline_hashes.add(h_hash)
        except Exception as e:
            print(f"⚠️ Error fetching {cat_name} from {feed_url}: {e}")
            
    if cleaned_titles:
        category_data[cat_name] = cleaned_titles[:6]

with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump({"seen_hashes": list(seen_headline_hashes)[-500:]}, f, indent=2)

# ==========================================
# 3. ADVANCED LLM INFOGRAPHIC CARD GENERATION
# ==========================================
def query_groq_llm(prompt_str):
    if not GROQ_API_KEY:
        print("⚠️ GROQ_API_KEY environment variable is empty or missing.")
        return None
    groq_url = "https://api.groq.com/openai/v1/chat/completions"
    groq_headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    models_to_try = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant"
    ]
    for model in models_to_try:
        try:
            payload = {"model": model, "messages": [{"role": "user", "content": prompt_str}], "temperature": 0.2}
            res = requests.post(groq_url, json=payload, headers=groq_headers, timeout=25)
            if res.status_code == 200:
                output = res.json()["choices"][0]["message"]["content"]
                return re.sub(r'```(?:html|json)?|```', '', output).strip()
            else:
                print(f"⚠️ Groq Model {model} returned HTTP {res.status_code}: {res.text}")
        except Exception as e:
            print(f"⚠️ Groq API Error on {model}: {e}")
    return None

intelligence_summary = ""
if category_data:
    print("=== Step 2: Generating Deep Light Terminal Intelligence ===")
    prompt_text = "\n".join([f"[{cat}]: " + " | ".join(items) for cat, items in category_data.items()])
    
    pass1_prompt = f"""
You are a financial research analyst. Synthesize these news headlines into concise bullet points for a terminal view:
{prompt_text}
"""
    intelligence_summary = query_groq_llm(pass1_prompt) or ""

# ==========================================
# 4. TELEGRAM & GREEN-API WHATSAPP BROADCASTS
# ==========================================
print("=== Step 3: Executing Telegram & WhatsApp Broadcasts ===")

def send_telegram_message(time_str, cat_dict):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials missing. Skipping broadcast.")
        return

    formatted_sections = []
    for cat_title, items in cat_dict.items():
        if not items:
            continue
        items_text = "\n• ".join(items[:4])
        section_block = f"<b>{cat_title}:</b>\n• {items_text}"
        formatted_sections.append(section_block)

    sections_text = "\n\n".join(formatted_sections)

    message_body = (
        f"🔥 <b>StockVersity Market Intelligence Briefing</b>\n"
        f"⏱️ <i>{time_str}</i>\n\n"
        f"{sections_text}\n\n"
        f"🌐 <a href='https://rajjeshrana.github.io/my-news-site/'>Open Live Terminal</a>"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_body,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            print("✅ Successfully sent formatted update to Telegram!")
        else:
            print(f"⚠️ Telegram Error {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ Telegram Request Exception: {e}")

def send_green_api_whatsapp(time_str, cat_dict):
    if not GREENAPI_INSTANCE_ID or not GREENAPI_API_TOKEN or not GREENAPI_CHAT_ID:
        print("⚠️ GREEN-API WhatsApp credentials missing. Skipping WhatsApp broadcast.")
        return

    formatted_sections = []
    for cat_title, items in cat_dict.items():
        if not items:
            continue
        items_text = "\n• ".join(items[:4])
        formatted_sections.append(f"*{cat_title}:*\n• {items_text}")

    sections_text = "\n\n".join(formatted_sections)

    wa_message_body = (
        f"🔥 *StockVersity Market Intelligence Briefing*\n"
        f"⏱️ _{time_str}_\n\n"
        f"{sections_text}\n\n"
        f"🌐 https://rajjeshrana.github.io/my-news-site/"
    )

    url = f"https://api.green-api.com/waInstance{GREENAPI_INSTANCE_ID}/sendMessage/{GREENAPI_API_TOKEN}"
    payload = {
        "chatId": GREENAPI_CHAT_ID,
        "message": wa_message_body
    }

    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            print("✅ Successfully broadcasted update to WhatsApp via GREEN-API!")
        else:
            print(f"⚠️ GREEN-API Error {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ GREEN-API Request Exception: {e}")

if category_data:
    send_telegram_message(current_time_str, category_data)
    send_green_api_whatsapp(current_time_str, category_data)

# ==========================================
# 5. RENDER DYNAMIC LIVE TERMINAL INDEX.HTML
# ==========================================
print("=== Step 4: Formatting Light 6-Block Terminal ===")

ist_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")

def render_block_html(cat_key):
    items = category_data.get(cat_key, [])
    if not items:
        return "<p style='color:#94a3b8;'>No fresh headlines ingested in this cycle.</p>"
    
    html_items = "".join([f"<li style='margin-bottom:8px;'>{item}</li>" for item in items])
    return f"<ul style='padding-left:16px;'>{html_items}</ul>"

block1_html = render_block_html("🎯 Breakout Stock Setups")
block2_html = render_block_html("🎯 Breakout Stock Setups")
block3_html = render_block_html("Indian Stock Market")
block4_html = render_block_html("⚡ Breaking Flashes & Geopolitics")
block5_html = render_block_html("US & Global Markets")
block6_html = render_block_html("Forex & Commodities")

css_styles = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { width: 100vw; height: 100vh; overflow: hidden; font-family: system-ui, -apple-system, sans-serif; background-color: #f8fafc; color: #1e293b; }
    .terminal-header { height: 50px; background-color: #ffffff; border-bottom: 2px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; padding: 0 20px; width: 100%; }
    .brand-logo { font-size: 1.25em; font-weight: 900; color: #0f172a; }
    .brand-logo span { color: #d97706; }
    .header-info { font-size: 0.85em; color: #64748b; font-weight: 600; }
    .terminal-grid { display: grid; grid-template-columns: repeat(3, 1fr); grid-template-rows: repeat(2, calc((100vh - 50px) / 2)); gap: 12px; padding: 12px; width: 100vw; height: calc(100vh - 50px); }
    .grid-block { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; display: flex; flex-direction: column; height: 100%; overflow: hidden; }
    .block-header { background-color: #f1f5f9; padding: 10px 14px; font-size: 0.88em; font-weight: 800; color: #d97706; border-bottom: 1px solid #cbd5e1; }
    .block-scroll-body { padding: 12px; overflow-y: auto; flex-grow: 1; font-size: 0.86em; line-height: 1.5; color: #334155; }
"""

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <title>StockVersity Terminal</title>
    <style>{css_styles}</style>
</head>
<body>
    <div class="terminal-header">
        <div class="brand-logo">Stock<span>Versity</span> Terminal</div>
        <div class="header-info">🕒 Synchronized: {ist_time}</div>
    </div>
    <div class="terminal-grid">
        <div class="grid-block"><div class="block-header">🌅 Pre-Market Briefing & Macro Sheet</div><div class="block-scroll-body">{block1_html}</div></div>
        <div class="grid-block"><div class="block-header">🎯 High-Conviction Breakout Setups</div><div class="block-scroll-body">{block2_html}</div></div>
        <div class="grid-block"><div class="block-header">🇮🇳 Indian Equities Wire</div><div class="block-scroll-body">{block3_html}</div></div>
        <div class="grid-block"><div class="block-header">⚡ Breaking Flashes & Geopolitics</div><div class="block-scroll-body">{block4_html}</div></div>
        <div class="grid-block"><div class="block-header">🌍 US & Global Macro Intelligence</div><div class="block-scroll-body">{block5_html}</div></div>
        <div class="grid-block"><div class="block-header">🛢️ Forex & Energy Boundaries</div><div class="block-scroll-body">{block6_html}</div></div>
    </div>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("=== Successfully executed Telegram & GREEN-API WhatsApp broadcast! ===")