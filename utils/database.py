import sqlite3
import json

def update_document_embedding(user_id: str, file_id: str, embedding: list) -> bool:
    """Update embedding for existing document"""
    try:
        with sqlite3.connect('docsapp.db') as conn:
            conn.execute('''
                UPDATE documents 
                SET embedding = ?
                WHERE user_id = ? AND file_id = ?
            ''', (json.dumps(embedding), user_id, file_id))
        return True
    except sqlite3.Error as e:
        print(f"Database error: {str(e)}")
        return False