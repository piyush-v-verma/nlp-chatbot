import re
import nltk
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation

def run_lda(text, n_topics=3):
    """
    Performs Latent Dirichlet Allocation (LDA) topic modeling.
    Enforces a validation limit of minimum 80 words.
    """
    if not text or not text.strip():
        return {"error": "Please enter some text to analyze.", "topics": []}
        
    # Count words
    words = re.findall(r'\b\w+\b', text)
    word_count = len(words)
    
    if word_count < 80:
        return {
            "error": f"Topic modeling works best on longer documents. Please provide a paragraph containing approximately 80 or more words. (Current count: {word_count} words)",
            "topics": []
        }
        
    try:
        try:
            sentences = nltk.sent_tokenize(text)
        except Exception:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
            
        if len(sentences) < 2:
            return {"error": "Topic modeling requires multiple sentences to run successfully.", "topics": []}
            
        vectorizer = CountVectorizer(stop_words='english')
        dtm = vectorizer.fit_transform(sentences)
        
        if dtm.shape[1] == 0:
            return {"error": "No informative words found after removing stop-words.", "topics": []}
            
        n_topics = min(n_topics, dtm.shape[0], dtm.shape[1])
        if n_topics < 1:
            n_topics = 1
            
        lda = LatentDirichletAllocation(n_components=n_topics, random_state=42)
        lda.fit(dtm)
        
        feature_names = vectorizer.get_feature_names_out()
        topics_data = []
        for idx, topic in enumerate(lda.components_):
            top_words = [feature_names[i] for i in topic.argsort()[:-6:-1]] # Top 5 words
            topics_data.append({
                "topic_id": idx + 1,
                "words": top_words
            })
            
        doc_topics = lda.transform(dtm)
        doc_distribution = []
        for idx, doc_dist in enumerate(doc_topics):
            doc_distribution.append({
                "doc_index": idx,
                "text": sentences[idx],
                "topics": doc_dist.tolist()
            })
            
        return {
            "topics": topics_data,
            "document_distribution": doc_distribution
        }
    except Exception as e:
        print(f"LDA topic modeling error: {e}")
        return {"error": "An unexpected error occurred while processing your request. Please try again.", "topics": []}
