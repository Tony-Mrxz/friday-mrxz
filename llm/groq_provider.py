import time
import requests
from typing import List, Dict, Any, Optional
from config.settings import get_groq_key, GROQ_MODEL_NAME, GROQ_WHISPER_MODEL
from llm.base import BaseLLMProvider
from core.logger import logger

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
TRANSCRIPTION_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
FALLBACK_GROQ_MODELS = ["groq/compound", "groq/compound-mini", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]


def _trim_messages_for_413(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Trims messages context down to just system prompt + user query for 413 retries."""
    if len(messages) <= 2:
        return messages
    sys_msg = messages[0] if messages[0].get("role") == "system" else None
    user_msg = messages[-1] if messages[-1].get("role") == "user" else None

    trimmed = []
    if sys_msg:
        trimmed.append(sys_msg)
    if user_msg:
        trimmed.append(user_msg)
    return trimmed


def _extract_search_sources(executed_tools: Any) -> List[Dict[str, str]]:
    """Defensively extracts, sanitizes, deduplicates, and truncates search sources from Groq executed_tools."""
    sources = []
    seen_urls = set()

    if not isinstance(executed_tools, list):
        return sources

    for tool in executed_tools:
        if not isinstance(tool, dict):
            continue

        tool_type = str(tool.get("type", "")).lower()
        if tool_type != "search" and "search_results" not in tool:
            continue

        sr = tool.get("search_results")
        raw_results = []
        if isinstance(sr, dict):
            raw_results = sr.get("results", [])
        elif isinstance(sr, list):
            raw_results = sr

        if not isinstance(raw_results, list):
            continue

        for item in raw_results:
            if not isinstance(item, dict):
                continue

            raw_url = str(item.get("url", "")).strip()
            if not raw_url or not (raw_url.startswith("http://") or raw_url.startswith("https://")):
                continue

            if raw_url in seen_urls:
                continue

            seen_urls.add(raw_url)

            title = str(item.get("title", "")).strip() or raw_url
            snippet = str(item.get("snippet") or item.get("content") or "").strip()
            if len(snippet) > 300:
                snippet = snippet[:297] + "..."

            sources.append({
                "title": title,
                "url": raw_url,
                "snippet": snippet
            })

    return sources


class GroqProvider(BaseLLMProvider):

    def __init__(self, api_key: str = None, model: str = None):
        self._api_key = api_key
        self.model = model or "groq/compound"

    @property
    def api_key(self) -> str:
        return self._api_key or get_groq_key()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature)

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        res_dict = self.chat_with_metadata(messages, temperature=temperature)
        return res_dict.get("content", "")

    def chat_with_metadata(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> Dict[str, Any]:
        curr_key = self.api_key
        if not curr_key:
            raise ValueError("Groq API Key (GROQ_API_KEY) is missing. Set it in .env file.")

        # Deduplicate target models sequence
        models_to_try = []
        for m in [self.model] + FALLBACK_GROQ_MODELS:
            if m and m not in models_to_try:
                models_to_try.append(m)

        compound_attempted = False
        last_error = None

        for target_model in models_to_try:
            is_compound_model = "compound" in target_model
            if is_compound_model:
                compound_attempted = True

            curr_messages = list(messages)

            payload = {
                "messages": curr_messages,
                "model": target_model,
                "temperature": temperature,
                "max_tokens": 1000
            }

            try:
                res = requests.post(ENDPOINT, headers=self._get_headers(), json=payload, timeout=25)

                # Handle 413 Payload Too Large by trimming context and retrying ONCE
                if res.status_code == 413 or "413" in res.text or "payload_too_large" in res.text:
                    logger.warning(f"⚠️ Groq model '{target_model}' 413 Payload Too Large. Trimming context and retrying once...")
                    curr_messages = _trim_messages_for_413(curr_messages)
                    payload["messages"] = curr_messages
                    res = requests.post(ENDPOINT, headers=self._get_headers(), json=payload, timeout=25)

                if res.status_code == 200:
                    data = res.json()
                    msg = data.get("choices", [{}])[0].get("message", {})
                    content = msg.get("content", "").strip()
                    executed_tools = msg.get("executed_tools", [])

                    try:
                        sources = _extract_search_sources(executed_tools)
                    except Exception as err:
                        logger.error(f"Error parsing search sources: {err}")
                        sources = []

                    used_web = len(sources) > 0

                    return {
                        "content": content,
                        "sources": sources,
                        "used_web": used_web,
                        "web_requested": compound_attempted,
                        "web_failed": compound_attempted and not is_compound_model
                    }

                elif res.status_code == 429 or "rate_limit" in res.text:
                    retry_after_hdr = res.headers.get("Retry-After")
                    sleep_sec = 1.0
                    if retry_after_hdr:
                        try:
                            sleep_sec = min(float(retry_after_hdr), 3.0)
                        except Exception:
                            sleep_sec = 1.0
                    logger.warning(f"⚠️ Groq model '{target_model}' rate limited (429). Backing off {sleep_sec}s before trying next model...")
                    time.sleep(sleep_sec)
                    last_error = RuntimeError(f"Groq API Error 429: {res.text}")
                    continue

                elif res.status_code == 404 or "model_not_found" in res.text:
                    logger.warning(f"⚠️ Groq model '{target_model}' not found (404), trying fallback model...")
                    last_error = RuntimeError(f"Groq API Error {res.status_code}: {res.text}")
                    continue
                else:
                    logger.error(f"❌ Groq API error ({res.status_code}): {res.text}")
                    last_error = RuntimeError(f"Groq API Error {res.status_code}: {res.text}")
                    continue

            except Exception as e:
                err_str = str(e)
                if any(k in err_str for k in ["model_not_found", "404", "413", "429", "rate_limit"]):
                    last_error = e
                    continue
                logger.error(f"❌ Groq request failed: {e}")
                last_error = e

        if last_error:
            raise last_error
        raise RuntimeError("All Groq models failed.")


    def transcribe_audio(self, file_path: str) -> str:
        """Transcribes audio file using Groq Cloud Whisper API."""
        curr_key = self.api_key
        if not curr_key:
            raise ValueError("Groq API Key missing for audio transcription.")

        headers = {"Authorization": f"Bearer {curr_key}"}
        try:
            with open(file_path, "rb") as audio_file:
                files = {"file": audio_file}
                data = {"model": GROQ_WHISPER_MODEL}
                res = requests.post(TRANSCRIPTION_ENDPOINT, headers=headers, files=files, data=data, timeout=30)
                if res.status_code == 200:
                    return res.json().get("text", "").strip()
                else:
                    logger.error(f"❌ Whisper transcription failed: {res.text}")
                    return ""
        except Exception as e:
            logger.error(f"❌ Error transcribing audio: {e}")
            return ""
