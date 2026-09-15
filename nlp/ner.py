import nltk

# Global cache for spaCy NLP model
_spacy_nlp = None

def load_spacy_model():
    """Dynamically loads spaCy model. Returns None if not available."""
    global _spacy_nlp
    if _spacy_nlp is None:
        try:
            import spacy
            _spacy_nlp = spacy.load("en_core_web_sm")
        except Exception:
            # spaCy or model is not installed, return None
            pass
    return _spacy_nlp

def get_ner(text):
    """
    Performs Named Entity Recognition.
    Defaults to NLTK, using spaCy dynamically as an optional enhancement if available.
    """
    if not text:
        return []
        
    nlp = load_spacy_model()
    if nlp is not None:
        try:
            doc = nlp(text)
            entities = []
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "label": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char
                })
            return entities
        except Exception as e:
            print(f"spaCy NER error: {e}. Falling back to NLTK.")
            
    return get_nltk_ner(text)

def get_nltk_ner(text):
    """Performs NER using NLTK ne_chunk pipeline."""
    try:
        tokens = nltk.word_tokenize(text)
        pos_tags = nltk.pos_tag(tokens)
        chunks = nltk.ne_chunk(pos_tags)
        entities = []
        
        for chunk in chunks:
            if isinstance(chunk, nltk.Tree):
                label = chunk.label()
                ent_text = " ".join([child[0] for child in chunk])
                entities.append({
                    "text": ent_text,
                    "label": label,
                    "start": -1,
                    "end": -1
                })
        return entities
    except Exception as e:
        print(f"NLTK NER error: {e}")
        return []
