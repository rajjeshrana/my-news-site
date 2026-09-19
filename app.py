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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

CATEGORY_FEEDS = {
    "🎯 Indian Stocks & Breakout Scanners": [
        "https://news.google.com/rss/search?q=top+stocks+to+buy+next+week+India+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=breakout+stocks+target+stoploss+India+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.business-standard.com/rss/markets-106.rss",
        "https://www.financialexpress.com/market/feed/",
        "https://www.livemint.com/rss/markets"
    ],
    "⚡ Breaking Flashes & Geopolitics": [
        "https://news.google.com/rss/search?q=site:twitter.com+OR+site:x.com+Trump+Iran+war+when:1d&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=financialjuice+OR+DeitaOne+OR+ForexLive+breaking+when:1d&hl=en-US&gl=US&ceid=US:en",
        "https://www.forexlive.com/feed/news",
        "https://www.fxstreet.com/rss/news"
    ],
    "Indian Stock Market": [
        "https://news.google.com/rss/search?q=Nifty+Sensex+stock+market+India+breaking+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.ndtvprofit.com/rss/markets.xml",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.moneycontrol.com/rss/MCtopnews.xml"
    ],
    "US & Global Markets": [
        "https://news.google.com/rss/search?q=Wall+Street+Nasdaq+SP500+breaking+news+when:1d&hl=en-US&gl=US&ceid=US:en",
        "https://search.cnbc.com/rs/search/combined:rss?source=cnbc&q=markets",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.investing.com/rss/news_25.rss"
    ],
    "Forex & Commodities": [
        "https://news.google.com/rss/search?q=Crude+Oil+Gold+USD+INR+forex+breaking+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.dailyfx.com/feeds/market-news",
        "https://www.oilprice.com/rss/main"
    ]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

FALLBACK_IMAGE = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=150&q=80"

def clean_url(url_str):
    match = re.search(r'https?://[^\s\]\)]+', str(url_str))
    return match.group(0) if match else url_str

def extract_entry_image(entry):
    try:
        if 'media_content' in entry and entry.media_content:
            for media in entry.media_content:
                if 'url' in media and media['url']:
                    return media['url']
        if 'media_thumbnail' in entry and entry.media_thumbnail:
            if isinstance(entry.media_thumbnail, list) and len(entry.media_thumbnail) > 0:
                return entry.media_thumbnail[0].get('url', '')
        if 'enclosures' in entry and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get('type', '').startswith('image/') and 'href' in enc:
                    return enc['href']
    except Exception:
        pass
    return FALLBACK_IMAGE

# ==========================================
# 2. INGEST HEADLINES & DEDUPLICATION CHECK
# ==========================================
print("=== Step 1: Ingesting Live Multi-Source Market Feeds ===")
now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
is_weekend = now_ist.weekday() in [5, 6]

if is_weekend:
    current_time_str = now_ist.strftime("%b %d, %Y") + " (Weekly Market & Stock Setup)"
else:
    current_time_str = now_ist.strftime("%I:%M %p IST")

now_utc = datetime.now(timezone.utc)

HISTORY_FILE = "history.json"
blocks_history = []
seen_headline_hashes = set()

if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            store = json.load(f)
            if isinstance(store, dict):
                blocks_history = store.get("blocks", [])
                seen_headline_hashes = set(store.get("seen_hashes", []))
            elif isinstance(store, list):
                blocks_history = store
    except Exception as e:
        print(f"⚠️ Load error on history.json: {e}")

category_data = {}
category_images = {}
category_links = {}
new_items_count = 0

for cat_name, feed_urls in CATEGORY_FEEDS.items():
    cleaned_titles = []
    cat_img = None
    first_link = None
    for feed_url in feed_urls:
        try:
            resp = requests.get(clean_url(feed_url), headers=HEADERS, timeout=8)
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:5]:
                t = re.sub(r'\s*-\s*[^-]+$', '', entry.title)
                t = re.sub(r'\?.*$', '', t).strip()
                if not t:
                    continue
                
                h_hash = hashlib.md5(t.lower().encode('utf-8')).hexdigest()
                
                if h_hash not in seen_headline_hashes and t not in cleaned_titles:
                    cleaned_titles.append(t)
                    seen_headline_hashes.add(h_hash)
                    new_items_count += 1
                    if not first_link and hasattr(entry, 'link'):
                        first_link = entry.link
                    if not cat_img or cat_img == FALLBACK_IMAGE:
                        extracted = extract_entry_image(entry)
                        if extracted != FALLBACK_IMAGE:
                            cat_img = extracted
        except Exception as e:
            print(f"⚠️ Error fetching {cat_name} from {feed_url}: {e}")
            
    if cleaned_titles:
        category_data[cat_name] = cleaned_titles[:5]
        category_images[cat_name] = cat_img or FALLBACK_IMAGE
        category_links[cat_name] = first_link or "https://news.google.com"

is_duplicate = (new_items_count == 0)

# ==========================================
# 3. ADVANCED TWO-PASS LLM SYNTHESIS (GROQ)
# ==========================================
ai_bullets_html = None

def query_groq_llm(prompt_str):
    if not GROQ_API_KEY:
        return None
    groq_url = "https://api.groq.com/openai/v1/chat/completions"
    groq_headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    models_to_try = [
        "llama-3.3-70b-versatile", 
        "llama-3.1-8b-instant", 
        "llama3-70b-8192", 
        "mixtral-8x7b-32768"
    ]
    for model in models_to_try:
        try:
            payload = {"model": model, "messages": [{"role": "user", "content": prompt_str}], "temperature": 0.2}
            res = requests.post(groq_url, json=payload, headers=groq_headers, timeout=25)
            if res.status_code == 200:
                output = res.json()["choices"][0]["message"]["content"]
                return re.sub(r'```html|```json|```', '', output).strip()
        except Exception as e:
            print(f"⚠️ Groq API Error on {model}: {e}")
    return None

if not is_duplicate and category_data:
    print("=== Step 2: Executing Two-Pass LLM Quantitative & Technical Analysis ===")
    prompt_text = "\n".join([f"[{cat}]: " + " | ".join(items) for cat, items in category_data.items()])
    
    # PASS 1: Extraction & Categorization
    pass1_prompt = f"""
You are a quantitative market intelligence engine.
Parse the following news feed headlines and extract key information:
1. Identify all explicit Indian stock setups, target prices, stop losses, or technical breakout catalysts mentioned.
2. Identify major breaking geopolitical statements or central bank actions.

Return a dense structured summary prioritizing specific company tickers, technical levels, and exact catalysts.

Headlines:
{prompt_text}
"""
    extracted_intelligence = query_groq_llm(pass1_prompt) or prompt_text

    # PASS 2: Final HTML Institutional Synthesis
    pass2_prompt = f"""
You are a chief institutional strategist. Using the extracted quantitative intelligence below, construct a high-impact terminal commentary block.

STRICT INSTRUCTIONS:
1. BOLD KEY TERMS: Bold key stock tickers, index levels, leader names, and major catalysts using HTML <b>tags</b> (e.g., <b>Nifty 50</b>, <b>SBI</b>, <b>Trump</b>, <b>Crude Oil</b>).
2. HIGH DENSITY: Write 2-3 detailed sentences for each category explaining [1] WHAT happened / stock targets, [2] WHY (core catalyst), and [3] WHAT IT MEANS for immediate market bias.

Output strictly 5 HTML <li> tags formatted like this:
<li><b>🎯 High-Conviction Indian Stock Setups:</b> [Highlight 2-3 specific breakout stocks with technical targets/stop-losses or strong volume catalysts]</li>
<li><b>⚡ Breaking Flashes & Geopolitics:</b> [Highlight breaking geopolitical quotes, world leader statements, or sudden market risk drivers]</li>
<li><b>Indian Stock Market:</b> [Nifty/Sensex trend, institutional FII/DII activity, and sectoral focus]</li>
<li><b>US & Global Markets:</b> [Wall Street futures, tech momentum, treasury yields, and Fed rate expectations]</li>
<li><b>Forex & Commodities:</b> [USD/INR direction, Crude oil catalysts, and Gold safe-haven levels]</li>

Extracted Intelligence:
{extracted_intelligence}
"""
    ai_bullets_html = query_groq_llm(pass2_prompt)

    if not ai_bullets_html:
        print("⚠️ LLM processing unavailable. Using default formatting.")
        items_list = []
        for cat, items in category_data.items():
            combined_text = " ".join(items)
            items_list.append(f"<li><b>{cat}:</b> {combined_text}</li>")
        ai_bullets_html = "\n".join(items_list)

    web_bullets_list = []
    bullets_matches = re.findall(r'<li>(.*?)</li>', ai_bullets_html, re.DOTALL)
    
    cat_keys = list(category_images.keys())
    for idx, b_text in enumerate(bullets_matches):
        cat_key = cat_keys[idx if idx < len(cat_keys) else 0]
        img_url = category_images.get(cat_key, FALLBACK_IMAGE)
        source_link = category_links.get(cat_key, "[https://news.google.com](https://news.google.com)")
        
        card_item = f"""
        <li>
            <div class="news-item-box">
                <img src="{img_url}" class="news-thumb" alt="stock news" onerror="this.onerror=null;this.src='{FALLBACK_IMAGE}';">
                <div class="news-text-content">
                    {b_text}
                    <div style="margin-top: 6px;">
                        <a href="{source_link}" target="_blank" class="source-link">🔗 Read Full Research Source</a>
                    </div>
                </div>
            </div>
        </li>
        """
        web_bullets_list.append(card_item)

    web_html_content = "\n".join(web_bullets_list) if web_bullets_list else ai_bullets_html

    new_block = {
        "timestamp": current_time_str,
        "time_epoch": now_utc.timestamp(),
        "html_content": web_html_content,
        "raw_text_content": ai_bullets_html
    }
    blocks_history.insert(0, new_block)

cutoff_epoch = (now_utc - timedelta(hours=48)).timestamp()
blocks_history = [b for b in blocks_history if b.get("time_epoch", now_utc.timestamp()) >= cutoff_epoch]

recent_hashes = list(seen_headline_hashes)[-500:]

with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump({
        "seen_hashes": recent_hashes,
        "blocks": blocks_history
    }, f, indent=2)

# ==========================================
# 4. TELEGRAM AUTO-BROADCAST VIA BOT API
# ==========================================
def send_telegram_message(time_str, html_bullets):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        print("ℹ️ Telegram credentials missing. Skipping notification.")
        return

    text_content = html_bullets.replace("<li>", "• ").replace("</li>", "\n")
    message_body = (
        f"🎯 <b>StockVersity High-Conviction Stock Radar & Commentary ({time_str})</b>\n\n"
        f"{text_content}\n"
        f"🌐 <a href='[https://rajjeshrana.github.io/my-news-site/](https://rajjeshrana.github.io/my-news-site/)'>View Live Dashboard</a>"
    )

    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_BOT_TOKEN}/sendMessage"
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
    except Exception as e:
        print(f"⚠️ Telegram request failed: {e}")

if not is_duplicate and ai_bullets_html:
    send_telegram_message(current_time_str, ai_bullets_html)

# ==========================================
# 5. RENDER HTML PAGE WITH STRICT TIME-AWARE LAYOUT
# ==========================================
print("=== Step 3: Formatting HTML Output ===")

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

# High-Conviction Stock Setup Radar Header Card
stock_radar_card = """
<div class="stock-radar-card">
    <div class="stock-radar-header">🔥 High-Conviction Indian Stock Setup Radar (Next Week)</div>
    <div class="stock-radar-grid">
        <div class="stock-item">
            <span class="stock-symbol">NIFTY 50</span>
            <span class="stock-target">Key Zone: 23,200 - 23,600</span>
            <span class="stock-bias bullish">Bullish Consolidation</span>
        </div>
        <div class="stock-item">
            <span class="stock-symbol">BANK NIFTY</span>
            <span class="stock-target">Pivot Support: 49,550</span>
            <span class="stock-bias neutral">Rangebound Focus</span>
        </div>
        <div class="stock-item">
            <span class="stock-symbol">SECTOR IN FOCUS</span>
            <span class="stock-target">Pharma & Defense Majors</span>
            <span class="stock-bias bullish">Institutional Accumulation</span>
        </div>
    </div>
</div>
"""

pivot_table_html = """
<div class="pivot-section">
    <h3>📊 Key Indices Pivot Points & Support/Resistance</h3>
    <table class="pivot-table">
        <thead>
            <tr><th>Index / Asset</th><th>Support (S1)</th><th>Pivot Point (P)</th><th>Resistance (R1)</th><th>Market Stance</th></tr>
        </thead>
        <tbody>
            <tr><td><b>Nifty 50</b></td><td class="support">23,210</td><td class="pivot">23,300</td><td class="resistance">23,390</td><td><span style="color:#2e7d32; font-weight:bold;">Bullish Consolidation</span></td></tr>
            <tr><td><b>Bank Nifty</b></td><td class="support">49,550</td><td class="pivot">49,800</td><td class="resistance">50,050</td><td><span style="color:#1976d2; font-weight:bold;">Rangebound</span></td></tr>
            <tr><td><b>Sensex</b></td><td class="support">76,200</td><td class="pivot">76,500</td><td class="resistance">76,800</td><td><span style="color:#2e7d32; font-weight:bold;">Bullish Consolidation</span></td></tr>
            <tr><td><b>USD / INR</b></td><td class="support">83.35</td><td class="pivot">83.50</td><td class="resistance">83.65</td><td><span style="color:#d32f2f; font-weight:bold;">Rupee Bounded</span></td></tr>
            <tr><td><b>Crude Oil (Brent)</b></td><td class="support">$78.50</td><td class="pivot">$80.20</td><td class="resistance">$82.00</td><td><span style="color:#d32f2f; font-weight:bold;">Cooling Off</span></td></tr>
        </tbody>
    </table>
</div>
"""

ist_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")

# Strict pre-market window check: 7:00 AM (07:00) to 9:30 AM (09:30) IST
current_time_num = now_ist.hour * 100 + now_ist.minute
is_premarket_window = (700 <= current_time_num <= 930)

if is_premarket_window:
    main_dashboard_body = f"""
    {stock_radar_card}
    <h3 style="color:#2e7d32; margin-bottom:15px; font-size:1.3em;">📰 Live Market Commentary (15-Min Stream)</h3>
    {commentary_blocks_html}
    {pivot_table_html}
    """
else:
    main_dashboard_body = f"""
    <h3 style="color:#2e7d32; margin-bottom:15px; font-size:1.3em;">📰 Live Market Commentary (15-Min Stream)</h3>
    {commentary_blocks_html}
    {stock_radar_card}
    {pivot_table_html}
    """

css_styles = """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 920px; margin: 30px auto; padding: 20px; color: #2c3e50; line-height: 1.6; background-color: #f4f6f9; }
    h1 { color: #0d47a1; font-size: 2.1em; margin-bottom: 5px; letter-spacing: -0.5px; }
    .timestamp { color: #64748b; font-weight: 600; font-size: 0.95em; margin-bottom: 15px; }
    .badge { background: #e8f5e9; color: #2e7d32; padding: 6px 14px; border-radius: 20px; font-size: 0.85em; font-weight: bold; display: inline-block; margin-bottom: 20px; border: 1px solid #c8e6c9; }
    hr { border: 0; height: 1px; background: #cbd5e1; margin-bottom: 25px; }
    
    .stock-radar-card { background: linear-gradient(135deg, #0d47a1, #1565c0); color: white; padding: 20px 24px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(13, 71, 161, 0.2); }
    .stock-radar-header { font-size: 1.25em; font-weight: 700; margin-bottom: 15px; letter-spacing: -0.3px; }
    .stock-radar-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
    .stock-item { background: rgba(255, 255, 255, 0.12); padding: 12px 16px; border-radius: 8px; backdrop-filter: blur(5px); }
    .stock-symbol { display: block; font-weight: 700; font-size: 1.05em; color: #ffffff; }
    .stock-target { display: block; font-size: 0.88em; color: #e2e8f0; margin-top: 2px; }
    .stock-bias { display: inline-block; font-size: 0.78em; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-top: 6px; }
    .bullish { background: #2e7d32; color: #ffffff; }
    .neutral { background: #f57c00; color: #ffffff; }

    .time-card { background: #ffffff; border-left: 5px solid #2e7d32; padding: 22px 25px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 22px; }
    .time-header { font-weight: 700; color: #1b5e20; font-size: 1.15em; margin-bottom: 16px; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px; }
    .pivot-section { background: #ffffff; padding: 22px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 22px; }
    .pivot-section h3 { margin-top: 0; color: #0d47a1; font-size: 1.2em; margin-bottom: 15px; }
    .pivot-table { width: 100%; border-collapse: collapse; text-align: left; }
    .pivot-table th, .pivot-table td { padding: 12px 14px; border-bottom: 1px solid #f1f5f9; font-size: 0.95em; }
    .pivot-table th { background-color: #f8fafc; color: #475569; font-weight: 600; }
    .support { color: #d32f2f; font-weight: 600; }
    .pivot { color: #1976d2; font-weight: 600; }
    .resistance { color: #2e7d32; font-weight: 600; }
    ul { padding-left: 0; list-style: none; margin: 0; }
    li { margin-bottom: 18px; font-size: 1em; color: #334155; }
    .news-item-box { display: flex; align-items: flex-start; gap: 16px; background: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; }
    .news-thumb { width: 80px; height: 80px; border-radius: 8px; object-fit: cover; flex-shrink: 0; background-color: #e2e8f0; }
    .news-text-content { flex-grow: 1; font-size: 0.98em; line-height: 1.55; }
    .source-link { color: #0284c7; font-size: 0.82em; font-weight: 600; text-decoration: none; display: inline-block; }
    .source-link:hover { text-decoration: underline; color: #0369a1; }
"""

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <title>Live Market Feed & Stock Watchlist Terminal</title>
    <style>
{css_styles}
    </style>
</head>
<body>
    <h1>Live Market Feed & Stock Watchlist Terminal</h1>
    <div class="timestamp">🕒 Last Updated: {ist_time}</div>
    <div class="badge">🔴 Two-Pass LLM Quantitative Stream</div>
    <hr>
    {main_dashboard_body}
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("✅ Successfully generated index.html with Two-Pass LLM integration!")