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


def expand_query_with_gpt(company_name, sector, description):
    prompt = (
        f"Given the company name '{company_name}', its sector '{sector}', and description:\n"
        f"{description}\n\n"
        "List and explain all key factors that can influence the stock price of this company. Include:\n\n"
        "- Macroeconomic Factors: RBI interest rate changes, inflation, fiscal policy, and global economic trends\n"
        "- Regulatory Environment: sector-specific rules (e.g., IRDAI, SEBI), FDI policy, tax law changes\n"
        "- Industry Trends: digital adoption, growth or contraction, consumer behavior, innovation in the sector\n"
        "- Company-Specific Fundamentals: earnings, guidance, partnerships, new products, M&A, promoter actions\n"
        "- Competitive Landscape: peer moves, pricing pressure, market share shifts\n"
        "- Parent or Group Influence: performance of parent/group companies\n"
        "- Board Member and Executive News: appointments, resignations, controversies, statements\n"
        "- Media and Market Sentiment: headlines, analyst ratings, social media buzz\n\n"
        "Now, generate a **single enriched search query string** (max 150 characters) using relevant keywords from above that may help find news affecting the company's stock."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ GPT enrichment failed: {e}")
        return company_name


def is_article_relevant(article_title, article_desc, company_name, enriched_query):
    content = f"Title: {article_title}\nDescription: {article_desc}\n"
    prompt = (
        f"Given the following article:\n{content}\n\n"
        f"Is this article relevant to the stock performance or business developments of '{company_name}'? "
        f"Use the context of this enriched keyword list: {enriched_query}.\n"
        "Respond only with 'yes' or 'no'."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content.strip().lower() == "yes"
    except Exception as e:
        print(f"GPT relevance check failed: {e}")
        return False


@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    holdings = load_holdings()
    holdings_with_news = []

    # Fetch business news
    params = {
        "topic": "business",
        "lang": "en",
        "country": "in",
        "max": 50,
        "token": GNEWS_API_KEY
    }
    resp = requests.get(GNEWS_ENDPOINT, params=params)
    if resp.status_code != 200:
        print(f"❌ GNews failed: {resp.status_code} - {resp.text}")
        return templates.TemplateResponse("holdings.html", {"request": request, "data": []})

    data = resp.json()
    all_articles = data.get("articles", [])
    seen_urls = set()

    for h in holdings:
        tradingsymbol = h["tradingsymbol"].strip()
        relevant_articles = []

        if not tradingsymbol:
            continue

        yf_ticker = yf.Ticker(f"{tradingsymbol}.NS")
        info = yf_ticker.info
        company_name = info.get("longName", tradingsymbol)
        sector = info.get("sector", "")
        description = info.get("longBusinessSummary", "")

        enriched_query = expand_query_with_gpt(company_name, sector, description)

        for article in all_articles:
            url = article.get("url")
            if url in seen_urls:
                continue

            title = article.get("title", "")
            desc = article.get("description", "")
            if is_article_relevant(title, desc, company_name, enriched_query):
                relevant_articles.append(article)
                seen_urls.add(url)

        holdings_with_news.append({
            "symbol":     tradingsymbol,
            "quantity":   h["quantity"],
            "avg_price":  h["average_price"],
            "last_price": h["last_price"],
            "articles":   relevant_articles
        })

    return templates.TemplateResponse(
        "holdings.html",
        {"request": request, "data": holdings_with_news}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
