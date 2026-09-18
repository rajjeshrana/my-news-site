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

# Dedicated RSS feeds per category for high information value
CATEGORY_FEEDS = {
    "Indian Stock Market": "https://news.google.com/rss/search?q=nifty+sensex+stock+market+india&hl=en-IN&gl=IN&ceid=IN:en",
    "Global Markets": "https://news.google.com/rss/search?q=nasdaq+sp500+dow+jones+global+markets&hl=en-IN&gl=IN&ceid=IN:en",
    "Forex": "https://news.google.com/rss/search?q=usd+inr+forex+currency+dollar+index&hl=en-IN&gl=IN&ceid=IN:en",
    "Crypto": "https://news.google.com/rss/search?q=bitcoin+ethereum+crypto+market+news&hl=en-IN&gl=IN&ceid=IN:en",
    "Crude & Commodities": "https://news.google.com/rss/search?q=crude+oil+gold+price+commodities&hl=en-IN&gl=IN&ceid=IN:en",
    "Economy & Inflation": "https://news.google.com/rss/search?q=rbi+inflation+gdp+indian+economy+fed+rates&hl=en-IN&gl=IN&ceid=IN:en"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def clean_url(url_str):
    match = re.search(r'https?://[^\s\]\)]+', str(url_str))
    return match.group(0) if match else url_str

# ==========================================
# 2. INGEST CATEGORY FEEDS
# ==========================================
print("=== Step 1: Ingesting Live Categorized Market Feeds ===")
categorized_news = {}
all_articles_text = []

for cat_name, feed_url in CATEGORY_FEEDS.items():
    try:
        clean_f_url = clean_url(feed_url)
        resp = requests.get(clean_f_url, headers=HEADERS, timeout=10)
        feed = feedparser.parse(resp.content)
        titles = [entry.title for entry in feed.entries[:3]]
        if titles:
            categorized_news[cat_name] = titles[0]
            all_articles_text.append(f"[{cat_name}]: " + " | ".join(titles))
        else:
            categorized_news[cat_name] = "Markets showing steady sideways movement today."
    except Exception as e:
        print(f"⚠️ Error fetching {cat_name}: {e}")
        categorized_news[cat_name] = "Market activity trading within standard daily ranges."

news_text = "\n".join(all_articles_text)

# ==========================================
# 3. GENERATE RICH AI SUMMARY VIA GROQ
# ==========================================
print("=== Step 2: Generating Detailed Market Summaries ===")
prompt = f"""
You are an expert financial educator. Explain today's market movements in simple, clear layman terms.
Write a detailed 2-3 sentence update for each of the following 6 categories (~35 words per block, 200-250 words total across the page).

Format your output EXACTLY as 6 HTML blocks like this:

<div class="block">
    <h3>1. Indian Stock Market</h3>
    <p>Detailed explanation in simple words about Nifty/Sensex trend, top drivers, and market mood today.</p>
</div>
<div class="block">
    <h3>2. Global Markets</h3>
    <p>Clear explanation of US and Asian market movements, interest rate expectations, and investor sentiment.</p>
</div>
<div class="block">
    <h3>3. Forex</h3>
    <p>Simple breakdown of the USD/INR currency trend, Rupee movement, and Dollar strength.</p>
</div>
<div class="block">
    <h3>4. Crypto</h3>
    <p>Key updates on Bitcoin, major altcoins, and overall crypto market momentum in basic terms.</p>
</div>
<div class="block">
    <h3>5. Crude & Commodities</h3>
    <p>Updates on Gold prices, Crude oil trends, and what is driving commodity prices today.</p>
</div>
<div class="block">
    <h3>6. Economy & Inflation</h3>
    <p>Simple insights on RBI policy, inflation figures, interest rates, and macro economic growth.</p>
</div>

RULES:
- Provide high information value for readers without complex jargon.
- Do NOT output markdown code blocks (no ```html).

Articles Data:
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
            "temperature": 0.4
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

# Smart Categorized Fallback if Groq API key is inactive
if not ai_html_content:
    print("⚠️ Rendering categorized fallback with full context.")
    blocks = []
    for idx, (cat, headline) in enumerate(categorized_news.items()):
        blocks.append(
            f'<div class="block">'
            f'<h3>{idx+1}. {cat}</h3>'
            f'<p><b>Latest Update:</b> {headline}. Markets are currently reacting to broad sector trends, investor flows, and ongoing economic data releases.</p>'
            f'</div>'
        )
    ai_html_content = "\n".join(blocks)

# ==========================================
# 4. CONSTRUCT HTML PAGE (GRID LAYOUT)
# ==========================================
print("=== Step 3: Formatting HTML Page with Live IST Timestamp ===")
ist_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%b %d, %Y | %I:%M %p IST")

full_html = (
    "<!DOCTYPE html>\n"
    '<html lang="en">\n'
    "<head>\n"
    '    <meta charset="UTF-8">\n'
    '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
    "    <title>Daily Market Snapshot</title>\n"
    "    <style>\n"
    "        body {\n"
    "            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;\n"
    "            max-width: 950px;\n"
    "            margin: 40px auto;\n"
    "            padding: 20px;\n"
    "            color: #2c3e50;\n"
    "            line-height: 1.6;\n"
    "            background-color: #f8f9fa;\n"
    "        }\n"
    "        h1 {\n"
    "            color: #0d47a1;\n"
    "            margin-bottom: 5px;\n"
    "        }\n"
    "        .timestamp {\n"
    "            color: #666;\n"
    "            font-weight: 600;\n"
    "            font-size: 0.95em;\n"
    "            margin-bottom: 20px;\n"
    "        }\n"
    "        hr {\n"
    "            border: 0;\n"
    "            height: 1px;\n"
    "            background: #e0e0e0;\n"
    "            margin-bottom: 25px;\n"
    "        }\n"
    "        .grid-container {\n"
    "            display: grid;\n"
    "            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));\n"
    "            gap: 18px;\n"
    "        }\n"
    "        .block {\n"
    "            background: #ffffff;\n"
    "            border-top: 4px solid #1976d2;\n"
    "            padding: 18px;\n"
    "            border-radius: 8px;\n"
    "            box-shadow: 0 3px 8px rgba(0,0,0,0.06);\n"
    "        }\n"
    "        .block h3 {\n"
    "            margin-top: 0;\n"
    "            margin-bottom: 10px;\n"
    "            color: #0d47a1;\n"
    "            font-size: 1.1em;\n"
    "        }\n"
    "        .block p {\n"
    "            margin: 0;\n"
    "            font-size: 0.95em;\n"
    "            color: #444;\n"
    "        }\n"
    "    </style>\n"
    "</head>\n"
    "<body>\n"
    "    <h1>Daily Market Snapshot</h1>\n"
    f'    <div class="timestamp">🕒 Last Updated: {ist_time}</div>\n'
    "    <hr>\n"
    '    <div class="grid-container">\n'
    f"        {ai_html_content}\n"
    "    </div>\n"
    "</body>\n"
    "</html>"
)

# ==========================================
# 5. WRITE DIRECTLY TO index.html FILE
# ==========================================
print("=== Step 4: Writing index.html file ===")
with open("index.html", "w", encoding="utf-8") as f:
    f.write(full_html)

print("✅ Successfully generated index.html!")