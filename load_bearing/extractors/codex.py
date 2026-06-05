import json
import sqlite3
from pathlib import Path
from load_bearing.extractors import BaseExtractor
from load_bearing.database import upsert_session, insert_message

class CodexExtractor(BaseExtractor):
    def find_state_db(self, codex_dir):
        # Look for state_*.sqlite databases in the .codex folder (usually state_5.sqlite)
        db_files = list(codex_dir.glob("state_*.sqlite"))
        if not db_files:
            return None
        # Sort to get the highest numbered state database (e.g. state_5 over state_1)
        db_files.sort(key=lambda x: x.name, reverse=True)
        return db_files[0]

    def extract(self, cursor):
        logs_path = Path(self.logs_dir)
        if not logs_path.exists():
            print(f"Warning: Codex logs directory not found at {logs_path}")
            return 0, 0

        codex_dir = logs_path.parent
        state_db = self.find_state_db(codex_dir)
        
        # Load thread metadata from Codex SQLite if available
        thread_metadata = {}
        if state_db and state_db.exists():
            print(f"Reading Codex thread metadata from state DB {state_db}...")
            try:
                conn = sqlite3.connect(state_db)
                db_cursor = conn.cursor()
                # Query threads table
                db_cursor.execute("SELECT id, model, cwd FROM threads")
                for thread_id, model, cwd in db_cursor.fetchall():
                    thread_metadata[thread_id] = {
                        "model": model or "openai-codex",
                        "project_name": Path(cwd).name if cwd else "unknown"
                    }
                conn.close()
                print(f"Loaded metadata for {len(thread_metadata)} Codex threads.")
            except Exception as e:
                print(f"Warning: Could not read Codex state database: {e}")

        print(f"Scanning for Codex sessions in {logs_path}...")
        jsonl_files = list(logs_path.glob("**/rollout-*.jsonl"))
        total_files = len(jsonl_files)
        print(f"Found {total_files} Codex session files.")

        inserted_sessions = 0
        inserted_messages = 0

        for idx, filepath in enumerate(jsonl_files, 1):
            # Extract session ID from rollout filename: rollout-YYYY-MM-DDTHH-MM-SS-<session_id>.jsonl
            # The session ID is the last group before extension
            try:
                session_id = filepath.name.split("-")[-1].replace(".jsonl", "")
            except Exception:
                session_id = filepath.stem

            # Get metadata from DB if we have it, else fallbacks
            meta = thread_metadata.get(session_id, {"model": "openai-codex", "project_name": "unknown"})
            project_name = meta["project_name"]
            model = meta["model"]

            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if 'response_item' not in line:
                            continue
                            
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Filter for assistant response items
                        if data.get("type") != "response_item":
                            continue
                        
                        payload = data.get("payload") or {}
                        role = payload.get("role")
                        if role != "assistant":
                            continue

                        # Extract text blocks
                        content = payload.get("content") or []
                        text_parts = []
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "output_text":
                                    val = block.get("text")
                                    if val:
                                        text_parts.append(val)
                        
                        raw_text = "\n".join(text_parts).strip()
                        if not raw_text:
                            continue

                        timestamp = data.get("timestamp")
                        # Combine timestamp and session for unique message ID
                        msg_id = f"codex_{session_id}_{timestamp}"
                        
                        cleaned_text = self.clean_message_text(raw_text)
                        word_count = len(cleaned_text.split())

                        if not cleaned_text:
                            continue

                        # Extract project name from user input context if db didn't have it
                        if project_name == "unknown":
                            # We will search the database's user messages later or fallback
                            pass

                        # Upsert session
                        upsert_session(cursor, session_id, project_name, "codex", model, timestamp)
                        
                        # Insert message
                        insert_message(cursor, msg_id, session_id, timestamp, raw_text, cleaned_text, word_count)
                        inserted_messages += 1
                        
            except Exception as e:
                print(f"Warning: Failed to process file {filepath}: {e}")
                continue

        # Recount sessions that were successfully created/updated
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE provider='codex'")
        inserted_sessions = cursor.fetchone()[0]

        return inserted_sessions, inserted_messages
