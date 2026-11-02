import os
import time
import uuid
import threading
import requests
import yfinance as yf
from flask import Flask

# ----------------------------------------------------
# 1. कॉन्फ़िगरेशन
# ----------------------------------------------------
# यहाँ अपना Google Apps Script Webhook URL डालें
SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbxiJpRJAuNej8Z2OJOVDALYl_kbcMOONjJY13XnSS0ysD2QBJZC8UCkM8fg4JqutZ7D6A/exec"

# यूएस स्टॉक्स जिन्हें आप ट्रैक करना चाहते हैं
WATCHLIST = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN"]

ACTIVE_TRADES = {}

# ----------------------------------------------------
# 2. Google Sheet लॉगिंग फ़ंक्शन्स
# ----------------------------------------------------
def open_virtual_trade(symbol: str, trade_type: str, entry: float, sl: float, tp1: float, tp2: float):
    trade_id = str(uuid.uuid4())[:8]
    trade_data = {
        "action": "OPEN_TRADE",
        "trade_id": trade_id,
        "symbol": symbol.upper(),
        "type": trade_type.upper(),
        "lots": 0.01,
        "entry": float(entry),
        "sl": float(sl),
        "tp1": float(tp1),
        "tp2": float(tp2),
    }
    try:
        if "http" in SHEET_WEBHOOK_URL and not SHEET_WEBHOOK_URL.startswith("https://script.google.com/macros/s/AKfycbx..."):
            requests.post(SHEET_WEBHOOK_URL, json=trade_data, timeout=5)
            print(f"[ENTRY LOGGED] {trade_id} {symbol} {trade_type} @ {entry}")
    except Exception as e:
        print(f"Sheet Open Log Error: {e}")

    ACTIVE_TRADES[trade_id] = trade_data
    return trade_id

def update_trade_exit(trade_id: str, exit_price: float, status: str):
    if trade_id not in ACTIVE_TRADES:
        return
    tr = ACTIVE_TRADES[trade_id]
    entry = tr["entry"]
    direction = tr["type"]
    sym = tr["symbol"]

    diff = (exit_price - entry) if direction == "BUY" else (entry - exit_price)

    # 0.01 लॉट / शेयर के हिसाब से PnL ($)
    pnl = round(diff * 1.0, 2)

    close_data = {
        "action": "CLOSE_TRADE",
        "trade_id": trade_id,
        "exit_price": exit_price,
        "status": status,
        "pnl": pnl
    }
    try:
        if "http" in SHEET_WEBHOOK_URL and not SHEET_WEBHOOK_URL.startswith("https://script.google.com/macros/s/AKfycbx..."):
            requests.post(SHEET_WEBHOOK_URL, json=close_data, timeout=5)
            print(f"[EXIT LOGGED] {trade_id} {status} @ {exit_price} | PnL: ${pnl}")
    except Exception as e:
        print(f"Sheet Close Log Error: {e}")

    del ACTIVE_TRADES[trade_id]

# ----------------------------------------------------
# 3. लाइव प्राइस और मॉनिटरिंग लूप
# ----------------------------------------------------
def get_live_price(symbol: str) -> float:
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            return round(float(data["Close"].iloc[-1]), 2)
    except Exception as e:
        print(f"Price fetch error for {symbol}: {e}")
    return 0.0

def monitor_active_trades():
    closed_ids = []
    for trade_id, tr in list(ACTIVE_TRADES.items()):
        curr_price = get_live_price(tr["symbol"])
        if curr_price <= 0:
            continue

        direction = tr["type"]
        sl = tr["sl"]
        tp = tr["tp2"]

        if direction == "BUY":
            if curr_price <= sl:
                update_trade_exit(trade_id, sl, "SL_HIT")
                closed_ids.append(trade_id)
            elif curr_price >= tp:
                update_trade_exit(trade_id, tp, "TP_HIT")
                closed_ids.append(trade_id)

        elif direction == "SELL":
            if curr_price >= sl:
                update_trade_exit(trade_id, sl, "SL_HIT")
                closed_ids.append(trade_id)
            elif curr_price <= tp:
                update_trade_exit(trade_id, tp, "TP_HIT")
                closed_ids.append(trade_id)

def background_worker():
    """यह लूप 24/7 चलता रहेगा और हर 30 सेकंड में मॉनिटर करेगा"""
    print("Paper trading background worker started.")
    while True:
        try:
            if ACTIVE_TRADES:
                monitor_active_trades()
            time.sleep(30)
        except Exception as e:
            print(f"Worker exception: {e}")
            time.sleep(10)

# ----------------------------------------------------
# 4. Render वेब सर्वर (ताकि App कभी Exit न हो)
# ----------------------------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return {
        "status": "running",
        "active_trades_count": len(ACTIVE_TRADES),
        "service": "US Stocks Paper Trader"
    }

if __name__ == "__main__":
    # 1. बैकग्राउंड ट्रैकर चालू करें
    worker_thread = threading.Thread(target=background_worker, daemon=True)
    worker_thread.start()

    # 2. Render पोर्ट पर वेब सर्वर चालू करें
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
