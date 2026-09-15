import re
import nltk
from nlp.preprocessing import preprocess_text

def clean_summarization_prompt(text):
    """Strips common summarization prompts and instructional prefixes from the text."""
    if not text:
        return ""
    
    # List of regular expressions matching common summarization instructions
    patterns = [
        # E.g. "Can you summarize this paragraph:", "Please summarize the following text:"
        r'^(?:can\s+you|please|could\s+you|would\s+you\s+mind|go\s+ahead\s+and)?\s*summarize\s+(?:this|the|a|an|following|paragraph|text|sentence|review|article|words|word|for\s+me)*\s*:?\s*',
        r'^summarize\s*:?\s*'
    ]
    
    cleaned = text.strip()
    for pat in patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned

def summarize_text(text, num_sentences=2):
    """
    Summarizes text using a length-normalized, discount-weighted extractive method.
    If the text has fewer than 2 sentences or 40 words, it returns a friendly warning dictionary.
    """
    if not text or not text.strip():
        return {"error": "Please provide a paragraph to summarize."}
        
    # Extract only the content to be summarized
    cleaned_text = clean_summarization_prompt(text)
    if not cleaned_text or not cleaned_text.strip():
        return {"error": "Please provide a paragraph to summarize."}
        
    # Count words in cleaned content
    words = [w for w in cleaned_text.split() if w.strip()]
    word_count = len(words)
    
    try:
        sentences = nltk.sent_tokenize(cleaned_text)
    except Exception:
        # Fallback split
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', cleaned_text) if s.strip()]
        
    # Enforce minimum bounds for meaningful extractive summarization
    if len(sentences) < 2 or word_count < 40:
        return {
            "error": f"Meaningful summarization requires a longer paragraph containing at least two sentences and approximately 40 or more words. (Current content has {len(sentences)} sentence(s) and {word_count} word(s).)"
        }
        
    try:
        # Tokenize and clean words for frequency table
        pre = preprocess_text(cleaned_text)
        cleaned_words = [w.lower() for w in pre["cleaned_tokens"]]
        
        if not cleaned_words:
            return " ".join(sentences[:num_sentences])
            
        # Frequency map
        freq_map = {}
        for w in cleaned_words:
            freq_map[w] = freq_map.get(w, 0) + 1
            
        # Normalize word frequencies
        max_freq = max(freq_map.values())
        for w in freq_map:
            freq_map[w] /= max_freq
            
        # Score sentences
        sent_scores = {}
        discount_phrases = ["for example", "for instance", "such as", "in addition", "moreover"]
        
        for i, sent in enumerate(sentences):
            sent_clean = sent.lower().strip()
            
            try:
                sent_words = nltk.word_tokenize(sent.lower())
            except Exception:
                sent_words = re.findall(r'\b\w+\b', sent.lower())
                
            # Filter non-alphanumeric words for length denominator
            words_only = [w for w in sent_words if w.isalnum()]
            n_words = len(words_only)
            
            if n_words == 0:
                sent_scores[i] = 0.0
                continue
                
            # Calculate raw frequency score
            raw_score = sum(freq_map.get(w, 0.0) for w in sent_words)
            
            # Normalize by sentence length to avoid bias towards longer sentences
            norm_score = raw_score / (n_words ** 0.6)
            
            # Apply discount factor (0.3) if the sentence starts with example/transitional words
            has_discount = False
            for phrase in discount_phrases:
                if sent_clean.startswith(phrase):
                    has_discount = True
                    break
            
            if has_discount:
                norm_score *= 0.3
                
            sent_scores[i] = norm_score
            
        # Pick top sentences in original order
        top_indices = sorted(sent_scores, key=sent_scores.get, reverse=True)[:num_sentences]
        top_indices.sort()
        
        return " ".join([sentences[idx] for idx in top_indices])
    except Exception as e:
        print(f"Summarization error: {e}")
        return " ".join(sentences[:num_sentences])
