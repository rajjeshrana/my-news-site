import os
import sys
import re
import requests
import feedparser
from datetime import datetime
from zoneinfo import ZoneInfo

# ==========================================
# 1. SECRETS VALIDATION & CLEANING
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip("'").strip('"')

RAW_RSS_FEEDS = [
    "https://news.google.com/rss/search?q=nifty+sensex+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en",
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
# 2. INGEST RSS FEEDS
# ==========================================
print("=== Step 1: Ingesting Live Market Feeds ===")
articles = []
for feed_url in RSS_FEEDS:
    try:
        resp = requests.get(feed_url, headers=HEADERS, timeout=10)
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:5]:
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
print("=== Step 2: Generating Market Summary ===")
prompt = f"""
You are a financial journalist. Summarize these news articles into simple layman terms under 100 words total.
Organize into EXACTLY 6 HTML blocks formatted as:

<div class="block"><h3>1. Indian Stock Market</h3><p>Simple short text here.</p></div>
<div class="block"><h3>2. Global Markets</h3><p>Simple short text here.</p></div>
<div class="block"><h3>3. Forex</h3><p>Simple short text here.</p></div>
<div class="block"><h3>4. Crypto</h3><p>Simple short text here.</p></div>
<div class="block"><h3>5. Crude & Commodities</h3><p>Simple short text here.</p></div>
<div class="block"><h3>6. Economy & Inflation</h3><p>Simple short text here.</p></div>

RULES:
- Max 100 words total for the entire response.
- Do NOT include markdown blocks like ```html.
- Keep explanation super basic for beginners.

Articles:
{news_text}
"""

raw_groq_url = "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)"
groq_url = clean_url(raw_groq_url)

groq_headers = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

MODELS_TO_TRY = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
ai_html_content = None

if GROQ_API_KEY:
    for model_name in MODELS_TO_TRY:
        print(f"Attempting Groq completion with model: {model_name}")
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        try:
            response = requests.post(groq_url, json=payload, headers=groq_headers, timeout=30)
            if response.status_code == 200:
                ai_html_content = response.json()["choices"][0]["message"]["content"]
                print(f"✅ Success using model: {model_name}")
                break
            else:
                print(f"⚠️ Failed with {model_name}: {response.status_code} - {response.text}")
        except Exception as err:
            print(f"⚠️ Request error with {model_name}: {err}")

# Fallback structured 6-block layout if Groq call fails
if not ai_html_content:
    print("⚠️ Groq API unavailable. Rendering structured 6-block layout from feeds.")
    categories = [
        "Indian Stock Market", "Global Markets", "Forex", 
        "Crypto", "Crude & Commodities", "Economy & Inflation"
    ]
    blocks = []
    for idx, cat in enumerate(categories):
        headline = articles[idx % len(articles)].replace("- ", "")
        blocks.append(f"""
        <div class="block">
            <h3>{idx+1}. {cat}</h3>
            <p>{headline}</p>
        </div>
        """)
    ai_html_content = "".join(blocks)

# ==========================================
# 4. CONSTRUCT HTML PAGE (GRID LAYOUT)
# ==========================================
print("=== Step 3: Formatting HTML Page with Live IST Timestamp ===")
ist_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%b %d, %Y | %I:%M %p IST")

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Market Snapshot</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            max-width: 900