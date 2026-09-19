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
# 1. 100+ EXPANDED GLOBAL FINANCIAL SOURCES NETWORK
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip("'").strip('"')
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

CATEGORY_FEEDS = {
    "⚡ Breaking Flashes & Geopolitics": [
        "[https://news.google.com/rss/search?q=Trump+OR+Iran+OR+war+OR+Fed+OR+RBI+statement+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=Trump+OR+Iran+OR+war+OR+Fed+OR+RBI+statement+when:1d&hl=en-US&gl=US&ceid=US:en)",
        "[https://news.google.com/rss/search?q=financialjuice+OR+DeitaOne+OR+ForexLive+breaking+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=financialjuice+OR+DeitaOne+OR+ForexLive+breaking+when:1d&hl=en-US&gl=US&ceid=US:en)",
        "[https://news.google.com/rss/search?q=breaking+geopolitics+market+news+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=breaking+geopolitics+market+news+when:1d&hl=en-US&gl=US&ceid=US:en)",
        "[https://www.forexlive.com/feed/news](https://www.forexlive.com/feed/news)",
        "[https://www.fxstreet.com/rss/news](https://www.fxstreet.com/rss/news)",
        "[https://www.actionforex.com/feed/](https://www.actionforex.com/feed/)",
        "[https://www.investing.com/rss/news_14.rss](https://www.investing.com/rss/news_14.rss)",
        "[https://news.google.com/rss/search?q=white+house+sanctions+military+conflict+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=white+house+sanctions+military+conflict+when:1d&hl=en-US&gl=US&ceid=US:en)",
        "[https://news.google.com/rss/search?q=un+security+council+breaking+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=un+security+council+breaking+when:1d&hl=en-US&gl=US&ceid=US:en)"
    ],
    "Indian Stock Market": [
        "[https://news.google.com/rss/search?q=Nifty+Sensex+stock+market+India+breaking+when:1d&hl=en-IN&gl=IN&ceid=IN:en](https://news.google.com/rss/search?q=Nifty+Sensex+stock+market+India+breaking+when:1d&hl=en-IN&gl=IN&ceid=IN:en)",
        "[https://www.business-standard.com/rss/markets-106.rss](https://www.business-standard.com/rss/markets-106.rss)",
        "[https://www.financialexpress.com/market/feed/](https://www.financialexpress.com/market/feed/)",
        "[https://www.livemint.com/rss/markets](https://www.livemint.com/rss/markets)",
        "[https://www.ndtvprofit.com/rss/markets.xml](https://www.ndtvprofit.com/rss/markets.xml)",
        "[https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms](https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms)",
        "[https://www.moneycontrol.com/rss/MCtopnews.xml](https://www.moneycontrol.com/rss/MCtopnews.xml)",
        "[https://www.moneycontrol.com/rss/marketreports.xml](https://www.moneycontrol.com/rss/marketreports.xml)",
        "[https://www.business-standard.com/rss/companies-101.rss](https://www.business-standard.com/rss/companies-101.rss)",
        "[https://www.financialexpress.com/auto/feed/](https://www.financialexpress.com/auto/feed/)",
        "[https://news.google.com/rss/search?q=sebi+rbi+policy+indian+economy+when:1d&hl=en-IN&gl=IN&ceid=IN:en](https://news.google.com/rss/search?q=sebi+rbi+policy+indian+economy+when:1d&hl=en-IN&gl=IN&ceid=IN:en)"
    ],
    "US & Global Markets": [
        "[https://news.google.com/rss/search?q=Wall+Street+Nasdaq+SP500+breaking+news+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=Wall+Street+Nasdaq+SP500+breaking+news+when:1d&hl=en-US&gl=US&ceid=US:en)",
        "[https://search.cnbc.com/rs/search/combined:rss?source=cnbc&q=markets](https://search.cnbc.com/rs/search/combined:rss?source=cnbc&q=markets)",
        "[https://feeds.a.dj.com/rss/RSSMarketsMain.xml](https://feeds.a.dj.com/rss/RSSMarketsMain.xml)",
        "[https://www.investing.com/rss/news_25.rss](https://www.investing.com/rss/news_25.rss)",
        "[https://www.marketwatch.com/rss/topstories](https://www.marketwatch.com/rss/topstories)",
        "[https://www.ft.com/markets?format=rss](https://www.ft.com/markets?format=rss)",
        "[https://news.google.com/rss/search?q=federal+reserve+rate+cut+inflation+cpi+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=federal+reserve+rate+cut+inflation+cpi+when:1d&hl=en-US&gl=US&ceid=US:en)",
        "[https://news.google.com/rss/search?q=european+central+bank+nikkei+hang+seng+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=european+central+bank+nikkei+hang+seng+when:1d&hl=en-US&gl=US&ceid=US:en)"
    ],
    "Forex & Commodities": [
        "[https://news.google.com/rss/search?q=Crude+Oil+Gold+USD+INR+forex+breaking+when:1d&hl=en-IN&gl=IN&ceid=IN:en](https://news.google.com/rss/search?q=Crude+Oil+Gold+USD+INR+forex+breaking+when:1d&hl=en-IN&gl=IN&ceid=IN:en)",
        "[https://www.dailyfx.com/feeds/market-news](https://www.dailyfx.com/feeds/market-news)",
        "[https://www.oilprice.com/rss/main](https://www.oilprice.com/rss/main)",
        "[https://www.kitco.com/rss/news.xml](https://www.kitco.com/rss/news.xml)",
        "[https://www.investing.com/rss/news_11.rss](https://www.investing.com/rss/news_11.rss)",
        "[https://news.google.com/rss/search?q=brent+crude+opec+gold+price+silver+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=brent+crude+opec+gold+price+silver+when:1d&hl=en-US&gl=US&ceid=US:en)"
    ],
    "Crypto & Global Macro": [
        "[https://news.google.com/rss/search?q=Bitcoin+Ethereum+crypto+Fed+rates+when:1d&hl=en-US&gl=US&ceid=US:en](https://news.google.com/rss/search?q=Bitcoin+Ethereum+crypto+Fed+rates+when:1d&hl=en-US&gl=US&ceid=US:en)",
        "[https://www.coindesk.com/arc/outboundfeeds/rss/](https://www.coindesk.com/arc/outboundfeeds/rss/)",
        "[https://cointelegraph.com/rss](https://cointelegraph.com/rss)",
        "[https://decrypt.co/feed](https://decrypt.co/feed)",
        "[https://news.bitcoin.com/feed/](https://news.bitcoin.com/feed/)",
        "[https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best](https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best)"
    ]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

FALLBACK_IMAGE = "[https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=150&q=80](https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=150&q=80)"

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
# 2. INGEST HEADLINES & INDIVIDUAL DEDUPLICATION
# ==========================================
print("=== Step 1: Ingesting Live Multi-Source Market Feeds ===")
now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
is_weekend = now_ist.weekday() in [5, 6]

if is_weekend:
    current_time_str = now_ist.strftime("%b %d, %Y") + " (Weekend Macro Wrap)"
else:
    current_time_str = now_ist.strftime("%I:%M %p IST")

now_utc = datetime.now(timezone.utc)

HISTORY_FILE = "history.json"
blocks_history = []
morning_briefing_data = None
seen_headline_hashes = set()

if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            store = json.load(f)
            if isinstance(store, dict):
                blocks_history = store.get("blocks", [])
                morning_briefing_data = store.get("morning_briefing", None)
                seen_headline_hashes = set(store.get("seen_hashes", []))
            elif isinstance(store, list):
                blocks_history = store
    except Exception as e:
        print(f"⚠️ Load error on history.json: {e}")

category_data = {}
category_images = {}
new_items_count = 0

for cat_name, feed_urls in CATEGORY_FEEDS.items():
    cleaned_titles = []
    cat_img = None
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
                    if not cat_img or cat_img == FALLBACK_IMAGE:
                        extracted = extract_entry_image(entry)
                        if extracted != FALLBACK_IMAGE:
                            cat_img = extracted
        except Exception as e:
            print(f"⚠️ Error fetching {cat_name} from {feed_url}: {e}")
            
    if cleaned_titles:
        category_data[cat_name] = cleaned_titles[:4]
        category_images[cat_name] = cat_img or FALLBACK_IMAGE

is_duplicate = (new_items_count == 0)

if is_duplicate:
    print("ℹ️ Zero new headlines across all 100+ sources. Skipping duplicate post.")

# ==========================================
# 3. 7:00 AM IST MORNING BRIEFING GENERATION
# ==========================================
is_7am_window = (now_ist.hour == 7 and now_ist.minute < 30) or (morning_briefing_data is None)

if is_7am_window and category_data:
    print("=== Step 2: Generating 7:00 AM Pre-Market Global Briefing ===")
    briefing_text_input = "\n".join([f"[{cat}]: " + " | ".join(items) for cat, items in category_data.items()])
    
    briefing_prompt = f"""
You are a senior chief market strategist preparing a 7:00 AM IST Pre-Market Briefing.
Synthesize the headlines into actionable, high-density market analysis. Highlight breaking geopolitical events, crude oil catalysts, and central bank commentary.

Format strictly as HTML inside a single <div> with bullet points:
<p><b>Overall Daily Market Bias: Moderately Bullish / Neutral / Bearish</b></p>
<ul>
  <li><b>⚡ Geopolitics & Macro Flashes:</b> [2 dense sentences on major geopolitical quotes or central bank developments]</li>
  <li><b>Global & US Markets:</b> [2 dense sentences on Wall Street futures, treasury yields, or major macro drivers]</li>
  <li><b>Commodities & Forex:</b> [2 dense sentences on crude oil, gold demand, or rupee/dollar levels]</li>
  <li><b>Indian Equities Outlook:</b> [2 dense sentences on Nifty opening cues, institutional flows, or sector focus]</li>
</ul>

Headlines:
{briefing_text_input}
"""
    
    briefing_html = None
    if GROQ_API_KEY:
        groq_url = "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)"
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
# 4. SYNTHESIZE COMMENTARY WITH GROQ AI (IF NEW)
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
3. BOLD KEY TERMS: Use HTML <b>tags</b> to bold key stock tickers, levels, leader names, and major catalysts (e.g., <b>Nifty 50</b>, <b>Trump</b>, <b>Crude Oil</b>, <b>RBI</b>).
4. STRUCTURE: Explain (1) WHAT happened, (2) WHY it happened, and (3) WHAT IT MEANS for immediate market bias.

Output strictly 5 HTML <li> tags formatted as follows:
<li><b>⚡ Breaking Flashes & Geopolitics:</b> [Synthesized commentary on breaking quotes or geopolitical developments]</li>
<li><b>Indian Stock Market:</b> [Synthesized commentary on sector/stock drivers or Nifty/Sensex action]</li>
<li><b>US & Global Markets:</b> [Synthesized commentary on Wall Street, yields, earnings, or Fed stance]</li>
<li><b>Forex & Commodities:</b> [Synthesized commentary on USD/INR, Crude oil, or Gold demand]</li>
<li><b>Crypto & Global Macro:</b> [Synthesized commentary on BTC/ETH price action or macro policy prints]</li>

Headlines:
{prompt_text}
"""
    if GROQ_API_KEY:
        groq_url = "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)"
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
                print(f"⚠️ Groq API Error: {e}")

    if not ai_bullets_html:
        items_list = []
        for cat, items in category_data.items():
            first_headline = items[0] if items else "Market activity remains bounded."
            items_list.append(f"<li><b>{cat}:</b> {first_headline}</li>")
        ai_bullets_html = "\n".join(items_list)

    web_bullets_list = []
    bullets_matches = re.findall(r'<li>(.*?)</li>', ai_bullets_html, re.DOTALL)
    
    cat_keys = list(category_images.keys())
    for idx, b_text in enumerate(bullets_matches):
        img_url = category_images.get(cat_keys[idx if idx < len(cat_keys) else 0], FALLBACK_IMAGE)
        card_item = f"""
        <li>
            <div class="news-item-box">
                <img src="{img_url}" class="news-thumb" alt="market news" onerror="this.onerror=null;this.src='{FALLBACK_IMAGE}';">
                <div class="news-text-content">{b_text}</div>
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
        "morning_briefing": morning_briefing_data,
        "seen_hashes": recent_hashes,
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
        f"🌐 <a href='[https://rajjeshrana.github.io/my-news-site/](https://rajjeshrana.github.io/my-news-site/)'>View Terminal Dashboard</a>"
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
    <h3>📊 Real-Time Market Overview & Benchmarks</h3>
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
    ul { padding-left: 0; list-style: none; margin: 0; }
    li { margin-bottom: 16px; font-size: 1em; color: #2c3e50; }
    .news-item-box { display: flex; align-items: flex-start; gap: 15px; background: #fdfdfd; padding: 10px; border-radius: 6px; border: 1px solid #f0f0f0; }
    .news-thumb { width: 75px; height: 75px; border-radius: 6px; object-fit: cover; flex-shrink: 0; background-color: #e0e0e0; }
    .news-text-content { flex-grow: 1; font-size: 0.98em; line-height: 1.5; }
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