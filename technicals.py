import yfinance as yf
import ta
import pandas as pd


def get_data(ticker: str, period: str = "3mo") -> pd.DataFrame:
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]
    return df


def compute_signals(df: pd.DataFrame) -> dict:
    close = df["close"]

    rsi_series = ta.momentum.RSIIndicator(close).rsi()
    rsi = rsi_series.iloc[-1]
    # Smooth slope over 3 days to avoid day-to-day noise
    rsi_slope = float(rsi_series.iloc[-1] - rsi_series.iloc[-4]) / 3

    macd_obj = ta.trend.MACD(close)
    macd = macd_obj.macd().iloc[-1]
    macd_signal = macd_obj.macd_signal().iloc[-1]
    macd_hist = macd_obj.macd_diff()
    # Smooth histogram slope over 3 days
    macd_hist_slope = float(macd_hist.iloc[-1] - macd_hist.iloc[-4]) / 3

    # Fast MACD (8/17/9) — more sensitive, catches early crossovers
    macd_fast_obj = ta.trend.MACD(close, window_slow=17, window_fast=8, window_sign=9)
    macd_fast_bullish = bool(macd_fast_obj.macd().iloc[-1] > macd_fast_obj.macd_signal().iloc[-1])

    bb = ta.volatility.BollingerBands(close)
    bb_high = bb.bollinger_hband()
    bb_low = bb.bollinger_lband()
    price = close.iloc[-1]
    bb_pos = float((price - bb_low.iloc[-1]) / (bb_high.iloc[-1] - bb_low.iloc[-1]) * 100)
    bb_pos_prev = float((close.iloc[-2] - bb_low.iloc[-2]) / (bb_high.iloc[-2] - bb_low.iloc[-2]) * 100)
    bb_slope = bb_pos - bb_pos_prev  # positive = moving toward upper band

    # Bollinger Band width — narrow = squeeze (big move coming), wide = expanded
    bb_width = float((bb_high.iloc[-1] - bb_low.iloc[-1]) / close.iloc[-1] * 100)
    bb_width_prev = float((bb_high.iloc[-5] - bb_low.iloc[-5]) / close.iloc[-5] * 100)
    bb_squeeze = bb_width < bb_width_prev * 0.85  # bands tightened >15% in 5 days

    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator().iloc[-1]
    ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1]

    volume_today = df["volume"].iloc[-1]
    volume_avg = df["volume"].rolling(20).mean().iloc[-1]
    volume_ratio = volume_today / volume_avg if volume_avg > 0 else 1.0
    # Volume trend: is volume building over last 3 days?
    vol_3day_avg = df["volume"].iloc[-3:].mean()
    vol_prior_avg = df["volume"].iloc[-6:-3].mean()
    volume_building = bool(vol_3day_avg > vol_prior_avg * 1.1)

    atr = ta.volatility.AverageTrueRange(df["high"], df["low"], close, window=14).average_true_range().iloc[-1]
    atr_pct = round(float(atr / price * 100), 2)

    return {
        "price": round(float(price), 2),
        "rsi": round(float(rsi), 1),
        "rsi_slope": round(rsi_slope, 2),       # rising or falling
        "macd_bullish": bool(macd > macd_signal),
        "macd_fast_bullish": macd_fast_bullish,
        "macd_hist_slope": round(macd_hist_slope, 4),  # momentum accelerating or dying
        "above_bb_mid": bool(price > (bb_high.iloc[-1] + bb_low.iloc[-1]) / 2),
        "bb_position": round(bb_pos, 1),
        "bb_slope": round(bb_slope, 2),          # moving up or down within bands
        "bb_squeeze": bb_squeeze,                # volatility compression = big move ahead
        "ema_trend": "bullish" if ema20 > ema50 else "bearish",
        "volume_ratio": round(float(volume_ratio), 2),
        "volume_building": volume_building,
        "atr_pct": atr_pct,
    }


def get_spy_regime() -> dict:
    """
    Returns how far SPY is from its 50 EMA as a continuous gradient.
    deviation > 0 = above EMA (bull), < 0 = below (bear).
    Also returns the 3-day slope of SPY itself.
    """
    try:
        df = get_data("SPY", period="3mo")
        close = df["close"]
        ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator()
        price = float(close.iloc[-1])
        ema = float(ema50.iloc[-1])
        deviation_pct = (price - ema) / ema * 100  # % above/below EMA50
        spy_slope = float(close.iloc[-1] - close.iloc[-4]) / 3  # 3-day price slope
        return {"deviation_pct": round(deviation_pct, 2), "slope": round(spy_slope, 2)}
    except:
        return {"deviation_pct": 0.0, "slope": 0.0}


def probability_score(signals: dict, spy_regime: dict = None) -> int:
    """
    Returns a 0-100 score. Above 65 = bullish, below 35 = bearish.

    Regime penalty is a continuous gradient (not binary):
    - SPY 5%+ above EMA50: no penalty (strong bull market)
    - SPY at EMA50: -5 on bullish components
    - SPY 5%+ below EMA50: -12 on bullish components (headwind)
    This shrinks appetite for longs in downtrends without distorting the sell side.
    """
    if spy_regime is None:
        spy_regime = {"deviation_pct": 0.0, "slope": 0.0}
    score = 50.0

    # --- RSI: continuous ramp from +15 (RSI=30) to 0 (RSI=50) to -15 (RSI=70) ---
    rsi = signals["rsi"]
    if rsi <= 50:
        rsi_points = 15 * (50 - rsi) / 20   # +15 at RSI 30, 0 at RSI 50
        rsi_points = min(rsi_points, 15)
    else:
        rsi_points = -15 * (rsi - 50) / 20  # 0 at RSI 50, -15 at RSI 70
        rsi_points = max(rsi_points, -15)
    score += rsi_points

    # RSI slope bonus: rising RSI = bounce, falling RSI = weakening
    rsi_slope = signals["rsi_slope"]
    if rsi_slope > 3:
        score += 5   # RSI rising fast — momentum picking up
    elif rsi_slope > 1:
        score += 2
    elif rsi_slope < -3:
        score -= 5   # RSI falling fast — momentum dying
    elif rsi_slope < -1:
        score -= 2

    # --- Bollinger Band position: continuous ramp ---
    bb_pos = signals["bb_position"]
    bb_points = 10 * (50 - bb_pos) / 50     # +10 at BB=0, 0 at BB=50, -10 at BB=100
    bb_points = max(-10, min(10, bb_points))
    score += bb_points

    # BB slope: price moving toward lower band = bearish, upper = bullish
    bb_slope = signals["bb_slope"]
    if bb_slope > 5:
        score += 3   # price rising within bands
    elif bb_slope < -5:
        score -= 3

    # BB squeeze: bands tightening = big move brewing (direction-agnostic, slight bonus)
    if signals["bb_squeeze"] and signals["macd_bullish"]:
        score += 4   # squeeze + bullish momentum = setup forming

    # --- EMA trend (lagging, lower weight) ---
    if signals["ema_trend"] == "bullish":
        score += 6
    else:
        score -= 6

    # --- Volume ---
    vol_ratio = signals["volume_ratio"]
    if signals["macd_bullish"]:
        # Volume confirmation on bullish momentum
        if vol_ratio > 2.0:
            score += 6
        elif vol_ratio > 1.5:
            score += 4
        elif vol_ratio > 1.2:
            score += 2
    else:
        # High volume on bearish momentum = distribution (selling)
        if vol_ratio > 1.5:
            score -= 3

    if signals["volume_building"] and signals["macd_bullish"]:
        score += 3   # sustained volume increase behind bullish move

    # --- MACD histogram slope: is momentum accelerating or dying? ---
    macd_hist_slope = signals["macd_hist_slope"]
    if macd_hist_slope > 0:
        score += 3   # histogram expanding in bullish direction
    else:
        score -= 3   # histogram shrinking — momentum fading

    # --- Regime awareness: continuous gradient, only penalises bullish appetite ---
    # Scale: 0 penalty at SPY +5% above EMA, max -12 at SPY -5% below EMA
    dev = spy_regime.get("deviation_pct", 0.0)
    regime_penalty = max(0, min(12, -dev * 1.2 + 6)) if dev < 5 else 0
    # Only subtract from the bullish component (above 50), not sell signals
    if score > 50:
        score -= regime_penalty * ((score - 50) / 50)  # proportional to how bullish the setup is

    score = max(0, min(100, score))

    # --- MACD veto gate ---
    # Either standard (12/26/9) or fast (8/17/9) bullish crossover counts.
    # Fast MACD catches early momentum shifts — higher risk, more signals.
    # If neither is bullish: cap at 62. If either is bullish: floor at 45.
    either_bullish = signals["macd_bullish"] or signals.get("macd_fast_bullish", False)
    if not either_bullish:
        score = min(score, 62)
    else:
        score = max(score, 45)

    return int(round(score))
