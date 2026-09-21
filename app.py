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

FALLBACK_IMAGE = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=800&q=80"

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

formatted_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")

if is_weekend:
    current_time_str = f"{formatted_time} (Weekend Stock & Macro Radar)"
else:
    current_time_str = f"{formatted_time} (Live Market Stream)"

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
        category_links[cat_name] = first_link or "https://rajjeshrana.github.io/my-news-site/"

link_featured = category_links.get("Indian Stock Market", "https://rajjeshrana.github.io/my-news-site/")
link_breakouts = category_links.get("🎯 Breakout Stock Setups", "https://rajjeshrana.github.io/my-news-site/")
link_macro = category_links.get("⚡ Breaking Flashes & Geopolitics", "https://rajjeshrana.github.io/my-news-site/")

# ==========================================
# 3. ADVANCED LLM INFOGRAPHIC CARD GENERATION
# ==========================================
ai_bullets_html = None

def query_groq_llm(prompt_str):
    if not GROQ_API_KEY:
        print("⚠️ GROQ_API_KEY environment variable is empty or missing.")
        return None
    groq_url = "https://api.groq.com/openai/v1/chat/completions"
    groq_headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    models_to_try = [
        "llama-3.3-70b-versatile", 
        "llama-3.1-8b-instant", 
        "llama-3.2-11b-vision-preview", 
        "llama3-8b-8192"
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

if category_data:
    print("=== Step 2: Generating Deep Light-Theme Cards & Macro Intelligence ===")
    prompt_text = "\n".join([f"[{cat}]: " + " | ".join(items) for cat, items in category_data.items()])
    
    pass1_prompt = f"""
You are an institutional research desk analyst preparing a full stock breakdown report for Indian equity markets.
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
<div class="card-badge category-stock">Breakout Radar</div>
<h3 class="card-title-heading">🎯 High-Conviction Breakout Recommendations</h3>
<div class="stock-breakdown-box">
  <div class="stock-row"><span class="ticker">APARIND</span> <span class="tag buy">BUY: ₹17,750–₹17,800</span> <span class="tag target">TARGET: ₹19,200</span> <span class="tag sl">SL: ₹16,528</span></div>
  <p class="rationale">Demonstrates strong relative strength despite broader market volatility. Bullish oversold PMOX reading combined with a 14-day RSI crossover signal momentum resumption.</p>
</div>
<div class="stock-breakdown-box">
  <div class="stock-row"><span class="ticker">BEML</span> <span class="tag buy">BUY: ₹2,000–₹2,010</span> <span class="tag target">TARGET: ₹2,120</span> <span class="tag sl">SL: ₹1,920</span></div>
  <p class="rationale">Defense manufacturing major retesting a key 40-brick Renko moving average, presenting a favorable risk-to-reward ratio following short-term base building.</p>
</div>
<div class="stock-breakdown-box">
  <div class="stock-row"><span class="ticker">AEGISVOPAK</span> <span class="tag buy">BUY: ₹305–₹308</span> <span class="tag target">TARGET: ₹335</span> <span class="tag sl">SL: ₹291</span></div>
  <p class="rationale">52-week high breakout accompanied by a substantial volume surge. Outperforming the Nifty 500 index across multiple timeframes.</p>
</div>
</li>

<li>
<div class="card-badge category-geo">Geopolitics</div>
<h3 class="card-title-heading">⚡ Breaking Flashes & Geopolitical Wire</h3>
<p class="card-body-text">Geopolitical risk premiums remain elevated as global energy markets monitor ongoing Middle East developments and White House military presence discussions in Greenland. Sanctions pressure on Russia continues to intensify as central banks track potential supply disruptions.</p>
</li>

<li>
<div class="card-badge category-india">Indian Equities</div>
<h3 class="card-title-heading">🇮🇳 Indian Equities & Nifty 50 Index Outlook</h3>
<p class="card-body-text">Nifty 50 approaches a critical historical demand confluence near 23,200–23,000, aligning with the 61.8% Fibonacci retracement level. While FII selling pressures top-tier financials, aggressive domestic institutional (DII) inflows support select defense, healthcare, and capital goods counters.</p>
</li>

<li>
<div class="card-badge category-global">Global Markets</div>
<h3 class="card-title-heading">🌍 US & Global Macro Intelligence</h3>
<p class="card-body-text">Wall Street benchmarks consolidate as 10-year Treasury yields hold near 4.90%. Market participants evaluate Federal Reserve interest rate guidance ahead of key US CPI inflation prints and upcoming mega-cap tech earnings announcements.</p>
</li>

<li>
<div class="card-badge category-comm">Forex & Energy</div>
<h3 class="card-title-heading">🛢️ Forex & Energy Market Boundaries</h3>
<p class="card-body-text">Brent Crude holds near $80.20/bbl supported by regional geopolitical risk. USD/INR trades within a narrow 83.35–83.65 corridor, maintained by active Reserve Bank of India foreign exchange liquidity intervention.</p>
</li>

Extracted Intelligence:
{extracted_intelligence}
"""
    ai_bullets_html = query_groq_llm(pass2_prompt)

    if not ai_bullets_html:
        items_list = []
        for cat, items in category_data.items():
            combined_text = " ".join(items)
            items_list.append(f"<li><div class='card-badge category-stock'>{cat}</div><h3 class='card-title-heading'>{cat}</h3><p class='card-body-text'>{combined_text}</p></li>")
        ai_bullets_html = "\n".join(items_list)

    web_bullets_list = []
    bullets_matches = re.findall(r'<li>(.*?)</li>', ai_bullets_html, re.DOTALL)
    
    cat_keys = list(category_images.keys())
    for idx, b_text in enumerate(bullets_matches):
        cat_key = cat_keys[idx if idx < len(cat_keys) else 0]
        img_url = category_images.get(cat_key, FALLBACK_IMAGE)
        source_link = category_links.get(cat_key, "https://rajjeshrana.github.io/my-news-site/")
        
        card_item = f"""
        <div class="trending-card">
            <a href="{source_link}" target="_blank" class="card-image-link">
                <div class="card-image-wrap" style="background-image: url('{img_url}');">
                    <div class="image-overlay"></div>
                </div>
            </a>
            <div class="card-content-wrap">
                {b_text}
                <div class="card-footer">
                    <span class="meta-author">👤 StockVersity Desk</span>
                    <a href="{source_link}" target="_blank" class="read-more-link">Read Full Wire ➔</a>
                </div>
            </div>
        </div>
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
print("=== Step 3: Executing Telegram Broadcast ===")
def send_telegram_message(time_str, html_bullets):
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is empty. Check GitHub Secrets.")
        return
    if not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_CHAT_ID is empty. Check GitHub Secrets.")
        return

    text_content = html_bullets.replace("<li>", "• ").replace("</li>", "\n\n").replace("<br>", "\n")
    text_content = re.sub(r'<div[^>]*>', '', text_content).replace('</div>', '')
    text_content = re.sub(r'<span[^>]*>', '', text_content).replace('</span>', '')
    text_content = re.sub(r'<h3[^>]*>', '<b>', text_content).replace('</h3>', '</b>\n')
    
    message_body = (
        f"🔥 <b>StockVersity Light Terminal Intelligence Update</b>\n"
        f"⏱️ <i>{time_str}</i>\n\n"
        f"{text_content}\n"
        f"🌐 <a href='https://rajjeshrana.github.io/my-news-site/'>Open Dashboard</a>"
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
            print(f"⚠️ Telegram API Error Code {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ Telegram Request Exception: {e}")

if ai_bullets_html:
    send_telegram_message(current_time_str, ai_bullets_html)

# ==========================================
# 5. RENDER HTML PAGE WITH DETAILED BRIEFING
# ==========================================
print("=== Step 4: Formatting Light Theme Detailed Briefing Layout ===")

latest_block = blocks_history[0] if blocks_history else {}
latest_cards_html = latest_block.get("html_content", "")
latest_timestamp = latest_block.get("timestamp", formatted_time)
latest_raw_content = latest_block.get("raw_text_content", "")

# Extract pure <li> elements from raw intelligence to render inside Morning Briefing Box
briefing_bullets = re.findall(r'<li>(.*?)</li>', latest_raw_content, re.DOTALL)
briefing_inner_html = "".join([f"<div class='briefing-item-card'>{b}</div>" for b in briefing_bullets]) if briefing_bullets else "<p class='briefing-desc'>Synchronizing latest market intelligence...</p>"

# Full Pre-Market Briefing Card with Embedded Intelligence, Levels & Stock Picks
morning_briefing_banner = f"""
<div class="morning-briefing-card">
    <div class="briefing-header">
        <span class="yellow-badge">MORNING BRIEFING</span>
        <span class="briefing-time">🌅 {formatted_time}</span>
    </div>
    <h2 class="briefing-title">Pre-Market Market Setup & Institutional Intelligence Briefing</h2>
    <div class="briefing-body-grid">
        {briefing_inner_html}
    </div>
</div>
"""

featured_mosaic_html = f"""
<div class="featured-mosaic-grid">
    <a href="{link_featured}" target="_blank" class="mosaic-link large-hero">
        <div class="mosaic-item" style="background-image: url('https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80');">
            <div class="mosaic-overlay"></div>
            <div class="mosaic-content">
                <span class="yellow-badge">FEATURED RESEARCH</span>
                <span class="mosaic-date">⏱️ {latest_timestamp}</span>
                <h2 class="mosaic-title">New Research: Institutional Flows, Nifty Confluence Zones & Weekly Breakouts</h2>
            </div>
        </div>
    </a>
    
    <a href="{link_breakouts}" target="_blank" class="mosaic-link medium-top">
        <div class="mosaic-item" style="background-image: url('https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=800&q=80');">
            <div class="mosaic-overlay"></div>
            <div class="mosaic-content">
                <span class="yellow-badge">BREAKOUTS</span>
                <h3 class="mosaic-title-sm">APARIND, BEML & Aegis Vopak Lead Momentum Charts</h3>
            </div>
        </div>
    </a>

    <a href="{link_macro}" target="_blank" class="mosaic-link medium-bottom">
        <div class="mosaic-item" style="background-image: url('https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?auto=format&fit=crop&w=800&q=80');">
            <div class="mosaic-overlay"></div>
            <div class="mosaic-content">
                <span class="yellow-badge">GLOBAL MACRO</span>
                <h3 class="mosaic-title-sm">Geopolitical Flashes: Crude Oil Holds Near $80 as Fed Tracks CPI</h3>
            </div>
        </div>
    </a>
</div>
"""

pivot_table_html = """
<div class="pivot-section">
    <div class="section-title-wrap">
        <span class="yellow-badge">BENCHMARKS</span>
        <h2 class="section-heading-text">Key Indices Pivot Matrix</h2>
    </div>
    <table class="pivot-table">
        <thead>
            <tr><th>Index / Asset</th><th>Support (S1)</th><th>Pivot Point (P)</th><th>Resistance (R1)</th><th>Market Stance</th></tr>
        </thead>
        <tbody>
            <tr><td><b>Nifty 50</b></td><td class="support">23,210</td><td class="pivot">23,300</td><td class="resistance">23,390</td><td><span class="stance-badge bullish">Bullish Consolidation</span></td></tr>
            <tr><td><b>Bank Nifty</b></td><td class="support">49,550</td><td class="pivot">49,800</td><td class="resistance">50,050</td><td><span class="stance-badge rangebound">Rangebound</span></td></tr>
            <tr><td><b>Sensex</b></td><td class="support">76,200</td><td class="pivot">76,500</td><td class="resistance">76,800</td><td><span class="stance-badge bullish">Bullish Consolidation</span></td></tr>
            <tr><td><b>USD / INR</b></td><td class="support">83.35</td><td class="pivot">83.50</td><td class="resistance">83.65</td><td><span class="stance-badge bearish">Rupee Bounded</span></td></tr>
            <tr><td><b>Crude Oil (Brent)</b></td><td class="support">$78.50</td><td class="pivot">$80.20</td><td class="resistance">$82.00</td><td><span class="stance-badge bearish">Cooling Off</span></td></tr>
        </tbody>
    </table>
</div>
"""

ist_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")

css_styles = """
    * { box-sizing: border-box; }
    body { 
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
        max-width: 1200px; 
        margin: 0 auto; 
        padding: 20px; 
        color: #1e293b; 
        line-height: 1.5; 
        background-color: #f8fafc; 
    }

    .top-header-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 15px;
        border-bottom: 2px solid #e2e8f0;
        margin-bottom: 25px;
    }

    .brand-title {
        font-size: 2.2em;
        font-weight: 900;
        letter-spacing: -1px;
        color: #0f172a;
        text-transform: uppercase;
    }

    .brand-title span { color: #d97706; }

    .header-time {
        font-size: 0.9em;
        color: #64748b;
        font-weight: 600;
    }

    /* DETAILED MORNING BRIEFING BANNER */
    .morning-briefing-card {
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-left: 6px solid #d97706;
        border-radius: 8px;
        padding: 22px 26px;
        margin-bottom: 30px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.04);
    }

    .briefing-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 8px;
    }

    .briefing-time {
        font-size: 0.88em;
        color: #64748b;
        font-weight: 700;
    }

    .briefing-title {
        font-size: 1.4em;
        font-weight: 800;
        color: #0f172a;
        margin: 0 0 16px 0;
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 10px;
    }

    .briefing-body-grid {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .briefing-item-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 16px 18px;
        border-radius: 8px;
    }

    /* CLICKABLE MOSAIC WRAPPERS */
    .featured-mosaic-grid {
        display: grid;
        grid-template-columns: 2fr 1fr;
        grid-template-rows: 220px 220px;
        gap: 15px;
        margin-bottom: 40px;
    }

    .mosaic-link {
        display: block;
        text-decoration: none;
        overflow: hidden;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }

    .mosaic-link:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.18);
    }

    .mosaic-link.large-hero { grid-row: span 2; }

    .mosaic-item {
        position: relative;
        height: 100%;
        width: 100%;
        background-size: cover;
        background-position: center;
    }

    .mosaic-overlay {
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.2) 0%, rgba(15, 23, 42, 0.88) 90%);
    }

    .mosaic-content {
        position: absolute;
        bottom: 0; left: 0; right: 0;
        padding: 22px;
        z-index: 2;
    }

    .yellow-badge {
        background-color: #d97706;
        color: #ffffff;
        font-size: 0.72em;
        font-weight: 800;
        text-transform: uppercase;
        padding: 4px 10px;
        border-radius: 3px;
        display: inline-block;
        margin-bottom: 8px;
        letter-spacing: 0.5px;
    }

    .mosaic-date {
        color: #e2e8f0;
        font-size: 0.82em;
        margin-left: 8px;
        font-weight: 600;
    }

    .mosaic-title {
        font-size: 1.65em;
        font-weight: 800;
        color: #ffffff;
        margin: 6px 0 0 0;
        line-height: 1.3;
    }

    .mosaic-title-sm {
        font-size: 1.1em;
        font-weight: 700;
        color: #ffffff;
        margin: 4px 0 0 0;
        line-height: 1.3;
    }

    .section-header-bar {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 25px;
    }

    .section-main-heading {
        font-size: 2em;
        font-weight: 800;
        color: #94a3b8;
        letter-spacing: -0.5px;
        margin: 0;
    }

    .section-main-heading b { color: #0f172a; }

    .trending-grid-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
        gap: 22px;
        margin-bottom: 40px;
    }

    .trending-card {
        background-color: #ffffff;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.04);
        display: flex;
        flex-direction: column;
    }

    .card-image-link { display: block; }

    .card-image-wrap {
        height: 180px;
        background-size: cover;
        background-position: center;
        position: relative;
    }

    .image-overlay {
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.4) 100%);
    }

    .card-content-wrap {
        padding: 20px;
        flex-grow: 1;
        display: flex;
        flex-direction: column;
    }

    .card-badge {
        display: inline-block;
        font-size: 0.72em;
        font-weight: 800;
        text-transform: uppercase;
        padding: 3px 8px;
        border-radius: 3px;
        margin-bottom: 10px;
    }

    .category-stock { background-color: #d97706; color: #fff; }
    .category-geo { background-color: #dc2626; color: #fff; }
    .category-india { background-color: #0284c7; color: #fff; }
    .category-global { background-color: #9333ea; color: #fff; }
    .category-comm { background-color: #16a34a; color: #fff; }

    .card-title-heading {
        font-size: 1.15em;
        font-weight: 800;
        color: #0f172a;
        margin: 0 0 12px 0;
        line-height: 1.35;
    }

    .card-body-text {
        font-size: 0.92em;
        color: #334155;
        line-height: 1.6;
        margin: 0 0 15px 0;
    }

    .stock-breakdown-box {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        padding: 10px 12px;
        border-radius: 6px;
        margin-bottom: 10px;
    }

    .stock-row {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
        font-size: 0.9em;
        margin-bottom: 4px;
    }

    .ticker { font-weight: 800; color: #0f172a; }

    .tag {
        font-size: 0.72em;
        font-weight: 800;
        padding: 2px 6px;
        border-radius: 3px;
    }

    .tag.buy { background: #e0f2fe; color: #0369a1; }
    .tag.target { background: #dcfce7; color: #15803d; }
    .tag.sl { background: #fee2e2; color: #b91c1c; }

    .rationale {
        font-size: 0.85em;
        color: #475569;
        margin: 0;
        line-height: 1.45;
    }

    .card-footer {
        margin-top: auto;
        padding-top: 14px;
        border-top: 1px solid #f1f5f9;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.82em;
    }

    .meta-author { color: #64748b; font-weight: 600; }
    .read-more-link { color: #d97706; font-weight: 700; text-decoration: none; }
    .read-more-link:hover { text-decoration: underline; }

    .pivot-section {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.04);
        margin-bottom: 30px;
    }

    .section-title-wrap { margin-bottom: 15px; }

    .section-heading-text {
        font-size: 1.3em;
        font-weight: 800;
        color: #0f172a;
        margin: 4px 0 0 0;
    }

    .pivot-table { width: 100%; border-collapse: collapse; text-align: left; }
    .pivot-table th, .pivot-table td { padding: 12px 14px; border-bottom: 1px solid #f1f5f9; font-size: 0.92em; }
    .pivot-table th { background-color: #f8fafc; color: #64748b; font-weight: 700; }

    .support { color: #dc2626; font-weight: 700; }
    .pivot { color: #2563eb; font-weight: 700; }
    .resistance { color: #16a34a; font-weight: 700; }

    .stance-badge {
        font-size: 0.78em;
        font-weight: 800;
        padding: 3px 8px;
        border-radius: 3px;
    }

    .stance-badge.bullish { background: #dcfce7; color: #15803d; }
    .stance-badge.rangebound { background: #fef3c7; color: #b45309; }
    .stance-badge.bearish { background: #fee2e2; color: #b91c1c; }

    @media (max-width: 850px) {
        .featured-mosaic-grid {
            grid-template-columns: 1fr;
            grid-template-rows: auto;
        }
        .mosaic-link.large-hero { grid-row: auto; height: 260px; }
        .mosaic-link { height: 180px; }
    }
"""

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <title>StockVersity Terminal | Detailed Morning Intelligence</title>
    <style>
{css_styles}
    </style>
</head>
<body>
    <div class="top-header-bar">
        <div class="brand-title">Stock<span>Versity</span></div>
        <div class="header-time">🕒 {ist_time}</div>
    </div>

    {morning_briefing_banner}

    {featured_mosaic_html}

    <div class="section-header-bar">
        <span class="yellow-badge">DON'T MISS</span>
        <h2 class="section-main-heading"><b>Trending</b> Now</h2>
    </div>

    <div class="trending-grid-container">
        {latest_cards_html}
    </div>

    {pivot_table_html}
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("✅ Successfully generated detailed Morning Briefing index.html!")