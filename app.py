from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from newsapi import NewsApiClient
from newsapi.newsapi_exception import NewsAPIException
import csv


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ← your NewsAPI key:
newsapi = NewsApiClient(api_key="066812ee48ac40448e0ec0bc53903897")

def load_holdings(path="holdings.csv"):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    holdings = load_holdings()

    holdings_with_news = []
    for h in holdings:
        tradingsymbol = h["tradingsymbol"].strip()
        articles = []

        if tradingsymbol:
            try:
                # fetch top 3 matching articles
                resp = newsapi.get_everything(
                    q=tradingsymbol,
                    language="en",
                    sort_by="publishedAt",
                    page_size=3
                )
                articles = resp.get("articles", [])
            except NewsAPIException as e:
                # If NewsAPI complains about missing parameters, log & skip
                print(f"⚠️ NewsAPIException for '{tradingsymbol}': {e}")
                # —or fallback to top-headlines if you prefer:
                # top = newsapi.get_top_headlines(country="in", page_size=3)
                # articles = top.get("articles", [])
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
