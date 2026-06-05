import json
from pathlib import Path
from load_bearing.extractors import BaseExtractor
from load_bearing.database import upsert_session, insert_message

class GeminiExtractor(BaseExtractor):
    def extract(self, cursor):
        logs_path = Path(self.logs_dir)
        if not logs_path.exists():
            print(f"Warning: Gemini logs directory not found at {logs_path}")
            return 0, 0

        print(f"Scanning for Gemini logs in {logs_path}...")
        
        # Files are at logs_path / <session-id> / .system_generated / logs / transcript.jsonl
        transcript_files = list(logs_path.glob("**/transcript.jsonl"))
        total_files = len(transcript_files)
        print(f"Found {total_files} Gemini log files.")

        inserted_sessions = 0
        inserted_messages = 0

        for idx, filepath in enumerate(transcript_files, 1):
            # Session ID is the UUID directory name (4 levels up from the file)
            # e.g., .../brain/<session-id>/.system_generated/logs/transcript.jsonl
            try:
                session_id = filepath.parts[-4]
            except IndexError:
                session_id = filepath.parent.name
                
            project_name = "unknown"
            model = "gemini-3.5-flash" # Default fallback
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # Extract project name from the first user request cwd
                        if "cwd" in data and project_name == "unknown":
                            cwd = data.get("cwd") or ""
                            if cwd:
                                project_name = Path(cwd).name

                        # Extract model settings change if present
                        if "User changed setting `Model Selection`" in (data.get("content") or ""):
                            # Try to extract model name
                            content = data.get("content")
                            if "to" in content:
                                model = content.split("to")[-1].strip().replace(".", "")

                        # Filter for model user-facing responses
                        source = data.get("source")
                        step_type = data.get("type")
                        
                        # We want planner response or final responses that contain content
                        if source != "MODEL":
                            continue
                            
                        # Standard user-facing output is usually inside PLANNER_RESPONSE
                        # or other steps that don't invoke tool calls
                        if step_type not in ["PLANNER_RESPONSE", "GENERIC"]:
                            continue

                        raw_text = data.get("content")
                        if not raw_text or not isinstance(raw_text, str):
                            continue

                        timestamp = data.get("created_at")
                        msg_id = f"gemini_{session_id}_{data.get('step_index')}"
                        cleaned_text = self.clean_message_text(raw_text)
                        word_count = len(cleaned_text.split())

                        if not cleaned_text:
                            continue

                        # Upsert session
                        upsert_session(cursor, session_id, project_name, "gemini", model, timestamp)
                        
                        # Insert message
                        insert_message(cursor, msg_id, session_id, timestamp, raw_text, cleaned_text, word_count)
                        inserted_messages += 1
                        
            except Exception as e:
                print(f"Warning: Failed to process file {filepath}: {e}")
                continue

        # Recount sessions that were successfully created/updated
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE provider='gemini'")
        inserted_sessions = cursor.fetchone()[0]

        return inserted_sessions, inserted_messages
