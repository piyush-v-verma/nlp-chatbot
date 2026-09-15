import nltk
import re

def get_pos_tags(text):
    """Returns Part-Of-Speech tagging using NLTK."""
    if not text:
        return []
    try:
        tokens = nltk.word_tokenize(text)
        return nltk.pos_tag(tokens)
    except Exception as e:
        print(f"POS tagging error: {e}")
        # Regex fallback
        tokens = re.findall(r'\b\w+\b', text)
        return [(w, "NN") for w in tokens]
