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
        f"Company: “{company_name}” (sector: {sector})\n"
        f"Description:\n{description}\n\n"
        "List the 8 most important keywords that drive its share price, "
        "then output **only** a single space-separated string of those keywords "
        "(max 150 chars)."
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
        "Answer **exactly** YES if any keyword directly relates to this company’s business or stock performance; otherwise NO."
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

    # 2) Fallback: simple keyword‐presence scan
    text = (title + " " + desc).lower()
    for kw in enriched_query.split():
        if len(kw) > 2 and kw.lower() in text:
            logging.info(f"[fallback] matched keyword “{kw}” in article {title!r}")
            return True

    return False

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    holdings = load_holdings()
    all_articles = requests.get(
        GNEWS_ENDPOINT,
        params={"topic": "business","lang": "en","country": "in","max": 50,"token": GNEWS_API_KEY}
    ).json().get("articles", [])

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

        enriched_query = expand_query_with_gpt(name, sector, desc)
        logging.info(f"[DEBUG] enriched_query for {symbol}: {enriched_query}")

        relevant = []
        for art in all_articles:
            if is_article_relevant(art, name, enriched_query):
                relevant.append(art)

        logging.info(f"{symbol}: found {len(relevant)} relevant articles")
        holdings_with_news.append({
            "symbol":        symbol,
            "quantity":      h["quantity"],
            "avg_price":     h["average_price"],
            "last_price":    h["last_price"],
            "enriched_query": enriched_query,   # pass it through so you can print in the template
            "articles":      relevant
        })

    return templates.TemplateResponse(
        "holdings.html",
        {"request": request, "data": holdings_with_news}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
