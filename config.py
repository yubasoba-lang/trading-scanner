# Tickers you want to watch
WATCHLIST = ["AAPL", "NVDA", "TSLA", "MSFT", "SPY", "META", "AMZN", "MRNA"]

# Starting balance in JPY for paper trading simulation
STARTING_BALANCE_JPY = 60000
USD_JPY_RATE = 155  # update this manually if rate changes significantly

# Position sizing — how much to put into each trade
# Rule: never risk more than this % of your account on one trade
RISK_PER_TRADE_PCT = 5  # 5% of account per trade = ~¥3,000 = ~$20

# Dashboard URL (update this once hosted publicly)
DASHBOARD_URL = "http://localhost:8766/dashboard.html"

# Probability score thresholds
BUY_THRESHOLD = 65    # score >= this → potential buy signal
SELL_THRESHOLD = 35   # score <= this → potential sell / avoid signal

# Finnhub API key (free at finnhub.io — no credit card needed)
FINNHUB_API_KEY = "d8tb609r01qhcnk1e3v0d8tb609r01qhcnk1e3vg"
CLAUDE_API_KEY = "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"

# Email alerts
EMAIL_SENDER = "yuva.y.ajeesh@gmail.com"
EMAIL_PASSWORD = "rdkl nytt rjmf ycdj"
EMAIL_RECEIVER = "yuva.y.ajeesh@gmail.com"
