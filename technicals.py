import yfinance as yf
import ta
import pandas as pd


def get_data(ticker: str, period: str = "3mo") -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
    return df


def compute_signals(df: pd.DataFrame) -> dict:
    close = df["close"]

    rsi = ta.momentum.RSIIndicator(close).rsi().iloc[-1]

    macd_obj = ta.trend.MACD(close)
    macd = macd_obj.macd().iloc[-1]
    macd_signal = macd_obj.macd_signal().iloc[-1]

    bb = ta.volatility.BollingerBands(close)
    bb_high = bb.bollinger_hband().iloc[-1]
    bb_low = bb.bollinger_lband().iloc[-1]
    price = close.iloc[-1]

    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1]
    ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1]

    volume_today = df["volume"].iloc[-1]
    volume_avg = df["volume"].rolling(20).mean().iloc[-1]
    volume_ratio = volume_today / volume_avg if volume_avg > 0 else 1.0

    atr = ta.volatility.AverageTrueRange(df["high"], df["low"], close, window=14).average_true_range().iloc[-1]
    atr_pct = round(float(atr / price * 100), 2)

    return {
        "price": round(float(price), 2),
        "rsi": round(float(rsi), 1),
        "macd_bullish": bool(macd > macd_signal),
        "above_bb_mid": bool(price > (bb_high + bb_low) / 2),
        "bb_position": round(float((price - bb_low) / (bb_high - bb_low) * 100), 1),
        "ema_trend": "bullish" if ema20 > ema50 else "bearish",
        "volume_ratio": round(float(volume_ratio), 2),
        "atr_pct": atr_pct,
    }


def probability_score(signals: dict) -> int:
    """
    Returns a 0-100 score. Above 65 = bullish bias, below 35 = bearish bias.
    MACD acts as a momentum veto: bearish crossover hard-caps score at 55 (no buy),
    bullish crossover hard-floors score at 45 (no sell). This prevents EMA/RSI
    from dragging a conflicted setup into a buy signal.
    """
    score = 50  # neutral baseline

    # RSI: oversold = bullish setup, overbought = bearish
    rsi = signals["rsi"]
    if rsi < 30:
        score += 15
    elif rsi < 45:
        score += 7
    elif rsi > 70:
        score -= 15
    elif rsi > 55:
        score -= 5

    # Bollinger Band position
    bb_pos = signals["bb_position"]
    if bb_pos < 20:
        score += 10
    elif bb_pos > 80:
        score -= 10

    # EMA trend (lagging — weighted less than momentum)
    if signals["ema_trend"] == "bullish":
        score += 7
    else:
        score -= 7

    # Volume confirmation
    if signals["volume_ratio"] > 1.5 and signals["macd_bullish"]:
        score += 5

    score = max(0, min(100, score))

    # MACD veto gate: momentum overrides trend alignment
    # Bearish crossover → cap at 55 (below buy threshold of 65)
    # Bullish crossover → floor at 45 (above sell threshold of 35)
    if not signals["macd_bullish"]:
        score = min(score, 55)
    else:
        score = max(score, 45)

    return score
