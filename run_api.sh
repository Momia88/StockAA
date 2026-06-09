#!/bin/bash
# StockAA — 啟動 FastAPI 後端（未來 App 使用）
cd "$(dirname "$0")"
.venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
