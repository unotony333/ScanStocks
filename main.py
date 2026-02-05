import os
import time
import pandas as pd
from FinMind.data import DataLoader
import requests

# --- 從 GitHub Secrets 讀取設定 ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN")

def send_telegram_msg(message):
    if not TOKEN or not CHAT_ID:
        print("Telegram 設定缺失")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"發送訊息失敗: {e}")

def scan_all_taiwan_stocks():
    dl = DataLoader()
    if FINMIND_TOKEN:
        dl.api_token = FINMIND_TOKEN
    
    # 1. 取得全台股清單
    stock_info = dl.taiwan_stock_info()
    # 僅保留普通股 (4位數代碼)
    stock_list = stock_info[stock_info['stock_id'].str.len() == 4]['stock_id'].tolist()
    
    print(f"🚀 開始掃描全市場 {len(stock_list)} 檔標的...")
    match_count = 0
    
    for stock_id in stock_list:
        try:
            # 2. 獲取近期股價資料 (抓取 260 天，足以計算 52 週新高與均量)
            price_df = dl.taiwan_stock_daily(stock_id=stock_id, start_date='2024-02-01')
            if len(price_df) < 20: continue # 排除剛上市的新股
            
            # --- 額外篩選：流動性過濾 ---
            # 計算近 5 日平均成交量 (單位：張)
            avg_volume_5d = price_df['Trading_Volume'].tail(5).mean() / 1000
            if avg_volume_5d < 500: # 門檻：500張 (可自行調整)
                continue

            # 3. 條件篩選邏輯
            current_price = price_df['close'].iloc[-1]
            high_52w = price_df['max'].max()
            
            # 條件 1: 52週新高 (容許 1% 以內的誤差)
            if current_price < high_52w * 0.99:
                continue
                
            # 條件 2: 本益比 < 12
            pe_df = dl.taiwan_stock_per_pbr(stock_id=stock_id)
            if pe_df.empty: continue
            current_pe = pe_df['PE'].iloc[-1]
            if current_pe <= 0 or current_pe > 12:
                continue
            
            # 條件 3: 近三個月營收平均 YoY > 20%
            rev_df = dl.taiwan_stock_month_revenue(stock_id=stock_id).tail(3)
            if rev_df.empty: continue
            avg_yoy = rev_df['revenue_month_growth_rate'].mean()
            if avg_yoy < 20:
                continue
                
            # --- 達標通知 ---
            match_count += 1
            success_msg = (
                f"🎯 【選股達標】 {stock_id}\n"
                f"💰 現價: {current_price}\n"
                f"📊 PE: {current_pe:.2f}\n"
                f"📈 營收平均YoY: {avg_yoy:.1f}%\n"
                f"💧 5日均量: {int(avg_volume_5d)}張"
            )
            print(success_msg)
            send_telegram_msg(success_msg)
            
            # 避免 API 頻繁請求限制
            time.sleep(0.3) 
            
        except Exception as e:
            print(f"跳過 {stock_id}，原因：{e}")
            continue

    send_telegram_msg(f"✅ 今日掃描完畢，共發現 {match_count} 檔符合條件標的。")

if __name__ == "__main__":
    scan_all_taiwan_stocks()