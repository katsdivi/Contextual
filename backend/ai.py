import json
import re
import time
import threading
import ollama
from datetime import datetime, timedelta
import dateutil.parser  # Safe date parsing

MODEL = "qwen2.5-coder:3b"

# ----------------------------
# Intent Cache (Thread-safe)
# ----------------------------
_INTENT_CACHE = {}
_INTENT_CACHE_LOCK = threading.Lock()
_INTENT_CACHE_TTL_SEC = 120  # 2 minutes

def _cache_get(key: str):
    now = time.time()
    with _INTENT_CACHE_LOCK:
        item = _INTENT_CACHE.get(key)
        if not item:
            return None
        value, expires = item
        if now > expires:
            _INTENT_CACHE.pop(key, None)
            return None
        return value

def _cache_set(key: str, value: str):
    with _INTENT_CACHE_LOCK:
        _INTENT_CACHE[key] = (value, time.time() + _INTENT_CACHE_TTL_SEC)

def clean_string(s):
    if not s:
        return ""
    return re.sub(r"[^\w\s]", " ", s).strip()

# ----------------------------
# Deterministic fast-path rules
# ----------------------------
def _rule_based_intent(user_query: str) -> str | None:
    q = (user_query or "").strip().lower()

    # files from 2024  -> year-wide filter (do NOT allow day/month invention)
    m = re.search(r"\bfiles\s+from\s+(20\d{2})\b", q)
    if m:
        y = m.group(1)
        return f'(created_str:"{y}" OR modified_str:"{y}")'

    # files in 2024
    m = re.search(r"\bfiles\s+in\s+(20\d{2})\b", q)
    if m:
        y = m.group(1)
        return f'(created_str:"{y}" OR modified_str:"{y}")'

    # budget files -> keyword “budget” (single token, prioritize path/ext too)
    if q in ("budget files", "budget file"):
        return '(path:budget* OR content:budget OR summary:budget OR ext:csv OR ext:md)'

    return None

# ----------------------------
# AI functions
# ----------------------------
def generate_summary(text_content):
    try:
        truncated_text = text_content[:4000]
        prompt = f"""
Analyze the following text and provide a specific, high-density summary.

RULES:
1. IF IT IS CODE/CONFIG: Identify the project name, key tech stack (versions), and the specific logic implemented.
2. IF IT IS PROSE/TEXT: Identify the core subject, key characters/entities, and the narrative arc or purpose.

Output a single paragraph (max 50 words). Be direct.

--- CONTENT START ---
{truncated_text}
--- CONTENT END ---
"""
        response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"].strip()
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return "Analysis failed."

def refine_summary(current_summary, user_instruction):
    try:
        prompt = f"""
You are a text editor. Update the following summary based on the user's instruction.
Keep the tone professional. Output ONLY the new summary.

--- CURRENT SUMMARY ---
{current_summary}

--- USER INSTRUCTION ---
{user_instruction}
"""
        response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"].strip()
    except Exception as e:
        return f"Error refining: {e}"

def detect_tech_stack(content):
    prompt = f"""
Identify the programming language, data format (e.g., JSON, YAML, Markdown),
or software frameworks used in this file.

Output ONLY the specific names (comma separated).
Example: "TypeScript, React, JSON"
If it is standard prose/text with no code, say "Plain Text".

--- CONTENT ---
{content[:2000]}
"""
    try:
        response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"].strip()
    except Exception:
        return "Unknown"

def analyze_search_context(content, query):
    prompt = f"""
The user searched for the term: "{query}".
Explain specifically HOW and WHERE this term is used in the file below.
Give context (e.g., "It is a variable in the auth function" or "It is a character name").
Keep it to 1 sentence.

--- CONTENT ---
{content[:3000]}
"""
    try:
        response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"].strip()
    except Exception:
        return "Context analysis failed."

# ----------------------------
# Robust intent parse
# ----------------------------
def parse_search_intent(user_query):
    normalized = clean_string((user_query or "").lower())
    cached = _cache_get(normalized)
    if cached is not None:
        return cached

    # 0) Rule-based fast path (removes flakiness for core patterns)
    ruled = _rule_based_intent(user_query)
    if ruled:
        _cache_set(normalized, ruled)
        return ruled

    today = datetime.now()
    date_context = today.strftime("%Y-%m-%d")

    prompt = f"""
You are a Search Intent Parser.
CONTEXT: Today is {date_context}.

Return ONLY valid JSON (double quotes, no trailing commas). No markdown fences.

JSON SCHEMA:
{{
  "date_filter": "string or null",
  "tech_filter": "string or null",
  "keywords": "string or null"
}}

User Query: "{user_query}"
"""

    try:
        response = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}])
        result = (response["message"]["content"] or "").strip()

        # Strip code fences if model ignores instruction
        clean_result = result.replace("```json", "").replace("```", "").strip()

        # Try strict JSON extraction first
        match = re.search(r"\{.*\}", clean_result, re.DOTALL)
        if match:
            blob = match.group(0)
            try:
                data = json.loads(blob)
                final = build_fts_query(data, user_query)
                if not final:
                    final = clean_string(user_query)
                _cache_set(normalized, final)
                return final
            except Exception:
                # 1) JSON repair fallback: extract fields via regex
                # Handles outputs like: {date_filter: 2024, tech_filter: null, keywords: "budget"}
                repaired = _regex_extract_intent(clean_result)
                final = build_fts_query(repaired, user_query)
                if not final:
                    final = clean_string(user_query)
                _cache_set(normalized, final)
                return final

        fallback = clean_string(user_query)
        _cache_set(normalized, fallback)
        return fallback

    except Exception as e:
        print(f"⚠️ Intent Error: {e}")
        fallback = clean_string(user_query)
        _cache_set(normalized, fallback)
        return fallback

def _regex_extract_intent(text: str) -> dict:
    # Defaults
    out = {"date_filter": None, "tech_filter": None, "keywords": None}

    # date_filter
    m = re.search(r"date_filter\s*:\s*(null|\"[^\"]*\"|\d{4}|\w+)", text, re.IGNORECASE)
    if m:
        v = m.group(1)
        out["date_filter"] = None if v.lower() == "null" else v.strip('"')

    # tech_filter
    m = re.search(r"tech_filter\s*:\s*(null|\"[^\"]*\"|\w+)", text, re.IGNORECASE)
    if m:
        v = m.group(1)
        out["tech_filter"] = None if v.lower() == "null" else v.strip('"')

    # keywords
    m = re.search(r"keywords\s*:\s*(null|\"[^\"]*\")", text, re.IGNORECASE)
    if m:
        v = m.group(1)
        out["keywords"] = None if v.lower() == "null" else v.strip('"')

    return out

# ----------------------------
# Query builder
# ----------------------------
def build_fts_query(data, original_query):
    parts = []
    oq = (original_query or "").lower()

    # --- 1. DATE FILTER ---
    time_triggers = [
        "today", "yesterday", "week", "month", "year",
        "202", "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "oct", "nov", "dec"
    ]
    user_mentioned_time = any(t in oq for t in time_triggers)

    if user_mentioned_time:
        # Year override when user typed a bare year and did not specify a month.
        year_match = re.search(r"\b(20\d{2})\b", oq)
        has_month_word = any(m in oq for m in ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"])

        if year_match and not has_month_word and ("today" not in oq and "yesterday" not in oq):
            year = year_match.group(1)
            parts.append(f'(created_str:"{year}" OR modified_str:"{year}")')
        else:
            date_raw = data.get("date_filter")
            if date_raw and str(date_raw).lower() != "null":
                val = str(date_raw).lower()
                today = datetime.now()
                date_str = val

                if "yesterday" in val:
                    date_str = (today - timedelta(days=1)).strftime("%Y %b %d")
                elif "today" in val:
                    date_str = today.strftime("%Y %b %d")
                else:
                    # If user specified a concrete date, format it.
                    # If it's a bare year, keep as "2024".
                    if re.fullmatch(r"20\d{2}", val):
                        date_str = val
                    else:
                        try:
                            dt = dateutil.parser.parse(val)
                            date_str = dt.strftime("%Y %b %d")
                        except Exception:
                            pass

                parts.append(f'(created_str:"{date_str}" OR modified_str:"{date_str}")')

    # --- 2. TECH FILTER ---
    tech_raw = data.get("tech_filter")
    tech_val = None
    if tech_raw and str(tech_raw).lower() != "null":
        tech_val = clean_string(str(tech_raw))

        ext_map = {
            "python": "py",
            "javascript": "js",
            "typescript": "ts",
            "react": "tsx",
            "tsx": "tsx",
            "jsx": "jsx",
            "sql": "sql",
            "csv": "csv",
            "markdown": "md",
            "json": "json",
            "yaml": "yml",
        }

        clauses = [f'content:{tech_val}', f'path:{tech_val}']

        if tech_val.lower() in ext_map:
            ext_tok = ext_map[tech_val.lower()]
            clauses.append(f'ext:{ext_tok}')
            clauses.append(f'path:{ext_tok}')
            clauses.append(f'path:{ext_tok}*')

        parts.append(f"({' OR '.join(clauses)})")

    # --- 3. KEYWORDS ---
    kw_raw = data.get("keywords")
    if kw_raw and str(kw_raw).lower() != "null":
        val = clean_string(str(kw_raw))

        fillers = [
            "files", "file", "made", "created", "modified",
            "scripts", "script", "documents", "document",
            "show", "me", "find", "give", "list",
            "main", "components", "component", "app",
            "from", "in", "on", "of", "the", "a", "an",
            "today", "yesterday", "tomorrow",
            "week", "month", "year",
            "jan", "feb", "mar", "apr", "may", "jun",
            "jul", "aug", "sep", "oct", "nov", "dec",
        ]
        if tech_val:
            fillers.append(tech_val.lower())

        clean_words = [w for w in val.split() if w.lower() not in fillers]

        if clean_words:
            final_kw = " ".join(clean_words)

            if len(final_kw.split()) == 1:
                parts.append(f'(path:{final_kw}* OR ext:{final_kw} OR content:{final_kw} OR summary:{final_kw})')
            else:
                parts.append(f'(content:{final_kw} OR summary:{final_kw} OR path:{final_kw}*)')

    if not parts:
        return ""

    # Remove exact duplicate clauses (you got duplicated date clauses in logs)
    deduped = []
    seen = set()
    for p in parts:
        if p not in seen:
            deduped.append(p)
            seen.add(p)

    return " AND ".join(deduped)


if __name__ == "__main__":
    print(parse_search_intent("files from 2024"))
    print(parse_search_intent("budget files"))
    print(parse_search_intent("files from 2024"))  # cache hit
