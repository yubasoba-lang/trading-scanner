"""
Daily signal history — append-only JSONL store.

Schema per line (raw indicator values only — source of truth):
  date, ticker, price, rsi, macd_bullish, macd_hist, bb_position,
  ema_trend, volume_ratio, atr_pct, spy_deviation_pct, score, engine_version

Rules:
- Raw indicators are immutable facts. Never change them.
- `score` is a frozen snapshot of what the engine said that day.
  Tag engine_version so you know which scoring logic produced it.
  Never feed score back into future calculations — use raw fields.
- Slopes are computed at read time from raw fields across rows,
  never stored. This keeps history valid across scoring changes.
"""

import json
import os
from datetime import datetime

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "daily_scores.jsonl")
ENGINE_VERSION = "3.2"  # bump when scoring logic changes materially


def append_day(results: list, spy_regime: dict):
    """Append one row per ticker for today's scan. Skip if already logged today."""
    today = datetime.now().strftime("%Y-%m-%d")
    existing_today = set()

    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if row.get("date") == today:
                        existing_today.add(row["ticker"])
                except json.JSONDecodeError:
                    continue

    with open(HISTORY_FILE, "a") as f:
        for r in results:
            if "error" in r or r["ticker"] in existing_today:
                continue
            row = {
                "date": today,
                "ticker": r["ticker"],
                "price": r["price"],
                # Raw indicator values — source of truth, never changes meaning
                "rsi": r["rsi"],
                "macd_bullish": r["macd_bullish"],
                "macd_hist_slope": r.get("macd_hist_slope"),
                "bb_position": r.get("bb_position"),
                "ema_trend": r["ema_trend"],
                "volume_ratio": r["volume_ratio"],
                "atr_pct": r["atr_pct"],
                "spy_deviation_pct": spy_regime.get("deviation_pct"),
                # Frozen snapshot of engine output — for backtest audit only
                "score": r["score"],
                "bias": r["bias"],
                "engine_version": ENGINE_VERSION,
            }
            f.write(json.dumps(row) + "\n")


def load_ticker(ticker: str) -> list[dict]:
    """Load all history rows for one ticker, oldest first."""
    rows = []
    if not os.path.exists(HISTORY_FILE):
        return rows
    with open(HISTORY_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if row["ticker"] == ticker:
                    rows.append(row)
            except json.JSONDecodeError:
                continue
    return sorted(rows, key=lambda r: r["date"])


def rsi_slope(ticker: str, days: int = 3) -> float | None:
    """
    Compute RSI slope from raw stored values over last `days` rows.
    Computed at read time — valid across scoring version changes.
    Returns points-per-day, or None if insufficient history.
    """
    rows = load_ticker(ticker)
    if len(rows) < days + 1:
        return None
    recent = rows[-days:]
    oldest = rows[-(days + 1)]
    return (recent[-1]["rsi"] - oldest["rsi"]) / days


def backtest_summary() -> dict:
    """
    Join history with paper_trades to check if score predicted outcome.
    Requires paper_trades.json with closed trades.
    Returns win rate by score bucket — use only with 30+ closed trades.
    """
    from paperlog import load_log
    trades = [t for t in load_log() if t["status"] != "open"]
    if not trades:
        return {"error": "No closed trades yet"}

    # Load history indexed by (date, ticker)
    history = {}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    history[(row["date"], row["ticker"])] = row
                except json.JSONDecodeError:
                    continue

    buckets = {"45-54": [], "55-64": [], "65-74": [], "75+": []}
    for trade in trades:
        entry = history.get((trade["date"], trade["ticker"]))
        if not entry:
            continue
        score = entry["score"]
        won = trade["status"] == "target_hit"
        if score < 55:
            buckets["45-54"].append(won)
        elif score < 65:
            buckets["55-64"].append(won)
        elif score < 75:
            buckets["65-74"].append(won)
        else:
            buckets["75+"].append(won)

    return {
        bucket: {
            "trades": len(results),
            "win_rate": f"{round(sum(results)/len(results)*100)}%" if results else "—",
        }
        for bucket, results in buckets.items()
    }
