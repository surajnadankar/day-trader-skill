import uuid
import requests

# यहाँ आपका Google Apps Script का Webhook URL आएगा
SHEET_WEBHOOK_URL = "YOUR_APPS_SCRIPT_WEBHOOK_URL_HERE"

ACTIVE_TRADES = {}

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
        if "http" in SHEET_WEBHOOK_URL:
            requests.post(SHEET_WEBHOOK_URL, json=trade_data, timeout=5)
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

    # 0.01 लॉट PnL गणना ($)
    if "XAU" in sym or "GOLD" in sym:
        pnl = round(diff * 1.0, 2)       # गोल्ड: $1 चाल = $1 (0.01 लॉट)
    elif "JPY" in sym:
        pips = diff / 0.01
        pnl = round(pips * 0.07, 2)
    elif any(fx in sym for fx in ["EUR", "GBP", "AUD", "CAD", "USD"]):
        pips = diff / 0.0001
        pnl = round(pips * 0.10, 2)      # 1 पिप = $0.10 (0.01 लॉट)
    else:
        pnl = round(diff * 0.01, 2)

    close_data = {
        "action": "CLOSE_TRADE",
        "trade_id": trade_id,
        "exit_price": exit_price,
        "status": status,
        "pnl": pnl
    }
    try:
        if "http" in SHEET_WEBHOOK_URL:
            requests.post(SHEET_WEBHOOK_URL, json=close_data, timeout=5)
    except Exception as e:
        print(f"Sheet Close Log Error: {e}")

    del ACTIVE_TRADES[trade_id]
