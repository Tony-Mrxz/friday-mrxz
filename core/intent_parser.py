"""
core/intent_parser.py - Fast 0ms Regex Parser + LLM Intent Fallback Resolver
"""
import re
from typing import Dict, Any, Tuple
from tools.apps import open_application, close_application
from tools.window_manager import focus_application, minimize_application
from tools.volume import set_volume, toggle_mute
from tools.screen_vision import capture_screen
from core.panic import trigger_panic_mode

# Questioning prefixes that mean the user is ASKING a question, NOT giving a command
QUESTION_PREFIXES = [
    "why", "how", "what", "where", "who", "when",
    "did you", "why did", "why do", "why would", "is it", "should i", "can i"
]


def parse_and_execute_fast(user_text: str) -> Tuple[bool, str]:
    """
    Tries 0ms deterministic regex matching for basic system actions.
    Excludes questioning phrases and handles compound instructions.
    """
    text = user_text.strip().lower()
    clean_text = re.sub(r"[;\:\-\_\=\+\!\?\.\,]+$", "", text).strip()

    # If sentence starts with a question word, do NOT run fast parser action
    first_word = clean_text.split()[0] if clean_text.split() else ""
    if first_word in QUESTION_PREFIXES or any(clean_text.startswith(qp) for qp in QUESTION_PREFIXES):
        return False, ""

    # 1. Panic lockdown
    if clean_text in ["/panic", "panic", "emergency stop"]:
        return True, trigger_panic_mode()

    # 2. Volume control
    vol_match = re.search(r"(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})%?", clean_text)
    if vol_match:
        val = int(vol_match.group(1))
        res = set_volume(val)
        return True, res["message"]

    if any(kw in clean_text for kw in ["mute volume", "mute audio", "silence audio"]) or clean_text == "mute":
        res = toggle_mute(True)
        return True, res["message"]

    if any(kw in clean_text for kw in ["unmute volume", "unmute audio"]) or clean_text == "unmute":
        res = toggle_mute(False)
        return True, res["message"]

    # 3. Screen capture
    if any(kw in clean_text for kw in ["screenshot", "take screenshot", "capture screen"]):
        res = capture_screen()
        return True, res["message"]

    # 4. Compound command handling (e.g. 'open opera and head to youtube', 'open chrome and search google')
    if " and " in clean_text or " then " in clean_text:
        parts = re.split(r"\b(?:and|then|and\s+head\s+to|and\s+go\s+to|and\s+open)\b", clean_text)
        results = []
        for part in parts:
            part_clean = part.strip()
            if part_clean:
                # Remove filler words
                sub_target = re.sub(r"^(?:open|launch|start|head\s+to|go\s+to)\s+", "", part_clean).strip()
                sub_target = re.sub(r"^(?:the|app|website|browser|page)\s+", "", sub_target).strip()
                if sub_target:
                    res = open_application(sub_target)
                    results.append(res["message"])
        if results:
            return True, "\n".join(results)

    # 5. Single Open app / website matching
    open_match = re.search(r"\b(?:open|launch|start|go\s+to|head\s+to)\s+([a-zA-Z0-9\.\_\-\s]+)$", clean_text)
    if open_match:
        target = open_match.group(1).strip()
        target = re.sub(r"^(?:the|app|website|browser|page)\s+", "", target).strip()
        res = open_application(target)
        return True, res["message"]

    # 6. Focus window
    focus_match = re.search(r"\b(?:focus|switch\s+to|bring\s+up)\s+([a-zA-Z0-9\.\_\-\s]+)$", clean_text)
    if focus_match:
        app = focus_match.group(1).strip()
        res = focus_application(app)
        return True, res["message"]

    # 7. Minimize window
    min_match = re.search(r"\b(?:minimize|hide)\s+([a-zA-Z0-9\.\_\-\s]+)$", clean_text)
    if min_match:
        app = min_match.group(1).strip()
        res = minimize_application(app)
        return True, res["message"]

    # Not handled by fast parser
    return False, ""
