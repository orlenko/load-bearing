import os
import sys
import json
import argparse
import sqlite3
import http.server
import socketserver
import webbrowser
from pathlib import Path
from load_bearing.database import get_db_connection
from load_bearing.nlp import mine_candidates
from load_bearing.verify import verify_candidates
from load_bearing.analyze import compile_trends

DEFAULT_DB = "messages.db"
DEFAULT_CANDIDATES = "candidates.json"
DEFAULT_METAPHOR_OUTPUT = "verified_metaphors.json"
DEFAULT_TRENDS_OUTPUT = "trends.json"
DEFAULT_CODEX_LOGS = str(Path.home() / ".codex" / "sessions")

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, pkg_dir=None, **kwargs):
        self.pkg_dir = Path(pkg_dir)
        # Initialize without directory argument for standard Handler
        super().__init__(*args, **kwargs)
        
    def do_GET(self):
        if self.path in ["/", "/index.html"]:
            dashboard_path = self.pkg_dir / "dashboard" / "dashboard.html"
            if dashboard_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                with open(dashboard_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(500, "Dashboard template not found in package.")
        elif self.path in ["/trends.js", "/trends.json"]:
            filename = self.path.lstrip("/")
            local_file = Path(os.getcwd()) / filename
            if local_file.exists():
                self.send_response(200)
                content_type = "application/javascript" if "js" in self.path else "application/json"
                self.send_header("Content-Type", content_type)
                self.end_headers()
                with open(local_file, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(200)
                content_type = "application/javascript" if "js" in self.path else "application/json"
                self.send_header("Content-Type", content_type)
                self.end_headers()
                # Return empty fallback
                if "js" in self.path:
                    self.wfile.write(b"const TREND_DATA = {baseline:{},months:[],metaphors:[]};")
                else:
                    self.wfile.write(b"{}")
        else:
            self.send_error(404, "Not found")

    def log_message(self, format, *args):
        # Suppress logging spam in CLI
        pass

def serve_dashboard(port=8080):
    pkg_dir = Path(__file__).parent
    
    # Custom handler factory to pass pkg_dir
    def handler_factory(*args, **kwargs):
        return DashboardHandler(*args, pkg_dir=pkg_dir, **kwargs)
        
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", port), handler_factory) as httpd:
            url = f"http://localhost:{port}"
            print(f"Serving dashboard at {url} ...")
            print("Press Ctrl+C to stop the server.")
            webbrowser.open(url)
            httpd.serve_forever()
    except OSError as e:
        print(f"Error starting server on port {port}: {e}")
        print("Try specifying a different port using --port.")

def run_extraction(provider, logs_dir, db_path):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    if provider == "claude":
        from load_bearing.extractors.claude import ClaudeExtractor
        extractor = ClaudeExtractor(logs_dir)
    elif provider == "gemini":
        from load_bearing.extractors.gemini import GeminiExtractor
        extractor = GeminiExtractor(logs_dir)
    elif provider == "codex":
        from load_bearing.extractors.codex import CodexExtractor
        extractor = CodexExtractor(logs_dir)
    else:
        print(f"Error: Unknown provider '{provider}'")
        conn.close()
        return

    sessions, messages = extractor.extract(cursor)
    conn.commit()
    conn.close()
    
    print(f"\nExtraction for '{provider}' complete.")
    print(f"SQLite DB: {db_path}")
    print(f"Sessions indexed: {sessions}")
    print(f"Messages indexed: {messages}")

def run_pipeline(args, run_llm=True):
    db_path = args.db
    
    # 1. Extract Claude (default path)
    claude_logs = args.claude_logs or str(Path.home() / ".claude" / "projects")
    if Path(claude_logs).exists():
        run_extraction("claude", claude_logs, db_path)
    
    # 2. Extract Gemini (default path)
    gemini_logs = args.gemini_logs or str(Path.home() / ".gemini" / "antigravity" / "brain")
    if Path(gemini_logs).exists():
        run_extraction("gemini", gemini_logs, db_path)

    # 3. Extract Codex (default path)
    codex_logs = args.codex_logs or str(Path.home() / ".codex" / "sessions")
    if Path(codex_logs).exists():
        run_extraction("codex", codex_logs, db_path)

    # Check if we actually indexed messages
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM messages")
    count = cursor.fetchone()[0]
    conn.close()
    
    if count == 0:
        print("Error: No messages found in logs. Check log directories.")
        return

    # 3. Mine candidates
    print("\nMining phrase candidates...")
    conn = get_db_connection(db_path)
    total_cand, top_cand = mine_candidates(
        conn, 
        DEFAULT_CANDIDATES, 
        min_freq=4, 
        max_candidates=300, 
        blacklist_path=args.blacklist
    )
    conn.close()

    # 4. Verify metaphors (with LLM)
    if run_llm:
        print("\nVerifying metaphors with LLM...")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("\033[0;33mWarning: OPENAI_API_KEY environment variable is not set. Skipping LLM verification.\033[0m")
            run_llm = False
        else:
            conn = get_db_connection(db_path)
            try:
                verify_candidates(conn, DEFAULT_CANDIDATES, DEFAULT_METAPHOR_OUTPUT, args.model)
            except Exception as e:
                print(f"\033[0;31mError during LLM verification: {e}\033[0m")
                print("Falling back to existing verified list if present...")
            conn.close()

    # If verify was skipped or failed, check if we have an existing verified file
    if not run_llm and not Path(DEFAULT_METAPHOR_OUTPUT).exists():
        # Write empty template with just load-bearing and smoking gun to avoid empty states
        print("Creating default verified metaphor templates...")
        defaults = [
            {"phrase": "load bearing", "classification": "metaphor", "category": "Architecture", "explanation": "Structural metaphor."},
            {"phrase": "smoking gun", "classification": "metaphor", "category": "Law/Crime", "explanation": "Conclusive evidence metaphor."}
        ]
        with open(DEFAULT_METAPHOR_OUTPUT, 'w') as f:
            json.dump(defaults, f, indent=2)

    # 5. Compile trends
    print("\nCompiling trend datasets...")
    conn = get_db_connection(db_path)
    compile_trends(conn, DEFAULT_METAPHOR_OUTPUT, DEFAULT_TRENDS_OUTPUT, args.blacklist)
    conn.close()
    
    print("\n\033[0;32mPipeline Run Complete!\033[0m")
    if args.serve:
        serve_dashboard(args.port)

def main():
    parser = argparse.ArgumentParser(
        description="load-bearing: Discover and track overused metaphorical language in AI coding logs."
    )
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Command: run (full pipeline)
    run_parser = subparsers.add_parser("run", help="Run the complete analysis pipeline (with LLM verify)")
    run_parser.add_argument("--db", type=str, default=DEFAULT_DB, help="SQLite database path")
    run_parser.add_argument("--claude-logs", type=str, help="Claude projects directory path")
    run_parser.add_argument("--gemini-logs", type=str, help="Gemini logs directory path")
    run_parser.add_argument("--codex-logs", type=str, help="Codex sessions directory path")
    run_parser.add_argument("--model", type=str, default="gpt-5.4-mini", help="OpenAI model for verify")
    run_parser.add_argument("--blacklist", type=str, default="blacklist.txt", help="Blacklist file path")
    run_parser.add_argument("--serve", action="store_true", help="Start dashboard server after run")
    run_parser.add_argument("--port", type=int, default=8080, help="Dashboard port")

    # Command: run-quick (skips LLM)
    quick_parser = subparsers.add_parser("run-quick", help="Run a quick update of trends (skips LLM verify)")
    quick_parser.add_argument("--db", type=str, default=DEFAULT_DB, help="SQLite database path")
    quick_parser.add_argument("--claude-logs", type=str, help="Claude projects directory path")
    quick_parser.add_argument("--gemini-logs", type=str, help="Gemini logs directory path")
    quick_parser.add_argument("--codex-logs", type=str, help="Codex sessions directory path")
    quick_parser.add_argument("--blacklist", type=str, default="blacklist.txt", help="Blacklist file path")
    quick_parser.add_argument("--serve", action="store_true", help="Start dashboard server after run")
    quick_parser.add_argument("--port", type=int, default=8080, help="Dashboard port")

    # Command: extract
    ext_parser = subparsers.add_parser("extract", help="Extract logs from a specific provider")
    ext_parser.add_argument("--provider", type=str, required=True, choices=["claude", "gemini", "codex"], help="Log provider")
    ext_parser.add_argument("--logs-dir", type=str, required=True, help="Logs directory path")
    ext_parser.add_argument("--db", type=str, default=DEFAULT_DB, help="SQLite database path")

    # Command: dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Start the interactive dashboard web server")
    dash_parser.add_argument("--port", type=int, default=8080, help="Server port")

    # Command: clean
    subparsers.add_parser("clean", help="Remove local cache database and JSON/JS dataset files")

    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(args, run_llm=True)
    elif args.command == "run-quick":
        run_pipeline(args, run_llm=False)
    elif args.command == "extract":
        run_extraction(args.provider, args.logs_dir, args.db)
    elif args.command == "dashboard":
        serve_dashboard(args.port)
    elif args.command == "clean":
        files_to_remove = [DEFAULT_DB, DEFAULT_CANDIDATES, DEFAULT_METAPHOR_OUTPUT, DEFAULT_TRENDS_OUTPUT, "trends.js"]
        for f in files_to_remove:
            path = Path(f)
            if path.exists():
                path.unlink()
                print(f"Removed: {f}")
        print("Clean complete.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
