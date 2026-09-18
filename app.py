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

# RSS Feeds for Financial Market Updates
RAW_RSS_FEEDS = [
    "https://news.google.com/rss/search?q=nifty+sensex+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=usd+inr+forex+crypto+commodities&hl=en-IN&gl=IN&ceid=IN:en"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_url(url_str):
    """Strips Markdown links or extra brackets if copied accidentally."""
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
        for entry in feed.entries[:5]:  # Top 5 articles per feed
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
payload = {
    "model": "llama-3.3-70b-versatile",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0.5
}

response = requests.post(groq_url, json=payload, headers=groq_headers)
if response.status_code != 200:
    print(f"❌ Groq API Error: {response.status_code} - {response.text}")