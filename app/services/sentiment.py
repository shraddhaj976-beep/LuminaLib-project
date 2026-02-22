from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()


def sentiment_score(text: str) -> int:
    txt = (text or "").strip()
    if not txt:
        return 0
    compound = analyzer.polarity_scores(txt).get("compound", 0.0)
    if compound >= 0.05:
        return 1
    if compound <= -0.05:
        return -1
    return 0
