import os
import time
import pandas as pd
from FinMind.data import DataLoader
import requests

# --- 設定區 ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN")

api_call_count = 0
match_list = []  # 存儲成功標的代碼

def send_telegram_msg(message):
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
    global api_call_count
    max_retries = 2  # 即時重試次數
    for attempt in range(max_retries + 1):
        try:
            api_call_count += 1
            if api_call_count >= 590:
                print(f"⏳ API 接近上限，本地暫停 1 小時...")
                time.sleep(3605)
                api_call_count = 1
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries:
                time.sleep(5)
                continue
            raise e

def process_stock(dl, stock_id):
    """核心選股邏輯，成功回傳訊息字串，失敗則拋出異常"""
    # 1. 股價
    price_df = call_finmind_api(dl.taiwan_stock_daily, stock_id=stock_id, start_date='2025-01-01')
    if price_df.empty or len(price_df) < 60: return None

    avg_vol = price_df['Trading_Volume'].tail(5).mean() / 1000
    current_price = price_df['close'].iloc[-1]
    max_price_52w = price_df['max'].max()
    if avg_vol < 500 or current_price < max_price_52w * 0.99: return None

    # 2. 本益比
    pe_df = call_finmind_api(dl.taiwan_stock_per_pbr, stock_id=stock_id)
    if pe_df.empty or pe_df['PE'].iloc[-1] <= 0 or pe_df['PE'].iloc[-1] > 12: return None

    # 3. 營收
    rev_df = call_finmind_api(dl.taiwan_stock_month_revenue, stock_id=stock_id).tail(3)
    if rev_df.empty or rev_df['revenue_month_growth_rate'].mean() < 20: return None

    return (f"🎯 【達標】 {stock_id}\n現價: {current_price}\n"
            f"PE: {pe_df['PE'].iloc[-1]:.2f}\n"
            f"營收YoY: {rev_df['revenue_month_growth_rate'].mean():.1f}%")

def scan_tse_stocks():
    dl = DataLoader()
    if FINMIND_TOKEN: dl.api_token = FINMIND_TOKEN
    
    try:
        stock_info = call_finmind_api(dl.taiwan_stock_info)
        tse_list = stock_info[(stock_info['type'] == 'twse') & (stock_info['stock_id'].str.len() == 4)]['stock_id'].tolist()
        print(f"🚀 開始掃描上市股 {len(tse_list)} 檔...")
    except Exception as e:
        print(f"初始化失敗: {e}"); return

    failed_list = [] # 記錄徹底失敗的股票

    # --- 第一輪主掃描 ---
    for stock_id in tse_list:
        try:
            result = process_stock(dl, stock_id)
            if result:
                match_list.append(stock_id)
                send_telegram_msg(result)
        except Exception:
            print(f"❌ {stock_id} 暫時失敗，加入二次重試清單")
            failed_list.append(stock_id)

    # --- 第二輪二次嘗試 (Final Retry) ---
    if failed_list:
        print(f"🔍 開始二次補償嘗試，剩餘 {len(failed_list)} 檔...")
        time.sleep(10) # 稍微喘息一下再開始
        
        still_failed_count = 0
        for stock_id in failed_list:
            try:
                result = process_stock(dl, stock_id)
                if result:
                    match_list.append(stock_id)
                    send_telegram_msg(f"♻️ [補償成功]\n{result}")
            except Exception as e:
                print(f"💀 {stock_id} 最終仍失敗: {e}")
                still_failed_count += 1
    
    # --- 總結回報 ---
    summary = f"🏁 掃描完畢\n✅ 符合標的: {', '.join(match_list) if match_list else '無'}"
    if failed_list:
        summary += f"\n⚠️ 最終失敗數: {still_failed_count}"
    send_telegram_msg(summary)

if __name__ == "__main__":
    scan_tse_stocks()