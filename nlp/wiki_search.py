import requests
import nltk
import re
import json

def search_wikipedia(query):
    """
    Searches Wikipedia for the query.
    Checks and writes to SQLite database-level wiki_cache table.
    Returns: JSON-serialized dictionary string with keys 'query', 'extract', 'url' or error string.
    """
    if not query or not query.strip():
        return "Please enter some text to analyze."
        
    query_clean = query.strip().lower()
    
    # 1. Check cache first
    try:
        import database
        cached = database.get_wiki_cache(query_clean)
        if cached:
            return cached
    except Exception as e:
        print(f"Wikipedia Cache read error: {e}")
        
    # 2. Run Network Search
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        headers = {
            "User-Agent": "NLPChatbot/1.0 (contact@nlpchatbot.local)"
        }
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1
        }
        res = requests.get(search_url, params=search_params, headers=headers, timeout=5)
        if res.status_code != 200:
            return "Sorry, the translation/wikipedia service is currently unavailable. Please try again later."
            
        search_results = res.json().get("query", {}).get("search", [])
        if not search_results:
            return "No matching Wikipedia article was found for your query. Try using different keywords."
            
        title = search_results[0]["title"]
        
        # Get intro extract of the page
        summary_params = {
            "action": "query",
            "prop": "extracts",
            "exintro": True,
            "explaintext": True,
            "titles": title,
            "format": "json"
        }
        res_summary = requests.get(search_url, params=summary_params, headers=headers, timeout=5)
        if res_summary.status_code != 200:
            return "Sorry, the translation/wikipedia service is currently unavailable. Please try again later."
            
        pages = res_summary.json().get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if page_id == "-1":
                continue
            extract = page_data.get("extract", "")
            if extract:
                try:
                    sentences = nltk.sent_tokenize(extract)
                except Exception:
                    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', extract) if s.strip()]
                    
                summary = " ".join(sentences[:3])
                wiki_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                
                # Format structured output dictionary
                result_data = {
                    "query": title,
                    "extract": summary,
                    "url": wiki_url
                }
                result_str = json.dumps(result_data)
                
                # Write to SQLite Cache
                try:
                    database.save_wiki_cache(query_clean, result_str)
                except Exception as ce:
                    print(f"Wikipedia Cache write error: {ce}")
                    
                return result_str
                
        return "No matching Wikipedia article was found for your query. Try using different keywords."
    except Exception as e:
        print(f"Wikipedia API error: {e}")
        return "An unexpected error occurred while processing your request. Please try again."
