"""
memory/memory_injector.py - Memory Context Injector for Friday System Prompts
Injects compact (~150 token) user identity & relationship stage into system prompt.
"""
from memory.memory_manager import read_soul_profile, read_user_profile, STAGE_LABELS


def build_memory_context() -> str:
    """Builds a compact memory string to inject into system prompt."""
    soul = read_soul_profile()
    stage_num = soul.get("stage", 0)
    stage_name = STAGE_LABELS.get(stage_num, "Stranger")
    sessions = soul.get("sessions_together", 0)
    
    user_text = read_user_profile()
    lines = [line.strip() for line in user_text.splitlines() if line.strip().startswith("-")]
    facts_summary = "; ".join(lines[:5]) if lines else "No prior facts recorded."

    context = (
        f"\n--- FRIDAY MEMORY CONTEXT ---\n"
        f"Relationship Stage: {stage_name} (Level {stage_num}, {sessions} sessions together)\n"
        f"Key User Facts: {facts_summary}\n"
        f"-----------------------------\n"
    )
    return context
