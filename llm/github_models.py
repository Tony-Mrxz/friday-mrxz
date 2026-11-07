"""
llm/github_models.py - GitHub Models API Client for Free Access
"""
import requests
from typing import List, Dict, Any, Optional
from config.settings import get_github_token, GITHUB_MODEL_NAME
from llm.base import BaseLLMProvider
from core.logger import logger

ENDPOINT = "https://models.github.ai/inference/chat/completions"


class GitHubModelsProvider(BaseLLMProvider):

    def __init__(self, token: str = None, model: str = None):
        self._token = token
        self.model = model or GITHUB_MODEL_NAME

    @property
    def token(self) -> str:
        return self._token or get_github_token()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

    def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature)

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        curr_token = self.token
        if not curr_token:
            raise ValueError("GitHub Token (GITHUB_TOKEN) is missing. Set it in .env file.")

        payload = {
            "messages": messages,
            "model": self.model,
            "temperature": temperature,
            "max_tokens": 1000
        }

        try:
            res = requests.post(ENDPOINT, headers=self._get_headers(), json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            elif res.status_code == 410:
                err_text = res.text
                logger.warning(f"⚠️ GitHub Models API brownout/retired (410): {err_text}")
                raise RuntimeError("GitHub Models API is temporarily unavailable (scheduled retirement brownout).")
            else:
                logger.debug(f"GitHub Models API status {res.status_code}: {res.text}")
                raise RuntimeError(f"GitHub Models API HTTP {res.status_code}: {res.text}")
        except Exception as e:
            raise e

