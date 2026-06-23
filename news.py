import requests
import anthropic
from datetime import datetime, timedelta
from config import FINNHUB_API_KEY, CLAUDE_API_KEY


def get_news_sentiment(ticker: str) -> dict:
    """
    Fetches recent news from Finnhub and returns sentiment summary.
    Free tier: 60 calls/minute.
    """
    if FINNHUB_API_KEY == "your_finnhub_api_key_here":
        return {"sentiment": "unavailable", "score": 0, "headlines": [], "note": "Add Finnhub API key in config.py"}

    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={week_ago}&to={today}&token={FINNHUB_API_KEY}"

    try:
        res = requests.get(url, timeout=5)
        articles = res.json()[:10]  # last 10 articles

        if not articles:
            return {"sentiment": "neutral", "score": 0, "headlines": []}

        # Finnhub doesn't give sentiment scores on free tier, so we do basic keyword scoring
        positive_words = {"surge", "beat", "growth", "record", "upgrade", "buy", "bullish", "gain", "profit", "strong"}
        negative_words = {"drop", "fall", "miss", "downgrade", "sell", "bearish", "loss", "weak", "cut", "crash", "lawsuit", "fraud"}

        total_score = 0
        headlines = []
        for article in articles:
            headline = article.get("headline", "").lower()
            headlines.append(article.get("headline", ""))
            pos = sum(1 for w in positive_words if w in headline)
            neg = sum(1 for w in negative_words if w in headline)
            total_score += (pos - neg)

        avg = total_score / len(articles)
        if avg > 0.3:
            sentiment = "positive"
        elif avg < -0.3:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # Summarize with Claude Haiku
        summary = summarize_with_claude(ticker, headlines[:5])

        return {
            "sentiment": sentiment,
            "score": round(avg, 2),
            "headlines": headlines[:3],
            "summary": summary,
        }

    except Exception as e:
        return {"sentiment": "error", "score": 0, "headlines": [], "summary": "", "error": str(e)}


def summarize_with_claude(ticker: str, headlines: list) -> str:
    if not headlines:
        return "No recent news."
    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        headlines_text = "\n".join(f"- {h}" for h in headlines)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{
                "role": "user",
                "content": f"You are helping a beginner swing trader. Summarize these {ticker} headlines in 2 sentences. Plain English, no jargon. Focus on what it means for the stock price this week.\n\nHeadlines:\n{headlines_text}"
            }]
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"Summary unavailable: {str(e)[:50]}"
