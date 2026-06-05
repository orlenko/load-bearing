import json
from pathlib import Path
from load_bearing.extractors import BaseExtractor
from load_bearing.database import upsert_session, insert_message

class ClaudeExtractor(BaseExtractor):
    def parse_project_name(self, path_parts):
        for part in path_parts:
            if part.startswith("-"):
                clean = part.replace("-", "/")
                return clean.split("/")[-1]
        return "unknown"

    def extract(self, cursor):
        logs_path = Path(self.logs_dir)
        if not logs_path.exists():
            print(f"Warning: Claude logs directory not found at {logs_path}")
            return 0, 0

        print(f"Scanning for Claude projects in {logs_path}...")
        jsonl_files = list(logs_path.glob("**/*.jsonl"))
        total_files = len(jsonl_files)
        print(f"Found {total_files} Claude log files.")

        inserted_sessions = 0
        inserted_messages = 0

        for idx, filepath in enumerate(jsonl_files, 1):
            project_name = self.parse_project_name(filepath.parts)
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if 'assistant' not in line:
                            continue
                            
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        role = data.get("type") or (data.get("message") or {}).get("role")
                        if role != "assistant":
                            continue

                        session_id = data.get("sessionId")
                        if not session_id:
                            continue

                        timestamp = data.get("timestamp")
                        model = (data.get("message") or {}).get("model") or "unknown"
                        content = (data.get("message") or {}).get("content")
                        
                        text_parts = []
                        if isinstance(content, str):
                            text_parts.append(content)
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    val = block.get("text")
                                    if val:
                                        text_parts.append(val)
                        
                        raw_text = "\n".join(text_parts).strip()
                        if not raw_text:
                            continue

                        msg_id = data.get("uuid") or data.get("id") or f"claude_{inserted_messages}"
                        cleaned_text = self.clean_message_text(raw_text)
                        word_count = len(cleaned_text.split())

                        if not cleaned_text:
                            continue

                        # Upsert session
                        upsert_session(cursor, session_id, project_name, "claude", model, timestamp)
                        
                        # Insert message
                        insert_message(cursor, msg_id, session_id, timestamp, raw_text, cleaned_text, word_count)
                        inserted_messages += 1
                        
            except Exception as e:
                print(f"Warning: Failed to process file {filepath}: {e}")
                continue

        # Recount sessions that were successfully created/updated
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE provider='claude'")
        inserted_sessions = cursor.fetchone()[0]

        return inserted_sessions, inserted_messages
