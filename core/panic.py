"""
core/panic.py - Emergency Lockdown Handler for Friday AI
"""
from core.logger import logger

PANIC_MODE_ACTIVE = False


def trigger_panic_mode() -> str:
    """Instantly locks down Friday system operations."""
    global PANIC_MODE_ACTIVE
    PANIC_MODE_ACTIVE = True
    logger.critical("🚨 EMERGENCY PANIC MODE ACTIVATED! ALL AUTOMATIONS HALTED.")
    return "🚨 EMERGENCY PANIC MODE ACTIVATED! Friday is locked down. Restart system to resume."


def reset_panic_mode() -> str:
    """Manually resets panic mode."""
    global PANIC_MODE_ACTIVE
    PANIC_MODE_ACTIVE = False
    logger.info("🟢 Panic mode reset. System operational.")
    return "🟢 Panic mode reset. Systems operational."


def is_panic_active() -> bool:
    return PANIC_MODE_ACTIVE
