import json

def format_sentiment(label, compound, pos, neu, neg, confidence=1.0):
    """Formats VADER sentiment output."""
    explanation = f"VADER analyzed the text. It contains a positive ratio of {pos:.2f}, neutral ratio of {neu:.2f}, and negative ratio of {neg:.2f}. "
    if label.lower() == "positive":
        explanation += "The overall sentiment indicates positive emotion, support, or optimism."
    elif label.lower() == "negative":
        explanation += "The overall sentiment indicates negative emotion, frustration, or concern."
    else:
        explanation += "The overall sentiment is neutral and balanced, with no strong polarity detected."
        
    return {
        "type": "sentiment",
        "title": "Sentiment Analysis",
        "confidence": confidence,
        "explanation": explanation,
        "data": {
            "label": label.capitalize(),
            "compound": round(compound, 4),
            "pos": pos,
            "neu": neu,
            "neg": neg
        }
    }

def format_translation(detected_lang, target_lang, original, translated, confidence=1.0):
    """Formats bidirectional translation output."""
    explanation = f"The source text was detected as {detected_lang} and translated into {target_lang}."
    return {
        "type": "translation",
        "title": "Translation",
        "confidence": confidence,
        "explanation": explanation,
        "data": {
            "source_lang": detected_lang,
            "target_lang": target_lang,
            "original": original,
            "translated": translated
        }
    }

def format_ner(entities, confidence=1.0):
    """Formats NLTK/spaCy entity output."""
    label_meanings = {
        "PERSON": "Person", "ORG": "Organization", "GPE": "Location",
        "DATE": "Date", "TIME": "Time", "MONEY": "Monetary Value", 
        "PERCENT": "Percentage", "CARDINAL": "Numeric Value", "ORDINAL": "Order Indicator",
        "FAC": "Facility / Structure", "LOC": "Geographic Area", "PRODUCT": "Product / Brand",
        "EVENT": "Named Event", "WORK_OF_ART": "Work of Art", "LAW": "Law / Regulation",
        "LANGUAGE": "Language", "NORP": "Group Identity", "QUANTITY": "Measurement"
    }
    
    formatted_data = []
    for ent in entities:
        lbl = ent.get("label", "OTHER").upper()
        full_lbl = label_meanings.get(lbl, lbl.capitalize())
        formatted_data.append({
            "text": ent.get("text", ""),
            "label": full_lbl
        })
        
    explanation = f"Extracted {len(formatted_data)} named entities (such as people, organizations, and geographic locations) from the text."
    return {
        "type": "ner",
        "title": "Named Entity Recognition",
        "confidence": confidence,
        "explanation": explanation,
        "data": formatted_data
    }

def format_pos(pos_tags, confidence=1.0):
    """Formats grammatical POS tag outputs."""
    tag_meanings = {
        'CC': 'Coordinating conjunction', 'CD': 'Cardinal number', 'DT': 'Determiner',
        'IN': 'Preposition / Conjunction', 'JJ': 'Adjective', 'JJR': 'Adjective (comparative)',
        'JJS': 'Adjective (superlative)', 'MD': 'Modal verb', 'NN': 'Noun (singular)',
        'NNS': 'Noun (plural)', 'NNP': 'Proper noun (singular)', 'PRP': 'Personal pronoun',
        'RB': 'Adverb', 'TO': 'to', 'VB': 'Verb (base)', 'VBD': 'Verb (past)',
        'VBG': 'Verb (gerund)', 'VBN': 'Verb (past participle)', 'VBP': 'Verb (non-3rd present)',
        'VBZ': 'Verb (3rd present)', 'WP': 'Wh-pronoun', 'WRB': 'Wh-adverb'
    }
    
    formatted_data = []
    for word, tag in pos_tags:
        meaning = tag_meanings.get(tag, "Grammatical Tag")
        formatted_data.append({
            "word": word,
            "tag": tag,
            "meaning": meaning
        })
        
    explanation = "Identified parts of speech and grammatical syntax markers for words in the input."
    return {
        "type": "pos",
        "title": "Part-of-Speech Tagging",
        "confidence": confidence,
        "explanation": explanation,
        "data": formatted_data
    }

def format_summarization(summary, confidence=1.0):
    """Formats extractive text summary outputs."""
    explanation = "Extracted the highest-scoring informative sentences, normalized by sentence length."
    return {
        "type": "summarize",
        "title": "Text Summarization",
        "confidence": confidence,
        "explanation": explanation,
        "data": {
            "summary": summary
        }
    }

def format_wikipedia(query, extract, url, confidence=1.0):
    """Formats cached/fetched Wikipedia query search lookup."""
    explanation = f"Retrieved factual encyclopedic summary details for '{query}' from Wikipedia."
    return {
        "type": "wikipedia",
        "title": "Wikipedia Search",
        "confidence": confidence,
        "explanation": explanation,
        "data": {
            "query": query,
            "extract": extract,
            "url": url
        }
    }

def format_general(response, confidence=1.0):
    """Formats built-in chatbot chitchat response."""
    explanation = "Simple conversational response returned from local chatbot knowledge base."
    return {
        "type": "general",
        "title": "General Conversation",
        "confidence": confidence,
        "explanation": explanation,
        "data": {
            "response": response
        }
    }

def format_error(error_message, error_type="Internal Error"):
    """Formats modular NLP error boundary outputs."""
    return {
        "type": "error",
        "title": error_type,
        "confidence": 0.0,
        "explanation": "An issue occurred while processing the text in the NLP backend.",
        "data": {
            "error_message": error_message
        }
    }

def format_math(math_res, confidence=1.0):
    """Formats SymPy mathematical outputs."""
    if "error" in math_res:
        return format_error(math_res["error"], "Math Solver Error")
        
    explanation = "Evaluated the mathematical query using SymPy computer algebra system."
    return {
        "type": "math",
        "title": "SymPy Math Solver",
        "confidence": confidence,
        "explanation": explanation,
        "data": math_res
    }
