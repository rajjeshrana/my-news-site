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
    "Macro Intelligence": [
        "https://news.google.com/rss/search?q=Nifty+Sensex+stock+market+India+macro+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.business-standard.com/rss/markets-106.rss",
        "https://www.livemint.com/rss/markets"
    ],
    "🎯 Breakout Stock Setups": [
        "https://news.google.com/rss/search?q=top+stocks+to+buy+today+target+stoploss+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.financialexpress.com/market/feed/",
        "https://economictimes.indiatimes.com/markets/stocks/recoms/rssfeeds/2146842.cms"
    ],
    "Indian Stock Market": [
        "https://news.google.com/rss/search?q=Nifty+Sensex+stock+market+India+breaking+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.ndtvprofit.com/rss/markets.xml",
        "https://www.moneycontrol.com/rss/MCtopnews.xml"
    ],
    "⚡ Breaking Flashes & Geopolitics": [
        "https://news.google.com/rss/search?q=geopolitics+breaking+news+when:2d&hl=en-US&gl=US&ceid=US:en",
        "https://www.forexlive.com/feed/news",
        "https://www.fxstreet.com/rss/news"
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

def clean_url(url_str):
    match = re.search(r'https?://[^\s\]\)]+', str(url_str))
    return match.group(0) if match else url_str

# ==========================================
# 2. INGEST HEADLINES WITH LINKS
# ==========================================
print("=== Step 1: Ingesting Live Multi-Source Market Feeds ===")
now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
formatted_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")
current_time_str = f"{formatted_time} (Live Terminal Stream)"
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
    cleaned_items = []
    for feed_url in feed_urls:
        try:
            resp = requests.get(clean_url(feed_url), headers=HEADERS, timeout=8)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:6]:
                t = re.sub(r'\s*-\s*[^-]+$', '', entry.title)
                t = re.sub(r'\?.*$', '', t).strip()
                link = getattr(entry, 'link', 'https://rajjeshrana.github.io/my-news-site/')
                if not t:
                    continue
                
                h_hash = hashlib.md5(t.lower().encode('utf-8')).hexdigest()
                
                # Deduplicate by title
                if not any(item['title'] == t for item in cleaned_items):
                    cleaned_items.append({"title": t, "link": link})
                    seen_headline_hashes.add(h_hash)
        except Exception as e:
            print(f"⚠️ Error fetching {cat_name} from {feed_url}: {e}")
            
    if cleaned_items:
        category_data[cat_name] = cleaned_items[:6]

with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump({"seen_hashes": list(seen_headline_hashes)[-500:]}, f, indent=2)

# ==========================================
# 3. DYNAMIC TIME-BASED FIRST CARD HEADING
# ==========================================
current_hour = now_ist.hour
if 7 <= current_hour < 10:
    first_card_title = "🌅 Pre-Market Briefing & Macro Sheet"
else:
    first_card_title = "📊 Mid-Day Market Pulse & Macro Sheet"

# ==========================================
# 4. TELEGRAM & GREEN-API WHATSAPP BROADCASTS
# ==========================================
print("=== Step 2: Executing Telegram & WhatsApp Broadcasts ===")

def send_telegram_message(time_str, cat_dict):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials missing. Skipping broadcast.")
        return

    formatted_sections = []
    for cat_title, items in cat_dict.items():
        if not items:
            continue
        items_text = "\n• ".join([f"<a href='{item['link']}'>{item['title']}</a>" for item in items[:4]])
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
        items_text = "\n• ".join([f"{item['title']} ({item['link']})" for item in items[:3]])
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
# 5. RENDER DYNAMIC TERMINAL INDEX.HTML
# ==========================================
print("=== Step 3: Formatting Dynamic Terminal index.html ===")

ist_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")

def render_block_html(cat_key):
    items = category_data.get(cat_key, [])
    if not items:
        return "<p style='color:#94a3b8; font-size:0.85em;'>No fresh headlines ingested in this cycle.</p>"
    
    html_items = "".join([
        f"<li style='margin-bottom:10px; line-height:1.45;'><a href='{item['link']}' target='_blank' style='color:#1e293b; text-decoration:none; font-weight:600;' onmouseover=\"this.style.color='#d97706'\" onmouseout=\"this.style.color='#1e293b'\">{item['title']}</a></li>" 
        for item in items
    ])
    return f"<ul style='padding-left:18px; margin:0;'>{html_items}</ul>"

block1_html = render_block_html("Macro Intelligence")
block2_html = render_block_html("🎯 Breakout Stock Setups")
block3_html = render_block_html("Indian Stock Market")
block4_html = render_block_html("⚡ Breaking Flashes & Geopolitics")
block5_html = render_block_html("US & Global Markets")
block6_html = render_block_html("Forex & Commodities")

css_styles = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { width: 100vw; min-height: 100vh; overflow-x: hidden; font-family: system-ui, -apple-system, sans-serif; background-color: #f8fafc; color: #1e293b; }
    .terminal-header { height: 50px; background-color: #ffffff; border-bottom: 2px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; padding: 0 20px; width: 100%; position: sticky; top: 0; z-index: 100; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }
    .brand-logo { font-size: 1.25em; font-weight: 900; color: #0f172a; }
    .brand-logo span { color: #d97706; }
    .header-info { font-size: 0.85em; color: #64748b; font-weight: 600; }
    .terminal-grid { display: grid; grid-template-columns: repeat(3, 1fr); grid-template-rows: repeat(2, minmax(320px, 1fr)); gap: 14px; padding: 14px; width: 100vw; min-height: calc(100vh - 50px); }
    .grid-block { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; display: flex; flex-direction: column; max-height: 420px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    .block-header { background-color: #f1f5f9; padding: 10px 14px; font-size: 0.88em; font-weight: 800; color: #d97706; border-bottom: 1px solid #cbd5e1; flex-shrink: 0; }
    .block-scroll-body { padding: 12px 14px; overflow-y: auto; flex-grow: 1; font-size: 0.86em; color: #334155; }
    .block-scroll-body::-webkit-scrollbar { width: 5px; }
    .block-scroll-body::-webkit-scrollbar-thumb { background-color: #cbd5e1; border-radius: 4px; }
    @media (max-width: 1024px) {
        .terminal-grid { display: flex; flex-direction: column; height: auto; }
        .grid-block { max-height: none; height: auto; }
    }
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
        <div class="grid-block"><div class="block-header">{first_card_title}</div><div class="block-scroll-body">{block1_html}</div></div>
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

print("=== Successfully updated terminal layout and executed broadcasts! ===")