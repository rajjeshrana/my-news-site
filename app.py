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
    "🎯 Breakout Stock Setups": [
        "https://news.google.com/rss/search?q=top+stocks+to+buy+today+target+stoploss+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://news.google.com/rss/search?q=stock+market+recommendations+September+2026+when:3d&hl=en-IN&gl=IN&ceid=IN:en",
        "https://www.business-standard.com/rss/markets-106.rss",
        "https://www.financialexpress.com/market/feed/",
        "https://www.livemint.com/rss/markets"
    ],
    "⚡ Breaking Flashes & Geopolitics": [
        "https://news.google.com/rss/search?q=site:twitter.com+OR+site:x.com+Trump+Iran+war+when:2d&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=financialjuice+OR+DeitaOne+OR+ForexLive+breaking+when:2d&hl=en-US&gl=US&ceid=US:en",
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
is_weekend = now_ist.weekday() in [5, 6]  # 5 = Saturday, 6 = Sunday

if is_weekend:
    current_time_str = now_ist.strftime("%b %d, %Y") + " (Weekend Stock & Macro Radar)"
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
            for entry in feed.entries[:6]:
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
        category_data[cat_name] = cleaned_titles[:6]
        category_images[cat_name] = cat_img or FALLBACK_IMAGE
        category_links[cat_name] = first_link or "https://news.google.com"

is_duplicate = (new_items_count == 0)

# ==========================================
# 3. LLM INFOGRAPHIC CARD GENERATION
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
    print("=== Step 2: Generating Deep Infographic Stock Cards & Weekly Analysis ===")
    prompt_text = "\n".join([f"[{cat}]: " + " | ".join(items) for cat, items in category_data.items()])
    
    pass1_prompt = f"""
You are an institutional research desk analyst preparing a full weekend stock breakdown report for Indian equity markets.
Parse the provided market news and extract detailed stock recommendations and technical setups:

STRICT INSTRUCTIONS:
1. Extract 3-4 specific Indian stock recommendations (e.g., Apar Industries, BEML, Aegis Vopak Terminals, Mankind Pharma, Emcure Pharma, VA Tech Wabag).
2. For EACH stock, extract:
   - Ticker Symbol
   - Action (BUY / ACCUMULATE)
   - Buy Range
   - Stop Loss
   - Target Price
   - Full Technical/Fundamental Rationale (2-3 detailed sentences covering moving averages, RSI/MACD breakouts, or sectoral tailwinds).

3. Also synthesize:
   - Geopolitical & Macro Risk Wire (2-3 detailed sentences on Trump, Iran war, US sanctions, central banks).
   - Indian Equity Index Outlook (2-3 detailed sentences on Nifty 23,200-23,600 levels, Bank Nifty, and FII/DII activity).
   - Forex & Commodity Boundaries (2 detailed sentences on Crude Oil $78-$82, Gold, USD/INR).

Input Headlines:
{prompt_text}
"""
    extracted_intelligence = query_groq_llm(pass1_prompt) or prompt_text

    pass2_prompt = f"""
Convert the extracted market intelligence into 5 distinct, high-density HTML <li> tags for terminal card rendering:

Output strictly 5 HTML <li> tags formatted as follows:

<li>
<b>🎯 Top Breakout Stock Recommendations:</b><br>
<b>• APARIND (Apar Industries):</b> Buy Range: ₹17,750–₹17,800 | Stop Loss: ₹16,528 | Target: ₹19,200–₹19,300.<br>
<i>Technical Rationale:</i> Displays high relative strength despite broader market correction. Bullish oversold PMOX reading and 14-day RSI crossover confirm momentum resumption.<br>
<b>• BEML:</b> Buy Range: ₹2,000–₹2,010 | Stop Loss: ₹1,920 | Target: ₹2,120–₹2,130.<br>
<i>Technical Rationale:</i> Aerospace and defense manufacturing major retesting key 40-brick Renko moving average, offering favorable risk-reward following short-term consolidation breakout.<br>
<b>• AEGISVOPAK (Aegis Vopak Terminals):</b> Buy Range: ₹305–₹308 | Stop Loss: ₹291 | Target: ₹335–₹340.<br>
<i>Technical Rationale:</i> 52-week high breakout backed by surge in trading volume. Relative strength chart indicates outperformance against Nifty 500.
</li>

<li>
<b>⚡ Breaking Flashes & Geopolitics:</b><br>
Geopolitical risk premiums remain elevated as global energy markets track US-Iran war developments and White House military movements in Greenland. Sanctions pressure on Russia intensifies as central banks monitor oil price shocks.
</li>

<li>
<b>🇮🇳 Indian Stock Market Outlook:</b><br>
Nifty 50 approaches a key historical demand confluence near 23,200–23,000, corresponding to the 61.8% Fibonacci retracement zone. While FII outflows weigh on large-cap sentiment, aggressive DII buying provides strong underlying support for select pharma and defense majors.
</li>

<li>
<b>🌍 US & Global Markets:</b><br>
Wall Street benchmarks display controlled consolidation as treasury yields hold near 4.90%. Investors evaluate Federal Reserve policy commentary ahead of upcoming US CPI inflation prints and global tech earnings.
</li>

<li>
<b>🛢️ Forex & Commodities:</b><br>
Brent Crude fluctuates near $80.20/bbl due to Middle East supply disruption concerns. USD/INR trades in a tight corridor between 83.35 and 83.65 as RBI interventions stabilize domestic currency volatility.
</li>

Extracted Intelligence:
{extracted_intelligence}
"""
    ai_bullets_html = query_groq_llm(pass2_prompt)

    if not ai_bullets_html:
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
                    <div style="margin-top: 10px;">
                        <a href="{source_link}" target="_blank" class="source-link">🔗 Read Full Research Report & Source Wire</a>
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

    text_content = html_bullets.replace("<li>", "• ").replace("</li>", "\n\n").replace("<br>", "\n")
    message_body = (
        f"🔥 <b>StockVersity Weekend Stock Radar & Detailed Commentary ({time_str})</b>\n\n"
        f"{text_content}\n"
        f"🌐 <a href='[https://rajjeshrana.github.io/my-news-site/](https://rajjeshrana.github.io/my-news-site/)'>View Full Terminal Dashboard</a>"
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
            print("✅ Successfully broadcasted detailed update to Telegram!")
    except Exception as e:
        print(f"⚠️ Telegram request failed: {e}")

if not is_duplicate and ai_bullets_html:
    send_telegram_message(current_time_str, ai_bullets_html)

# ==========================================
# 5. RENDER HTML PAGE WITH INFOGRAPHIC STYLING
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

# Infographic Stock Setup Banner
stock_radar_card = """
<div class="stock-radar-card">
    <div class="stock-radar-header">🔥 High-Conviction Breakout Stocks & Targets (Next Week)</div>
    <div class="stock-radar-grid">
        <div class="stock-item">
            <span class="stock-symbol">APARIND</span>
            <span class="stock-target">Buy: ₹17,750 | Target: ₹19,200</span>
            <span class="stock-bias bullish">RSI & PMOX Crossover</span>
        </div>
        <div class="stock-item">
            <span class="stock-symbol">BEML</span>
            <span class="stock-target">Buy: ₹2,000 | Target: ₹2,120</span>
            <span class="stock-bias bullish">40-Brick Renko Retest</span>
        </div>
        <div class="stock-item">
            <span class="stock-symbol">AEGISVOPAK</span>
            <span class="stock-target">Buy: ₹305 | Target: ₹335</span>
            <span class="stock-bias bullish">52-Week High Breakout</span>
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

css_styles = """
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 940px; margin: 30px auto; padding: 20px; color: #1e293b; line-height: 1.6; background-color: #f8fafc; }
    h1 { color: #0f172a; font-size: 2.2em; margin-bottom: 5px; letter-spacing: -0.5px; }
    .timestamp { color: #64748b; font-weight: 600; font-size: 0.95em; margin-bottom: 15px; }
    .badge { background: #dcfce7; color: #15803d; padding: 6px 14px; border-radius: 20px; font-size: 0.85em; font-weight: bold; display: inline-block; margin-bottom: 20px; border: 1px solid #bbf7d0; }
    hr { border: 0; height: 1px; background: #e2e8f0; margin-bottom: 25px; }
    
    .stock-radar-card { background: linear-gradient(135deg, #1e3a8a, #2563eb); color: white; padding: 22px 26px; border-radius: 14px; margin-bottom: 25px; box-shadow: 0 10px 25px -5px rgba(37, 99, 235, 0.3); }
    .stock-radar-header { font-size: 1.3em; font-weight: 700; margin-bottom: 16px; letter-spacing: -0.3px; }
    .stock-radar-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
    .stock-item { background: rgba(255, 255, 255, 0.12); padding: 14px 18px; border-radius: 10px; backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.2); }
    .stock-symbol { display: block; font-weight: 800; font-size: 1.1em; color: #ffffff; }
    .stock-target { display: block; font-size: 0.9em; color: #f1f5f9; margin-top: 4px; }
    .stock-bias { display: inline-block; font-size: 0.78em; font-weight: 700; padding: 3px 10px; border-radius: 6px; margin-top: 8px; }
    .bullish { background: #16a34a; color: #ffffff; }

    .time-card { background: #ffffff; border-left: 6px solid #16a34a; padding: 24px 28px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); margin-bottom: 24px; border-top: 1px solid #f1f5f9; border-right: 1px solid #f1f5f9; border-bottom: 1px solid #f1f5f9; }
    .time-header { font-weight: 700; color: #15803d; font-size: 1.2em; margin-bottom: 18px; border-bottom: 1px solid #f1f5f9; padding-bottom: 10px; }
    .pivot-section { background: #ffffff; padding: 24px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.04); margin-bottom: 24px; }
    .pivot-section h3 { margin-top: 0; color: #1e3a8a; font-size: 1.25em; margin-bottom: 16px; }
    .pivot-table { width: 100%; border-collapse: collapse; text-align: left; }
    .pivot-table th, .pivot-table td { padding: 14px 16px; border-bottom: 1px solid #f1f5f9; font-size: 0.98em; }
    .pivot-table th { background-color: #f8fafc; color: #475569; font-weight: 700; }
    .support { color: #dc2626; font-weight: 600; }
    .pivot { color: #2563eb; font-weight: 600; }
    .resistance { color: #16a34a; font-weight: 600; }
    ul { padding-left: 0; list-style: none; margin: 0; }
    li { margin-bottom: 20px; font-size: 1.02em; color: #334155; }
    .news-item-box { display: flex; align-items: flex-start; gap: 18px; background: #ffffff; padding: 16px; border-radius: 10px; border: 1px solid #e2e8f0; }
    .news-thumb { width: 90px; height: 90px; border-radius: 10px; object-fit: cover; flex-shrink: 0; background-color: #e2e8f0; }
    .news-text-content { flex-grow: 1; font-size: 1em; line-height: 1.6; }
    .source-link { color: #0284c7; font-size: 0.85em; font-weight: 700; text-decoration: none; display: inline-block; }
    .source-link:hover { text-decoration: underline; color: #0369a1; }
"""

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <title>Weekend Stock Radar & Market Terminal</title>
    <style>
{css_styles}
    </style>
</head>
<body>
    <h1>Weekend Stock Radar & Market Terminal</h1>
    <div class="timestamp">🕒 Last Updated: {ist_time}</div>
    <div class="badge">🔴 Weekend Detailed Stock Research Mode</div>
    <hr>
    {stock_radar_card}
    <h3 style="color:#16a34a; margin-bottom:18px; font-size:1.35em;">📰 Deep Stock Breakdown & Macro Commentary</h3>
    {commentary_blocks_html}
    {pivot_table_html}
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("✅ Successfully generated index.html with Infographic Stock Cards!")