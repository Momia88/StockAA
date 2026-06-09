"""
StockAA FastAPI 後端入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import portfolio, transactions, prices

app = FastAPI(
    title="StockAA API",
    description="台灣股市投資組合管理 REST API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router)
app.include_router(transactions.router)
app.include_router(prices.router)


@app.get("/health")
def health():
    return {"status": "ok"}
