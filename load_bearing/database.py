import sqlite3
from pathlib import Path

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    setup_database(conn)
    return conn

def setup_database(db_conn):
    cursor = db_conn.cursor()
    
    # Create sessions table with provider column
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            project_name TEXT,
            provider TEXT,
            model TEXT,
            timestamp TEXT
        )
    """)
    
    # Create messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            timestamp TEXT,
            raw_text TEXT,
            cleaned_text TEXT,
            word_count INTEGER,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    """)
    
    # Create indexes for fast queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
    db_conn.commit()

def upsert_session(cursor, session_id, project_name, provider, model, timestamp):
    cursor.execute("""
        INSERT INTO sessions (id, project_name, provider, model, timestamp)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            timestamp = MIN(timestamp, excluded.timestamp),
            model = CASE WHEN model == 'unknown' THEN excluded.model ELSE model END
    """, (session_id, project_name, provider, model, timestamp))

def insert_message(cursor, msg_id, session_id, timestamp, raw_text, cleaned_text, word_count):
    cursor.execute("""
        INSERT INTO messages (id, session_id, timestamp, raw_text, cleaned_text, word_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO NOTHING
    """, (msg_id, session_id, timestamp, raw_text, cleaned_text, word_count))
