import os
import sys
import requests
import feedparser
from datetime import datetime
from zoneinfo import ZoneInfo

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("? ERROR: Missing GROQ_API_KEY secret.")
    sys.exit(1)

RSS_FEEDS = [
    "[https://news.google.com/rss/search?q=nifty+sensex+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en](https://news.google.com/rss/search?q=nifty+sensex+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en)",
    "[https://news.google.com/rss/search?q=usd+inr+forex+crypto+commodities&hl=en-IN&gl=IN&ceid=IN:en](https://news.google.com/rss/search?q=usd+inr+forex+crypto+commodities&hl=en-IN&gl=IN&ceid=IN:en)"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print("=== Step 1: Ingesting Live Market Feeds ===")
articles = []
for feed_url in RSS_FEEDS:
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=10)
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:5]:
            articles.append(f"- {entry.title}")
    except Exception as e:
        print(f"?? Error fetching feed {feed_url}: {e}")

if not articles:
    articles = [
        "- Indian stock markets show steady activity across key benchmark indices.",
        "- Forex market tracks USD/INR variations alongside major global currency trends."
    ]

news_text = "\n".join(articles)
print(f"Total articles gathered: {len(articles)}")

print("=== Step 2: Generating Market Summary with Groq AI ===")
prompt = f"""
You are a top financial journalist. Summarize the following news articles into structured market updates.
Return ONLY clean HTML body content using bullet points (`<ul>`, `<li>`), `<h3>` subheadings, and bold tags (`<b>`). 
Do not include Markdown block quotes like ```html or <html><body> wrappers.

Articles:
{news_text}
"""

groq_url = "https://api.groq.com/openai/v1/chat/completions"
groq_headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}
payload = {
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.5
}

response = requests.post(groq_url, json=payload, headers=groq_headers)
if response.status_code != 200:
    print(f"? Groq API Error: {response.status_code} - {response.text}")
    sys.exit(1)

ai_html_content = response.json()["choices"][0]["message"]["content"]

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
    <div class="timestamp">?? Last Updated: {ist_time}</div>
    <hr>
    <div class="card">
        {ai_html_content}
    </div>
</body>
</html>
"""

print("=== Step 4: Writing index.html file ===")
with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("? Successfully generated index.html!")
