import os
import time
import json
import uuid
import logging
import re
import threading
import secrets
from collections import defaultdict
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
import database
import nlp
import webbrowser
from threading import Timer

# Load environment variables
load_dotenv()

# Load Flask Secret Key securely
flask_secret = os.environ.get("FLASK_SECRET_KEY")
if not flask_secret:
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("FLASK_SECRET_KEY environment variable is required in production!")
    else:
        # Generate dynamic secret key during dev if env key is missing
        flask_secret = secrets.token_hex(32)

app = Flask(__name__)
app.secret_key = flask_secret

# Session Cookie Security Configurations
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if os.environ.get("FLASK_ENV") == "production":
    app.config['SESSION_COOKIE_SECURE'] = True
else:
    app.config['SESSION_COOKIE_SECURE'] = False

# Enable CSRF Protection globally
csrf = CSRFProtect(app)

# Memory-backed rate limiting records (isolated by feature)
# Suitable for development/single-process deployment. For production, replace with Redis.
failed_login_records = defaultdict(list)
signup_records = defaultdict(list)
forgot_records = defaultdict(list)
reset_records = defaultdict(list)

def check_rate_limit(records_dict, ip_address, limit=5, period=60):
    now = time.time()
    records_dict[ip_address] = [t for t in records_dict[ip_address] if now - t < period]
    if len(records_dict[ip_address]) >= limit:
        return True
    return False

def record_rate_limit_attempt(records_dict, ip_address):
    now = time.time()
    records_dict[ip_address].append(now)

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
def validate_email(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email))

def validate_password(password: str) -> bool:
    return len(password) >= 8

@app.after_request
def add_header(response):
    # Prevent back button cached navigation for protected pages
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    # Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response

# Ensure logging folder exists
os.makedirs('logs', exist_ok=True)

# Set up structured file logging
logging.basicConfig(
    filename='logs/chatbot.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Initialize database
database.init_db()

# Warm up NLTK / spaCy models asynchronously
threading.Thread(target=nlp.init_nlp_resources).start()

import google.generativeai as genai
import re

# Load Gemini API Key
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if not gemini_api_key:
    try:
        api_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api")
        if os.path.exists(api_path):
            with open(api_path, "r", encoding="utf-8") as f:
                gemini_api_key = f.read().strip()
    except Exception as e:
        logging.error(f"Error reading local api key file: {e}")

if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    logging.info("Gemini API key configured successfully.")
else:
    logging.warning("Gemini API key not found in environment or api file.")

def get_active_gemini_key():
    try:
        user_id = session.get("user_id")
        if user_id:
            user_key = database.get_user_api_key(user_id)
            if user_key:
                return user_key
    except Exception:
        pass
    return gemini_api_key

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def query_gemini(prompt):
    key = get_active_gemini_key()
    if not key:
        raise Exception("Gemini API Key is not configured. Please supply GEMINI_API_KEY environment variable or a local api file.")
    genai.configure(api_key=key)
    try:
        model = genai.GenerativeModel("gemini-3.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini API call failed: {e}")
        raise e

def query_gemini_chat(chat_id, user_message):
    key = get_active_gemini_key()
    if not key:
        raise Exception("Gemini API Key is not configured. Please supply GEMINI_API_KEY environment variable or a local api file.")
    genai.configure(api_key=key)
    try:
        history = nlp.ConversationManager.get_context(chat_id, limit=6)
        contents = []
        for msg in history:
            role = msg['role']
            content = msg['content']
            if role == 'assistant' and content.strip().startswith('{') and content.strip().endswith('}'):
                try:
                    data = json.loads(content)
                    if data.get('type') == 'general':
                        content = data['data'].get('response', '')
                    elif data.get('type') == 'summarize':
                        content = data['data'].get('summary', '')
                    elif data.get('type') == 'wikipedia':
                        content = data['data'].get('extract', '')
                    elif data.get('type') == 'translation':
                        content = data['data'].get('translated', '')
                    elif data.get('type') == 'math':
                        content = data['data'].get('result', '')
                except Exception:
                    pass
            
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": content}]
            })
        
        if not contents or contents[-1]["parts"][0]["text"] != user_message:
            contents.append({
                "role": "user",
                "parts": [{"text": user_message}]
            })
            
        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash",
            system_instruction="Your name is X-Pilot. You are a helpful assistant. If the user asks about your identity, who you are, or if you are Gemini, you must assert that you are X-Pilot."
        )
        response = model.generate_content(contents)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini chat API call failed: {e}")
        raise e

def query_gemini_math(text):
    prompt = (
        f"Solve the mathematical equation or expression: '{text}'.\n"
        f"Respond ONLY with a valid JSON block containing the following fields:\n"
        f"- 'type': one of 'equation', 'calculus', 'arithmetic'\n"
        f"- 'operation': name of the operation performed\n"
        f"- 'expression': the parsed expression/equation\n"
        f"- 'result': the final answer\n"
        f"- 'steps': brief step-by-step instructions of how to solve it\n"
        f"Do not include any formatting markdown like ```json, just output raw JSON text."
    )
    res = query_gemini(prompt)
    if res.startswith("```"):
        res = re.sub(r'^```(?:json)?\n', '', res)
        res = re.sub(r'\n```$', '', res)
    return json.loads(res.strip())

def is_general_chitchat(text):
    """Checks if a user query represents general casual conversation/greetings matching whole words."""
    import re
    text_clean = text.lower().strip().replace("?", "").replace(".", "").replace("!", "")
    
    # Split text into unique set of whole alphanumeric words
    words = set(re.findall(r'\b\w+\b', text_clean))
    
    greetings = {"hi", "hello", "hey", "greetings", "yo", "hola", "namaste", "morning", "evening"}
    thank_you = {"thank", "thanks", "appreciate", "grateful"}
    help_queries = {"help", "commands", "info", "capabilities"}
    
    # Whole-word intersections
    if words.intersection(greetings):
        return True
    if words.intersection(thank_you):
        return True
    if words.intersection(help_queries):
        return True
        
    # Conversational phrasing matches
    who_are_you = ["who are you", "what is your name", "whats your name", "who's you", "your identity"]
    how_are_you = ["how are you", "how's it going", "how do you do", "how are you doing", "how are things"]
    
    # Check substring matches
    for phrase in who_are_you + how_are_you:
        if re.search(r'\b' + re.escape(phrase) + r'\b', text_clean):
            return True
            
    # Fuzzy matching check for typos (e.g. "how are yoy")
    import difflib
    for phrase in who_are_you + how_are_you:
        ratio = difflib.SequenceMatcher(None, text_clean, phrase).ratio()
        if ratio >= 0.80:
            return True
            
    return False

def get_chitchat_response(text):
    """Returns local canned responses for chitchat."""
    text_clean = text.lower().strip().replace("?", "").replace(".", "").replace("!", "")
    words = text_clean.split()
    
    greetings = ["hi", "hello", "hey", "yo", "hola", "namaste"]
    who_are_you = ["who are you", "what is your name", "whats your name"]
    how_are_you = ["how are you", "how's it going", "how do you do"]
    thank_you = ["thank you", "thanks", "appreciate it"]
    
    if any(g in words for g in greetings):
        return "Hello! I am X-Pilot, your assistant. How can I help you today? Try typing a message or command like 'translate this' or 'summarize this text'."
    elif any(way in text_clean for way in who_are_you):
        return "I am X-Pilot, an interactive natural language processing workbench and assistant created to demonstrate preprocessing, sentiment, NER, POS tagging, translation, and topic modeling."
    elif any(hay in text_clean for hay in how_are_you):
        return "I'm X-Pilot, running smoothly and ready to analyze some text! How are you doing today?"
    elif any(ty in text_clean for ty in thank_you):
        return "You're very welcome! Let me know if you need any other text analyzed."
    else: # Help / Fallback
        return (
            "I support several NLP features. Simply ask me to do them naturally:\n\n"
            "- **Summarization**: 'Summarize this article: ...'\n"
            "- **Translation**: 'Translate I love my parents to Hindi'\n"
            "- **Sentiment**: 'What is the sentiment of this: I feel great!'\n"
            "- **NER**: 'Extract named entities from Barack Obama visited London'\n"
            "- **POS**: 'Tag parts of speech for: The dog barked.'\n"
            "- **Chunking**: 'Parse chunk structure of: The red bird sang.'\n"
            "- **Topic**: 'Extract topics from: [80+ words text]'"
        )

def compute_nlp_metadata(text, intent, confidence, selected_module, wiki_used, latency_ms, final_response):
    """Calculates all diagnostic metrics of the processing pipeline for the Inspector."""
    # Preprocessing
    pre = nlp.preprocess_text(text)
    # Sentiment
    sent = nlp.get_sentiment(text)
    # POS tags
    pos = nlp.get_pos_tags(text)
    # Entities
    entities = nlp.get_ner(text)
    
    return {
        "original_text": text,
        "intent_detected": intent,
        "intent_confidence": confidence,
        "selected_module": selected_module,
        "tokens": pre["tokens"],
        "removed_stop_words": pre["removed_stop_words"],
        "filtered_tokens": pre["cleaned_tokens"],
        "stemmed_tokens": pre["stemmed_tokens"],
        "pos_tags": pos,
        "entities": entities,
        "sentiment": sent,
        "processing_time": latency_ms,
        "wikipedia_used": "Yes" if wiki_used else "No",
        "final_response": final_response
    }

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/chats', methods=['GET'])
@login_required
def api_get_chats():
    chats = database.get_chats(session['user_id'])
    return jsonify(chats)

@app.route('/api/chats', methods=['POST'])
@login_required
def api_create_chat():
    chat_id = str(uuid.uuid4())
    title = "New Chat"
    database.create_chat(chat_id, session['user_id'], title)
    return jsonify({"id": chat_id, "title": title})

@app.route('/api/chats', methods=['DELETE'])
@login_required
def api_clear_all_chats():
    database.delete_all_chats(session['user_id'])
    return jsonify({"success": True, "message": "All conversations cleared successfully."})

@app.route('/api/chats/<chat_id>', methods=['DELETE'])
@login_required
def api_delete_chat(chat_id):
    database.delete_chat(chat_id, session['user_id'])
    return jsonify({"success": True})

@app.route('/api/chats/<chat_id>/messages', methods=['GET'])
@login_required
def api_get_messages(chat_id):
    messages = database.get_messages(chat_id)
    return jsonify(messages)

@app.route('/api/autocomplete', methods=['GET'])
@login_required
def api_autocomplete():
    q = request.args.get('q', '')
    chat_id = request.args.get('chat_id', '')
    
    context_text = ""
    if chat_id:
        try:
            # Use ConversationManager to get context text for autocompletes
            context_text = nlp.ConversationManager.get_context_text(chat_id, limit=5, role_filter=None)
        except Exception:
            pass
            
    suggestions = nlp.get_autocomplete_suggestions(q, context_text)
    return jsonify(suggestions)

@app.route('/api/chats/<chat_id>/messages', methods=['POST'])
@login_required
def api_send_message(chat_id):
    start_time = time.time()
    
    data = request.json or {}
    user_content = data.get('content', '').strip()
    
    if not user_content:
        return jsonify({"error": "Empty message"}), 400
        
    # 1. Detect Intent and Confidence Score
    intent, confidence, parsed_content = nlp.detect_intent(user_content)
    
    # 2. Route general or low confidence intents directly to Gemini general chat
    wiki_used = False
    selected_module = f"nlp.{intent}" if intent != "general" else "nlp.general"
    
    if intent == "general" or confidence < 0.60:
        intent = "general"
        selected_module = "nlp.general"
            
    # Process intent logic and format structured response
    bot_response_json = {}
    handled_exception = None
    
    try:
        if intent == "summarize":
            # Contextual fallback: summarize last 5 user messages if query is empty
            if not parsed_content:
                context_text = nlp.ConversationManager.get_context_text(chat_id, limit=5, role_filter='user')
                if not context_text.strip():
                    bot_response_json = nlp.format_error(
                        "There is no chat history to summarize yet. Please enter some text to analyze.",
                        "Empty Input"
                    )
                else:
                    summary = query_gemini(f"Summarize the following text concisely. Provide only the summary itself without any introductory text:\n\n{context_text}")
                    bot_response_json = nlp.format_summarization(summary, confidence)
            else:
                summary = query_gemini(f"Summarize the following text concisely. Provide only the summary itself without any introductory text:\n\n{parsed_content}")
                bot_response_json = nlp.format_summarization(summary, confidence)
                
        elif intent == "translate":
            # Contextual fallback: translate last assistant response if query is empty
            if not parsed_content:
                last_bot_msg = nlp.ConversationManager.get_last_assistant_message(chat_id)
                if not last_bot_msg.strip():
                    bot_response_json = nlp.format_error(
                        "There is no previous message to translate. Please specify text.",
                        "Empty Input"
                    )
                else:
                    is_hindi = any('\u0900' <= char <= '\u097f' for char in last_bot_msg)
                    src = "Hindi" if is_hindi else "English"
                    tgt = "English" if is_hindi else "Hindi"
                    translation = query_gemini(
                        f"Translate the following text from {src} to {tgt}. Keep it natural. "
                        f"Provide only the translated text itself without any introduction or quotes:\n\n{last_bot_msg}"
                    )
                    bot_response_json = nlp.format_translation(src, tgt, last_bot_msg, translation, confidence)
            else:
                is_hindi = any('\u0900' <= char <= '\u097f' for char in parsed_content)
                src = "Hindi" if is_hindi else "English"
                tgt = "English" if is_hindi else "Hindi"
                translation = query_gemini(
                    f"Translate the following text from {src} to {tgt}. Keep it natural. "
                    f"Provide only the translated text itself without any introduction or quotes:\n\n{parsed_content}"
                )
                bot_response_json = nlp.format_translation(src, tgt, parsed_content, translation, confidence)
                    
        elif intent == "sentiment":
            target = parsed_content if parsed_content else user_content
            prompt = (
                f"Analyze the sentiment of this text: '{target}'.\n"
                f"Respond ONLY with a valid JSON block containing the following fields:\n"
                f"- 'label': one of 'positive', 'negative', 'neutral'\n"
                f"- 'compound': a score between -1.0 (most negative) and 1.0 (most positive)\n"
                f"- 'pos': ratio of positive content (between 0.0 and 1.0)\n"
                f"- 'neu': ratio of neutral content (between 0.0 and 1.0)\n"
                f"- 'neg': ratio of negative content (between 0.0 and 1.0)\n"
                f"Ensure pos + neu + neg sum to approximately 1.0.\n"
                f"Do not include any formatting markdown like ```json, just output raw JSON text."
            )
            res = query_gemini(prompt)
            if res.startswith("```"):
                res = re.sub(r'^```(?:json)?\n', '', res)
                res = re.sub(r'\n```$', '', res)
            sent = json.loads(res.strip())
            bot_response_json = nlp.format_sentiment(sent["label"], sent["compound"], sent["pos"], sent["neu"], sent["neg"], confidence)
            
        elif intent == "ner":
            target = parsed_content if parsed_content else user_content
            prompt = (
                f"Perform Named Entity Recognition on the following text: '{target}'.\n"
                f"Identify entities such as people, organizations, locations, dates, etc.\n"
                f"Respond ONLY with a valid JSON array of objects, where each object has fields:\n"
                f"- 'text': the matching text substring\n"
                f"- 'label': the type of entity (e.g. PERSON, ORG, GPE, DATE, etc.)\n"
                f"Do not include any formatting markdown like ```json, just output raw JSON text."
            )
            res = query_gemini(prompt)
            if res.startswith("```"):
                res = re.sub(r'^```(?:json)?\n', '', res)
                res = re.sub(r'\n```$', '', res)
            entities = json.loads(res.strip())
            bot_response_json = nlp.format_ner(entities, confidence)
            
        elif intent == "pos":
            target = parsed_content if parsed_content else user_content
            prompt = (
                f"Tag the parts of speech for each word in this text: '{target}'. Use standard Penn Treebank POS tags.\n"
                f"Respond ONLY with a valid JSON array of arrays, where each sub-array contains [word, tag] (e.g., [['The', 'DT'], ['dog', 'NN']]).\n"
                f"Do not include any formatting markdown like ```json, just output raw JSON text."
            )
            res = query_gemini(prompt)
            if res.startswith("```"):
                res = re.sub(r'^```(?:json)?\n', '', res)
                res = re.sub(r'\n```$', '', res)
            pos_tags = json.loads(res.strip())
            bot_response_json = nlp.format_pos(pos_tags, confidence)
            
        elif intent == "chunk":
            target = parsed_content if parsed_content else user_content
            prompt = (
                f"Perform grammatical chunking on the following text: '{target}'.\n"
                f"Group words into syntactic phrases like Noun Phrase (NP), Verb Phrase (VP), Prepositional Phrase (PP), etc.\n"
                f"Respond ONLY with a valid JSON array of objects representing chunks, where each object has fields:\n"
                f"- 'text': the phrase string\n"
                f"- 'label': the phrase category (e.g. NP, VP, PP)\n"
                f"Do not include any formatting markdown like ```json, just output raw JSON text."
            )
            res = query_gemini(prompt)
            if res.startswith("```"):
                res = re.sub(r'^```(?:json)?\n', '', res)
                res = re.sub(r'\n```$', '', res)
            chunks = json.loads(res.strip())
            bot_response_json = {
                "type": "chunk",
                "title": "Syntax Chunking",
                "confidence": confidence,
                "explanation": "Parsed syntactic groups showing noun phrases (NP), verb phrases (VP), and prepositional phrases (PP).",
                "data": {
                    "chunks": chunks,
                    "target_text": target
                }
            }
            
        elif intent == "topic":
            target = parsed_content if parsed_content else user_content
            prompt = (
                f"Perform topic modeling on this text: '{target}'.\n"
                f"Identify up to 3 main topics/themes. For each topic, provide the topic name and a list of key terms associated with it.\n"
                f"Respond ONLY with a valid JSON block containing the following fields:\n"
                f"- 'topics': a list of objects, each containing 'topic_id' (integer), 'words' (array of strings of key terms), and 'name' (string of topic name)\n"
                f"- 'document_topics': a list of objects showing document alignment containing 'document_id' (0) and 'topic_distributions' (array of floats summing to 1.0 representing weights for each topic)\n"
                f"Do not include any formatting markdown like ```json, just output raw JSON text."
            )
            res = query_gemini(prompt)
            if res.startswith("```"):
                res = re.sub(r'^```(?:json)?\n', '', res)
                res = re.sub(r'\n```$', '', res)
            lda_res = json.loads(res.strip())
            if "error" in lda_res:
                bot_response_json = nlp.format_error(lda_res["error"], "Unsupported Operation")
            else:
                bot_response_json = {
                    "type": "topic",
                    "title": "LDA Topic Modeling",
                    "confidence": confidence,
                    "explanation": "Identified main subjects (topics) and keyword distributions using Latent Dirichlet Allocation.",
                    "data": lda_res
                }
                
        elif intent == "math":
            target = parsed_content if parsed_content else user_content
            math_res = query_gemini_math(target)
            bot_response_json = nlp.format_math(math_res, confidence)
            
        elif intent == "wikipedia":
            try:
                gemini_response = query_gemini_chat(chat_id, user_content)
                bot_response_json = nlp.format_general(gemini_response, confidence)
            except Exception as ge:
                logging.error(f"Failed to query Gemini chat for wikipedia fallback: {ge}")
                if is_general_chitchat(user_content):
                    canned = get_chitchat_response(user_content)
                    bot_response_json = nlp.format_general(canned, confidence)
                else:
                    bot_response_json = nlp.format_error(
                        f"Gemini API call failed: {ge}. Please try again later.",
                        "Gemini API Error"
                    )
                
        else: # general chitchat
            try:
                gemini_response = query_gemini_chat(chat_id, user_content)
                bot_response_json = nlp.format_general(gemini_response, confidence)
            except Exception as ge:
                logging.error(f"Failed to query Gemini chat: {ge}")
                if is_general_chitchat(user_content):
                    canned = get_chitchat_response(user_content)
                    bot_response_json = nlp.format_general(canned, confidence)
                else:
                    if "quota" in str(ge).lower() or "limit" in str(ge).lower() or "429" in str(ge):
                        bot_response_json = nlp.format_error(
                            "Your Gemini API Key has exceeded its daily free tier quota (rate limit). "
                            "Please upgrade your Gemini billing, wait 24 hours, or try a different key.",
                            "Gemini Quota Exceeded"
                        )
                    else:
                        bot_response_json = nlp.format_error(
                            f"Gemini API call failed: {ge}. Please try again later.",
                            "Gemini API Error"
                        )
            
    except Exception as e:
        handled_exception = str(e)
        bot_response_json = nlp.format_error(
            "An unexpected error occurred while processing your request. Please try again.",
            "Internal Error"
        )
        
    # Calculate Latency (Processing Time)
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Inject metadata directly into every assistant JSON response contract
    bot_response_json["processing_time"] = latency_ms
    bot_response_json["module_name"] = selected_module
    bot_response_json["timestamp"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    
    # Compile pipeline diagnostic metrics for the Inspector (both messages get identical diagnostic pipelines)
    user_pipeline_metadata = compute_nlp_metadata(
        user_content, intent, confidence, selected_module, wiki_used, latency_ms, bot_response_json
    )
    
    assistant_pipeline_metadata = compute_nlp_metadata(
        json.dumps(bot_response_json), "assistant_response", 1.0, "nlp.response_formatter", False, 0, bot_response_json
    )
    
    # Save user message
    database.save_message(chat_id, 'user', user_content, intent, user_pipeline_metadata)
    
    # Save assistant message as formatted JSON string
    database.save_message(chat_id, 'assistant', json.dumps(bot_response_json), intent, user_pipeline_metadata)
    
    # Write details to logs/chatbot.log (lightweight logging)
    logging.info(
        f"Query: '{user_content}' | Intent: '{intent}' | Conf: {confidence:.2f} | "
        f"Module: {selected_module} | Latency: {latency_ms}ms | Wiki: {wiki_used} | Exception: {handled_exception}"
    )
    
    # Fetch updated conversation list to return
    updated_messages = database.get_messages(chat_id)
    
    return jsonify({
        "user_message": updated_messages[-2],
        "assistant_message": updated_messages[-1]
    })

# --- Authentication and Account Routes ---

# --- Authentication and Account Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    error = None
    if request.method == 'POST':
        if check_rate_limit(failed_login_records, request.remote_addr):
            return render_template('login.html', error="Too many login attempts. Please try again later."), 429
            
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            error = "Invalid email or password."
            record_rate_limit_attempt(failed_login_records, request.remote_addr)
        else:
            user_id = database.authenticate_user(username, password)
            if user_id:
                # Clear failed attempts on successful authentication
                failed_login_records.pop(request.remote_addr, None)
                session['user_id'] = user_id
                session['username'] = username
                return redirect(url_for('index'))
            else:
                error = "Invalid email or password."
                record_rate_limit_attempt(failed_login_records, request.remote_addr)
    return render_template('login.html', error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    error = None
    if request.method == 'POST':
        if check_rate_limit(signup_records, request.remote_addr):
            return render_template('signup.html', error="Too many attempts. Please try again later."), 429
        record_rate_limit_attempt(signup_records, request.remote_addr)
        
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Default dummy values to satisfy the database schema
        sec_question = "What is your favorite color?"
        sec_answer = "blue"
        
        if not username or not password:
            error = "Please enter all required fields."
        elif not validate_email(username):
            error = "Please enter a valid email address."
        elif not validate_password(password):
            error = "Password does not meet the required security requirements."
        else:
            success = database.register_user(username, password, sec_question, sec_answer)
            if success:
                user_id = database.authenticate_user(username, password)
                if user_id:
                    session['user_id'] = user_id
                    session['username'] = username
                    return redirect(url_for('index'))
                else:
                    error = "Unable to create your account. Please try again."
            else:
                error = "Account already exists. Please login."
    return render_template('signup.html', error=error)

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        if check_rate_limit(forgot_records, request.remote_addr):
            return jsonify({"success": False, "message": "Too many attempts. Please try again later."}), 429
        record_rate_limit_attempt(forgot_records, request.remote_addr)
        
        # Support both form data and JSON requests
        username = request.form.get('username', '').strip()
        if not username and request.is_json:
            data = request.json or {}
            username = data.get('username', '').strip()
            
        if not username:
            msg = "Email address is required."
            return jsonify({"success": False, "message": msg})
            
        if not validate_email(username):
            msg = "Please enter a valid email address."
            return jsonify({"success": False, "message": msg})

        # Check if user exists in the database
        exists = database.get_user_security_question(username)
        if exists:
            token = secrets.token_urlsafe(32)
            database.create_reset_token(username, token)
            reset_url = url_for('reset_password', token=token)
            return jsonify({"success": True, "reset_url": reset_url})
        else:
            # Structured so it can easily switch to a generic response
            generic_response = False
            if generic_response:
                return jsonify({"success": True, "message": "If an account is associated with this email, you can continue with password recovery."})
            else:
                return jsonify({"success": False, "message": "No account found with this email."})
            
    return render_template('forgot.html', error=None, success=None)

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    token = request.args.get('token') or request.form.get('token')
    
    # Check rate limit ONLY on POST
    if request.method == 'POST':
        if check_rate_limit(reset_records, request.remote_addr):
            return jsonify({"success": False, "message": "Too many attempts. Please try again later."}), 429
        record_rate_limit_attempt(reset_records, request.remote_addr)
        
    # Validate the token for rendering/checking
    email = database.validate_reset_token(token)
    if not email:
        msg = "This password reset request is invalid or has expired."
        if request.method == 'POST':
            return jsonify({"success": False, "message": msg})
        return render_template('reset.html', error=msg, success=None, token=token, invalid_token=True)

    if request.method == 'POST':
        # Support form data or JSON data
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        if not new_password and request.is_json:
            data = request.json or {}
            new_password = data.get('new_password', '')
            confirm_password = data.get('confirm_password', '')
            
        if not new_password or not confirm_password:
            return jsonify({"success": False, "message": "Please enter all required fields."})
        elif new_password != confirm_password:
            return jsonify({"success": False, "message": "Passwords do not match."})
        elif not validate_password(new_password):
            return jsonify({"success": False, "message": "Password does not meet the required security requirements."})
            
        # Update user password and invalidate the token atomically inside a single transaction
        result = database.perform_atomic_password_reset(token, new_password)
        if not result["success"]:
            return jsonify({"success": False, "message": result["message"]})
        
        return jsonify({"success": True, "message": "Password Reset Successful"})

    return render_template('reset.html', token=token)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    user_id = session['user_id']
    if request.method == 'POST':
        data = request.json or {}
        api_key = data.get('gemini_api_key', '').strip()
        database.update_user_api_key(user_id, api_key)
        return jsonify({"success": True, "message": "Settings saved successfully."})
        
    api_key = database.get_user_api_key(user_id)
    return jsonify({
        "username": session['username'],
        "gemini_api_key": api_key or ""
    })

if __name__ == '__main__':
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        url = "http://127.0.0.1:5000"
        Timer(1.0, lambda: webbrowser.open_new(url)).start()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=True)
