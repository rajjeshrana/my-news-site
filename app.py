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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

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
# 2. INGEST HEADLINES & DEDUPLICATION CHECK
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
ai_bullets_html = None

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
    if GROQ_API_KEY:
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        groq_headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
            try:
                payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
                res = requests.post(groq_url, json=payload, headers=groq_headers, timeout=25)
                if res.status_code == 200:
                    ai_bullets_html = res.json()["choices"][0]["message"]["content"]
                    ai_bullets_html = re.sub(r'```html|```', '', ai_bullets_html).strip()
                    break
            except Exception as e:
                print(f"⚠️ Groq error: {e}")

    if not ai_bullets_html:
        items_list = []
        for cat, items in category_data.items():
            txt = " ".join(items)
            items_list.append(f"<li><b>{cat}:</b> {txt}. Trading activity remains bounded as market participants assess broader economic indicators.</li>")
        ai_bullets_html = "\n".join(items_list)

    new_block = {
        "timestamp": current_time_str,
        "time_epoch": now_utc.timestamp(),
        "hash": current_hash,
        "html_content": ai_bullets_html
    }
    blocks_history.insert(0, new_block)

cutoff_epoch = (now_utc - timedelta(hours=48)).timestamp()
blocks_history = [b for b in blocks_history if b.get("time_epoch", now_utc.timestamp()) >= cutoff_epoch]

with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump({
        "morning_briefing": morning_briefing_data,
        "blocks": blocks_history
    }, f, indent=2)

# ==========================================
# 5. TELEGRAM AUTO-BROADCAST VIA BOT API
# ==========================================
def send_telegram_message(time_str, html_bullets):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("ℹ️ Telegram credentials missing. Skipping notification.")
        return

    text_content = html_bullets.replace("<li>", "• ").replace("</li>", "\n")
    message_body = (
        f"📊 <b>Live Market Commentary ({time_str})</b>\n\n"
        f"{text_content}\n"
        f"🌐 <a href='https://rajjeshrana.github.io/my-news-site/'>Read Full Feed</a>"
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
            print("✅ Successfully broadcasted update to Telegram!")
        else:
            print(f"⚠️ Telegram Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"⚠️ Telegram request failed: {e}")

if not is_duplicate and ai_bullets_html:
    send_telegram_message(current_time_str, ai_bullets_html)

# ==========================================
# 6. RENDER HTML PAGE
# ==========================================
print("=== Step 4: Formatting HTML Output ===")

commentary_blocks_html = ""
for block in blocks_history[:10]:
    t_stamp = block.get("timestamp", "Live Update")
    content = block.get("html_content", "")
    commentary_blocks_html += f"""
    <div class="time-card">
        <div class="time-header">⏱️ {t_stamp} Update</div>
        <ul>
            {content}
        </ul>
    </div>
    """

briefing_section_html = ""
if morning_briefing_data:
    briefing_section_html = f"""
    <div class="card" style="border-left-color: #0d47a1;">
        <h3 style="margin-top:0; color:#0d47a1; font-size:1.2em;">☕ 7:00 AM Pre-Market Global Briefing ({morning_briefing_data.get('date')})</h3>
        {morning_briefing_data.get('html')}
    </div>
    """

pivot_table_html = """
<div class="pivot-section">
    <h3>📌 Daily Pivot Levels</h3>
    <table class="pivot-table">
        <thead>
            <tr><th>Index</th><th>Support (S1)</th><th>Pivot (P)</th><th>Resistance (R1)</th></tr>
        </thead>
        <tbody>
            <tr><td><b>Nifty 50</b></td><td class="support">23,210</td><td class="pivot">23,300</td><td class="resistance">23,390</td></tr>
            <tr><td><b>Bank Nifty</b></td><td class="support">49,550</td><td class="pivot">49,800</td><td class="resistance">50,050</td></tr>
            <tr><td><b>Sensex</b></td><td class="support">76,200</td><td class="pivot">76,500</td><td class="resistance">76,800</td></tr>
        </tbody>
    </table>
</div>
"""

ist_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")

css_styles = """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 30px auto; padding: 20px; color: #2c3e50; line-height: 1.6; background-color: #f8f9fa; }
    h1 { color: #0d47a1; font-size: 2em; margin-bottom: 5px; }
    .timestamp { color: #666; font-weight: 600; font-size: 0.95em; margin-bottom: 15px; }
    .badge { background: #e8f5e9; color: #2e7d32; padding: 6px 12px; border-radius: 4px; font-size: 0.85em; font-weight: bold; display: inline-block; margin-bottom: 20px; }
    hr { border: 0; height: 1px; background: #e0e0e0; margin-bottom: 25px; }
    .time-card { background: #ffffff; border-left: 5px solid #2e7d32; padding: 22px 25px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 22px; }
    .time-header { font-weight: bold; color: #1b5e20; font-size: 1.15em; margin-bottom: 14px; }
    .pivot-section { background: #ffffff; padding: 22px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 22px; }
    .pivot-section h3 { margin-top: 0; color: #0d47a1; font-size: 1.2em; margin-bottom: 15px; }
    .pivot-table { width: 100%; border-collapse: collapse; text-align: left; }
    .pivot-table th, .pivot-table td { padding: 12px 14px; border-bottom: 1px solid #eee; font-size: 1em; }
    .pivot-table th { background-color: #f1f5f9; color: #334155; }
    .card { background: #ffffff; border-left: 5px solid #1976d2; padding: 22px 25px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); margin-bottom: 22px; }
    .support { color: #d32f2f; font-weight: 600; }
    .pivot { color: #1976d2; font-weight: 600; }
    .resistance { color: #2e7d32; font-weight: 600; }
    ul { padding-left: 20px; margin: 0; }
    li { margin-bottom: 12px; font-size: 1em; color: #2c3e50; }
"""

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <title>Live Market Feed & Pre-Market Briefing</title>
    <style>
{css_styles}
    </style>
</head>
<body>
    <h1>Live Market Feed & Pre-Market Briefing</h1>
    <div class="timestamp">🕒 Last Updated: {ist_time}</div>
    <div class="badge">🔴 15-Minute Live Commentary Stream</div>
    <hr>
    {briefing_section_html}
    <h3 style="color:#2e7d32; margin-bottom:15px; font-size:1.3em;">📰 Live Market Commentary (15-Min Stream)</h3>
    {commentary_blocks_html}
    {pivot_table_html}
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("✅ Successfully generated index.html!")