from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
import csv
import yfinance as yf

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

GNEWS_API_KEY = "bff075c4b9fc381c5273d513d0ff7e19"
GNEWS_ENDPOINT = "https://gnews.io/api/v4/search"

def load_holdings(path="holdings.csv"):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)

def get_company_name(ticker):
    try:
        full_ticker = f"{ticker}.NS"  # NSE-specific
        stock = yf.Ticker(full_ticker)
        return stock.info.get("longName") or stock.info.get("shortName") or ticker
    except Exception as e:
        print(f"⚠️ Could not fetch company name for {ticker}: {e}")
        return ticker  # fallback

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    holdings = load_holdings()
    holdings_with_news = []

    for h in holdings:
        tradingsymbol = h["tradingsymbol"].strip()
        articles = []
        query_term = tradingsymbol

        if tradingsymbol:
            company_name = get_company_name(tradingsymbol)
            query_term = company_name if company_name else tradingsymbol
            print(f"🔍 Searching GNews for: '{query_term}'")

            try:
                params = {
                    "q": query_term,
                    "lang": "en",
                    "max": 3,
                    "token": GNEWS_API_KEY
                }
                resp = requests.get(GNEWS_ENDPOINT, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    articles = data.get("articles", [])
                else:
                    print(f"⚠️ GNews API error for '{query_term}': {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"⚠️ Error fetching GNews for '{query_term}': {e}")
        else:
            print("⚠️ Skipping empty symbol entry")

        holdings_with_news.append({
            "symbol":     tradingsymbol or "(no symbol)",
            "quantity":   h["quantity"],
            "avg_price":  h["average_price"],
            "last_price": h["last_price"],
            "articles":   articles
        })

    return templates.TemplateResponse(
        "holdings.html",
        {"request": request, "data": holdings_with_news}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
