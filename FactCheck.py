import os
import ollama

AUDITOR_PROMPT = (
    "You are a strict fact-checking auditor. Compare the DRAFT ANSWER against the REFERENCE ARTICLES.\n"
    "Rules:\n"
    "1. Every single fact, number, date, and title in the final answer MUST be explicitly proven by the REFERENCE ARTICLES.\n"
    "2. If the DRAFT ANSWER repeats a false assumption from the QUESTION that is not in the REFERENCE ARTICLES (such as claiming a 'second' prize when only one is mentioned), fix it immediately.\n"
    "3. If the REFERENCE ARTICLES do not actually answer the QUESTION, replace the draft with: 'The provided offline articles do not contain enough information to answer that.'\n"
    "4. Output ONLY the clean, verified 2-4 sentence final answer. Do not mention 'Draft Answer' or 'Auditor'."
)


def verify_and_stream(model: str, context_text: str, question: str, draft_answer: str, stream_callback):
    # Dynamically read what hardware.py flagged at boot time
    hardware_mode = os.environ.get("INTERACT_ACCEL", "GPU")
    
    # Scale windows down on naked CPU to prevent system locks
    ctx_limit = 2048 if hardware_mode == "CPU" else 4096
    predict_limit = 150 if hardware_mode == "CPU" else 250

    # 1. Turn off stream=True to prevent bleeding words onto the screen prematurely
    response = ollama.chat(
        model=model,
        think=False,
        stream=False, # <--- Changed to False
        options={
            "temperature": 0.0, 
            "num_ctx": ctx_limit, 
            "num_predict": predict_limit
        },
        messages=[
            {"role": "system", "content": AUDITOR_PROMPT},
            {
                "role": "user",
                "content": (
                    f"REFERENCE ARTICLES:\n{context_text}\n\n"
                    f"QUESTION: {question}\n\n"
                    f"DRAFT ANSWER:\n{draft_answer}"
                ),
            },
        ],
    )
    
    # 2. Extract the finalized, verified, clean text block
    verified_answer = response["message"]["content"]
    
    # 3. Hand the fully completed, safe answer to the interface all at once
    stream_callback(verified_answer)
