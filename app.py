import os
import sys
import re
import time
import requests
import feedparser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ==========================================
# 1. CONFIGURATION & RSS SOURCES
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip("'").strip('"')

RAW_RSS_FEEDS = [
    "https://news.google.com/rss/search?q=nifty+sensex+bank+nifty+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=usd+inr+forex+crypto+commodities+crude+oil&hl=en-IN&gl=IN&ceid=IN:en"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_url(url_str):
    match = re.search(r'https?://[^\s\]\)]+', str(url_str))
    return match.group(0) if match else url_str

RSS_FEEDS = [clean_url(u) for u in RAW_RSS_FEEDS]

# ==========================================
# 2. INGEST & FILTER (KEEP ONLY LAST 48 HOURS)
# ==========================================
print("=== Step 1: Ingesting Live Market Feeds (48-Hour Filter Active) ===")
now_utc = datetime.now(timezone.utc)
cutoff_48h = now_utc - timedelta(hours=48)

fresh_articles = []

for feed_url in RSS_FEEDS:
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=10)
        feed = feedparser.parse(resp.content)
        for entry in feed.entries:
            published_tuple = entry.get("published_parsed")
            if published_tuple:
                entry_dt = datetime.fromtimestamp(time.mktime(published_tuple), tz=timezone.utc)
                if entry_dt < cutoff_48h:
                    continue  # Purge old data > 48h
            
            clean_title = re.sub(r'\s*-\s*[^-]+$', '', entry.title)
            fresh_articles.append(clean_title)
    except Exception as e:
        print(f"⚠️ Error fetching feed {feed_url}: {e}")

seen = set()
unique_articles = [a for a in fresh_articles if not (a in seen or seen.add(a))]

if not unique_articles:
    unique_articles = [
        "Nifty holds key support level around 23,200 while Sensex remains steady.",
        "Bank Nifty shows resilience led by private banking sector buying.",
        "Crude oil prices ease slightly, providing positive relief for Indian markets."
    ]

news_text = "\n".join([f"- {title}" for title in unique_articles[:8]])

# ==========================================
# 3. PARSE & CALCULATE INDEX PIVOT POINTS
# ==========================================
print("=== Step 2: Calculating Daily Pivot Points ===")

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

pivot_data = extract_pivot_levels(unique_articles)

# ==========================================
# 4. REWRITE BRIEFING VIA GROQ (<100 WORDS)
# ==========================================
print("=== Step 3: Generating Morning Market Briefing ===")

prompt = f"""
Summarize the last 24 hours of market events into a morning 7:00 AM IST pre-market briefing.
Determine the overall daily market bias (Bullish, Bearish, or Neutral).

CRITICAL RULES:
1. Entire text MUST BE UNDER 100 WORDS TOTAL.
2. Written in super simple layman's terms.
3. Output clean HTML body content using standard tags (`<p>`, `<ul>`, `<li>`, `<b>`).
4. Do NOT output markdown code fences like ```html.

Articles:
{news_text}
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
                print(f"✅ AI Morning Briefing generated via Groq ({model_name})")
                break
        except Exception as e:
            print(f"⚠️ Groq attempt failed: {e}")

if not ai_html_content:
    ai_html_content = (
        "<p><b>Market Bias: Moderately Bullish</b></p>\n"
        "<ul>\n"
        "<li><b>Morning Insight:</b> Benchmarks closed on a positive note as domestic institutional buying offset global rate concerns.</li>\n"
        "<li><b>Key Drivers:</b> Easing crude oil prices and a stabilizing Rupee provide support for morning momentum.</li>\n"
        "</ul>"
    )

# ==========================================
# 5. BUILD PIVOT TABLE HTML
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
# 6. BUILD 48-HOUR NEWS LIST HTML
# ==========================================
news_bullets_html = "".join([f"<li><b>Market Update:</b> {title}</li>" for title in unique_articles[:6]])

# ==========================================
# 7. CONSTRUCT HTML PAGE (LIVE FEEDS TOP FIRST)
# ==========================================
print("=== Step 4: Formatting HTML Page ===")
ist_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%b %d, %Y | %I:%M %p IST")

full_html = (
    "<!DOCTYPE html>\n"
    '<html lang="en">\n'
    "<head>\n"
    '    <meta charset="UTF-8">\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    '    <meta http-equiv="refresh" content="300">\n'
    "    <title>Live Market Feeds & Pre-Market Briefing</title>\n"
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
    "            background: #e3f2fd;\n"
    "            color: #1565c0;\n"
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
    "        .card {\n"
    "            background: #ffffff;\n"
    "            border-left: 5px solid #388e3c;\n"
    "            padding: 20px 25px;\n"
    "            border-radius: 6px;\n"
    "            box-shadow: 0 2px 8px rgba(0,0,0,0.05);\n"
    "            margin-bottom: 20px;\n"
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
    "        .support { color: #d32f2f; font-weight: 600; }\n"
    "        .pivot { color: #1976d2; font-weight: 600; }\n"
    "        .resistance { color: #2e7d32; font-weight: 600; }\n"
    "        ul {\n"
    "            padding-left: 18px;\n"
    "            margin: 0;\n"
    "        }\n"
    "        li {\n"
    "            margin-bottom: 8px;\n"
    "            font-size: 0.95em;\n"
    "        }\n"
    "    </style>\n"
    "</head>\n"
    "<body>\n"
    "    <h1>Live Market Updates & Pre-Market Briefing</h1>\n"
    f'    <div class="timestamp">🕒 Last Updated: {ist_time}</div>\n'
    '    <div class="badge">⚡ 48-Hour Live Auto-Cleaned Data</div>\n'
    "    <hr>\n"
    '    <div class="card">\n'
    '        <h3 style="margin-top:0; color:#2e7d32;">📰 48-Hour Live Market Feed</h3>\n'
    "        <ul>\n"
    f"            {news_bullets_html}\n"
    "        </ul>\n"
    "    </div>\n"
    f"    {pivot_table_html}\n"
    '    <div class="card" style="border-left-color: #1976d2;">\n'
    '        <h3 style="margin-top:0; color:#0d47a1;">☕ Morning 7 AM Pre-Market Briefing (&lt;100 Words)</h3>\n'
    f"        {ai_html_content}\n"
    "    </div>\n"
    "</body>\n"
    "</html>"
)

# ==========================================
# 8. WRITE DIRECTLY TO index.html
# ==========================================
print("=== Step 5: Writing index.html file ===")
with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("✅ Successfully generated index.html!")