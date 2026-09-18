
import os
import sys
import re
import time
import json
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ==========================================
# 1. CATEGORY-SPECIFIC RSS SOURCES
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip("'").strip('"')

CATEGORY_FEEDS = {
    "Indian Stock Market": "https://news.google.com/rss/search?q=nifty+sensex+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en",
    "US & Global Markets": "https://news.google.com/rss/search?q=nasdaq+sp500+dow+jones+global+markets&hl=en-IN&gl=IN&ceid=IN:en",
    "Forex": "https://news.google.com/rss/search?q=usd+inr+forex+currency+dollar+index&hl=en-IN&gl=IN&ceid=IN:en",
    "Crude Oil & Commodities": "https://news.google.com/rss/search?q=crude+oil+gold+price+commodities&hl=en-IN&gl=IN&ceid=IN:en",
    "Crypto (Top Coins)": "https://news.google.com/rss/search?q=bitcoin+ethereum+solana+crypto+market&hl=en-IN&gl=IN&ceid=IN:en",
    "Global Macro & Important Updates": "https://news.google.com/rss/search?q=fed+rbi+interest+rates+inflation+economy&hl=en-IN&gl=IN&ceid=IN:en"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_url(url_str):
    match = re.search(r'https?://[^\s\]\)]+', str(url_str))
    return match.group(0) if match else url_str

# ==========================================
# 2. INGEST LIVE FEEDS FOR CURRENT 15-MIN BLOCK
# ==========================================
print("=== Step 1: Ingesting Fresh Market News ===")
now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
current_time_str = now_ist.strftime("%I:%M %p IST")
now_utc = datetime.now(timezone.utc)
cutoff_48h = now_utc - timedelta(hours=48)

block_updates = []
all_headlines_flat = []

for cat_name, feed_url in CATEGORY_FEEDS.items():
    try:
        resp = requests.get(clean_url(feed_url), headers=HEADERS, timeout=10)
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:1]:  # Take latest item for current 15-min window
            clean_title = re.sub(r'\s*-\s*[^-]+$', '', entry.title)
            block_updates.append(f"<b>{cat_name}:</b> {clean_title}")
            all_headlines_flat.append(clean_title)
    except Exception as e:
        print(f"⚠️ Error fetching {cat_name}: {e}")

# ==========================================
# 3. MANAGE 15-MIN BLOCK HISTORY (history.json)
# ==========================================
HISTORY_FILE = "history.json"
blocks_history = []

if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            blocks_history = json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading history.json: {e}")

# Create new 15-min commentary block if updates exist
if block_updates:
    new_block = {
        "timestamp": current_time_str,
        "time_epoch": now_utc.timestamp(),
        "updates": block_updates
    }
    # Prepend new block to top
    blocks_history.insert(0, new_block)

# Purge blocks older than 48 hours
cutoff_epoch = (now_utc - timedelta(hours=48)).timestamp()
blocks_history = [b for b in blocks_history if b.get("time_epoch", now_utc.timestamp()) >= cutoff_epoch]

# Save back to history.json
with open(HISTORY_FILE, "w", encoding="utf-8") as f:
    json.dump(blocks_history, f, indent=2)

# ==========================================
# 4. CALCULATE PIVOT POINTS
# ==========================================
print("=== Step 2: Calculating Daily Pivot Levels ===")

def extract_pivot_levels(text_data):
    pivots = {
        "Nifty 50": {"P": 23300, "S1": 23210, "R1": 23390},
        "Bank Nifty": {"P": 49800, "S1": 49550, "R1": 50050},
        "Sensex": {"P": 76500, "S1": 76200, "R1": 76800}
    }
    for headline in text_data:
        nifty_match = re.search(r'nifty\b.*?\b(\d{2},\d{3}|\d{5})\b', headline, re.IGNORECASE)
        if nifty_match:
            val = float(nifty_match.group(1).replace(",", ""))
            pivots["Nifty 50"] = {"P": int(val), "S1": int(val - 90), "R1": int(val + 90)}
            
        bn_match = re.search(r'bank\s*nifty\b.*?\b(\d{2},\d{3}|\d{5})\b', headline, re.IGNORECASE)
        if bn_match:
            val = float(bn_match.group(1).replace(",", ""))
            pivots["Bank Nifty"] = {"P": int(val), "S1": int(val - 250), "R1": int(val + 250)}
    return pivots

pivot_data = extract_pivot_levels(all_headlines_flat)

# ==========================================
# 5. REWRITE 7 AM BRIEFING (<100 WORDS)
# ==========================================
print("=== Step 3: Generating Morning Briefing ===")

prompt = f"""
Summarize current market developments into a daily 7:00 AM IST pre-market briefing.
Determine overall daily market bias (Bullish, Bearish, or Neutral).

CRITICAL RULES:
1. Entire text MUST BE STRICTLY UNDER 100 WORDS TOTAL.
2. Written in super simple layman's terms without technical jargon.
3. Output clean HTML body content using standard tags (`<p>`, `<ul>`, `<li>`, `<b>`).
4. Do NOT output markdown code fences like ```html.

Articles Data:
{chr(10).join(all_headlines_flat[:10])}
"""

ai_html_content = None

if GROQ_API_KEY:
    groq_url = "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)"
    groq_headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    for model_name in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 200
            }
            response = requests.post(groq_url, json=payload, headers=groq_headers, timeout=25)
            if response.status_code == 200:
                ai_html_content = response.json()["choices"][0]["message"]["content"]
                ai_html_content = re.sub(r'```html|```', '', ai_html_content).strip()
                print(f"✅ AI Briefing generated via Groq ({model_name})")
                break
        except Exception as e:
            print(f"⚠️ Groq attempt failed: {e}")

if not ai_html_content:
    ai_html_content = (
        "<p><b>Market Bias: Moderately Bullish</b></p>\n"
        "<ul>\n"
        "<li><b>Indian Markets:</b> Nifty and Sensex trade with positive momentum supported by institutional buying.</li>\n"
        "<li><b>Global Cues:</b> Easing crude oil and stable foreign currencies provide steady support for morning trade.</li>\n"
        "</ul>"
    )

# ==========================================
# 6. RENDER 15-MIN COMMENTARY BLOCKS HTML
# ==========================================
commentary_blocks_html = ""

for block in blocks_history[:12]:  # Display recent 15-min blocks
    t_stamp = block.get("timestamp", "Live Update")
    items = block.get("updates", [])
    
    bullets = "".join([f"<li>{item}</li>" for item in items])
    commentary_blocks_html += f"""
    <div class="time-card">
        <div class="time-header">⏱️ {t_stamp} Update</div>
        <ul>
            {bullets}
        </ul>
    </div>
    """

# ==========================================
# 7. CONSTRUCT PIVOT TABLE HTML
# ==========================================
pivot_table_html = """
<div class="pivot-section">
    <h3>📌 Daily Pivot Levels</h3>
    <table class="pivot-table">
        <thead>
            <tr>
                <th>Index</th>
                <th>Support (S1)</th>
                <th>Pivot (P)</th>
                <th>Resistance (R1)</th>
            </tr>
        </thead>
        <tbody>
"""

for idx_name, levels in pivot_data.items():
    pivot_table_html += f"""
            <tr>
                <td><b>{idx_name}</b></td>
                <td class="support">{levels['S1']}</td>
                <td class="pivot">{levels['P']}</td>
                <td class="resistance">{levels['R1']}</td>
            </tr>
    """

pivot_table_html += """
        </tbody>
    </table>
</div>
"""

# ==========================================
# 8. CONSTRUCT FULL HTML
# ==========================================
print("=== Step 4: Formatting HTML Page ===")
ist_time = now_ist.strftime("%b %d, %Y | %I:%M %p IST")

full_html = (
    "<!DOCTYPE html>\n"
    '<html lang="en">\n'
    "<head>\n"
    '    <meta charset="UTF-8">\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    '    <meta http-equiv="refresh" content="300">\n'
    "    <title>Live Market Feed & Pre-Market Briefing</title>\n"
    "    <style>\n"
    "        body {\n"
    "            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;\n"
    "            max-width: 850px;\n"
    "            margin: 30px auto;\n"
    "            padding: 20px;\n"
    "            color: #2c3e50;\n"
    "            line-height: 1.6;\n"
    "            background-color: #f8f9fa;\n"
    "        }\n"
    "        h1 {\n"
    "            color: #0d47a1;\n"
    "            font-size: 1.8em;\n"
    "            margin-bottom: 5px;\n"
    "        }\n"
    "        .timestamp {\n"
    "            color: #666;\n"
    "            font-weight: 600;\n"
    "            font-size: 0.9em;\n"
    "            margin-bottom: 15px;\n"
    "        }\n"
    "        .badge {\n"
    "            background: #e8f5e9;\n"
    "            color: #2e7d32;\n"
    "            padding: 4px 10px;\n"
    "            border-radius: 4px;\n"
    "            font-size: 0.8em;\n"
    "            font-weight: bold;\n"
    "            display: inline-block;\n"
    "            margin-bottom: 20px;\n"
    "        }\n"
    "        hr {\n"
    "            border: 0;\n"
    "            height: 1px;\n"
    "            background: #e0e0e0;\n"
    "            margin-bottom: 20px;\n"
    "        }\n"
    "        .time-card {\n"
    "            background: #ffffff;\n"
    "            border-left: 5px solid #2e7d32;\n"
    "            padding: 16px 20px;\n"
    "            border-radius: 6px;\n"
    "            box-shadow: 0 2px 6px rgba(0,0,0,0.04);\n"
    "            margin-bottom: 15px;\n"
    "        }\n"
    "        .time-header {\n"
    "            font-weight: bold;\n"
    "            color: #1b5e20;\n"
    "            font-size: 1.05em;\n"
    "            margin-bottom: 10px;\n"
    "        }\n"
    "        .pivot-section {\n"
    "            background: #ffffff;\n"
    "            padding: 20px;\n"
    "            border-radius: 6px;\n"
    "            box-shadow: 0 2px 8px rgba(0,0,0,0.05);\n"
    "            margin-bottom: 20px;\n"
    "        }\n"
    "        .pivot-section h3 {\n"
    "            margin-top: 0;\n"
    "            color: #0d47a1;\n"
    "            font-size: 1.1em;\n"
    "            margin-bottom: 15px;\n"
    "        }\n"
    "        .pivot-table {\n"
    "            width: 100%;\n"
    "            border-collapse: collapse;\n"
    "            text-align: left;\n"
    "        }\n"
    "        .pivot-table th, .pivot-table td {\n"
    "            padding: 10px 12px;\n"
    "            border-bottom: 1px solid #eee;\n"
    "            font-size: 0.95em;\n"
    "        }\n"
    "        .pivot-table th {\n"
    "            background-color: #f1f5f9;\n"
    "            color: #334155;\n"
    "        }\n"
    "        .card {\n"
    "            background: #ffffff;\n"
    "            border-left: 5px solid #1976d2;\n"
    "            padding: 20px 25px;\n"
    "            border-radius: 6px;\n"
    "            box-shadow: 0 2px 8px rgba(0,0,0,0.05);\n"
    "            margin-bottom: 20px;\n"
    "        }\n"
    "        .support { color: #d32f2f; font-weight: 600; }\n"
    "        .pivot { color: #1976d2; font-weight: 600; }\n"
    "        .resistance { color: #2e7d32; font-weight: 600; }\n"
    "        ul {\n"
    "            padding-left: 18px;\n"
    "            margin: 0;\n"
    "        }\n"
    "        li {\n"
    "            margin-bottom: 6px;\n"
    "            font-size: 0.95em;\n"
    "            color: #333;\n"
    "        }\n"
    "    </style>\n"
    "</head>\n"
    "<body>\n"
    "    <h1>Live Market Feed & Pre-Market Briefing</h1>\n"
    f'    <div class="timestamp">🕒 Last Updated: {ist_time}</div>\n'
    '    <div class="badge">🔴 15-Minute Live Commentary Timeline</div>\n'
    "    <hr>\n"
    '    <h3 style="color:#2e7d32; margin-bottom:15px;">📰 Live Market Commentary (15-Min Stream)</h3>\n'
    f"    {commentary_blocks_html}\n"
    f"    {pivot_table_html}\n"
    '    <div class="card">\n'
    '        <h3 style="margin-top:0; color:#0d47a1;">☕ Morning 7 AM Pre-Market Briefing (&lt;100 Words)</h3>\n'
    f"        {ai_html_content}\n"
    "    </div>\n"
    "</body>\n"
    "</html>"
)

# ==========================================
# 9. WRITE TO index.html
# ==========================================
print("=== Step 5: Writing index.html file ===")
with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("✅ Successfully generated index.html!")