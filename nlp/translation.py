import requests

# Local high-fidelity dictionary to bypass crowdsourced database spam for common greetings
LOCAL_TRANSLATIONS_EN_TO_HI = {
    "hello": "नमस्ते (Namaste)",
    "hi": "नमस्ते (Namaste)",
    "how are you": "आप कैसे हैं? (Aap kaise hain?)",
    "how are you doing": "आप कैसे हैं? (Aap kaise hain?)",
    "what is your name": "आपका नाम क्या है? (Aapka naam kya hai?)",
    "thank you": "धन्यवाद (Dhanyavaad)",
    "thanks": "धन्यवाद (Dhanyavaad)",
    "good morning": "शुभ प्रभात (Shubh prabhat)",
    "good night": "शुभ रात्रि (Shubh raatri)",
    "goodbye": "अलविदा (Alvida)",
    "yes": "हाँ (Haan)",
    "no": "नहीं (Nahi)",
    "love": "प्यार (Pyaar)",
    "world": "दुनिया (Duniya)",
    "chatbot": "चैटबॉट (Chatbot)",
    "i love my parents": "मैं अपने माता-पिता से प्यार करता हूँ। (Main apne mata-pita se pyar karta hoon.)",
    "i love my family": "मैं अपने परिवार से प्यार करता हूँ। (Main apne parivar se pyar karta hoon.)",
    "what are you doing": "आप क्या कर रहे हैं? (Aap kya kar rahe hain?)"
}

LOCAL_TRANSLATIONS_HI_TO_EN = {
    "नमस्ते": "Hello / Greetings",
    "धन्यवाद": "Thank you",
    "हाँ": "Yes",
    "नहीं": "No",
    "प्यार": "Love",
    "दुनिया": "World",
    "आप कैसे हैं": "How are you?",
    "आपका नाम क्या है": "What is your name?",
    "मैं अपने माता-पिता से प्यार करता हूँ": "I love my parents",
    "मैं अपने परिवार से प्यार करता हूँ": "I love my family"
}

def contains_devnagari(text):
    """Returns True if the text contains any Devnagari characters (Hindi script)."""
    return any('\u0900' <= char <= '\u097f' for char in text)

def get_local_translation(text, detected_lang):
    """Checks for high-fidelity offline translation dictionary matches."""
    text_clean = text.lower().strip().replace("?", "").replace(".", "").replace("!", "").replace(",", "")
    
    if detected_lang == "English":
        if text_clean in LOCAL_TRANSLATIONS_EN_TO_HI:
            return LOCAL_TRANSLATIONS_EN_TO_HI[text_clean], "English", "Hindi"
    else:
        # Check direct match
        if text_clean in LOCAL_TRANSLATIONS_HI_TO_EN:
            return LOCAL_TRANSLATIONS_HI_TO_EN[text_clean], "Hindi", "English"
        # Check substring match
        for k, v in LOCAL_TRANSLATIONS_HI_TO_EN.items():
            if k in text_clean:
                return v, "Hindi", "English"
                
    return None

def select_best_translation(original_text, matches_list, response_translated_text, target_lang):
    """
    Selects the best translation from the MyMemory matches list by:
    1. Priority 1: First translation matching the script of the target language.
    2. Priority 2: First translation different from the original text.
    3. Priority 3: Fallback response.
    """
    orig_clean = original_text.lower().strip()
    
    if matches_list:
        for m in matches_list:
            trans = m.get("translation", "").strip()
            if trans:
                if target_lang == "hi" and contains_devnagari(trans):
                    return trans
                elif target_lang == "en" and not contains_devnagari(trans) and trans.lower() != orig_clean:
                    return trans
                    
    if matches_list:
        for m in matches_list:
            trans = m.get("translation", "").strip()
            if trans and trans.lower() != orig_clean:
                return trans
                
    if response_translated_text:
        trans = response_translated_text.strip()
        if target_lang == "hi" and contains_devnagari(trans):
            return trans
        if target_lang == "en" and not contains_devnagari(trans) and trans.lower() != orig_clean:
            return trans
            
    if matches_list:
        first = matches_list[0].get("translation", "").strip()
        if first:
            return first
            
    return response_translated_text

def translate_text(text):
    """
    Translates English to Hindi or Hindi to English based on language detection.
    Returns: (translated_text, detected_lang, target_lang)
    """
    if not text or not text.strip():
        return "Please provide text to translate.", "Unknown", "Unknown"
        
    is_hindi = contains_devnagari(text)
    detected_lang = "Hindi" if is_hindi else "English"
    
    # 1. Check local high-fidelity cache first to prevent database spam matches
    local_match = get_local_translation(text, detected_lang)
    if local_match:
        return local_match
        
    target_lang = "en" if is_hindi else "hi"
    langpair = "hi|en" if is_hindi else "en|hi"
    
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {
            "q": text,
            "langpair": langpair
        }
        res = requests.get(url, params=params, timeout=4)
        if res.status_code == 200:
            data = res.json()
            matches = data.get("matches", [])
            response_translated = data.get("responseData", {}).get("translatedText", "")
            
            # Select best translation filtering out database noise
            translated_text = select_best_translation(text, matches, response_translated, target_lang)
            if translated_text:
                return translated_text, detected_lang, "Hindi" if target_lang == "hi" else "English"
    except Exception as e:
        print(f"Translation API error: {e}")
        
    return fallback_translate(text, detected_lang)

def fallback_translate(text, detected_lang):
    """Simple dictionary-based fallback for translation if network is unavailable."""
    # Check local list (same dictionary for compatibility)
    local_match = get_local_translation(text, detected_lang)
    if local_match:
        return local_match
        
    # Return friendly error message instead of throwing an exception
    dest_lang = "English" if detected_lang == "Hindi" else "Hindi"
    return f"Sorry, the translation service is currently unavailable. Please try again later.", detected_lang, dest_lang
