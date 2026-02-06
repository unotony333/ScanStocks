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

def send_telegram_msg(message):
    if not TOKEN or not CHAT_ID:
        print("Telegram 設定缺失")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"發送通知失敗: {e}")

def check_api_limit():
    """檢查是否達到 600 次上限，若是則等待一小時"""
    global api_call_count
    api_call_count += 1
    # 設定在 580 次就先停，預留一點緩衝空間
    if api_call_count >= 580:
        wait_msg = "⏳ 已達 FinMind API 每小時上限，進入冷卻模式，將等待 3605 秒..."
        print(wait_msg)
        send_telegram_msg(wait_msg)
        
        time.sleep(3605) # 等待 1 小時又 5 秒
        
        api_call_count = 0 # 重置
        send_telegram_msg("🚀 冷卻結束，恢復上市股掃描。")

def scan_tse_stocks():
    dl = DataLoader()
    if FINMIND_TOKEN:
        dl.api_token = FINMIND_TOKEN
    
    try:
        # 1. 取得股票基本資訊
        stock_info = dl.taiwan_stock_info()
        check_api_limit()
        
        # 關鍵過濾：僅保留「上市股 (TSE)」且「普通股 (代碼長度為4)」
        tse_list = stock_info[
            (stock_info['industry_category'] != 'ETF') & 
            (stock_info['type'] == 'twse') & 
            (stock_info['stock_id'].str.len() == 4)
        ]['stock_id'].tolist()
        
        print(f"🚀 開始掃描全【上市】股票，共計 {len(tse_list)} 檔...")
    except Exception as e:
        print(f"初始化失敗: {e}")
        return

    match_count = 0
    for stock_id in tse_list:
        try:
            # --- API 1: 股價 (計算 52週新高與均量) ---
            # 抓取最近 260 天資料
            price_df = dl.taiwan_stock_daily(stock_id=stock_id, start_date='2025-01-01')
            check_api_limit()
            
            if price_df.empty or len(price_df) < 60:
                continue

            # 過濾 A: 5日均量 > 500張 (初步排除殭屍股，省下後續 API)
            avg_vol = price_df['Trading_Volume'].tail(5).mean() / 1000
            if avg_vol < 500:
                continue
            
            # 過濾 B: 52週新高 (目前收盤價 >= 過去一年最高價的 99%)
            current_price = price_df['close'].iloc[-1]
            max_price_52w = price_df['max'].max()
            if current_price < max_price_52w * 0.99:
                continue

            # --- API 2: 本益比 (條件: < 12) ---
            pe_df = dl.taiwan_stock_per_pbr(stock_id=stock_id)
            check_api_limit()
            
            if pe_df.empty:
                continue
            
            current_pe = pe_df['PE'].iloc[-1]
            if current_pe <= 0 or current_pe > 12:
                continue

            # --- API 3: 營收 (條件: 近 3 個月平均 YoY > 20%) ---
            rev_df = dl.taiwan_stock_month_revenue(stock_id=stock_id).tail(3)
            check_api_limit()
            
            if rev_df.empty:
                continue
                
            avg_yoy = rev_df['revenue_month_growth_rate'].mean()
            if avg_yoy < 20:
                continue

            # --- 符合三項指標 ---
            match_count += 1
            success_msg = (
                f"🎯 【上市股達標】 {stock_id}\n"
                f"💰 現價: {current_price}\n"
                f"📊 PE: {current_pe:.2f}\n"
                f"📈 營收平均YoY: {avg_yoy:.1f}%\n"
                f"💧 5日均量: {int(avg_vol)}張"
            )
            print(f"找到符合標的: {stock_id}")
            send_telegram_msg(success_msg)
            
            # 基礎延遲避免請求過快
            time.sleep(0.1)

        except Exception as e:
            print(f"跳過 {stock_id}，原因：{e}")
            continue

    send_telegram_msg(f"✅ 上市股掃描完畢。今日符合條件總數: {match_count}")

if __name__ == "__main__":
    scan_tse_stocks()