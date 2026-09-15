import nltk

# Import all modular NLP functions
from nlp.preprocessing import preprocess_text
from nlp.sentiment import get_sentiment
from nlp.summarization import summarize_text
from nlp.translation import translate_text
from nlp.pos import get_pos_tags
from nlp.chunking import get_chunks
from nlp.ner import get_ner
from nlp.topic_modeling import run_lda
from nlp.word_generation import get_autocomplete_suggestions
from nlp.wiki_search import search_wikipedia
from nlp.intent_detection import detect_intent
from nlp.conversation import ConversationManager
from nlp.math_solver import solve_math

# Expose response formatter functions
from nlp.response_formatter import (
    format_sentiment,
    format_translation,
    format_ner,
    format_pos,
    format_summarization,
    format_wikipedia,
    format_general,
    format_error,
    format_math
)

def init_nlp_resources():
    """Download required NLTK datasets and warm up spaCy loading."""
    resources = ['punkt', 'stopwords', 'averaged_perceptron_tagger', 'vader_lexicon', 'maxent_ne_chunker', 'words']
    for res in resources:
        try:
            nltk.download(res, quiet=True)
        except Exception as e:
            print(f"Error downloading NLTK resource {res}: {e}")
            
    # Warm up spaCy optional loading
    from nlp.ner import load_spacy_model
    load_spacy_model()
