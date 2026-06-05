import os
import sys
import json
import urllib.request
import urllib.error
import re
from pathlib import Path

def get_contexts(cursor, phrase, num_contexts=3):
    search_pattern = "%" + "%".join(phrase.split()) + "%"
    cursor.execute(
        "SELECT cleaned_text FROM messages WHERE cleaned_text LIKE ? LIMIT ?",
        (search_pattern, num_contexts)
    )
    rows = cursor.fetchall()
    
    contexts = []
    for (text,) in rows:
        words = phrase.split()
        # Sentence splitting
        sentences = [s for s in re.split(r'[\.\?\!\;]', text) if s.strip()]
        for sentence in sentences:
            if all(w in sentence.lower() for w in words):
                contexts.append(sentence.strip())
                break
        else:
            contexts.append(text[:200] + "...")
            
    return contexts[:num_contexts]

def call_openai_api(api_key, model, prompt):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a linguistic expert analyzing phrases extracted from AI coding assistant logs. "
                    "Your task is to classify each phrase into one of three classes:\n"
                    "1. 'metaphor': A figure of speech, idiom, or metaphorical expression (e.g., 'load bearing', 'smoking gun', 'shed light', 'blast radius', 'source of truth').\n"
                    "2. 'literal': Used in its literal sense, specifically technical/coding terms, files, variables, code components, or direct instructions (e.g., 'volpe lite', 'unit test', 'in the database', 're-renders', 'pinch zoom').\n"
                    "3. 'boilerplate': Common conversational starters, transitions, or agent fillers (e.g., 'let me read', 'let me confirm', 'rather than', 'as you can see').\n\n"
                    "For each phrase, we provide up to 3 sentence contexts. Use these to determine its predominant usage.\n"
                    "Return a JSON object with a single key 'results' containing an array of objects. Each object must have:\n"
                    "- 'phrase': The input phrase string.\n"
                    "- 'classification': 'metaphor', 'literal', or 'boilerplate'.\n"
                    "- 'category': A 1-3 word description of the semantic domain (e.g., 'Construction', 'Law/Crime', 'Conversational', 'Software Architecture', 'Water/Flow').\n"
                    "- 'explanation': A short, single-sentence explanation of its usage and why it is classified this way."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    
    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode('utf-8'), 
        headers=headers, 
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            content_str = res_data["choices"][0]["message"]["content"]
            return json.loads(content_str)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        raise RuntimeError(f"HTTP Error {e.code}: {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Connection error: {e}")

def verify_candidates(db_conn, candidates_path, output_path, model_name="gpt-5.4-mini"):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Error: OPENAI_API_KEY environment variable is not set.")

    if not Path(candidates_path).exists():
        raise FileNotFoundError(f"Error: {candidates_path} does not exist.")

    with open(candidates_path, 'r', encoding='utf-8') as f:
        candidates = json.load(f)

    cursor = db_conn.cursor()
    enriched_candidates = []
    for c in candidates:
        phrase = c["phrase"]
        contexts = get_contexts(cursor, phrase)
        enriched_candidates.append({
            "phrase": phrase,
            "count": c["count"],
            "contexts": contexts
        })

    batch_size = 30
    results = []

    print(f"Starting classification using model: {model_name}...")
    
    for i in range(0, len(enriched_candidates), batch_size):
        batch = enriched_candidates[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(enriched_candidates) - 1)//batch_size + 1} ({len(batch)} items)...")
        
        prompt_data = [{"phrase": item["phrase"], "contexts": item["contexts"]} for item in batch]
        prompt_str = json.dumps(prompt_data, indent=2)
        
        success = False
        models_to_try = [model_name, "gpt-4o-mini", "gpt-4"]
        unique_models = []
        for m in models_to_try:
            if m not in unique_models:
                unique_models.append(m)
                
        for current_model in unique_models:
            try:
                batch_res = call_openai_api(api_key, current_model, prompt_str)
                batch_results = batch_res.get("results", [])
                
                count_map = {item["phrase"]: item["count"] for item in batch}
                for r in batch_results:
                    phrase = r["phrase"]
                    r["count"] = count_map.get(phrase, 0)
                    results.append(r)
                
                success = True
                break
            except Exception as e:
                print(f"Warning: Failed with model {current_model}: {e}")
                print("Trying next model in fallback chain...")
                
        if not success:
            raise RuntimeError("Error: All models in the fallback chain failed.")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    return results
