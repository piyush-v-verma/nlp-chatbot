from nltk.sentiment.vader import SentimentIntensityAnalyzer

def get_sentiment(text):
    """Performs sentiment analysis using NLTK VADER."""
    if not text or not text.strip():
        return {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0, "label": "neutral"}
        
    try:
        sia = SentimentIntensityAnalyzer()
        scores = sia.polarity_scores(text)
        compound = scores['compound']
        
        if compound >= 0.05:
            label = 'positive'
        elif compound <= -0.05:
            label = 'negative'
        else:
            label = 'neutral'
            
        return {
            "compound": compound,
            "pos": scores['pos'],
            "neu": scores['neu'],
            "neg": scores['neg'],
            "label": label
        }
    except Exception as e:
        print(f"VADER Sentiment error: {e}")
        return {"compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0, "label": "neutral", "error": str(e)}
