#!/bin/bash
# StockAA — 啟動 Web UI
cd "$(dirname "$0")"
.venv/bin/streamlit run src/web/app.py --server.port 8501 --server.headless false
