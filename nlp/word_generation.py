import re

COMMON_WORDS = [
    # NLP Keywords / Core Intents
    "summarize", "summary", "translate", "translation", "sentiment", "ner", "entities", 
    "pos", "parts-of-speech", "chunk", "chunking", "topic", "lda", "wikipedia", "search",
    "math", "calculate", "solve", "algebra", "equation", "formula", "grammar", "syntax",
    # Common conversational & technical keywords
    "hello", "hi", "hey", "how", "what", "where", "who", "why", "when", "which", "whose",
    "help", "explain", "analyze", "generate", "information", "about", "describe", "define",
    "python", "javascript", "flask", "sqlite", "nlp", "chatbot", "natural", "language", "processing", 
    "artificial", "intelligence", "machine", "learning", "data", "science", "software", 
    "development", "computer", "system", "programming", "developer", "browser", "interface",
    "algorithm", "neural", "network", "transformer", "spacy", "nltk", "scikit-learn",
    "analysis", "analytics", "performance", "database", "security", "function", "variable",
    "response", "question", "message", "conversation", "context", "history", "settings",
    "overview", "tokens", "tokenization", "stemming", "lemmatization", "classification"
]

def get_autocomplete_suggestions(query, context_text=""):
    """Returns autocomplete suggestions based on query prefix and contextual text with ultra-fast matching."""
    if not query:
        return []
        
    query_lower = query.lower().strip()
    suggestions = set()
    
    # Prefix matches from general vocabulary
    for word in COMMON_WORDS:
        if word.lower().startswith(query_lower):
            suggestions.add(word)
            
    # Harvest words from active context window if available
    if context_text:
        words = re.findall(r'\b[a-zA-Z]{2,20}\b', context_text)
        for w in words:
            w_lower = w.lower()
            if w_lower.startswith(query_lower) and len(w_lower) > len(query_lower):
                suggestions.add(w_lower)
                
    # Sort: matching commands first, then shorter matches, then alphabetically
    commands = ["summarize", "translate", "sentiment", "ner", "pos", "chunk", "topic", "math", "wikipedia"]
    sorted_suggs = sorted(
        list(suggestions),
        key=lambda x: (not x.lower() in commands, len(x), x.lower())
    )
    
    return sorted_suggs[:10]

