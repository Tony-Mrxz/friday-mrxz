"""
memory/memory_manager.py - Persistent Identity, Automatic Fact Extraction, and 4-Stage Relationship Manager
"""
import os
import json
import re
import datetime
from pathlib import Path
from typing import Dict, Any, List
from config.settings import MEMORY_DIR
from core.logger import logger

USER_FILE = MEMORY_DIR / "user.md"
SOUL_FILE = MEMORY_DIR / "soul.md"
SESSIONS_DIR = MEMORY_DIR / "sessions"
HISTORY_FILE = MEMORY_DIR / "chat_history.json"

STAGE_LABELS = {
    0: "Stranger",
    1: "Acquaintance",
    2: "Familiar",
    3: "Companion"
}

THRESHOLDS = {
    1: (3, 3),    # Stage 1 requires 3 sessions & 3 facts
    2: (8, 5),    # Stage 2 requires 8 sessions & 5 facts
    3: (20, 10)   # Stage 3 requires 20 sessions & 10 facts
}

EXTRACTION_KEYWORDS = [
    "im ", "i'm ", "my name is", "call me", "i work as", "i am a",
    "i live in", "i prefer", "i love", "i hate", "i am founder",
    "founder and", "creator of", "aka ", "irl name",
    "friend", "best friend", "bro", "brother", "sister", "buddy", "bff",
    "also known as", "known as", "alias", "nickname", "partner", "cousin"
]



def ensure_memory_files():
    """Ensures memory files and directories exist."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    if not USER_FILE.exists():
        USER_FILE.write_text(
            "# User Profile Memory\n\n"
            "## Identity & Facts\n",
            encoding="utf-8"
        )

    if not SOUL_FILE.exists():
        SOUL_FILE.write_text(
            "# Friday Soul Profile\n\n"
            "stage: 0\n"
            "sessions_together: 0\n"
            "facts_count: 0\n"
            "created_at: " + datetime.datetime.now().isoformat() + "\n",
            encoding="utf-8"
        )


def read_soul_profile() -> Dict[str, Any]:
    """Reads soul.md metadata."""
    ensure_memory_files()
    profile = {"stage": 0, "sessions_together": 0, "facts_count": 0}
    try:
        content = SOUL_FILE.read_text(encoding="utf-8")
        for line in content.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k = k.strip()
                v = v.strip()
                if k in ["stage", "sessions_together", "facts_count"]:
                    profile[k] = int(v)
    except Exception as e:
        logger.error(f"Error reading soul profile: {e}")
    return profile


def write_soul_profile(stage: int, sessions: int, facts: int):
    """Updates soul.md file."""
    ensure_memory_files()
    SOUL_FILE.write_text(
        f"# Friday Soul Profile\n\n"
        f"stage: {stage}\n"
        f"sessions_together: {sessions}\n"
        f"facts_count: {facts}\n"
        f"updated_at: {datetime.datetime.now().isoformat()}\n",
        encoding="utf-8"
    )


def read_user_profile() -> str:
    """Reads user profile markdown text."""
    ensure_memory_files()
    try:
        return USER_FILE.read_text(encoding="utf-8")
    except Exception:
        return ""


def get_session_history_file(session_id: str = "default") -> Path:
    """Returns Path object for a given session ID."""
    ensure_memory_files()
    if not session_id or session_id in ["default", "terminal"]:
        return HISTORY_FILE
    safe_id = re.sub(r"[^\w\-]", "_", session_id)
    return SESSIONS_DIR / f"chat_history_{safe_id}.json"


def save_chat_history(history: List[Dict[str, str]], session_id: str = "default"):
    """Persists chat history to disk per session."""
    file_path = get_session_history_file(session_id)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save chat history for session '{session_id}': {e}")


def load_chat_history(session_id: str = "default") -> List[Dict[str, str]]:
    """Loads persisted chat history from disk per session."""
    file_path = get_session_history_file(session_id)
    if not file_path.exists():
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


NEGATIVE_FACT_KEYWORDS = [
    "no clear information", "not mentioned", "lacks specific", "no information",
    "not provided", "cannot be determined", "unclear", "no facts", "none",
    "informal", "does not contain", "no details", "n/a", "unknown", "message appears",
    "name: friday", "role: ai assistant", "developer: tony", "im friday", "i am friday"
]


def is_valid_user_fact(fact: str) -> bool:
    """Validates that extracted string is a real user fact and not an LLM meta-explanation."""
    f_lower = fact.lower().strip()
    if len(f_lower) < 4:
        return False
    if any(neg in f_lower for neg in NEGATIVE_FACT_KEYWORDS):
        return False
    return True


def append_user_fact(fact: str):
    """Appends a new learned fact to user.md."""
    ensure_memory_files()
    if not is_valid_user_fact(fact):
        return
    try:
        content = USER_FILE.read_text(encoding="utf-8")
        if fact.lower() not in content.lower():
            content += f"- {fact}\n"
            USER_FILE.write_text(content, encoding="utf-8")
            
            soul = read_soul_profile()
            soul["facts_count"] += 1
            check_and_advance_stage(soul)
            logger.info(f"🧠 Friday learned new user fact: {fact}")
    except Exception as e:
        logger.error(f"Error appending user fact: {e}")


def check_and_extract_facts(user_text: str):
    """Checks if message contains self-introductions or facts and extracts them."""
    lower = user_text.lower()
    if any(kw in lower for kw in EXTRACTION_KEYWORDS):
        try:
            from llm.router import LLMRouter
            router = LLMRouter()
            prompt = (
                f"Analyze this user message for explicit user facts (such as name, age, job, role, location, preferences, friends, social relationships, nicknames):\n"
                f"'{user_text}'\n\n"
                "RULES:\n"
                "1. ONLY extract concrete, positive facts explicitly stated by the user.\n"
                "2. If NO concrete facts about the user are stated, reply ONLY with 'NONE'.\n"
                "3. DO NOT output explanations, meta-comments, or statements like 'No information available'.\n"
                "4. Format valid facts as simple bullet points starting with '- ' (e.g. '- Best Friend: Nihar', '- Friend: Tanusree')."
            )
            extracted = router.chat([{"role": "user", "content": prompt}], temperature=0.1)
            if "none" in extracted.lower().strip():
                return

            for line in extracted.splitlines():
                line = line.strip()
                if line.startswith("-") and len(line) > 3:
                    fact_str = line[1:].strip()
                    if is_valid_user_fact(fact_str):
                        append_user_fact(fact_str)
        except Exception as e:
            logger.error(f"Fact extraction failed: {e}")



def check_and_advance_stage(soul: Dict[str, Any]):
    """Silently advances relationship stage if thresholds met."""
    current_stage = soul.get("stage", 0)
    sessions = soul.get("sessions_together", 0)
    facts = soul.get("facts_count", 0)

    user_prof = read_user_profile().lower()
    if "tony" in user_prof or "founder" in user_prof or facts >= 3:
        next_stage = 3  # Companion stage for Tony!
        sessions = max(sessions, 25)
    else:
        next_stage = current_stage
        for stg in [3, 2, 1]:
            req_sessions, req_facts = THRESHOLDS[stg]
            if sessions >= req_sessions and facts >= req_facts:
                next_stage = max(current_stage, stg)
                break

    write_soul_profile(next_stage, sessions, facts)
