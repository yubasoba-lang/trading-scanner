import json
import os
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "paper_trades.json")


def load_log():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE) as f:
        return json.load(f)


def save_log(trades):
    with open(LOG_FILE, "w") as f:
        json.dump(trades, f, indent=2)


SLIPPAGE_PCT = 0.001  # 0.1% slippage on entry — pessimistic but realistic for retail


def log_signal(ticker, price, score, bias, sl, tp, sl_pct, tp_pct, atr_pct, earnings_warning=False):
    trades = load_log()
    today = datetime.now().strftime("%Y-%m-%d")
    # Don't log duplicate signals for same ticker on same day
    if any(t["ticker"] == ticker and t["date"] == today for t in trades):
        return
    # Apply slippage: you never get the exact close price, you pay a little more
    fill_price = round(price * (1 + SLIPPAGE_PCT), 2)
    trades.append({
        "id": len(trades) + 1,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "ticker": ticker,
        "entry_price": fill_price,
        "score": score,
        "bias": bias,
        "sl": sl,
        "tp": tp,
        "sl_pct": sl_pct,
        "tp_pct": tp_pct,
        "atr_pct": atr_pct,
        "earnings_warning": earnings_warning,
        "status": "open",
        "exit_price": None,
        "exit_date": None,
        "result_pct": None,
    })
    save_log(trades)


def update_outcomes():
    """Check open trades against latest prices and mark closed if SL/TP hit."""
    import yfinance as yf
    trades = load_log()
    open_trades = [t for t in trades if t["status"] == "open"]
    if not open_trades:
        return

    tickers = list(set(t["ticker"] for t in open_trades))
    prices = {}
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="1d", progress=False, auto_adjust=True)
            prices[ticker] = round(float(data["Close"].iloc[-1]), 2)
        except:
            pass

    for trade in trades:
        if trade["status"] != "open":
            continue
        price = prices.get(trade["ticker"])
        if not price:
            continue
        if price <= trade["sl"]:
            trade["status"] = "stopped_out"
            trade["exit_price"] = trade["sl"]
            trade["exit_date"] = datetime.now().strftime("%Y-%m-%d")
            trade["result_pct"] = trade["sl_pct"]
        elif price >= trade["tp"]:
            trade["status"] = "target_hit"
            trade["exit_price"] = trade["tp"]
            trade["exit_date"] = datetime.now().strftime("%Y-%m-%d")
            trade["result_pct"] = trade["tp_pct"]

    save_log(trades)


def summary():
    trades = load_log()
    closed = [t for t in trades if t["status"] != "open"]
    open_trades = [t for t in trades if t["status"] == "open"]

    if not trades:
        return "No trades logged yet."

    wins = [t for t in closed if t["status"] == "target_hit"]
    losses = [t for t in closed if t["status"] == "stopped_out"]
    total_pct = sum(t["result_pct"] for t in closed) if closed else 0
    win_rate = round(len(wins) / len(closed) * 100) if closed else 0

    lines = [
        f"PAPER TRADE LOG — {datetime.now().strftime('%Y-%m-%d')}",
        "=" * 45,
        f"Total signals logged: {len(trades)}",
        f"Open:   {len(open_trades)}",
        f"Closed: {len(closed)}  (W:{len(wins)} L:{len(losses)}  WR:{win_rate}%)",
        f"Total P&L (paper): {'+' if total_pct >= 0 else ''}{round(total_pct, 1)}%",
        "",
        "OPEN TRADES",
        "-" * 45,
    ]

    for t in open_trades:
        lines.append(f"  {t['ticker']:6} entry ${t['entry_price']}  SL ${t['sl']}  TP ${t['tp']}  logged {t['date']}")

    if closed:
        lines.append("")
        lines.append("CLOSED TRADES")
        lines.append("-" * 45)
        for t in closed[-10:]:
            result = f"+{t['result_pct']}%" if t['result_pct'] > 0 else f"{t['result_pct']}%"
            status = "✓ TP" if t['status'] == "target_hit" else "✗ SL"
            lines.append(f"  {t['ticker']:6} {status}  {result}  exited {t['exit_date']}")

    return "\n".join(lines)
