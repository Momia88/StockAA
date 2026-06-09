# StockAA 桌面版打包說明

將 Streamlit Web UI 打包成 macOS / Windows 可直接執行的獨立程式。

## 檔案

| 檔案 | 用途 |
|------|------|
| `run_desktop.py` | 桌面啟動器：啟動內嵌 Streamlit 並開啟瀏覽器 |
| `StockAA.spec` | PyInstaller 打包設定（跨平台） |
| `../requirements-desktop.txt` | 桌面版執行所需相依 |
| `../.github/workflows/build-desktop.yml` | GitHub Actions 自動建置 |

## 推薦：透過 GitHub Actions 建置（雲端、雙平台）

PyInstaller **無法跨平台編譯**——Mac 上做不出 Windows `.exe`。
透過 GitHub Actions 可同時產出兩種平台執行檔。

1. 將專案推上 GitHub。
2. 觸發建置（擇一）：
   - **打 tag**：`git tag v1.0.0 && git push origin v1.0.0`
     → 自動建置並把產物附加到該版本的 Release。
   - **手動**：GitHub repo → Actions → 「Build Desktop App」→ Run workflow。
3. 完成後於 Actions 該次執行頁面（或 Release）下載：
   - `StockAA-macOS-arm64.zip`
   - `StockAA-Windows-x64.zip`

> CI 使用 Python 3.12（PyInstaller 完整支援），與本機 Python 3.14 無關。
> Intel Mac 需求：在 workflow matrix 取消 `macos-13` 那段註解即可。

## 使用方式（解壓後）

- **macOS**：執行 `StockAA/StockAA`。首次開啟若被 Gatekeeper 攔下，
  於「系統設定 → 隱私權與安全性」按「仍要開啟」，或對檔案按右鍵 →「開啟」。
- **Windows**：執行 `StockAA/StockAA.exe`。若跳出 SmartScreen，
  點「其他資訊 → 仍要執行」。

程式會自動：
1. 在使用者家目錄建立 `~/StockAA/` 資料夾（存放 `portfolio.db` 與 `logs/`）。
2. 啟動本機伺服器並開啟瀏覽器到 `http://localhost:8501`。

### 搭配 Google Drive 同步

在 `~/StockAA/` 放一個 `.env`，內容指向 Google Drive 同步資料夾即可：

```
DB_PATH=/Users/<你的帳號>/Google Drive/My Drive/StockAA/portfolio.db
```

## 本機自行建置（選用，僅產出當前平台）

需先以「PyInstaller 有支援的 Python 版本」（建議 3.12）建立虛擬環境：

```bash
python3.12 -m venv .venv-build
source .venv-build/bin/activate        # Windows: .venv-build\Scripts\activate
pip install -r requirements-desktop.txt pyinstaller
pyinstaller packaging/StockAA.spec --noconfirm
# 產物：dist/StockAA/
```

> ⚠️ 本專案開發環境為 Python 3.14，PyInstaller 對 3.14 支援尚不穩定，
> 直接用 3.14 打包可能失敗。建置請改用 3.12。
