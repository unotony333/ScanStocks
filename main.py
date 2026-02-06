import os
import time
import pandas as pd
from FinMind.data import DataLoader
import requests

# --- 設定區 ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN")

api_call_count = 0  # 追蹤 API 呼叫次數
error_log = []      # 記錄失敗的標的

def send_telegram_msg(message):
    """只用於核心通知"""
    if not TOKEN or not CHAT_ID:
        print(f"[TG 模擬] {message}")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=payload, timeout=10)
        result = r.json()
        if not result.get('ok'):
            print(f"Telegram 發送失敗: {result}")
    except Exception as e:
        print(f"Telegram 發送失敗: {e}")

def call_finmind_api(func, *args, **kwargs):
    """
    包裝 API 呼叫：含計數器、冷卻機制與重試邏輯
    非必要通知改用 print
    """
    global api_call_count
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            # 處理 600 次限制
            api_call_count += 1
            if api_call_count >= 590:
                print(f"⏳ API 接近上限 ({api_call_count})，本地等待 1 小時...")
                time.sleep(3605)
                api_call_count = 1
            
            return func(*args, **kwargs)
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠️ API 錯誤: {e}, 正在進行第 {attempt + 1} 次重試...")
                time.sleep(retry_delay)
                continue
            else:
                raise e

def scan_tse_stocks():
    dl = DataLoader()
    if FINMIND_TOKEN:
        dl.api_token = FINMIND_TOKEN
    
    try:
        # 取得上市清單 (必要時 print 日誌)
        stock_info = call_finmind_api(dl.taiwan_stock_info)
        tse_list = stock_info[
            (stock_info['industry_category'] != 'ETF') & 
            (stock_info['type'] == 'twse') & 
            (stock_info['stock_id'].str.len() == 4)
        ]['stock_id'].tolist()
        
        print(f"🚀 開始掃描上市股共 {len(tse_list)} 檔...")
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
        return

    match_count = 0
    results = []

    for stock_id in tse_list:
        try:
            # --- 步驟 1: 股價 ---
            price_df = call_finmind_api(dl.taiwan_stock_daily, stock_id=stock_id, start_date='2025-01-01')
            
            if price_df.empty or len(price_df) < 60:
                continue

            # 門檻過濾：均量 > 500張 & 52週新高
            avg_vol = price_df['Trading_Volume'].tail(5).mean() / 1000
            current_price = price_df['close'].iloc[-1]
            max_price_52w = price_df['max'].max()
            
            if avg_vol < 500 or current_price < max_price_52w * 0.99:
                continue

            # --- 步驟 2: 本益比 ---
            pe_df = call_finmind_api(dl.taiwan_stock_per_pbr(stock_id=stock_id))
            if pe_df.empty or pe_df['PE'].iloc[-1] <= 0 or pe_df['PE'].iloc[-1] > 12:
                continue

            # --- 步驟 3: 營收 ---
            rev_df = call_finmind_api(dl.taiwan_stock_month_revenue, stock_id=stock_id).tail(3)
            if rev_df.empty or rev_df['revenue_month_growth_rate'].mean() < 20:
                continue

            # --- 🎯 必要通知：發現標的 ---
            match_count += 1
            msg = (f"🎯 【達標】 {stock_id}\n"
                   f"現價: {current_price}\n"
                   f"PE: {pe_df['PE'].iloc[-1]:.2f}\n"
                   f"營收YoY: {rev_df['revenue_month_growth_rate'].mean():.1f}%")
            
            send_telegram_msg(msg)
            print(f"✅ 發現標的：{stock_id}")

        except Exception as e:
            print(f"❌ {stock_id} 處理出錯: {e}")
            error_log.append(stock_id)
            continue

    # --- 🎯 必要通知：掃描結算 ---
    final_summary = f"🏁 掃描完畢。\n符合標的數: {match_count}"
    if error_log:
        final_summary += f"\n(註: 有 {len(error_log)} 檔執行失敗，請查看 Log)"
    
    send_telegram_msg(final_summary)

if __name__ == "__main__":
    scan_tse_stocks()