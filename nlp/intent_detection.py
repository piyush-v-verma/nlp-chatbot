import re
import difflib

# Intent synonyms mapping for natural language variations
INTENT_SYNONYMS = {
    "summarize": ["summarize", "summary", "shorten", "brief", "condense", "gist", "outline", "abstract", "shrink", "synopsis"],
    "translate": ["translate", "translation", "convert", "meaning in hindi", "hindi meaning", "in hindi", "translate to hindi", "hindi translation"],
    "sentiment": ["sentiment", "feel", "feeling", "emotion", "polarity", "mood", "tone", "attitude", "opinion", "review"],
    "ner": ["ner", "entity", "entities", "named entities", "extract names", "find names", "names", "organizations", "locations", "places", "people"],
    "pos": ["pos", "parts of speech", "parts-of-speech", "tag words", "tagging", "syntax tags", "grammar tags", "word classes"],
    "chunk": ["chunk", "chunking", "phrase structure", "noun phrase", "verb phrase", "syntax tree", "parse tree"],
    "topic": ["topic", "topics", "lda", "subject", "subjects", "theme", "themes", "main points", "categorize"],
    "math": ["math", "sympy", "solve", "equation", "calculate", "simplify", "derivative", "integrate", "differentiate", "diff", "calculus", "algebra", "arithmetic", "plus", "minus", "divided by", "multiplied by"]
}

def detect_intent(text):
    """
    Detects the user's intent using helper-prefix removal, synonym lists, and fuzzy matching.
    Returns: (intent_name, confidence_score, extracted_content)
    """
    if not text or not text.strip():
        return "general", 0.0, ""
        
    text_clean = text.strip()
    text_lower = text_clean.lower()
    
    # Strip common helper prefixes to uncover core action phrase
    prefix_pattern = r'^(please|can you|could you|would you mind|go ahead and|i want to|show me|find the|analyze the|tag the|extract the|get the|show the|solve the|solve|calculate|evaluate|simplify)\s+'
    core_text = re.sub(prefix_pattern, '', text_lower).strip()
    
    # 1. Prefix Match against synonyms
    for intent, synonyms in INTENT_SYNONYMS.items():
        for syn in synonyms:
            # Matches prefix synonyms followed optionally by a sequence of connector words, spaces, and colons
            pattern = r'^' + re.escape(syn) + r'\b(?:\s+(?:this|the|a|an|following|paragraph|text|sentence|review|article|words|word|into\s+hindi|to\s+hindi|into|to|mathematical|equations|equation|expressions|expression|math))*\s*:?\s*(.*)$'
            match = re.match(pattern, core_text)
            if match:
                target_lower = match.group(1).strip()
                if target_lower:
                    idx = text_lower.find(target_lower)
                    content = text_clean[idx:].strip() if idx != -1 else target_lower
                else:
                    content = ""
                return intent, 1.0, content

    # 2. In-sentence keyword match
    for intent, synonyms in INTENT_SYNONYMS.items():
        for syn in synonyms:
            if re.search(r'\b' + re.escape(syn) + r'\b', text_lower):
                content = re.sub(r'\b' + re.escape(syn) + r'\b(?:\s+(?:this|the|a|an|following|paragraph|text|sentence|review|article|words|word|into\s+hindi|to\s+hindi|into|to|mathematical|equations|equation|expressions|expression|math))*\s*:?', '', text_clean, flags=re.IGNORECASE).strip()
                return intent, 0.90, content

    # 3. Fuzzy matching on words
    stop_words = {"the", "and", "but", "for", "with", "this", "that", "you", "they", "him", "her", "his", "their", "our", "its", "are", "was", "were", "been", "have", "has", "had", "will", "would", "shall", "should", "can", "could", "may", "might", "must"}
    words = [w for w in re.findall(r'\b[a-zA-Z]{3,15}\b', text_lower) if w not in stop_words]
    best_intent = None
    best_score = 0.0
    matched_word = ""
    
    for word in words:
        for intent, synonyms in INTENT_SYNONYMS.items():
            for syn in synonyms:
                ratio = difflib.SequenceMatcher(None, word, syn).ratio()
                if ratio >= 0.75 and ratio > best_score:
                    best_score = ratio
                    best_intent = intent
                    matched_word = word
                    
    if best_intent:
        content = re.sub(r'\b' + re.escape(matched_word) + r'\b\s*:?', '', text_clean, flags=re.IGNORECASE).strip()
        return best_intent, round(best_score, 2), content
        
    return "general", 0.0, text_clean
