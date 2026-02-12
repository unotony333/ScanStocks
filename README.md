# 股票篩選 (ScanStocks)

一個簡單的台灣上市股票篩選腳本，會使用 FinMind API 抓取股價、財報與營收資料，根據自訂條件篩選出符合的標的，並可透過 Telegram 發送通知。

**主要檔案**
- [main.py](main.py#L1-L400): 篩選與通知主程式。
- [requirements.txt](requirements.txt#L1-L4): 執行所需套件列表。

**專案特色**
- 使用 FinMind API 取得股價、PE、營收等資料。
- 具備兩輪重試機制以提高資料抓取成功率。
- 可選擇透過 Telegram 發送篩選結果通知，或在未設定時於終端機列印模擬訊息。

**需求**
- Python 3.10 或更新版本
- 參考並安裝依賴：

```bash
pip install -r requirements.txt
```

或個別安裝：`pandas`, `FinMind`, `requests`, `tqdm`。

**環境變數（可選）**
- `TELEGRAM_TOKEN`: Telegram bot 的 token（若要發送通知則需設定）。
- `CHAT_ID`: 接收通知的 chat id。
- `FINMIND_TOKEN`: FinMind API token（若有，可設定以提高配額或權限）。

範例（Linux / macOS）：

```bash
export TELEGRAM_TOKEN="<your-telegram-bot-token>"
export CHAT_ID="<your-chat-id>"
export FINMIND_TOKEN="<your-finmind-token>"
python main.py
```

若未設定 `TELEGRAM_TOKEN` 或 `CHAT_ID`，程式會以 `[TG 模擬]` 前綴在終端機列印通知內容，方便測試。

**使用說明（重點）**
- 篩選邏輯位於 `process_stock()`，主要條件包括：近五日平均成交量、當前價接近 52 週高點、本益比範圍與營收年增率等。可根據需求調整條件或時間區間。
- 為避免 FinMind API 配額問題，程式有簡單的呼叫次數計數與接近上限時暫停機制（見程式內註解）。

**範例輸出**
- 成功篩選並發送的訊息格式示例：

```text
🎯 【達標】 2330
現價: 700.0
PE: 10.50
營收YoY: 25.0%
```
