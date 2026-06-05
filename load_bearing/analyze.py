import json
import sqlite3
import re
from pathlib import Path
from collections import defaultdict
from load_bearing.nlp import load_blacklist

def get_monthly_baselines(conn):
    cursor = conn.cursor()
    # Group by provider and month
    cursor.execute("""
        SELECT 
            s.provider,
            strftime('%Y-%m', m.timestamp) as month,
            COUNT(*) as total_messages,
            SUM(m.word_count) as total_words
        FROM messages m
        JOIN sessions s ON m.session_id = s.id
        WHERE m.timestamp IS NOT NULL
        GROUP BY s.provider, month
        ORDER BY s.provider, month
    """)
    rows = cursor.fetchall()
    
    baselines = defaultdict(dict)
    all_months = set()
    for provider, month, msgs, words in rows:
        if month and provider:
            baselines[provider][month] = {
                "total_messages": msgs,
                "total_words": words or 0
            }
            all_months.add(month)
            
    return baselines, sorted(list(all_months))

def compile_trends(db_conn, metaphors_path, output_path, blacklist_path=None):
    if not Path(metaphors_path).exists():
        raise FileNotFoundError(f"Error: {metaphors_path} does not exist.")

    with open(metaphors_path, 'r', encoding='utf-8') as f:
        verified_items = json.load(f)

    # Filter for metaphors
    metaphors = [item for item in verified_items if item["classification"] == "metaphor"]
    
    # Load and apply blacklist
    blacklist = load_blacklist(blacklist_path)
    print(f"Loaded {len(blacklist)} blacklisted terms for trend compilation.")
    
    filtered_metaphors = []
    for m in metaphors:
        if any(bl in m["phrase"] for bl in blacklist):
            continue
        filtered_metaphors.append(m)
    metaphors = filtered_metaphors
    print(f"Tracking {len(metaphors)} metaphors after blacklist filtering.")

    cursor = db_conn.cursor()
    
    # Get baselines grouped by provider and month
    baselines, months = get_monthly_baselines(db_conn)
    providers = list(baselines.keys())
    
    # Load messages into memory for regex matching
    print("Loading all messages into memory for regex matching...")
    cursor.execute("""
        SELECT 
            m.id, 
            m.session_id, 
            s.project_name, 
            s.provider,
            m.timestamp, 
            m.cleaned_text,
            m.raw_text,
            strftime('%Y-%m', m.timestamp) as month
        FROM messages m
        JOIN sessions s ON m.session_id = s.id
        WHERE m.timestamp IS NOT NULL
    """)
    
    messages = []
    for msg_id, sess_id, proj_name, provider, ts, cleaned, raw, month in cursor.fetchall():
        if month:
            messages.append({
                "id": msg_id,
                "session_id": sess_id,
                "project_name": proj_name,
                "provider": provider,
                "timestamp": ts,
                "cleaned": cleaned,
                "raw": raw,
                "month": month
            })
    print(f"Loaded {len(messages)} messages.")

    trend_dataset = {
        "baselines": baselines,
        "months": months,
        "providers": providers,
        "metaphors": []
    }

    matched_count = 0
    for met in metaphors:
        phrase = met["phrase"]
        
        escaped_phrase = re.escape(phrase)
        regex_pattern = r'\b' + escaped_phrase.replace(r'\ ', r'[- ]') + r'\b'
        
        try:
            rx = re.compile(regex_pattern, re.IGNORECASE)
        except Exception as e:
            print(f"Warning: Failed to compile regex for '{phrase}': {e}")
            continue

        # Count occurrences per provider, per month
        # Structure: counts[provider][month] = count
        monthly_counts = defaultdict(lambda: defaultdict(int))
        examples = []
        total_occurrences = 0

        for msg in messages:
            matches = rx.findall(msg["cleaned"])
            if matches:
                count = len(matches)
                monthly_counts[msg["provider"]][msg["month"]] += count
                total_occurrences += count

                # Extract context sentence
                sentences = re.split(r'[\.\?\!\;]', msg["cleaned"])
                context_sentence = ""
                for s in sentences:
                    if rx.search(s):
                        context_sentence = s.strip()
                        break
                
                # Keep examples (limit to 12 total, balanced across providers if possible)
                if len(examples) < 12:
                    examples.append({
                        "message_id": msg["id"],
                        "session_id": msg["session_id"],
                        "project_name": msg["project_name"],
                        "provider": msg["provider"],
                        "timestamp": msg["timestamp"],
                        "context": context_sentence or (msg["cleaned"][:200] + "..."),
                        "raw_text": msg["raw"]
                    })

        # Calculate normalized trends per provider, per month
        provider_trends = {}
        for prov in providers:
            provider_trends[prov] = {}
            for m in months:
                count = monthly_counts[prov][m]
                # Get total words for this provider in this month
                prov_month_baseline = baselines[prov].get(m, {})
                words = prov_month_baseline.get("total_words", 0)
                
                freq = (count / words) * 10000.0 if words > 0 else 0.0
                provider_trends[prov][m] = {
                    "count": count,
                    "frequency": round(freq, 3)
                }

        if total_occurrences > 0:
            trend_dataset["metaphors"].append({
                "phrase": phrase,
                "category": met["category"],
                "explanation": met["explanation"],
                "total_count": total_occurrences,
                "provider_trends": provider_trends,
                "examples": examples
            })
            matched_count += 1

    trend_dataset["metaphors"].sort(key=lambda x: x["total_count"], reverse=True)

    # Save to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(trend_dataset, f, indent=2)

    # Save to JS for CORS-free file:// protocol loading
    js_path = Path(output_path).with_suffix(".js")
    with open(js_path, 'w', encoding='utf-8') as f:
        f.write("const TREND_DATA = ")
        json.dump(trend_dataset, f, indent=2)
        f.write(";\n")

    return matched_count
