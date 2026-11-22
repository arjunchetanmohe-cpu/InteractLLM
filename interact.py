import os
import sys
import re
import sqlite3
import ollama
from Math import solve_math, check_letter_count
from FactCheck import verify_and_stream

# Always find wiki.db right next to interact.py OR InteractLLM.exe
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(BASE_DIR, "wiki.db")
BASE_MODEL = "qwen3:1.7b"
AUDITOR_MODEL = "llama3.2:1b"
VISION_MODEL = "moondream"  # Ensure you run 'ollama pull moondream'

STOP_WORDS = {
    "what", "is", "are", "was", "were", "the", "a", "an", "in", "on", "at",
    "to", "for", "of", "and", "or", "how", "why", "when", "where", "who",
    "which", "do", "does", "did", "can", "could", "would", "should", "with",
    "has", "have", "had", "she", "he", "they", "them", "her", "his", "each"
}

WIKI_SYSTEM_PROMPT = (
    "You are InteractLLM, a 100% offline encyclopedia AI. "
    "Write a concise 2-4 sentence draft answer using ONLY the provided reference articles. "
    "Do not guess or add outside facts."
)

GENERAL_SYSTEM_PROMPT = (
    "You are InteractLLM, a helpful, concise offline AI assistant. "
    "Think step-by-step for riddles or logic problems, then answer clearly in 2-4 sentences. "
    "Never mention reference articles or databases."
)

ROUTER_PROMPT = (
    "Extract ONLY the math expression or equation from the user's question so a Python calculator can solve it. "
    "Reply ONLY with the raw expression (e.g., 2*x + 5 = 15 or 482 * 19). "
    "If it is a logic riddle rather than a pure calculation, reply with NONE."
)

IMAGE_SYSTEM_PROMPT = (
    "You are InteractLLM's Vision Engine. Analyze the provided image thoroughly "
    "and answer the user's request accurately based on what you see. If the main "
    "focus of the image is identified as cartoon character/s, give the name of the "
    "character and state the show where they are from."
)

def is_math_query(query: str) -> bool:
    """Detects explicit math expressions, equations, or calculation requests."""
    if check_letter_count(query) is not None:
        return True
    has_operator = bool(re.search(r"\d\s*[\+\-\*/\^=]\s*[\d\(a-zA-Z]", query))
    has_math_keyword = bool(
        re.search(r"\b(solve|calculate|compute|sqrt|equation|factor|simplify|plus|minus|multiplied|divided)\b", query.lower())
    )
    return has_operator or has_math_keyword


def is_factual_query(query: str) -> bool:
    """Prevents riddles, jokes, and conversational prompts from triggering wiki.db."""
    q_lower = query.lower().strip()
    
    # Exclude obvious riddles or personal/hypothetical scenarios
    riddle_indicators = ("she has", "he has", "each brother", "each sister", "riddle", "joke", "write a", "code")
    if any(ind in q_lower for ind in riddle_indicators):
        return False

    factual_starters = (
        "who is", "who was", "what is", "what are", "what was", "when was",
        "where is", "tell me about", "history of", "define", "explain", "how did"
    )
    return q_lower.startswith(factual_starters)


def search_wiki(query: str, top_k: int = 3, min_bm25_score: float = -3.5):
    """
    Searches wiki.db using FTS5 BM25 ranking.
    """
    if not os.path.exists(DB_FILE):
        return []

    words = [
        w.lower()
        for w in re.findall(r"\b[a-zA-Z0-9]{2,}\b", query)
        if w.lower() not in STOP_WORDS
    ]
    if not words:
        return []

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    results = []
    seen_titles = set()

    if len(words) > 1:
        and_query = " AND ".join(words)
        cur.execute(
            """
            SELECT title, content, bm25(articles, 5.0, 1.0) AS score
            FROM articles
            WHERE articles MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (and_query, top_k),
        )
        for title, content, score in cur.fetchall():
            if score <= min_bm25_score and title not in seen_titles:
                results.append((title, content))
                seen_titles.add(title)

    if len(results) < top_k:
        or_query = " OR ".join(words)
        cur.execute(
            """
            SELECT title, content, bm25(articles, 5.0, 1.0) AS score
            FROM articles
            WHERE articles MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (or_query, top_k),
        )
        for title, content, score in cur.fetchall():
            if score <= min_bm25_score and title not in seen_titles:
                results.append((title, content))
                seen_titles.add(title)
                if len(results) >= top_k:
                    break

    conn.close()
    return results


def ask_interact_llm(query: str, stream_callback, image_path=None, **kwargs):
    """Main entry point called by gui.py, now supporting optional vision input."""
    query = query.strip()
    
    # NEW FAST LANE: Handle Image Scanning if an image file path is passed
    if image_path and os.path.exists(image_path):
        stream_callback("[Vision Engine • Scanning Image]\n")
        
        # Default prompt if user submitted an image without text instructions
        user_prompt = query if query else "Describe this image in detail."
        
        try:
            stream = ollama.chat(
                model=VISION_MODEL,
                think=False,
                stream=True,
                keep_alive="10m",
                options={"temperature": 0.2, "num_predict": 400},
                messages=[
                    {"role": "system", "content": IMAGE_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": user_prompt,
                        "images": [image_path] # Ollama natively accepts local paths here
                    },
                ],
            )
            for chunk in stream:
                stream_callback(chunk["message"]["content"])
            return
        except Exception as e:
            stream_callback(f"\n[Vision Error] Could not scan image: {e}\nMake sure to run 'ollama pull {VISION_MODEL}' in your terminal.")
            return

    if not query:
        return

    # LANE 1: Letter counting and SymPy Math (0ms deterministic tools)
    letter_ans = check_letter_count(query)
    if letter_ans:
        stream_callback(f"[String Tool]\n{letter_ans}")
        return

    if is_math_query(query):
        direct_try = solve_math(query)
        if not direct_try.startswith("Math Error"):
            stream_callback(f"[Math Engine]\n{direct_try}")
            return

        extract_resp = ollama.chat(
            model=BASE_MODEL,
            think=False,
            keep_alive="10m",
            options={"temperature": 0.0, "num_predict": 60},
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": query},
            ],
        )
        extracted_expr = extract_resp["message"]["content"].strip()
        if extracted_expr.upper() != "NONE":
            math_ans = solve_math(extracted_expr)
            if not math_ans.startswith("Math Error"):
                stream_callback(f"[Math Engine • {extracted_expr}]\n{math_ans}")
                return

    # LANE 2: Local Wikipedia and FactChecked Auditor
    if is_factual_query(query):
        articles = search_wiki(query, top_k=3, min_bm25_score=-3.5)
        if articles:
            titles = ", ".join(title for title, _ in articles)
            context_text = "\n\n".join(
                f"### {title}\n{content[:1200]}" for title, content in articles
            )

            draft_resp = ollama.chat(
                model=BASE_MODEL,
                think=False,
                keep_alive="10m",
                options={"temperature": 0.1, "num_ctx": 4096, "num_predict": 220},
                messages=[
                    {"role": "system", "content": WIKI_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"REFERENCE ARTICLES:\n{context_text}\n\nQUESTION: {query}",
                    },
                ],
            )
            draft_answer = draft_resp["message"]["content"].strip()

            stream_callback(f"[Wiki Fact-Checked • Sources: {titles}]\n")
            verify_and_stream(
                model=AUDITOR_MODEL,
                context_text=context_text,
                question=query,
                draft_answer=draft_answer,
                stream_callback=stream_callback,
            )
            return

    # LANE 3: General offline chat (Riddles, logic, jokes, coding)
    stream_callback("[General AI • Direct]\n")
    stream = ollama.chat(
        model=BASE_MODEL,
        think=False,
        stream=True,
        keep_alive="10m",
        options={"temperature": 0.4, "num_ctx": 4096, "num_predict": 300},
        messages=[
            {"role": "system", "content": GENERAL_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
    )
    for chunk in stream:
        stream_callback(chunk["message"]["content"])


if __name__ == "__main__":
    print("InteractLLM Offline CLI Ready (type 'exit' to quit)\n")
    while True:
        user_q = input("You: ")
        if user_q.lower() in ("exit", "quit"):
            break
        # Mocking an execution via terminal without image attachment
        ask_interact_llm(user_q, lambda text: print(text, end="", flush=True))
        print("\n")
