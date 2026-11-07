"""
llm/router.py - LLM Provider Failover Router & Health Diagnostic for Friday AI
"""
from typing import List, Dict, Any, Tuple
from llm.github_models import GitHubModelsProvider
from llm.groq_provider import GroqProvider
from config.settings import get_github_token, get_groq_key, GROQ_MODEL_NAME, GITHUB_MODEL_NAME
from core.logger import logger


class LLMRouter:

    def __init__(self):
        self.github_provider = GitHubModelsProvider()
        self.groq_provider = GroqProvider()

    def get_active_provider_info(self) -> Tuple[str, str]:
        """Returns (active_provider_name, active_model_name)."""
        groq_key = get_groq_key()
        gh_token = get_github_token()

        if groq_key:
            return "Groq Cloud", GROQ_MODEL_NAME
        elif gh_token:
            return "GitHub Models", GITHUB_MODEL_NAME
        else:
            return "None", "No API Key Configured"

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """Tries active LLM providers in priority order and returns plain text string."""
        res_dict = self.chat_with_metadata(messages, temperature=temperature)
        return res_dict.get("content", "")

    def chat_with_metadata(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
        """Tries active LLM providers in priority order and returns content + sources + state flags."""
        gh_token = get_github_token()
        groq_key = get_groq_key()
        errors = []

        # 1. Try Groq Cloud built-in web search compound models first
        if groq_key:
            try:
                return self.groq_provider.chat_with_metadata(messages, temperature=temperature)
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "Rate limit" in err_msg or "rate_limit_exceeded" in err_msg:
                    logger.warning(f"⚠️ Groq API rate limit reached: {e}")
                    errors.append(f"Groq Rate Limit: {e}")
                else:
                    logger.warning(f"⚠️ Groq API failed: {e}")
                    errors.append(f"Groq Error: {e}")

        # 2. Try GitHub Models API fallback
        if gh_token:
            try:
                content = self.github_provider.chat(messages, temperature=temperature)
                return {
                    "content": content,
                    "sources": [],
                    "used_web": False,
                    "web_requested": True,
                    "web_failed": True
                }
            except Exception as e:
                logger.warning(f"⚠️ GitHub Models API failed: {e}")
                errors.append(f"GitHub Models Error: {e}")

        if not groq_key and not gh_token:
            return {
                "content": (
                    "Notice: No LLM API key configured.\n"
                    "💡 **Solution:** Get a free Groq API Key from `console.groq.com` and type `config` to set it!"
                ),
                "sources": [],
                "used_web": False,
                "web_requested": False,
                "web_failed": False
            }

        err_summary = " | ".join(errors) if errors else "No active provider succeeded."
        return {
            "content": f"⚠️ Could not reach LLM providers. Details: {err_summary}",
            "sources": [],
            "used_web": False,
            "web_requested": True,
            "web_failed": True
        }

    def transcribe_audio(self, file_path: str) -> str:
        """Transcribes audio using Groq Whisper if available."""
        if get_groq_key():
            return self.groq_provider.transcribe_audio(file_path)
        return ""

