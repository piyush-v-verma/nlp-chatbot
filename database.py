import sqlite3
import os
import json
import bcrypt
import hashlib
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_FILE = 'chatbot.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 0. Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            security_question TEXT NOT NULL,
            security_answer_hash TEXT NOT NULL,
            gemini_api_key TEXT
        )
    ''')
    
    # Schema Migration: drop existing chats/messages if they don't have user_id
    cursor.execute("PRAGMA table_info(chats);")
    cols = cursor.fetchall()
    if cols:
        columns = [col['name'] for col in cols]
        if 'user_id' not in columns:
            cursor.execute("DROP TABLE IF EXISTS messages;")
            cursor.execute("DROP TABLE IF EXISTS chats;")
            
    # 1. Create chats table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # 2. Create messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            detected_intent TEXT NOT NULL,
            nlp_analysis TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
        )
    ''')
    
    # 3. Create Wikipedia Cache table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wiki_cache (
            query TEXT PRIMARY KEY,
            result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 4. Create password_reset_tokens table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def create_chat(chat_id, user_id, title):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chats (id, user_id, title) VALUES (?, ?, ?)",
        (chat_id, user_id, title)
    )
    conn.commit()
    conn.close()

def get_chats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    # Retrieve chats for user_id ordered by latest activity
    cursor.execute('''
        SELECT c.id, c.title, c.created_at, 
               (SELECT m.message FROM messages m WHERE m.chat_id = c.id ORDER BY m.timestamp DESC LIMIT 1) as last_message
        FROM chats c
        WHERE c.user_id = ?
        ORDER BY c.created_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    chats = []
    for row in rows:
        last_msg = row['last_message']
        if last_msg and last_msg.strip().startswith('{') and last_msg.strip().endswith('}'):
            try:
                data = json.loads(last_msg)
                t = data.get('type')
                if t == 'general':
                    last_msg = data['data'].get('response', '')
                elif t == 'translation':
                    last_msg = data['data'].get('translated', '')
                elif t == 'summarize':
                    last_msg = data['data'].get('summary', '')
                elif t == 'wikipedia':
                    last_msg = data['data'].get('extract', '')
                elif t == 'error':
                    last_msg = data['data'].get('error_message', '')
                else:
                    last_msg = data.get('explanation', '')
            except Exception:
                pass
                
        chats.append({
            'id': row['id'],
            'title': row['title'],
            'created_at': row['created_at'],
            'last_message': last_msg
        })
    conn.close()
    return chats

def delete_chat(chat_id, user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    cursor.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
    conn.commit()
    conn.close()

def delete_all_chats(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE chat_id IN (SELECT id FROM chats WHERE user_id = ?)", (user_id,))
    cursor.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_messages(chat_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sender AS role, message AS content, nlp_analysis, timestamp AS created_at 
        FROM messages 
        WHERE chat_id = ? 
        ORDER BY timestamp ASC
    ''', (chat_id,))
    rows = cursor.fetchall()
    messages = []
    for row in rows:
        nlp_data = None
        if row['nlp_analysis']:
            try:
                nlp_data = json.loads(row['nlp_analysis'])
            except ValueError:
                pass
        messages.append({
            'role': row['role'],
            'content': row['content'],
            'nlp_analysis': nlp_data,
            'created_at': row['created_at']
        })
    conn.close()
    return messages

def save_message(chat_id, sender, message, detected_intent, nlp_analysis=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    nlp_json = json.dumps(nlp_analysis) if nlp_analysis is not None else None
    cursor.execute(
        "INSERT INTO messages (chat_id, sender, message, detected_intent, nlp_analysis) VALUES (?, ?, ?, ?, ?)",
        (chat_id, sender, message, detected_intent, nlp_json)
    )
    conn.commit()
    
    # Auto-generate chat title from first user query (up to 30 characters)
    cursor.execute("SELECT COUNT(*) as count FROM messages WHERE chat_id = ?", (chat_id,))
    count = cursor.fetchone()['count']
    if count == 1 and sender == 'user':
        title = message[:30] + '...' if len(message) > 30 else message
        cursor.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))
        conn.commit()
        
    conn.close()

# --- Bcrypt Helper Functions ---
def bcrypt_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def bcrypt_verify(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

# --- User Auth Helpers ---
def register_user(username, password, sec_question, sec_answer):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        pw_hash = bcrypt_hash(password)
        ans_hash = bcrypt_hash(sec_answer.strip().lower())
        cursor.execute('''
            INSERT INTO users (username, password_hash, security_question, security_answer_hash)
            VALUES (?, ?, ?, ?)
        ''', (username.strip(), pw_hash, sec_question.strip(), ans_hash))
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success

def authenticate_user(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username.strip(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    
    pw_hash = row['password_hash']
    # 1. Try to verify with bcrypt
    if bcrypt_verify(password, pw_hash):
        conn.close()
        return row['id']
        
    # 2. Fallback check for Werkzeug/scrypt legacy password
    try:
        if check_password_hash(pw_hash, password):
            # Migrate users to bcrypt hash transparently
            new_hash = bcrypt_hash(password)
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row['id']))
            conn.commit()
            conn.close()
            return row['id']
    except Exception:
        pass
        
    conn.close()
    return None

def get_user_security_question(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT security_question FROM users WHERE username = ?", (username.strip(),))
    row = cursor.fetchone()
    conn.close()
    return row['security_question'] if row else None

def reset_password_with_security(username, sec_answer, new_password):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT security_answer_hash FROM users WHERE username = ?", (username.strip(),))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
        
    ans_hash = row['security_answer_hash']
    is_valid = False
    
    # Try verifying security answer with bcrypt first
    if bcrypt_verify(sec_answer.strip().lower(), ans_hash):
        is_valid = True
    else:
        # Fallback to Werkzeug/scrypt check
        try:
            if check_password_hash(ans_hash, sec_answer.strip().lower()):
                is_valid = True
        except Exception:
            pass
            
    if is_valid:
        new_pw_hash = bcrypt_hash(new_password)
        # Migrate security answer to bcrypt too
        new_ans_hash = bcrypt_hash(sec_answer.strip().lower())
        cursor.execute("UPDATE users SET password_hash = ?, security_answer_hash = ? WHERE username = ?", 
                       (new_pw_hash, new_ans_hash, username.strip()))
        conn.commit()
        success = True
    else:
        success = False
    conn.close()
    return success

# --- Secure Password Reset Token Helpers (SHA-256) ---
def get_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def create_reset_token(email: str, token: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    token_hash = get_token_hash(token)
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(minutes=10)).isoformat()
    cursor.execute('''
        INSERT INTO password_reset_tokens (email, token_hash, expires_at, used)
        VALUES (?, ?, ?, 0)
    ''', (email.strip(), token_hash, expires_at))
    conn.commit()
    conn.close()

def validate_reset_token(token: str) -> str:
    if not token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    token_hash = get_token_hash(token)
    cursor.execute('''
        SELECT email, expires_at FROM password_reset_tokens
        WHERE token_hash = ? AND used = 0
    ''', (token_hash,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
        
    expires_at_str = row['expires_at']
    try:
        if 'T' in expires_at_str:
            expires_at = datetime.datetime.fromisoformat(expires_at_str)
        else:
            expires_at = datetime.datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None
        
    if datetime.datetime.utcnow() > expires_at:
        return None
        
    return row['email']

def invalidate_reset_token(token: str):
    if not token:
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    token_hash = get_token_hash(token)
    cursor.execute('''
        UPDATE password_reset_tokens
        SET used = 1
        WHERE token_hash = ?
    ''', (token_hash,))
    conn.commit()
    conn.close()

def reset_user_password(email: str, new_password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    new_pw_hash = bcrypt_hash(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_pw_hash, email.strip()))
    conn.commit()
    conn.close()

def perform_atomic_password_reset(token: str, new_password: str) -> dict:
    """
    Atomically validates a reset token, updates the associated user's password,
    and invalidates the token in a single SQLite transaction.
    """
    if not token:
        return {"success": False, "message": "This password reset request is invalid or has expired."}
        
    conn = get_db_connection()
    cursor = conn.cursor()
    token_hash = get_token_hash(token)
    now = datetime.datetime.utcnow().isoformat()
    
    try:
        # Start transaction context
        with conn:
            # 1. Update the token to used=1 only if it is unused and not expired
            cursor.execute(
                """
                UPDATE password_reset_tokens
                SET used = 1
                WHERE token_hash = ? AND used = 0 AND expires_at > ?
                """,
                (token_hash, now)
            )
            # Verify exactly one token was consumed
            if cursor.rowcount != 1:
                return {"success": False, "message": "This password reset request is invalid or has expired."}
                
            # 2. Retrieve the email associated with this token hash
            cursor.execute(
                "SELECT email FROM password_reset_tokens WHERE token_hash = ?",
                (token_hash,)
            )
            row = cursor.fetchone()
            if not row:
                raise Exception("Token email not found.") # Triggers rollback
                
            email = row['email']
            
            # 3. Hash the new password with bcrypt
            new_pw_hash = bcrypt_hash(new_password)
            
            # 4. Update the user's password
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (new_pw_hash, email.strip())
            )
            if cursor.rowcount != 1:
                raise Exception("User not found.") # Triggers rollback
                
        return {"success": True, "message": "Password Reset Successful"}
    except Exception as e:
        logging.error(f"Atomic password reset failed: {e}")
        return {"success": False, "message": "Something went wrong. Please try again."}
    finally:
        conn.close()

def update_user_api_key(user_id, api_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET gemini_api_key = ? WHERE id = ?", (api_key.strip() if api_key else None, user_id))
    conn.commit()
    conn.close()

def get_user_api_key(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT gemini_api_key FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['gemini_api_key'] if row else None

# --- Wikipedia Cache Functions ---
def get_wiki_cache(query):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT result FROM wiki_cache WHERE query = ?", (query.strip().lower(),))
    row = cursor.fetchone()
    result = row['result'] if row else None
    conn.close()
    return result

def save_wiki_cache(query, result):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO wiki_cache (query, result) VALUES (?, ?)",
        (query.strip().lower(), result)
    )
    conn.commit()
    conn.close()
