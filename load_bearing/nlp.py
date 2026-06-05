import re
import json
import sqlite3
from pathlib import Path
from collections import Counter

# Standard English stop words
STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'if', 'because', 'as', 'of', 'at', 'by', 'for', 'with', 
    'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 
    'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 
    'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 
    'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 
    'very', 's', 't', 'can', 'will', 'just', 'should', 'now', 'i', 'me', 'my', 'myself', 'we', 'our', 
    'ours', 'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 
    'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 
    'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 
    'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 
    'would', 'could', 'should', 'ought', 'must', 'us', 'them', 'say', 'says', 'said', 'go', 'goes', 'went',
    "let's", 'let', 'look', 'take', 'see', 'want', 'need', 'make', 'use', 'get', 'set', 'add', 
    'find', 'check', 'verify', 'show', 'here is', 'here\'s', 'we can', 'we should', 'we need', 'you can', 
    'as you', 'please', 'thank', 'thanks', 'sorry', 'apologize', 'sure', 'ok', 'okay', 'yes', 'no',
    'the first', 'the second', 'the third', 'in this', 'in order', 'order to', 'take a', 'look at', 
    'as well', 'well as', 'you can see', 'we can see', 'seem', 'seems', 'like', 'looks', 'looks like', 
    'seems to', 'need to', 'want to', 'try to', 'let\'s take', 'take a look', 'a look at', 'the following', 
    'in the', 'on the', 'at the', 'to the', 'for the', 'with the', 'of the', 'is a', 'this is', 'it is', 
    'there is', 'there are', 'one of', 'some of', 'part of', 'out of', 'into the', 'up to', 'down to',
    'would be', 'should be', 'can be', 'will be', 'could be', 'has been', 'have been', 'had been', 
    'is the', 'are the', 'was the', 'were the', 'in a', 'on a', 'at a', 'to a', 'for a', 'with a',
    'i will', 'i\'ll', 'we will', 'we\'ll', 'you will', 'you\'ll', 'it will', 'it\'ll', 'they will'
}

# Programming terms to exclude from candidate lists
CODING_WORDS = {
    'code', 'file', 'files', 'line', 'lines', 'block', 'blocks', 'variable', 'variables', 'function', 
    'functions', 'method', 'methods', 'class', 'classes', 'object', 'objects', 'array', 'arrays', 
    'list', 'lists', 'string', 'strings', 'number', 'numbers', 'boolean', 'booleans', 'null', 'undefined',
    'import', 'imports', 'export', 'exports', 'require', 'const', 'let', 'var', 'def', 'fn', 'func', 
    'return', 'returns', 'if', 'else', 'for', 'while', 'switch', 'case', 'break', 'continue', 'try', 
    'catch', 'finally', 'throw', 'error', 'errors', 'exception', 'exceptions', 'bug', 'bugs', 'fix', 
    'fixes', 'fixed', 'issue', 'issues', 'test', 'tests', 'testing', 'run', 'runs', 'running', 'command', 
    'commands', 'terminal', 'shell', 'bash', 'sh', 'script', 'scripts', 'git', 'commit', 'commits', 
    'push', 'pull', 'merge', 'branch', 'branches', 'diff', 'diffs', 'patch', 'patches', 'repo', 
    'repos', 'repository', 'repositories', 'project', 'projects', 'workspace', 'workspaces', 'directory', 
    'directories', 'folder', 'folders', 'path', 'paths', 'url', 'urls', 'http', 'https', 'api', 'apis', 
    'json', 'xml', 'yaml', 'yml', 'config', 'configs', 'configuration', 'npm', 'package', 'packages', 
    'dependency', 'dependencies', 'module', 'modules', 'database', 'databases', 'db', 'dbs', 'sql', 
    'query', 'queries', 'table', 'tables', 'column', 'columns', 'row', 'rows', 'select', 'insert', 
    'update', 'delete', 'where', 'index', 'indexes', 'key', 'keys', 'value', 'values', 'server', 
    'servers', 'client', 'clients', 'host', 'hosts', 'port', 'ports', 'connection', 'connections', 
    'connect', 'connected', 'disconnect', 'app', 'apps', 'application', 'applications', 'framework', 
    'library', 'libraries', 'tool', 'tools', 'build', 'builds', 'compile', 'compiles', 'compiled', 
    'deploy', 'deploys', 'deployment', 'deployments', 'dev', 'prod', 'staging', 'local', 'environment', 
    'environments', 'log', 'logs', 'logging', 'output', 'input', 'data', 'user', 'users', 'admin', 
    'mock', 'mocks', 'stub', 'stubs', 'fake', 'fakes', 'dummy', 'temp', 'tmp', 'cache', 'caches', 
    'token', 'tokens', 'auth', 'authentication', 'authorization', 'login', 'logout', 'signin', 
    'signout', 'register', 'signup', 'password', 'email', 'name', 'names', 'id', 'ids', 'uuid', 
    'status', 'state', 'states', 'result', 'results', 'response', 'responses', 'request', 'requests', 
    'header', 'headers', 'body', 'params', 'parameters', 'parameter', 'argument', 'arguments', 
    'type', 'types', 'model', 'models', 'schema', 'schemas', 'field', 'fields', 'event', 'events', 
    'handler', 'handlers', 'callback', 'callbacks', 'promise', 'promises', 'async', 'await', 
    'thread', 'threads', 'process', 'processes', 'task', 'tasks', 'job', 'jobs', 'queue', 'queues'
}

ALL_EXCLUDE = STOP_WORDS.union(CODING_WORDS)

def get_sentences(text):
    return [s.strip() for s in re.split(r'[\.\?\!\;]', text) if s.strip()]

def get_words(sentence):
    sentence = sentence.replace('-', ' ')
    return re.findall(r"\b[a-zA-Z']+\b", sentence.lower())

def generate_ngrams(words, n):
    ngrams = []
    for i in range(len(words) - n + 1):
        ngrams.append(tuple(words[i:i+n]))
    return ngrams

def is_valid_candidate(ngram_words):
    if all(w in ALL_EXCLUDE for w in ngram_words):
        return False
    if not any(w not in ALL_EXCLUDE for w in ngram_words):
        return False

    weak_stopwords = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'as', 'from', 'this', 'that', 'it', 'is', 'are', 'was', 'were'}
    if ngram_words[0] in weak_stopwords or ngram_words[-1] in weak_stopwords:
        return False

    pronouns = {'i', 'we', 'you', 'he', 'she', 'they', 'my', 'our', 'your', 'his', 'her', 'their', 'me', 'us', 'him', 'them'}
    if ngram_words[0] in pronouns:
        return False

    tech_count = sum(1 for w in ngram_words if w in CODING_WORDS)
    if tech_count >= len(ngram_words) - 1:
        return False

    return True

def load_blacklist(custom_path=None):
    blacklist = set()
    # 1. Load default packaged blacklist
    pkg_blacklist = Path(__file__).parent / "blacklist.txt"
    if pkg_blacklist.exists():
        with open(pkg_blacklist, 'r', encoding='utf-8') as f:
            for line in f:
                val = line.strip().lower()
                if val:
                    blacklist.add(val)

    # 2. Load custom / local workspace blacklist
    local_path = Path(custom_path or "blacklist.txt")
    if local_path.exists() and local_path.resolve() != pkg_blacklist.resolve():
        with open(local_path, 'r', encoding='utf-8') as f:
            for line in f:
                val = line.strip().lower()
                if val:
                    blacklist.add(val)
                    
    return blacklist

def mine_candidates(db_conn, output_path, min_freq=4, max_candidates=300, blacklist_path=None):
    cursor = db_conn.cursor()
    cursor.execute("SELECT cleaned_text FROM messages")
    rows = cursor.fetchall()

    ngram_counts = Counter()
    for (text,) in rows:
        if not text:
            continue
        for sentence in get_sentences(text):
            words = get_words(sentence)
            if len(words) < 2:
                continue
            for n in range(2, 6):
                for ngram in generate_ngrams(words, n):
                    if is_valid_candidate(ngram):
                        ngram_counts[ngram] += 1

    blacklist = load_blacklist(blacklist_path)
    print(f"Loaded {len(blacklist)} blacklisted terms.")

    candidates = []
    for ngram, count in ngram_counts.items():
        if count >= min_freq:
            phrase = " ".join(ngram)
            if any(bl in phrase for bl in blacklist):
                continue
            candidates.append({"phrase": phrase, "count": count, "length": len(ngram)})

    candidates.sort(key=lambda x: x["count"], reverse=True)
    top_candidates = candidates[:max_candidates]

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(top_candidates, f, indent=2)

    return len(candidates), top_candidates
