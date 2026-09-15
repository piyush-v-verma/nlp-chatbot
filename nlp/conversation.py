import json
import database

class ConversationManager:
    """
    Manages chat session context history.
    Retrieves the last 5 messages from SQLite dynamically to ensure persistence.
    """
    
    @staticmethod
    def get_context(chat_id, limit=5):
        """Retrieves the last N messages of the chat session."""
        if not chat_id:
            return []
        try:
            return database.get_messages(chat_id)[-limit:]
        except Exception as e:
            print(f"ConversationManager error: {e}")
            return []

    @staticmethod
    def get_context_text(chat_id, limit=5, role_filter='user'):
        """Combines the text of the last N messages into a single block."""
        history = ConversationManager.get_context(chat_id, limit)
        texts = []
        for msg in history:
            if role_filter is None or msg['role'] == role_filter:
                content = msg['content']
                # Check if it is a JSON response
                if content.strip().startswith('{') and content.strip().endswith('}'):
                    try:
                        data = json.loads(content)
                        # Extract the meaningful text content depending on intent type
                        if data.get('type') == 'general':
                            texts.append(data['data'].get('response', ''))
                        elif data.get('type') == 'summarize':
                            texts.append(data['data'].get('summary', ''))
                        elif data.get('type') == 'wikipedia':
                            texts.append(data['data'].get('extract', ''))
                    except Exception:
                        texts.append(content)
                else:
                    texts.append(content)
        return " ".join([t for t in texts if t])

    @staticmethod
    def get_last_assistant_message(chat_id):
        """Finds and returns the text content of the last assistant message (unwrapped from JSON)."""
        history = ConversationManager.get_context(chat_id, 10)
        for msg in reversed(history):
            if msg['role'] == 'assistant':
                content = msg['content']
                if content.strip().startswith('{') and content.strip().endswith('}'):
                    try:
                        data = json.loads(content)
                        # Unpack depending on response type
                        t = data.get('type')
                        if t == 'translation':
                            return data['data'].get('translated', '')
                        elif t == 'general':
                            return data['data'].get('response', '')
                        elif t == 'wikipedia':
                            return data['data'].get('extract', '')
                        elif t == 'summarize':
                            return data['data'].get('summary', '')
                    except Exception:
                        pass
                return content
        return ""
