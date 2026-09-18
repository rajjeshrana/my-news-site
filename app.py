import os
import sys
import re
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

RAW_RSS_FEEDS = [
    "https://news.google.com/rss/search?q=nifty+sensex+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=usd+inr+forex+crypto+commodities&hl=en-IN&gl=IN&ceid=IN:en"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_url(url_str):
    """Strips Markdown link wrappers or extra brackets if copied accidentally."""
    match = re.search(r'https?://[^\s\]\)]+', str(url_str))
    return match.group(0) if match else url_str

RSS_FEEDS = [clean_url(u) for u in RAW_RSS_FEEDS]

# ==========================================
# 2. INGEST RSS FEEDS
# ==========================================
print("=== Step 1: Ingesting Live Market Feeds ===")
articles = []
for feed_url in RSS_FEEDS:
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=10)
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:5]:  # Get top 5 articles per feed
            articles.append(f"- {entry.title}")
    except Exception as e:
        print(f"⚠️ Error fetching feed {feed_url}: {e}")

if not articles:
    articles = [
        "- Indian stock markets show steady activity across key benchmark indices.",
        "- Forex market tracks USD/INR variations alongside major global currency trends."
    ]

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

raw_groq_url = "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)"
groq_url = clean_url(raw_groq_url)

groq_headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

# Fallback sequence across Groq production models
MODELS_TO_TRY = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
ai_html_content = None

for model_name in MODELS_TO_TRY:
    print(f"Attempting Groq completion with model: {model_name}")
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5
    }
    response = requests.post(groq_url, json=payload, headers=groq_headers)
    if response.status_code == 200:
        ai_html_content = response.json()["choices"][0]["message"]["content"]
        print(f"✅ Success using model: {model_name}")
        break
    else:
        print(f"⚠️ Failed with {model_name}: {response.status_code} - {response.text}")

if not ai_html_content:
    print("❌ Groq API Error: All model attempts failed. Please verify GROQ_API_KEY secret.")
    sys.exit(1)

# ==========================================
# 4. CONSTRUCT HTML PAGE WITH IST TIMESTAMP
# ==========================================
print("=== Step 3: Formatting HTML Page with Live IST Timestamp ===")
ist_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%b %d, %Y | %I:%M %p IST")

html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Financial Market Updates</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 20px;
            color: #333;
            line-height: 1.6;
        }
        h1 {
            color: #0d47a1;
            margin-bottom: 5px;
        }
        .timestamp {
            color: #666;
            font-weight: 600;
            font-size: 0.95em;
            margin-bottom: 20px;
        }
        hr {
            border: 0;
            height: 1px;
            background: #e0e0e0;
            margin-bottom: 25px;
        }
        .card {
            background: #f8f9fa;
            border-left: 4px solid #1976d2;
            padding: 15px 20px;
            border-radius: 4px;
            margin-bottom: 20px;
        }
        ul {
            padding-left: 20px;
        }
        li {
            margin-bottom: 8px;
        }
    </style>
</head>
<body>
    <h1>Global Markets Shift: Forex, India Stocks, Oil, and Crypto Update</h1>
    <div class="timestamp">🕒 Last Updated: {TIMESTAMP}</div>
    <hr>
    <div class="card">
        {CONTENT}
    </div>
</body>
</html>
"""

full_html = html_template.replace("{TIMESTAMP}", ist_time).replace("{CONTENT}", ai_html_content)

# ==========================================
# 5. WRITE DIRECTLY TO index.html FILE
# ==========================================
print("=== Step 4: Writing index.html file ===")
with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("✅ Successfully generated index.html!")