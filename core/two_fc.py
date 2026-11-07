"""
core/two_fc.py - Two-Factor Confirmation Engine for Sensitive Actions
Guards high-risk system commands (e.g. close application, delete memory, system shutdown).
"""
import time
from typing import Dict, Any, Optional
from core.logger import logger


class ConfirmationEngine:

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds
        self.pending_action: Optional[Dict[str, Any]] = None
        self.created_at: float = 0.0

    def is_confirmation_required(self, action_type: str, target: str) -> bool:
        """Determines if action type requires 2FC approval."""
        DANGEROUS_ACTIONS = ["close_app", "wipe_memory", "shutdown_system", "kill_process"]
        return action_type in DANGEROUS_ACTIONS

    def create_pending_confirmation(self, action_type: str, target: str, callback_data: Dict[str, Any]) -> str:
        """Stores a pending confirmation payload."""
        self.pending_action = {
            "action_type": action_type,
            "target": target,
            "callback_data": callback_data
        }
        self.created_at = time.time()
        return (
            f"⚠️ **CONFIRMATION REQUIRED**\n"
            f"Are you sure you want to perform: `{action_type}` on `{target}`?\n"
            f"Reply with `yes` / `confirm` or `no` / `cancel` within {self.timeout_seconds} seconds."
        )

    def process_response(self, user_reply: str) -> Dict[str, Any]:
        """Validates user reply against pending action."""
        if not self.pending_action:
            return {"active": False, "confirmed": False, "message": "No action pending confirmation."}

        if time.time() - self.created_at > self.timeout_seconds:
            self.pending_action = None
            return {"active": True, "confirmed": False, "message": "⏱️ Confirmation timed out. Action cancelled."}

        reply_clean = user_reply.strip().lower()
        if reply_clean in ["yes", "y", "confirm", "sure"]:
            action = self.pending_action
            self.pending_action = None
            return {"active": True, "confirmed": True, "action": action, "message": "✅ Action confirmed!"}
        elif reply_clean in ["no", "n", "cancel"]:
            self.pending_action = None
            return {"active": True, "confirmed": False, "message": "❌ Action cancelled by user."}

        return {"active": True, "confirmed": False, "message": "Invalid reply. Type 'yes' or 'no'."}
