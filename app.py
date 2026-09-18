import json
import os
import re
import sys
import time
import feedparser
import requests
from github import Auth, Github

# ---------------------------------------------------------
# 1. Custom Clean Environment Loader
# ---------------------------------------------------------
base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, ".env")


def manual_load_env(filepath: str):
    """Reads .env safely ignoring Windows UTF-8, UTF-16, or BOM artifacts."""
    if not os.path.exists(filepath):
        return

    for encoding in ["utf-8-sig", "utf-8", "utf-16", "latin-1"]:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and not os.getenv(key):
                        os.environ[key] = val
            break
        except (UnicodeDecodeError, Exception):
            continue


manual_load_env(env_path)

RAW_GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_KEY = re.sub(r"[^\w\.-]", "", RAW_GROQ_KEY)

RAW_GH_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_TOKEN = re.sub(r"[^\w\.-]", "", RAW_GH_TOKEN)

GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip()
WP_SITE_URL = os.getenv("WP_SITE_URL", "").strip()
WP_USERNAME = os.getenv("WP_USERNAME", "").strip()
WP_APP_PASSWORD = os.getenv("WP_APPLICATION_PASSWORD", "").strip()

if not GROQ_API_KEY:
    print(f"ERROR: GROQ_API_KEY is missing or invalid in '{env_path}'.")
    sys.exit(1)

# ---------------------------------------------------------
# 2. Multi-Market RSS Ingestion
# ---------------------------------------------------------
NEWS_FEEDS = {
    "Forex & Global Macro (FXStreet)": "https://www.fxstreet.com/rss/news",
    "Forex & Central Banks (ForexLive)": "https://www.forexlive.com/feed/news",
    "Indian Equity & Economy": "https://www.moneycontrol.com/rss/MCtopnews.xml",
    "Crypto (Top 5 & Market)": "https://cointelegraph.com/rss",
    "Global Markets & Commodities": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}


def fetch_multi_sector_news() -> list:
    """Collects top market news items from configured RSS sources."""
    collected_articles = []
    for category, url in NEWS_FEEDS.items():
        print(f"Fetching: {category}...")
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                for entry in feed.entries[:2]:
                    collected_articles.append(
                        {
                            "category": category,
                            "title": entry.title,
                            "summary": getattr(
                                entry,
                                "summary",
                                getattr(entry, "description", ""),
                            ),
                            "link": entry.link,
                        }
                    )
        except Exception as e:
            print(f"  └─ Warning: Failed to fetch {category}: {e}")
    return collected_articles


# ---------------------------------------------------------
# 3. Groq AI Synthesis (Dynamic Model Discovery)
# ---------------------------------------------------------
def process_with_ai(articles: list) -> dict:
    """Dynamically fetches active Groq models and uses the first available text synthesis model."""
    articles_context = json.dumps(articles, indent=2)

    prompt = f"""
    You are a senior financial analyst. Synthesize the following raw market news into a simple daily summary for an everyday investor:
    {articles_context}

    Output strictly valid JSON with these exact keys:
    - "title": Impactful headline under 12 words.
    - "html_content": Clean HTML snippet (using <h3>, <ul>, <li>, <b> tags) covering:
        1. Indian Stock Market & ADRs
        2. Forex & Global Currency Impact (USD/INR, Yen, Central Bank Rates)
        3. Crude Oil & Commodities (Impact on India)
        4. Gold & Silver Trends
        5. Crypto Top 5 Coins
    """

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    # Query active Groq catalog dynamically
    try:
        models_res = requests.get(
            "https://api.groq.com/openai/v1/models", headers=headers, timeout=10
        )
        if models_res.status_code == 200:
            available_models = [
                m["id"] for m in models_res.json().get("data", [])
            ]
        else:
            available_models = []
    except Exception as e:
        print(f"Notice: Could not fetch active model list dynamically: {e}")
        available_models = []

    preferred_keywords = ["llama-3", "llama3", "deepseek", "mixtral", "gemma"]
    candidate_models = []

    for kw in preferred_keywords:
        for m_id in available_models:
            if kw in m_id.lower() and m_id not in candidate_models:
                candidate_models.append(m_id)

    if not candidate_models:
        candidate_models = available_models or [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "deepseek-r1-distill-llama-70b",
        ]

    url = "https://api.groq.com/openai/v1/chat/completions"

    for model_name in candidate_models:
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You output strictly valid JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=30
            )
            res_data = response.json()

            if response.status_code == 200:
                raw_content = res_data["choices"][0]["message"]["content"]
                print(f"  └─ Successfully generated output using '{model_name}'")
                return json.loads(raw_content)
            else:
                err_msg = res_data.get("error", {}).get(
                    "message", response.text
                )
                print(
                    f"Notice: Model '{model_name}' failed ({response.status_code}). Trying next..."
                )
        except Exception as e:
            print(f"Notice: Connection error on {model_name}: {e}")

    print("ERROR: All active Groq models failed or were unavailable.")
    sys.exit(1)


# ---------------------------------------------------------
# 4. Publishing Gateways
# ---------------------------------------------------------
def publish_to_wordpress(title: str, html_body: str) -> bool:
    """Publishes post to WordPress REST API."""
    if not WP_SITE_URL or "yourwebsite.com" in WP_SITE_URL or not WP_USERNAME:
        return False

    endpoint = f"{WP_SITE_URL.rstrip('/')}/wp-json/wp/v2/posts"
    post_data = {"title": title, "content": html_body, "status": "draft"}
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }

    try:
        res = requests.post(
            endpoint,
            json=post_data,
            auth=(WP_USERNAME, WP_APP_PASSWORD),
            headers=headers,
            timeout=20,
        )
        if res.status_code in (200, 201):
            print(f"✅ Created WordPress draft: {res.json().get('link')}")
            return True
        return False
    except Exception:
        return False


def publish_to_github_pages(title: str, html_body: str) -> bool:
    """Updates index.html on GitHub Pages using modern PyGitHub Auth."""
    if (
        not GITHUB_TOKEN
        or not GITHUB_REPO
        or "your-github-username" in GITHUB_REPO
    ):
        return False

    try:
        auth = Auth.Token(GITHUB_TOKEN)
        g = Github(auth=auth)
        repo = g.get_repo(GITHUB_REPO)

        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 850px; margin: 40px auto; padding: 0 20px; line-height: 1.6; background-color: #f8fafc; color: #1e293b; }}
        h1 {{ color: #0f172a; border-bottom: 3px solid #0284c7; padding-bottom: 12px; font-size: 1.8rem; }}
        h3 {{ color: #0369a1; margin-top: 25px; border-left: 4px solid #0284c7; padding-left: 10px; }}
        ul {{ background: #ffffff; padding: 20px 35px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); list-style-type: square; }}
        li {{ margin-bottom: 12px; }}
        b {{ color: #0f172a; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    {html_body}
</body>
</html>"""

        try:
            contents = repo.get_contents("index.html")
            repo.update_file(
                contents.path,
                "Automated Daily Financial Update",
                full_html,
                contents.sha,
            )
            print("✅ Successfully updated live website on GitHub Pages!")
            return True
        except Exception:
            repo.create_file(
                "index.html", "Initial Website Publishing", full_html
            )
            print("✅ Successfully created new index.html on GitHub Pages!")
            return True
    except Exception as e:
        print(f"GitHub Pages Error: {e}")
        return False


# ---------------------------------------------------------
# 5. Pipeline Entrypoint
# ---------------------------------------------------------
def main():
    print("=== Step 1: Ingesting Live Market Feeds ===")
    news = fetch_multi_sector_news()
    print(f"Total articles gathered: {len(news)}")

    print("\n=== Step 2: Simplifying News with Free Groq AI ===")
    result = process_with_ai(news)

    print("\n=== Step 3: Publishing Website Update ===")
    wp_success = publish_to_wordpress(result["title"], result["html_content"])
    gh_success = publish_to_github_pages(
        result["title"], result["html_content"]
    )

    if not wp_success and not gh_success:
        print(
            "\n[Preview Mode]: Hosting credentials not active or host blocked request."
        )
        print("Generated output preview:\n")
        print(f"TITLE: {result['title']}\n")
        print(f"HTML CONTENT:\n{result['html_content']}\n")


if __name__ == "__main__":
    main()