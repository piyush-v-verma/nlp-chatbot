import re
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

def preprocess_text(text):
    """Tokenizes, calculates removed stop-words, and stems the text."""
    if not text:
        return {
            "tokens": [],
            "removed_stop_words": [],
            "cleaned_tokens": [],
            "stemmed_tokens": []
        }
        
    try:
        tokens = nltk.word_tokenize(text)
    except Exception:
        tokens = re.findall(r'\b\w+\b', text)
        
    try:
        stop_words = set(stopwords.words('english'))
    except Exception:
        stop_words = set()
        
    cleaned_tokens = [w for w in tokens if w.isalnum() and w.lower() not in stop_words]
    removed_stop_words = [w for w in tokens if w.isalnum() and w.lower() in stop_words]
    
    try:
        stemmer = PorterStemmer()
        stemmed_tokens = [stemmer.stem(w) for w in cleaned_tokens]
    except Exception:
        stemmed_tokens = cleaned_tokens
        
    return {
        "tokens": tokens,
        "removed_stop_words": removed_stop_words,
        "cleaned_tokens": cleaned_tokens,
        "stemmed_tokens": stemmed_tokens
    }
