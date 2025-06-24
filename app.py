# Full `app.py` with GPT-based article relevance and duplicate article filtering

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import csv
import yfinance as yf
from openai import OpenAI
import re
from dotenv import load_dotenv
import os
import json
import logging
from datetime import datetime, timedelta

load_dotenv()  # Load variables from .env into the environment
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

GNEWS_ENDPOINT = "https://gnews.io/api/v4/top-headlines"

client = OpenAI(api_key=openai_api_key)


def clean_query_string(text, max_length=150):
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()[:max_length]


def load_holdings(path="holdings.csv"):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


# configure basic logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def expand_query_with_gpt(company_name, sector, description):
    prompt = (
        f"You are a financial news analyst.\n"
        f"Company: \"{company_name}\" (sector: {sector})\n"
        f"Description:\n{description}\n\n"
        "Task: List up to 8 keywords or short phrases that are most likely to appear in recent news headlines or summaries about this company and its sector.\n"
        "- Focus on: the company's full name, ticker symbol, and common abbreviations; major products, services, platforms, or technologies; key partnerships, acquisitions, or regulatory events; sector-specific terms, regulatory bodies, or market trends relevant to this company; synonyms or alternate names used in the media.\n"
        "- Do NOT include generic financial terms like growth, performance, sentiment, economic, investment, market, financial, etc.\n"
        "- Prefer terms that are likely to be used in news headlines or summaries.\n"
        "Output only a single space-separated string of those keywords or phrases."
    )
    try:
        logging.info(f"[GPT] expand_query for {company_name!r}")
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        enriched = resp.choices[0].message.content.strip()
        logging.info(f"[GPT] enriched_query: {enriched}")
        return enriched
    except Exception as e:
        logging.error(f"⚠️ enrich failed for {company_name!r}: {e}")
        return company_name  # fallback to company name

def is_article_relevant(article, company_name, enriched_query, threshold=1):
    title = article.get("title", "")
    desc  = article.get("description", "")
    # 1) Primary: binary GPT check
    prompt = (
        f"You are a news classifier.\n"
        f"Title: {title}\n"
        f"Description: {desc}\n"
        f"Keywords: {enriched_query}\n\n"
        "Check if the article is relevant to the company's business or stock performance. "
        "If it is, return a relevant score between 0 and 100. "
        "If it is not, return a score of 0."
    )
    try:
        logging.info(f"[GPT] relevance check for article: {title!r}")
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        answer = resp.choices[0].message.content.strip().upper()
        logging.info(f"[GPT] raw answer: {answer!r}")
        if answer == "YES":
            return True
    except Exception as e:
        logging.error(f"⚠️ relevance GPT error on {title!r}: {e}")

    # 2) Fallback: simple keyword‐presence scan (REMOVED)
    # text = (title + " " + desc).lower()
    # for kw in enriched_query.split():
    #     if len(kw) > 2 and kw.lower() in text:
    #         logging.info(f"[fallback] matched keyword "{kw}" in article {title!r}")
    #         return True

    return False

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    holdings = load_holdings()
    # 1. Fetch top business headlines for the top section
    top_headlines = requests.get(
        GNEWS_ENDPOINT,
        params={"topic": "business", "lang": "en", "country": "in", "max": 10, "token": GNEWS_API_KEY}
    ).json().get("articles", [])

    # 2. For each holding, fetch company-specific news using the search API
    holdings_with_news = []
    for h in holdings:
        symbol = h["tradingsymbol"].strip()
        if not symbol:
            continue

        logging.info(f"Processing {symbol}")
        info = yf.Ticker(f"{symbol}.NS").info
        name = info.get("longName", symbol)
        sector = info.get("sector", "")
        desc = info.get("longBusinessSummary", "")

        # Use yfinance to get price history for day, week, month change
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(period="1mo")
        last_price = hist["Close"].iloc[-1] if not hist.empty else None
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else last_price
        day_change_pct = ((last_price - prev_close) / prev_close * 100) if last_price and prev_close else None
        # Weekly change: compare last price to price 5 trading days ago
        week_ago_idx = -6 if len(hist) >= 6 else 0
        week_ago = hist["Close"].iloc[week_ago_idx] if not hist.empty else None
        week_change_pct = ((last_price - week_ago) / week_ago * 100) if last_price and week_ago and week_ago != 0 else None
        # Monthly change: compare last price to first price in the month
        month_ago = hist["Close"].iloc[0] if not hist.empty else None
        month_change_pct = ((last_price - month_ago) / month_ago * 100) if last_price and month_ago and month_ago != 0 else None

        # Use LLM to generate search keywords
        enriched_query = expand_query_with_gpt(name, sector, desc)
        logging.info(f"[DEBUG] enriched_query for {symbol}: {enriched_query}")

        # Search for each keyword and company name separately, aggregate and deduplicate
        recent_days = 2
        from_date = (datetime.utcnow() - timedelta(days=recent_days)).strftime('%Y-%m-%dT%H:%M:%SZ')
        search_terms = [name] + enriched_query.split()
        all_articles = []
        seen_urls = set()
        for term in search_terms:
            params = {
                "q": term,
                "lang": "en",
                "country": "in",
                "max": 5,  # limit per term to avoid flooding
                "from": from_date,
                "token": GNEWS_API_KEY
            }
            try:
                resp = requests.get("https://gnews.io/api/v4/search", params=params)
                articles = resp.json().get("articles", [])
                for art in articles:
                    if art["url"] not in seen_urls:
                        seen_urls.add(art["url"])
                        all_articles.append(art)
            except Exception as e:
                logging.error(f"Error fetching search news for {symbol} with term '{term}': {e}")

        # Optionally filter with is_article_relevant
        relevant = [art for art in all_articles if is_article_relevant(art, name, enriched_query)]

        logging.info(f"{symbol}: found {len(relevant)} relevant articles")
        holdings_with_news.append({
            "symbol":        symbol,
            "quantity":      h["quantity"],
            "avg_price":     h["average_price"],
            "last_price":    last_price,
            "day_change_pct": day_change_pct,
            "week_change_pct": week_change_pct,
            "month_change_pct": month_change_pct,
            "enriched_query": enriched_query,   # pass it through so you can print in the template
            "articles":      relevant
        })

    return templates.TemplateResponse(
        "holdings.html",
        {"request": request, "top_headlines": top_headlines, "data": holdings_with_news}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
