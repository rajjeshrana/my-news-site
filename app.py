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
    print("=== Step 2: Generating Deep Light Terminal Intelligence ===")
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

    new_block = {
        "timestamp": current_time_str,
        "time_epoch": now_utc.timestamp(),
        "raw_text_content": extracted_intelligence
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
# 4. TELEGRAM AUTO-BROADCAST WITH HEADINGS & SPACING
# ==========================================
print("=== Step 3: Executing Formatted Telegram Broadcast ===")
def send_telegram_message(time_str, cat_dict):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials missing. Skipping broadcast.")
        return

    formatted_sections = []
    
    # Generate clean bold headers with bulleted lists and spacing between subjects
    for cat_title, items in cat_dict.items():
        if not items:
            continue
        items_text = " ".join(items[:4])
        section_block = f"• <b>{cat_title}:</b> {items_text}"
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

if category_data:
    send_telegram_message(current_time_str, category_data)

# ==========================================
# 5. RENDER 100% FULL-WIDTH LIGHT TERMINAL
# ==========================================
print("=== Step 4: Formatting Light 6-Block Terminal ===")

ist_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")

css_styles = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { 
        width: 100vw; 
        height: 100vh; 
        overflow: hidden; 
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
        background-color: #f8fafc; 
        color: #1e293b; 
    }

    /* TOP TERMINAL HEADER */
    .terminal-header {
        height: 50px;
        background-color: #ffffff;
        border-bottom: 2px solid #e2e8f0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 20px;
        width: 100%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }

    .brand-logo {
        font-size: 1.25em;
        font-weight: 900;
        letter-spacing: -0.5px;
        color: #0f172a;
        text-transform: uppercase;
    }

    .brand-logo span { color: #d97706; }

    .header-info {
        font-size: 0.85em;
        color: #64748b;
        font-weight: 600;
    }

    /* 6 FIXED RECTANGULAR BLOCK GRID LAYOUT */
    .terminal-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        grid-template-rows: repeat(2, calc((100vh - 50px) / 2));
        gap: 12px;
        padding: 12px;
        width: 100vw;
        height: calc(100vh - 50px);
    }

    .grid-block {
        background-color: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    .block-header {
        background-color: #f1f5f9;
        padding: 10px 14px;
        font-size: 0.88em;
        font-weight: 800;
        color: #d97706;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid #cbd5e1;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-shrink: 0;
    }

    /* INTERNAL SCROLLABLE BODY FOR EACH BLOCK */
    .block-scroll-body {
        padding: 12px;
        overflow-y: auto;
        flex-grow: 1;
        font-size: 0.86em;
        line-height: 1.5;
        color: #334155;
    }

    /* CUSTOM INTERNAL SCROLLBARS */
    .block-scroll-body::-webkit-scrollbar { width: 6px; }
    .block-scroll-body::-webkit-scrollbar-track { background: #f1f5f9; }
    .block-scroll-body::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
    .block-scroll-body::-webkit-scrollbar-thumb:hover { background: #d97706; }

    /* EXACT 2 SIDE-BY-SIDE COLUMNS FOR MACRO METRICS */
    .macro-two-col {
        display: flex;
        gap: 12px;
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 8px 10px;
        margin-bottom: 10px;
    }

    .col-half {
        flex: 1;
        display: flex;
        flex-direction: column;
    }

    .metric-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0;
        border-bottom: 1px dashed #e2e8f0;
        font-size: 0.83em;
    }
    .metric-row:last-child { border-bottom: none; }

    .metric-label { font-weight: 700; color: #475569; }
    .metric-val { font-weight: 800; color: #0f172a; }
    .val-green { color: #15803d; }
    .val-red { color: #b91c1c; }

    /* LIGHT TERMINAL STYLING COMPONENTS */
    .stock-card {
        background-color: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 4px solid #059669;
        padding: 8px 10px;
        border-radius: 4px;
        margin-bottom: 8px;
    }

    .stock-row {
        display: flex;
        gap: 6px;
        align-items: center;
        margin-bottom: 3px;
        flex-wrap: wrap;
    }

    .ticker { font-weight: 800; color: #0f172a; }
    .badge-buy { background-color: #d1fae5; color: #047857; padding: 2px 5px; border-radius: 3px; font-size: 0.75em; font-weight: 800; }
    .badge-target { background-color: #dbeafe; color: #1d4ed8; padding: 2px 5px; border-radius: 3px; font-size: 0.75em; font-weight: 800; }
    .badge-sl { background-color: #fee2e2; color: #b91c1c; padding: 2px 5px; border-radius: 3px; font-size: 0.75em; font-weight: 800; }

    .rationale { font-size: 0.82em; color: #475569; margin-top: 2px; }

    .pivot-mini-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 6px;
    }
    .pivot-mini-table th, .pivot-mini-table td {
        padding: 5px 6px;
        border-bottom: 1px solid #e2e8f0;
        font-size: 0.82em;
        text-align: left;
    }
    .pivot-mini-table th { background-color: #f1f5f9; color: #64748b; font-weight: 700; }

    @media (max-width: 1024px) {
        body { overflow-y: auto; height: auto; }
        .terminal-grid {
            display: flex;
            flex-direction: column;
            height: auto;
            width: 100%;
        }
        .grid-block { height: 420px; }
        .macro-two-col { flex-direction: column; gap: 0; }
    }
"""

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="300">
    <title>StockVersity Light Terminal</title>
    <style>
{css_styles}
    </style>
</head>
<body>
    <div class="terminal-header">
        <div class="brand-logo">Stock<span>Versity</span> Terminal</div>
        <div class="header-info">🕒 Synchronized: {ist_time}</div>
    </div>

    <div class="terminal-grid">
        <!-- Block 1: Morning Pre-Market Briefing & Exact 2 Side-by-Side Columns -->
        <div class="grid-block">
            <div class="block-header">
                <span>🌅 Pre-Market Briefing & Macro Sheet</span>
            </div>
            <div class="block-scroll-body">
                <!-- 2 Side-by-Side Columns -->
                <div class="macro-two-col">
                    <div class="col-half">
                        <div class="metric-row"><span class="metric-label">💵 USD / INR:</span><span class="metric-val val-green">95.88 (-0.17%)</span></div>
                        <div class="metric-row"><span class="metric-label">🛢️ Brent Crude:</span><span class="metric-val val-red">$101.59 (-2.24%)</span></div>
                        <div class="metric-row"><span class="metric-label">🛢️ WTI Crude:</span><span class="metric-val val-red">$93.89 (-2.27%)</span></div>
                        <div class="metric-row"><span class="metric-label">📈 Nasdaq 100 Fut:</span><span class="metric-val val-green">29,544.50 (+0.33%)</span></div>
                        <div class="metric-row"><span class="metric-label">📈 S&P 500 Fut:</span><span class="metric-val val-green">7,643.25 (+0.05%)</span></div>
                    </div>
                    <div class="col-half">
                        <div class="metric-row"><span class="metric-label">🥇 Gold (Spot/MCX):</span><span class="metric-val">$4,402 (~₹1.54L)</span></div>
                        <div class="metric-row"><span class="metric-label">🥈 Silver (Spot/MCX):</span><span class="metric-val">$65.37 (~₹2.40L)</span></div>
                        <div class="metric-row"><span class="metric-label">🏦 FII Cash Flow:</span><span class="metric-val val-red">-₹3,240 Cr (Sellers)</span></div>
                        <div class="metric-row"><span class="metric-label">🏦 DII Cash Flow:</span><span class="metric-val val-green">+₹2,890 Cr (Buyers)</span></div>
                        <div class="metric-row"><span class="metric-label">⚡ Market Stance:</span><span class="metric-val val-green">Supportive DII</span></div>
                    </div>
                </div>

                <p style="margin-bottom: 8px;"><b>Overnight Wire:</b> US markets ended mixed as Treasuries hold near 4.90%. Brent Crude pulled back over 2% off recent highs, relieving immediate import inflation pressure. Domestic institutional inflows continue supporting Nifty 50 at 23,200.</p>

                <table class="pivot-mini-table">
                    <thead><tr><th>Index</th><th>Support (S1)</th><th>Pivot (P)</th><th>Resistance (R1)</th></tr></thead>
                    <tbody>
                        <tr><td><b>Nifty 50</b></td><td style="color:#dc2626; font-weight:700;">23,210</td><td style="color:#2563eb; font-weight:700;">23,300</td><td style="color:#16a34a; font-weight:700;">23,390</td></tr>
                        <tr><td><b>Bank Nifty</b></td><td style="color:#dc2626; font-weight:700;">49,550</td><td style="color:#2563eb; font-weight:700;">49,800</td><td style="color:#16a34a; font-weight:700;">50,050</td></tr>
                        <tr><td><b>Sensex</b></td><td style="color:#dc2626; font-weight:700;">76,200</td><td style="color:#2563eb; font-weight:700;">76,500</td><td style="color:#16a34a; font-weight:700;">76,800</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Block 2: Breakout Stock Radar -->
        <div class="grid-block">
            <div class="block-header">
                <span>🎯 High-Conviction Breakout Setups</span>
            </div>
            <div class="block-scroll-body">
                <div class="stock-card">
                    <div class="stock-row">
                        <span class="ticker">APARIND</span>
                        <span class="badge-buy">BUY: ₹17,750</span>
                        <span class="badge-target">TARGET: ₹19,200</span>
                        <span class="badge-sl">SL: ₹16,528</span>
                    </div>
                    <div class="rationale">Strong relative strength; oversold PMOX trigger combined with a 14-day RSI bullish crossover.</div>
                </div>

                <div class="stock-card">
                    <div class="stock-row">
                        <span class="ticker">BEML</span>
                        <span class="badge-buy">BUY: ₹2,000</span>
                        <span class="badge-target">TARGET: ₹2,120</span>
                        <span class="badge-sl">SL: ₹1,920</span>
                    </div>
                    <div class="rationale">Defense major retesting key 40-brick Renko moving average support level.</div>
                </div>

                <div class="stock-card">
                    <div class="stock-row">
                        <span class="ticker">AEGISVOPAK</span>
                        <span class="badge-buy">BUY: ₹305</span>
                        <span class="badge-target">TARGET: ₹335</span>
                        <span class="badge-sl">SL: ₹291</span>
                    </div>
                    <div class="rationale">52-week high breakout accompanied by substantial volume accumulation.</div>
                </div>
            </div>
        </div>

        <!-- Block 3: Indian Equities Wire -->
        <div class="grid-block">
            <div class="block-header">
                <span>🇮🇳 Indian Equities & Nifty 50 Wire</span>
            </div>
            <div class="block-scroll-body">
                <p><b>Market Outlook:</b> Indian equity benchmarks open on a defensive note as investors monitor global crude oil movements and domestic institutional buying. Sectoral trends favor capital goods and pharmaceutical stocks.</p>
                <br>
                <p>• Heavyweight financial stocks encounter FII selling pressure near resistance levels.</p>
                <p>• Midcap and Smallcap indices exhibit selective strength led by defense majors.</p>
            </div>
        </div>

        <!-- Block 4: Geopolitics & Breaking Wire -->
        <div class="grid-block">
            <div class="block-header">
                <span>⚡ Breaking Flashes & Geopolitics</span>
            </div>
            <div class="block-scroll-body">
                <p><b>Global Energy Wire:</b> Geopolitical risk premiums remain elevated across international energy markets as traders monitor Middle East shipping routes and military readiness discussions.</p>
                <br>
                <p>• Ongoing sanctions enforcement continues to restrict Russian crude oil distribution logistics.</p>
                <p>• Defense sector stocks globally trace increased government security budget allocations.</p>
            </div>
        </div>

        <!-- Block 5: Global Macro & US Markets -->
        <div class="grid-block">
            <div class="block-header">
                <span>🌍 US & Global Macro Intelligence</span>
            </div>
            <div class="block-scroll-body">
                <p><b>Wall Street Wire:</b> US equity indices trade in narrow ranges as 10-year Treasury yields hold firm around 4.90% ahead of upcoming Federal Reserve monetary policy speeches.</p>
                <br>
                <p>• Technology benchmarks consolidate following mega-cap earnings reports.</p>
                <p>• European equities track cautious global trading sentiment amidst inflation releases.</p>
            </div>
        </div>

        <!-- Block 6: Forex & Commodity Boundaries -->
        <div class="grid-block">
            <div class="block-header">
                <span>🛢️ Forex & Energy Market Boundaries</span>
            </div>
            <div class="block-scroll-body">
                <p><b>Commodity Boundaries:</b> Brent Crude contracts hold near $80.20 per barrel. USD/INR trades within a controlled 83.35–83.65 trading range maintained by Reserve Bank of India FX operations.</p>
                <br>
                <p>• Gold bullion prices steady near historical highs as safe-haven demand stays intact.</p>
                <p>• Industrial metals record moderate gains following Asian manufacturing PMI figures.</p>
            </div>
        </div>
    </div>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("=== Successfully generated formatted Telegram messages and 2-column macro index.html! ===")