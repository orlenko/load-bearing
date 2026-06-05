from abc import ABC, abstractmethod
import re

class BaseExtractor(ABC):
    def __init__(self, logs_dir):
        self.logs_dir = logs_dir

    @abstractmethod
    def extract(self, cursor):
        """
        Extract sessions and messages from logs_dir and save them via cursor.
        """
        pass

    # Shared text cleaning utilities
    @staticmethod
    def clean_message_text(text):
        if not text:
            return ""
        # Strip markdown code blocks
        text = re.sub(r'```.*?```', ' ', text, flags=re.DOTALL)
        # Strip inline code
        text = re.sub(r'`[^`\n]+`', ' ', text)
        # Strip URLs
        text = re.sub(r'https?://\S+', ' ', text)
        # Strip file paths
        text = re.sub(r'(?:/[a-zA-Z0-9_\-\.]+)+', ' ', text)
        # Strip hex hashes and IDs
        text = re.sub(r'\b[0-9a-fA-F]{8,64}\b', ' ', text)
        # Strip markdown specific punctuation but preserve text & sentence markers
        text = re.sub(r'[^\w\s\.\?\!\-\']', ' ', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
