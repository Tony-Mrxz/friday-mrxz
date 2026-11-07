"""
core/agent_loop.py - Friday Pure LLM Function Calling & Conversation Orchestrator
Architecture:
Input ──> LLM ──┬──> Tool Call (JSON/Action) ──> Execute Function ──> Return Result
                └──> Normal Convo ──────────────────────────────────> Return Response
"""
import json
import re
import threading
from typing import Dict, Any, List, Tuple
from core.prompt_builder import build_system_prompt
from core.two_fc import ConfirmationEngine
from core.panic import is_panic_active
from llm.router import LLMRouter
from tools.apps import open_application, close_application, load_known_apps
from tools.window_manager import focus_application, minimize_application
from tools.volume import set_volume, toggle_mute
from tools.screen_vision import (
    capture_screen, analyze_screen_with_vision, locate_ui_element, click_and_inspect_result
)
from tools.input_controller import move_mouse, click, type_text, press_hotkey
from memory.memory_manager import (
    check_and_extract_facts, load_chat_history, save_chat_history
)
from config.settings import get_telegram_token, get_authorized_user_ids
from core.logger import logger

llm_router = LLMRouter()
two_fc_engine = ConfirmationEngine()

SESSION_HISTORIES: Dict[str, List[Dict[str, str]]] = {}
MAX_HISTORY_TURNS = 10
_history_lock = threading.Lock()


def get_session_history(session_id: str = "default") -> List[Dict[str, str]]:
    with _history_lock:
        if session_id not in SESSION_HISTORIES:
            SESSION_HISTORIES[session_id] = load_chat_history(session_id)
        return list(SESSION_HISTORIES[session_id])


TOOL_SCHEMAS = """
AVAILABLE SYSTEM TOOLS:
You can control the user's PC by returning a JSON tool call block in your response if the user requests an action:
```json
{"tool": "start_continuous_chat", "args": {"app": "whatsapp", "recipient": "contact_name"}}
{"tool": "stop_continuous_chat", "args": {"recipient": "contact_name"}}
{"tool": "reply_to_chat_user", "args": {"app": "whatsapp", "recipient": "contact_name", "instructions": "reply warm and friendly"}}
{"tool": "send_app_message", "args": {"app": "whatsapp", "recipient": "contact_name", "message": "message_text"}}
{"tool": "locate_element", "args": {"target": "blue color plus button"}}
{"tool": "click_and_inspect", "args": {"target": "blue color plus button"}}
{"tool": "read_screen", "args": {"prompt": "Describe what is on my screen in detail"}}
{"tool": "open_app_or_website", "args": {"target": "app_name_or_url"}}
{"tool": "close_app", "args": {"target": "app_name"}}
{"tool": "focus_window", "args": {"target": "app_name"}}
{"tool": "type_text", "args": {"text": "message text", "target": "chat box or input field name", "press_enter": true}}
{"tool": "set_volume", "args": {"level": 50}}
{"tool": "mute_volume", "args": {"mute": true}}
{"tool": "take_screenshot", "args": {}}
```
RULES:
1. If the user asks to "continue chatting with X", "keep chatting with X", "auto chat daemon for X", "start chatting with X", return ONLY `start_continuous_chat`.
2. If the user asks to "stop chatting with X", "stop talking to X", "terminate chat with X", "stop auto reply for X", return ONLY `stop_continuous_chat`.
3. If the user asks to "reply to X", "respond to X", "check if X replied and respond", return ONLY `reply_to_chat_user`.
4. If the user asks to open an app (like WhatsApp, Telegram, Discord, etc.) AND text/message someone (e.g. "open whatsapp, text Tanusree telling about you"), return ONLY `send_app_message`.
5. If the user asks to type/enter text into a specific chat, input field, or search bar (e.g. "in Google Meet chat type X"), ALWAYS specify `"target"` in `type_text` so Friday clicks into that box first!
6. If the user asks "can you see X on my screen", "do you see X", "find X", return ONLY `locate_element` (or `read_screen`).
7. If the user asks to OPEN, LAUNCH, START an app/website or GO TO a site, return ONLY `open_app_or_website`.
8. WEB RESEARCH POLICY: If the user asks about current information, recent news, latest products, software/API versions, prices, websites, or entities/projects/companies you are not 100% certain of (such as Prodex Studio, specific domain names, recent AI releases), perform a web search to verify facts before answering!
"""


def get_system_status_summary() -> Dict[str, str]:
    """Retrieves live status of LLM Provider, Automation Engine, and Telegram Bot."""
    provider_name, model_name = llm_router.get_active_provider_info()
    llm_status = f"{provider_name} ({model_name})" if provider_name != "None" else "Not Configured"

    apps_cache = load_known_apps()
    total_apps = apps_cache.get("_meta", {}).get("total_apps", 0)
    auto_status = f"Active ({total_apps} apps indexed)"

    tg_token = get_telegram_token()
    user_ids = get_authorized_user_ids()
    try:
        from connectors.telegram_bot import is_telegram_running
        tg_running = is_telegram_running()
    except Exception:
        tg_running = False

    if not tg_token:
        tg_status = "Token Missing"
    elif tg_running:
        tg_status = "Active (Running in background)"
    else:
        tg_status = f"Configured (Whitelisted User: {user_ids[0] if user_ids else 'All'})"

    return {
        "llm": llm_status,
        "automation": auto_status,
        "telegram": tg_status
    }


def execute_tool_call(tool_name: str, args: Dict[str, Any]) -> str:
    """Executes local Python function based on LLM tool selection."""
    try:
        if tool_name == "start_continuous_chat":
            app = args.get("app", "whatsapp")
            recip = args.get("recipient", "")
            from tools.chat_daemon import start_continuous_chat
            res = start_continuous_chat(app, recip)
            return res["message"]
        elif tool_name == "stop_continuous_chat":
            recip = args.get("recipient", "")
            from tools.chat_daemon import stop_continuous_chat
            res = stop_continuous_chat(recip)
            return res["message"]
        elif tool_name == "reply_to_chat_user":
            app = args.get("app", "whatsapp")
            recip = args.get("recipient", "")
            instr = args.get("instructions", "")
            from tools.app_automation import reply_to_chat_message
            res = reply_to_chat_message(app, recip, instr)
            return res["message"]
        elif tool_name == "send_app_message":
            app = args.get("app", "whatsapp")
            recip = args.get("recipient", "")
            msg = args.get("message", "")
            from tools.app_automation import send_app_message
            res = send_app_message(app, recip, msg)
            return res["message"]
        elif tool_name == "locate_element":
            target = args.get("target", "element")
            res = locate_ui_element(target)
            return res["message"]
        elif tool_name == "click_and_inspect":
            target = args.get("target")
            res = click_and_inspect_result(target)
            return res["message"]
        elif tool_name == "read_screen":
            p = args.get("prompt", "Describe what is on my screen in detail.")
            res = analyze_screen_with_vision(prompt=p)
            return res["message"]
        elif tool_name == "open_app_or_website":
            target = args.get("target", "").strip()
            res = open_application(target)
            return res["message"]
        elif tool_name == "close_app":
            target = args.get("target", "").strip()
            res = close_application(target)
            return res["message"]
        elif tool_name == "focus_window":
            target = args.get("target", "").strip()
            res = focus_application(target)
            return res["message"]
        elif tool_name == "move_mouse":
            x = int(args.get("x", 500))
            y = int(args.get("y", 500))
            res = move_mouse(x, y)
            return res["message"]
        elif tool_name == "click_mouse":
            x = args.get("x")
            y = args.get("y")
            res = click(x=int(x) if x is not None else None, y=int(y) if y is not None else None)
            return res["message"]
        elif tool_name == "type_text":
            txt = args.get("text", "")
            target_field = args.get("target") or args.get("field") or args.get("input")
            press_ent = bool(args.get("press_enter", False))
            res = type_text(txt, press_enter=press_ent, target=target_field)
            return res["message"]
        elif tool_name == "set_volume":
            level = int(args.get("level", 50))
            res = set_volume(level)
            return res["message"]
        elif tool_name == "mute_volume":
            mute = bool(args.get("mute", True))
            res = toggle_mute(mute)
            return res["message"]
        elif tool_name == "take_screenshot":
            res = capture_screen("screenshot_temp.png")
            if res.get("success"):
                return f"[SCREENSHOT:{res['path']}] 📸 Screenshot captured successfully!"
            return f"Failed to capture screenshot: {res.get('message')}"
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return f"Tool execution failed: {e}"
    return "Unknown tool request."


def has_action_intent(user_text: str) -> bool:
    """
    Validates if the user's input expresses a command, action intent, or follow-up request.
    Prevents false-positive tool executions when the user is simply chatting.
    """
    clean = re.sub(r"[^\w\s]", "", user_text.lower()).strip()
    if not clean or len(clean.split()) == 0:
        return False
    
    # Action verbs and follow-up intent patterns
    action_pattern = r"\b(open|launch|start|run|play|go|close|quit|focus|click|locate|find|see|read|scan|mute|unmute|volume|screenshot|take|type|move|press|look|check|show|now|again|about|reply|respond|answer|text|message|continue|chat|chatting|talk|talking|stop)\b"
    return bool(re.search(action_pattern, clean))


def extract_json_tool_payload(llm_output: str) -> Tuple[Optional[str], Dict[str, Any]]:
    """Extracts valid tool_name and args dict from any LLM output (fenced or unfenced)."""
    # 1. Try markdown fenced JSON first
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", llm_output, re.DOTALL)
    if fenced_match:
        try:
            data = json.loads(fenced_match.group(1).strip())
            if isinstance(data, dict) and "tool" in data:
                return data.get("tool"), data.get("args", {})
        except Exception:
            pass

    # 2. Extract JSON block by brace stack tracking
    start_idx = llm_output.find('{"tool"')
    if start_idx == -1:
        start_idx = llm_output.find('{ "tool"')
    if start_idx == -1:
        start_idx = llm_output.find("{\n  \"tool\"")

    if start_idx != -1:
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(llm_output)):
            ch = llm_output[i]
            if ch == '{':
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break

        if end_idx != -1:
            try:
                json_str = llm_output[start_idx:end_idx].strip()
                data = json.loads(json_str)
                if isinstance(data, dict) and "tool" in data:
                    return data.get("tool"), data.get("args", {})
            except Exception:
                pass

    return None, {}


def clean_llm_response_text(llm_output: str) -> str:
    """Strips JSON tool blocks cleanly using stack tracking leaving clean LLM text."""
    txt = re.sub(r"```(?:json)?\s*\{.*?\}\s*```", "", llm_output, flags=re.DOTALL)
    
    start_idx = txt.find('{"tool"')
    if start_idx == -1:
        start_idx = txt.find('{ "tool"')
    if start_idx == -1:
        start_idx = txt.find("{\n  \"tool\"")

    if start_idx != -1:
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(txt)):
            ch = txt[i]
            if ch == '{':
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        if end_idx != -1:
            txt = txt[:start_idx] + txt[end_idx:]

    txt = re.sub(r"\[ACTION:\s*.*?\]", "", txt)
    return txt.strip()


def has_typing_intent(user_text: str) -> bool:
    """Returns True ONLY if user explicitly asked to type, enter, write, paste, or send text."""
    clean = re.sub(r"[^\w\s]", "", user_text.lower()).strip()
    return bool(re.search(r"\b(type|enter|write|send|input|paste|fill|put|say)\b", clean))


def parse_and_run_llm_tool_json(llm_output: str, user_text: str = "") -> Tuple[bool, str]:
    """Detects and parses JSON tool blocks from LLM responses dynamically."""
    tool_name, args = extract_json_tool_payload(llm_output)

    # If a valid tool call was generated
    if tool_name:
        # STRICT TYPING GUARD: Never execute type_text unless user explicitly requested typing/writing!
        if tool_name == "type_text" and user_text and not has_typing_intent(user_text):
            is_vision_query = bool(re.search(r"\b(can u see|can you see|do u see|do you see|is .* open|check if|where is|what is on)\b", user_text.lower()))
            if is_vision_query:
                res = analyze_screen_with_vision(prompt=user_text)
                return True, res["message"]
            clean_txt = clean_llm_response_text(llm_output)
            return False, clean_txt if clean_txt else "I'm standing by!"

        # Execute tool if user text expresses action/follow-up intent OR if it's a vision/read_screen call
        if not user_text or has_action_intent(user_text) or tool_name in ["read_screen", "take_screenshot"]:
            result = execute_tool_call(tool_name, args)
            return True, result
        else:
            # Casual chat where LLM hallucinated an unwanted app tool call
            clean_txt = clean_llm_response_text(llm_output)
            return False, clean_txt if clean_txt else "I'm standing by!"

    # Legacy action tag fallback
    action_match = re.search(r"\[ACTION:\s*([a-zA-Z0-9\_\-\s\:\.\/]+)\]", llm_output)
    if action_match:
        raw_act = action_match.group(1).strip()
        if raw_act.startswith("open "):
            target = raw_act.replace("open ", "").strip()
            res = open_application(target)
            return True, res["message"]
        elif "read screen" in raw_act or "screen" in raw_act:
            res = analyze_screen_with_vision()
            return True, res["message"]

    # Normal conversational output
    clean_txt = clean_llm_response_text(llm_output)
    return False, clean_txt if clean_txt else llm_output.strip()


def _build_budgeted_messages(system_prompt: str, user_text: str, history: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Builds LLM messages array enforcing history message count & character budget limits.
    - System prompt is included at index 0.
    - Current user message is ALWAYS preserved in full at the final position.
    - History items are included from newest back to oldest while staying within budget.
    """
    messages = [{"role": "system", "content": system_prompt}]

    valid_history = []
    for item in history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            r = str(item["role"]).strip()
            c = str(item["content"]).strip()
            if r in ["user", "assistant", "system"] and c:
                valid_history.append({"role": r, "content": c})

    # Limit history to at most 10 recent messages (5 turns)
    if len(valid_history) > 10:
        valid_history = valid_history[-10:]

    # Ensure valid turn sequence (don't start with orphaned assistant response)
    if valid_history and valid_history[0]["role"] == "assistant" and len(valid_history) > 1:
        valid_history = valid_history[1:]

    # Enforce character budget for history (~20,000 chars)
    total_chars = sum(len(m["content"]) for m in valid_history)
    max_history_chars = 20000

    while valid_history and total_chars > max_history_chars:
        if len(valid_history) >= 2:
            removed1 = valid_history.pop(0)
            total_chars -= len(removed1["content"])
            if valid_history and valid_history[0]["role"] == "assistant":
                removed2 = valid_history.pop(0)
                total_chars -= len(removed2["content"])
        else:
            removed = valid_history.pop(0)
            total_chars -= len(removed["content"])

    for m in valid_history:
        messages.append(m)

    safe_text = str(user_text)
    messages.append({"role": "user", "content": safe_text})

    return messages


def process_user_input(user_text: str, session_id: str = "default") -> str:
    """
    Backward-compatible entry point for existing callers (Telegram, Terminal, WebRTC, GUI).
    Returns a plain text response string.
    """
    meta = process_user_input_with_metadata(user_text, session_id=session_id)
    return meta.get("response", "")


def process_user_input_with_metadata(user_text: str, session_id: str = "default") -> Dict[str, Any]:
    """
    Unified Pipeline returning structured metadata (response text, sources list, web state flags).
    """
    if is_panic_active():
        return {
            "response": "🚨 Friday is currently in Emergency Panic Lockdown. System commands are disabled.",
            "sources": [],
            "used_web": False,
            "web_requested": False,
            "web_failed": False
        }

    # 1. Active 2FC validation check
    confirm_res = two_fc_engine.process_response(user_text)
    if confirm_res["active"]:
        if confirm_res["confirmed"]:
            action_data = confirm_res["action"]
            action_type = action_data["action_type"]
            target = action_data["target"]
            if action_type == "close_app":
                res = close_application(target)
                return {
                    "response": f"✅ Confirmed: {res['message']}",
                    "sources": [],
                    "used_web": False,
                    "web_requested": False,
                    "web_failed": False
                }
        return {
            "response": confirm_res["message"],
            "sources": [],
            "used_web": False,
            "web_requested": False,
            "web_failed": False
        }

    # 2. Check and extract user identity/facts into user.md memory
    check_and_extract_facts(user_text)

    # Check for 2FC triggers manually if command matches dangerous keywords
    lower_text = user_text.lower().strip()
    if lower_text.startswith("close "):
        target_app = lower_text.replace("close ", "").strip()
        msg = two_fc_engine.create_pending_confirmation("close_app", target_app, {})
        return {
            "response": msg,
            "sources": [],
            "used_web": False,
            "web_requested": False,
            "web_failed": False
        }

    # 3. Pass input to LLM with Tool Schemas & Web Policy
    system_prompt = build_system_prompt() + "\n" + TOOL_SCHEMAS
    history = get_session_history(session_id)
    messages = _build_budgeted_messages(system_prompt, user_text, history)
    safe_text = str(user_text)

    try:
        res_meta = llm_router.chat_with_metadata(messages, temperature=0.2)
        llm_output = res_meta.get("content", "")
        sources = res_meta.get("sources", [])
        used_web = res_meta.get("used_web", False)
        web_requested = res_meta.get("web_requested", False)
        web_failed = res_meta.get("web_failed", False)

        # Detect if LLM issued a Function Tool Call or Normal Convo Response
        is_tool, response = parse_and_run_llm_tool_json(llm_output, user_text=user_text)

        safe_response = str(response) if response is not None else ""
        if safe_text.strip() and safe_response.strip():
            with _history_lock:
                if session_id not in SESSION_HISTORIES:
                    SESSION_HISTORIES[session_id] = load_chat_history(session_id)
                session_hist = SESSION_HISTORIES[session_id]
                session_hist.append({"role": "user", "content": safe_text})
                session_hist.append({"role": "assistant", "content": safe_response})

                if len(session_hist) > MAX_HISTORY_TURNS * 2:
                    session_hist = session_hist[-MAX_HISTORY_TURNS * 2:]
                    SESSION_HISTORIES[session_id] = session_hist

                save_chat_history(session_hist, session_id=session_id)

        return {
            "response": safe_response,
            "sources": sources if not is_tool else [],
            "used_web": used_web if not is_tool else False,
            "web_requested": web_requested,
            "web_failed": web_failed
        }
    except Exception as e:
        logger.error(f"Error in Friday agent processing loop: {e}")
        return {
            "response": f"I encountered an error processing your request: {e}",
            "sources": [],
            "used_web": False,
            "web_requested": False,
            "web_failed": True
        }
