import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

import yfinance as yf
from config import WATCHLIST, BUY_THRESHOLD, SELL_THRESHOLD, EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER, DASHBOARD_URL, STARTING_BALANCE_JPY, USD_JPY_RATE, RISK_PER_TRADE_PCT
from technicals import get_data, compute_signals, probability_score
from news import get_news_sentiment
from paperlog import log_signal, update_outcomes, summary, load_log
from email_template import build_html_email


SENTIMENT_BOOST = {"positive": 8, "neutral": 0, "negative": -8, "unavailable": 0, "error": 0}


def check_earnings_soon(ticker: str) -> bool:
    try:
        cal = yf.Ticker(ticker).calendar
        if cal is None or cal.empty:
            return False
        earnings_date = cal.iloc[0, 0]
        if hasattr(earnings_date, 'date'):
            earnings_date = earnings_date.date()
        today = datetime.now().date()
        return today <= earnings_date <= today + timedelta(days=7)
    except:
        return False


def analyze_ticker(ticker: str) -> dict:
    try:
        df = get_data(ticker)
        signals = compute_signals(df)
        tech_score = probability_score(signals)

        news = get_news_sentiment(ticker)
        sentiment_adj = SENTIMENT_BOOST.get(news["sentiment"], 0)
        final_score = max(0, min(100, tech_score + sentiment_adj))

        if final_score >= BUY_THRESHOLD:
            bias = "BULLISH"
        elif final_score <= SELL_THRESHOLD:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        earnings_warning = check_earnings_soon(ticker)

        return {
            "ticker": ticker,
            "price": signals["price"],
            "score": final_score,
            "bias": bias,
            "rsi": signals["rsi"],
            "ema_trend": signals["ema_trend"],
            "macd_bullish": signals["macd_bullish"],
            "volume_ratio": signals["volume_ratio"],
            "atr_pct": signals["atr_pct"],
            "news_sentiment": news["sentiment"],
            "top_headlines": news.get("headlines", []),
            "news_summary": news.get("summary", ""),
            "earnings_warning": earnings_warning,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}


def format_report(results: list) -> str:
    now = datetime.now()
    lines = [
        f"TRADING SCANNER — {now.strftime('%A, %b %d %Y  %H:%M')}",
        "=" * 55,
        f"Tickers scanned: {len(results)}   Market opens: 9:30am ET",
        "",
    ]

    bullish = [r for r in results if r.get("bias") == "BULLISH"]
    bearish = [r for r in results if r.get("bias") == "BEARISH"]
    neutral = [r for r in results if r.get("bias") == "NEUTRAL"]

    for group, label, emoji in [
        (bullish, "BULLISH SETUPS — Consider buying", "▲"),
        (bearish, "BEARISH — Avoid or watch for shorts", "▼"),
        (neutral, "NEUTRAL — No strong signal", "─"),
    ]:
        if not group:
            continue
        lines.append(f"{emoji} {label}")
        lines.append("-" * 55)
        for r in sorted(group, key=lambda x: x.get("score", 50), reverse=True):
            if "error" in r:
                lines.append(f"  {r['ticker']}: ERROR — {r['error']}")
                continue

            price = r["price"]
            atr_pct = r.get("atr_pct", 2.0)
            sl_pct = round(-(atr_pct * 1.5), 1)
            tp_pct = round(atr_pct * 2.5, 1)
            sl = round(price * (1 + sl_pct / 100), 2)
            tp = round(price * (1 + tp_pct / 100), 2)
            rr = round(tp_pct / abs(sl_pct), 1)

            # Position sizing — risk only 5% of account per trade
            account_usd = STARTING_BALANCE_JPY / USD_JPY_RATE
            risk_usd = round(account_usd * RISK_PER_TRADE_PCT / 100, 2)
            position_usd = round(min(risk_usd / (abs(sl_pct) / 100), account_usd * 0.20), 2)
            shares = round(position_usd / price, 4)
            max_loss_usd = round(position_usd * abs(sl_pct) / 100, 2)
            max_gain_usd = round(position_usd * tp_pct / 100, 2)
            position_jpy = round(position_usd * USD_JPY_RATE)

            rsi = r["rsi"]
            if rsi < 30:
                rsi_label = "OVERSOLD ← good"
            elif rsi > 70:
                rsi_label = "OVERBOUGHT ← caution"
            elif rsi < 45:
                rsi_label = "recovering"
            elif rsi > 55:
                rsi_label = "heating up"
            else:
                rsi_label = "neutral"

            macd_label = "bullish crossover" if r["macd_bullish"] else "bearish crossover"
            vol = r["volume_ratio"]
            vol_label = f"{vol}x avg {'← HIGH VOLUME' if vol > 1.5 else ''}"

            lines.append(f"  {r['ticker']}")
            lines.append(f"    Price:        ${price}")
            lines.append(f"    Score:        {r['score']}/100")
            lines.append(f"    RSI:          {rsi}  ({rsi_label})")
            lines.append(f"    Trend (EMA):  {r['ema_trend']}")
            lines.append(f"    MACD:         {macd_label}")
            lines.append(f"    Volume:       {vol_label}")
            lines.append(f"    Volatility:   {atr_pct}% avg daily move (ATR)")
            lines.append(f"    News:         {r['news_sentiment']}")
            if r.get("earnings_warning"):
                lines.append(f"    ⚠️  EARNINGS within 7 days — higher risk, skip this one")
            if r.get("top_headlines"):
                lines.append(f"    Headline:     {r['top_headlines'][0]}")
            if r.get("news_summary"):
                lines.append(f"    News Summary:")
                for sentence in r['news_summary'].replace('\n', ' ').split('. '):
                    sentence = sentence.strip()
                    if sentence:
                        lines.append(f"      {sentence}.")
            lines.append(f"")
            lines.append(f"    ── PAPER TRADE LEVELS ──")
            lines.append(f"    Entry:        ${price} per share")
            lines.append(f"    Stop Loss:    ${sl}  ({sl_pct}%)  ← auto-sell if wrong")
            lines.append(f"    Take Profit:  ${tp}  (+{tp_pct}%)  ← auto-sell when right")
            lines.append(f"    Risk/Reward:  1:{rr}")
            lines.append(f"")
            lines.append(f"    ── HOW MUCH TO INVEST ──")
            lines.append(f"    Invest:       ${position_usd}  (~¥{position_jpy})  [{shares} shares]")
            lines.append(f"    Max loss:     -${max_loss_usd}  if stop loss hits")
            lines.append(f"    Max gain:     +${max_gain_usd}  if take profit hits")
            lines.append(f"    (This risks {RISK_PER_TRADE_PCT}% of your ¥{STARTING_BALANCE_JPY:,} account)")
            lines.append("")

        lines.append("")

    lines.append("─" * 55)
    lines.append("HOW TO USE THIS EMAIL")
    lines.append("1. Look at BULLISH SETUPS only")
    lines.append("2. Pick 1-2 with the highest score")
    lines.append("3. Open your broker, place a buy order at Entry price")
    lines.append("4. Set Stop Loss and Take Profit at the levels above")
    lines.append("5. Walk away — broker handles the rest automatically")
    lines.append("")
    lines.append("⚠️  Paper trade only until you trust the signals.")
    lines.append("⚠️  Never trade more than 10% of your account on one ticker.")
    lines.append("⚠️  Not financial advice.")
    lines.append("")
    lines.append("─" * 55)
    lines.append(f"📊 LOG YOUR DECISIONS → {DASHBOARD_URL}")
    lines.append("Open the link, tap Buy/Skip/Watch for each signal, add your reasoning.")
    return "\n".join(lines)


def send_email(subject: str, html: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())


def run():
    print(f"Scanning {len(WATCHLIST)} tickers...\n")

    # First update any open paper trades with latest prices
    update_outcomes()

    results = []
    for ticker in WATCHLIST:
        print(f"  Analyzing {ticker}...", end=" ", flush=True)
        result = analyze_ticker(ticker)
        results.append(result)
        if "error" not in result:
            print(f"Score: {result['score']}/100 ({result['bias']})")
            # Auto-log bullish signals to paper trade ledger
            if result["bias"] == "BULLISH":
                price = result["price"]
                atr_pct = result.get("atr_pct", 2.0)
                sl_pct = round(-(atr_pct * 1.5), 1)
                tp_pct = round(atr_pct * 2.5, 1)
                sl = round(price * (1 + sl_pct / 100), 2)
                tp = round(price * (1 + tp_pct / 100), 2)
                log_signal(ticker, price, result["score"], result["bias"], sl, tp, sl_pct, tp_pct, atr_pct, result.get("earnings_warning", False))
        else:
            print(f"ERROR: {result['error']}")

    trades = load_log()
    html = build_html_email(results, trades, DASHBOARD_URL, STARTING_BALANCE_JPY, USD_JPY_RATE, RISK_PER_TRADE_PCT)
    print("\n" + format_report(results))

    send_email(f"Trading Scanner — {datetime.now().strftime('%b %d')}", html)
    print("\nEmail sent to", EMAIL_RECEIVER)


if __name__ == "__main__":
    run()
