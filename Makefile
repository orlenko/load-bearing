.PHONY: all install run run-quick clean help

all: help

help:
	@echo "load-bearing: AI Metaphor Discovery & Analysis Tool"
	@echo "==================================================="
	@echo "Available commands:"
	@echo "  make install     - Install the load-bearing CLI package locally (editable mode)"
	@echo "  make run         - Run the complete analysis pipeline (with LLM verify) and open dashboard"
	@echo "  make run-quick   - Run a quick update of trends (skips LLM verify) and open dashboard"
	@echo "  make clean       - Remove local SQLite database and JSON dataset cache files"

install:
	@echo "Installing load-bearing package..."
	pip install -e .
	@echo "Verification: Installation complete! You can now run 'load-bearing --help' anywhere."

run:
	@echo "Running complete analysis pipeline..."
	@if [ -z "$$OPENAI_API_KEY" ]; then \
		echo "\033[0;33mWarning: OPENAI_API_KEY is not set. verify_metaphors step will use default templates.\033[0m"; \
	fi
	load-bearing run --serve

run-quick:
	@echo "Running quick update (skipping LLM)..."
	load-bearing run-quick --serve

clean:
	@echo "Cleaning local SQLite caches and datasets..."
	load-bearing clean
