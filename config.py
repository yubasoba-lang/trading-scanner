# Tickers you want to watch
WATCHLIST = [
    # Mega-cap tech
    "AAPL", "NVDA", "TSLA", "MSFT", "META", "AMZN", "GOOGL",
    # Semiconductors
    "AMD", "AVGO", "TSM",
    # Finance
    "JPM", "V",
    # Healthcare / biotech
    "MRNA", "LLY", "UNH",
    # Energy
    "XOM",
    # Consumer / retail
    "COST", "WMT",
    # Broad market ETFs
    "SPY", "QQQ",
]

# Starting balance in JPY for paper trading simulation
STARTING_BALANCE_JPY = 60000
USD_JPY_RATE = 155  # update this manually if rate changes significantly

# Position sizing — how much to put into each trade
# Rule: never risk more than this % of your account on one trade
RISK_PER_TRADE_PCT = 5  # 5% of account per trade = ~¥3,000 = ~$20

# Dashboard URL
DASHBOARD_URL = "https://yubasoba-lang.github.io/trading-scanner/dashboard.html"

# Probability score thresholds
BUY_THRESHOLD = 65    # score >= this → potential buy signal
SELL_THRESHOLD = 35   # score <= this → potential sell / avoid signal

# Keys injected by GitHub Actions secrets (or set locally via environment)
import os
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")
