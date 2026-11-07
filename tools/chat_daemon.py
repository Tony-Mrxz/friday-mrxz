"""
tools/chat_daemon.py - Autonomous Background Mini-Agent Daemon for Continuous Chatting
Launches background threads that continuously monitor, read, and auto-reply to a specified contact
until explicitly stopped by the user via commands like 'stop chatting with Tanusree'.
"""
import time
import threading
import re
from typing import Dict, Any
from tools.app_automation import reply_to_chat_message
from core.logger import logger

_ACTIVE_CHAT_DAEMONS: Dict[str, Dict[str, Any]] = {}
_DAEMON_LOCK = threading.Lock()


def _chat_daemon_loop(app: str, recipient: str, poll_interval: int, stop_event: threading.Event):
    """Background thread loop that periodically checks and replies to incoming messages."""
    recip_clean = recipient.lower().strip()
    logger.info(f"🚀 Mini-Agent Chat Daemon started for '{recipient}' on {app.capitalize()} (Interval: {poll_interval}s)")

    # Keep track of last processed text to avoid duplicate spamming
    last_processed_text = ""

    while not stop_event.is_set():
        try:
            # Check if app/chat has new content or needs reply
            logger.debug(f"🔄 Mini-Agent polling chat for '{recipient}'...")
            res = reply_to_chat_message(app, recipient)
            if res.get("success"):
                logger.info(f"💬 Mini-Agent auto-replied to '{recipient}': {res.get('message')}")
        except Exception as e:
            logger.error(f"Error in chat daemon for '{recipient}': {e}")

        # Sleep for poll_interval checking stop_event every second
        for _ in range(poll_interval):
            if stop_event.is_set():
                break
            time.sleep(1)

    logger.info(f"🛑 Mini-Agent Chat Daemon stopped for '{recipient}'.")


def start_continuous_chat(app: str = "whatsapp", recipient: str = "", poll_interval: int = 15) -> dict:
    """
    Launches a background Mini-Agent daemon to continuously chat with a recipient.
    """
    if not recipient:
        return {"success": False, "message": "Please specify a contact name to chat with."}

    recip_clean = recipient.lower().strip()

    with _DAEMON_LOCK:
        if recip_clean in _ACTIVE_CHAT_DAEMONS:
            return {"success": True, "message": f"🤖 Mini-Agent is already continuously chatting with '{recipient}' in the background!"}

        stop_event = threading.Event()
        thread = threading.Thread(
            target=_chat_daemon_loop,
            args=(app, recipient, poll_interval, stop_event),
            daemon=True,
            name=f"ChatDaemon_{recip_clean}"
        )
        
        _ACTIVE_CHAT_DAEMONS[recip_clean] = {
            "app": app,
            "recipient": recipient,
            "thread": thread,
            "stop_event": stop_event,
            "started_at": time.strftime("%H:%M:%S")
        }

        thread.start()

    return {
        "success": True,
        "message": f"🚀 **Mini-Agent Launched!** Friday is now continuously chatting with **'{recipient}'** in the background on {app.capitalize()}.\nType *'stop chatting with {recipient}'* whenever you want to terminate the loop!"
    }


def stop_continuous_chat(recipient: str = "") -> dict:
    """
    Stops a running background chat daemon for a recipient (or stops all if recipient is empty).
    """
    recip_clean = recipient.lower().strip() if recipient else ""

    with _DAEMON_LOCK:
        if not _ACTIVE_CHAT_DAEMONS:
            return {"success": True, "message": "No active chat daemons are currently running."}

        if recip_clean and recip_clean in _ACTIVE_CHAT_DAEMONS:
            daemon = _ACTIVE_CHAT_DAEMONS.pop(recip_clean)
            daemon["stop_event"].set()
            return {"success": True, "message": f"🛑 **Stopped Mini-Agent!** Friday has stopped auto-chatting with **'{daemon['recipient']}'**."}

        # Stop all active daemons if specified target is 'all' or unmatched
        stopped_list = []
        for k in list(_ACTIVE_CHAT_DAEMONS.keys()):
            daemon = _ACTIVE_CHAT_DAEMONS.pop(k)
            daemon["stop_event"].set()
            stopped_list.append(daemon["recipient"])

        stopped_str = ", ".join(stopped_list)
        return {"success": True, "message": f"🛑 **Stopped All Mini-Agents!** Terminated chat loops for: **{stopped_str}**."}


def list_active_chat_daemons() -> list:
    """Returns list of currently running chat mini-agents."""
    with _DAEMON_LOCK:
        return [
            f"• {d['recipient']} ({d['app'].capitalize()}) - Started at {d['started_at']}"
            for d in _ACTIVE_CHAT_DAEMONS.values()
        ]
