import os
import sys
import requests
import feedparser
from datetime import datetime
from zoneinfo import ZoneInfo

# ==========================================
# 1. SECRETS VALIDATION
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("❌ ERROR: Missing GROQ_API_KEY secret.")
    sys.exit(1)

# RSS Feeds for Financial Market Updates
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=nifty+sensex+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=usd+inr+forex+crypto+commodities&hl=en-IN&gl=IN&ceid=IN:en"
]

# ==========================================
# 2. INGEST RSS FEEDS
# ==========================================
print("=== Step 1: Ingesting Live Market Feeds ===")
articles = []
for feed_url in RSS_FEEDS:
    feed = feedparser.parse(feed_url)
    for entry in feed.entries[:5]:  # Get top 5 articles per feed
        articles.append(f"- {entry.title}")

news_text = "\n".join(articles)
print(f"Total articles gathered: {len(articles)}")

# ==========================================
# 3. GENERATE AI SUMMARY VIA GROQ
# ==========================================
print("=== Step 2: Generating Market Summary with Groq AI ===")
prompt = f"""
You are a top financial journalist. Summarize the following news articles into structured market updates.
Return ONLY clean HTML body content using bullet points (`<ul>`, `<li>`), `<h3>` subheadings, and bold tags (`<b>`). 
Do not include Markdown block quotes like ```html or <html><body> wrappers.

Articles:
{news_text}
"""

groq_url = "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)"
headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.5
}

response = requests.post(groq_url, json=payload, headers=headers)
if response.status_code != 200:
    print(f"❌ Groq API Error: {response.status_code} - {response.text}")
    sys.exit(1)

ai_html_content = response.json()["choices"][0]["message"]["content"]

# ==========================================
# 4. CONSTRUCT COMPLETE HTML PAGE WITH IST TIMESTAMP
# ==========================================
print("=== Step 3: Formatting HTML Page with Live IST Timestamp ===")
ist_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%b %d, %Y | %I:%M %p IST")

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Financial Market Updates</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
            color: #333;
            line-height: 1.6;
        }}
        h1 {{
            color: #0d47a1;
            margin-bottom: 5px;
        }}
        .timestamp {{
            color: #666;
            font-weight: 600;
            font-size: 0.95em;
            margin-bottom: 20px;
        }}
        hr {{
            border: 0;
            height: 1px;
            background: #e0e0e0;
            margin-bottom: 25px;
        }}
        .card {{
            background: #f8f9fa;
            border-left: 4px solid #1976d2;
            padding: 15px 20px;
            border-radius: 4px;
            margin-bottom: 20px;
        }}
        ul {{
            padding-left: 20px;
        }}
        li {{
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <h1>Global Markets Shift: Forex, India Stocks, Oil, and Crypto Update</h1>
    <div class="timestamp">🕒 Last Updated: {ist_time}</div>
    <hr>
    <div class="card">
        {ai_html_content}
    </div>
</body>
</html>
"""

# ==========================================
# 5. WRITE DIRECTLY TO index.html FILE
# ==========================================
print("=== Step 4: Writing index.html file ===")
with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("✅ Successfully generated index.html!")