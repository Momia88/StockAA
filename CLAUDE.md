# CLAUDE.md — 代理人憲法 (Agent Constitution)
## 專案：台灣股市投資組合管理系統 (StockAA)

---

## 🏛️ 核心行為準則

你是本專案的首席架構師與開發者。所有你產出的程式碼與設計決策，必須遵守以下規範。

---

## 🎯 專案範疇（MVP 定義）

- **市場**：僅限台灣市場（TWSE 上市 + TPEx 上櫃）
- **資產類型**：台灣個股、股票型 ETF（如 0050、006208）、債券型 ETF（如 00679B）
- **計價幣別**：統一使用 **新台幣 (TWD)**，無多幣別需求
- **成本計算法**：**平均成本法（Average Cost）**
- **用戶模式**：單一用戶，無需認證或多用戶支援
- **資料同步**：透過 Google Drive 本機資料夾自動同步 SQLite 檔案

---

## 📐 資料結構規範 (Data Schema)

### AssetType 枚舉
```python
class AssetType(str, Enum):
    STOCK = "STOCK"           # 個股（如 2330 台積電）
    STOCK_ETF = "STOCK_ETF"   # 股票型 ETF（如 0050）
    BOND_ETF = "BOND_ETF"     # 債券型 ETF（如 00679B）
```

### TxAction 枚舉
```python
class TxAction(str, Enum):
    BUY = "BUY"               # 買入
    SELL = "SELL"             # 賣出
    DIVIDEND = "DIVIDEND"     # 現金股息
    STOCK_DIVIDEND = "STOCK_DIVIDEND"  # 股票股利
    SPLIT = "SPLIT"           # 股票分割/合併
```

### Asset（持倉快照）核心欄位
```python
@dataclass
class Asset:
    id: str               # UUID
    ticker: str           # 股票代碼（純數字或英數，如 "2330", "0050", "00679B"）
    name: str             # 股票名稱（如 "台積電", "元大台灣50"）
    asset_type: AssetType # 資產類型
    exchange: str         # "TWSE" 或 "TPEx"
    avg_cost: float       # 平均持有成本（含手續費，TWD）
    quantity: int         # 持有股數（台灣股市最小單位：1股，整張=1000股）
    total_invested: float # 總投入金額（TWD）
    first_buy_date: date  # 首次買入日
    notes: str            # 備註
```

### Transaction（交易記錄）核心欄位
```python
@dataclass
class Transaction:
    id: str               # UUID
    ticker: str           # 股票代碼
    action: TxAction      # 交易類型
    price: float          # 交易單價（TWD，元/股）
    quantity: int         # 交易股數
    fee: float            # 手續費（買賣雙向，最低 20 元，0.1425%）
    tax: float            # 證券交易稅（賣出 0.3%，ETF 賣出 0.1%）
    net_amount: float     # 淨交易金額（正=支出，負=收入）
    trade_date: date      # 交易日（民國/西元均接受，統一轉 date 儲存）
    settlement_date: date # 交割日（T+2）
    note: str             # 備註
```

---

## 💰 費用計算規範（台灣股市）

### 手續費
- 費率：**0.1425%**（買入與賣出均收）
- 最低手續費：**20 元**
- 公式：`fee = max(price * quantity * 0.001425, 20)`
- 網路下單折扣：可設定折扣率（預設 1.0，可改 0.6 代表六折）

### 證券交易稅（賣出才收）
- 個股：`tax = price * quantity * 0.003`（0.3%）
- ETF（股票型＋債券型）：`tax = price * quantity * 0.001`（0.1%）

### 平均成本計算
```
買入時：
  new_avg_cost = (舊持倉成本總額 + 本次買入總成本含手續費) / 新總持股數

賣出時：
  已實現損益 = (賣出單價 - 賣出當時平均成本) × 賣出股數 - 手續費 - 交易稅
  avg_cost 不變（平均成本法）
```

---

## 🔌 數據源規範

### 主要數據源（免費、官方）
1. **TWSE Open API** (`https://openapi.twse.com.tw/v1/`)
   - 用途：上市股票即時/收盤行情、公司基本資料
   - 端點：`/exchangeReport/STOCK_DAY_ALL`（全市場日行情）

2. **TPEx Open API** (`https://www.tpex.org.tw/openapi/`)
   - 用途：上櫃股票行情
   - 端點：`/v1/exchangeReport/DAILY_CLOSE_QUOTES`

3. **TWSE 歷史行情** (`https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY`)
   - 用途：個股月歷史行情（查詢損益基準）

### 數據抓取規範
- 所有 HTTP 請求**必須**設定 `User-Agent` header（避免被 403 封鎖）
- **必須**實作 retry（最多 3 次，退避 2 秒）
- **必須**將當日行情快取到本地 SQLite（避免重複打 API）
- 快取有效期：**交易日結束後（17:00 後）更新一次**

---

## 🗄️ 資料庫規範

### 資料庫引擎
- **SQLite**（單檔案 `portfolio.db`）
- 使用 **SQLAlchemy 2.0 ORM**
- 資料庫遷移使用 **Alembic**

### Google Drive 同步策略
- `portfolio.db` 儲存於 Google Drive 本機同步資料夾
- 路徑設定在 `.env` 中：`DB_PATH=/Users/{username}/Google\ Drive/My\ Drive/StockAA/portfolio.db`
- ⚠️ **警告**：勿在多裝置同時寫入（Google Drive 不支援並發寫入保護）
- 建議：每次操作前確認 Google Drive 同步完成

---

## 🏗️ 架構規範

- **設計模式**: Repository Pattern + Service Layer
- **設定管理**: `pydantic-settings` + `.env`，**禁止硬編碼任何路徑或參數**
- **日誌**: `loguru`，記錄所有 API 調用
- **測試**: `pytest`，財務計算邏輯覆蓋率 > 90%
- **CLI**: `typer` + `rich`（美化終端機輸出）

---

## ⛔ 禁止行為

1. **禁止**混用西元年與民國年（統一儲存西元年，顯示時可轉換民國年）
2. **禁止**使用浮點數直接比較金額（使用 `Decimal` 或乘以 100 轉整數）
3. **禁止**在未建立測試的情況下提交財務計算邏輯
4. **禁止**忽略手續費最低 20 元的限制
5. **禁止**對 ETF 賣出使用 0.3% 交易稅（應為 0.1%）
6. **禁止**將 portfolio.db 提交至 Git（應加入 .gitignore）
