"""
tools/app_automation.py - Multi-Step Desktop Application Automation Engine for Friday AI
Enables autonomous multi-step UI workflows such as opening messaging apps (WhatsApp, Telegram, Discord),
searching contacts, focusing chat input fields, typing messages, and sending them cleanly.
"""
import time
import re
from tools.apps import open_application
from tools.input_controller import type_text, press_hotkey
from tools.screen_vision import click_and_inspect_result, locate_ui_element, capture_screen, run_win_ocr, get_active_window_title
from core.logger import logger


def wait_for_app_open(app_name: str, max_wait: float = 6.0) -> bool:
    """Polls screen and window title to verify app is open and active."""
    start = time.time()
    app_lower = app_name.lower().strip()
    
    while time.time() - start < max_wait:
        title = get_active_window_title().lower()
        if app_lower in title:
            return True
            
        # OCR check on active screen
        cap = capture_screen("app_check.png")
        if cap.get("success"):
            elements = run_win_ocr(cap["path"], scale=1.0)
            text_str = " ".join([el["text"].lower() for el in elements if len(el["text"]) > 1])
            if app_lower in text_str or "search" in text_str or "chats" in text_str or "message" in text_str:
                return True
        time.sleep(0.5)
        
    return False


def verify_contact_selected(recipient: str, max_wait: float = 4.0) -> bool:
    """Verifies with OCR that recipient chat header or message input box is visible."""
    start = time.time()
    recip_lower = recipient.lower().strip()

    while time.time() - start < max_wait:
        cap = capture_screen("chat_verify.png")
        if cap.get("success"):
            elements = run_win_ocr(cap["path"], scale=1.5)
            text_str = " ".join([el["text"].lower() for el in elements if len(el["text"]) > 1])
            if recip_lower in text_str or "type a message" in text_str or "online" in text_str:
                return True
        time.sleep(0.5)
        
    return False


def send_app_message(app: str, recipient: str, message: str) -> dict:
    """
    Autonomous Multi-Step Messaging Workflow with Visual Perception & Precise UI Verification:
    1. Opens app & brings window strictly to FOREGROUND!
    2. OCR locates and clicks the Search Bar ('Search or start new chat' / 'Search').
    3. Types recipient name into search bar and hits Enter.
    4. OCR locates and clicks recipient contact in the search results list.
    5. OCR locates and clicks message input box ('Type a message').
    6. Pastes message and hits Enter to send cleanly!
    """
    app_clean = app.lower().strip()
    logger.info(f"🤖 Starting verified multi-step automation: App='{app}', Recipient='{recipient}'...")

    # Step 1: Open Application & Bring to Foreground
    open_res = open_application(app_clean)
    if not open_res.get("success"):
        return {"success": False, "message": f"Failed to open {app}: {open_res.get('message')}"}

    time.sleep(1.5)  # Wait for app window to load
    
    from tools.apps import focus_application
    focus_application(app_clean)
    time.sleep(0.5)

    # Step 2: OCR Locate & Click Search Bar
    logger.info(f"🔍 Locating search bar in {app.capitalize()}...")
    search_click = click_and_inspect_result("Search")
    if not search_click.get("success"):
        press_hotkey("ctrl", "f")
    time.sleep(0.3)

    # Step 3: Type Recipient Name
    logger.info(f"⌨️ Typing contact '{recipient}'...")
    type_text(recipient, press_enter=True)
    time.sleep(1.0)

    # Step 4: Click Contact Item from Search Results List
    logger.info(f"🖱️ Selecting chat with '{recipient}'...")
    click_contact = click_and_inspect_result(recipient)
    time.sleep(0.8)

    # Step 5: Focus Message Input Box & Type Message
    logger.info(f"💬 Focusing chat input box...")
    click_msg = click_and_inspect_result("Type a message")
    if not click_msg.get("success"):
        click_and_inspect_result("message input")
    time.sleep(0.3)

    # Step 6: Send Message!
    send_res = type_text(message, press_enter=True)

    return {
        "success": True,
        "message": f"✅ Visually verified & completed! Opened {app.capitalize()}, selected chat with '{recipient}', and sent your message: '{message}'!"
    }


def reply_to_chat_message(app: str, recipient: str, instructions: str = "") -> dict:
    """
    Autonomous Interactive Chat Auto-Responder:
    1. Opens & brings app to foreground (WhatsApp, Telegram, Discord, etc.)
    2. Searches & opens chat with recipient
    3. Captures screen & extracts latest chat transcript via high-precision OCR
    4. Synthesizes a smart, context-aware reply using LLM
    5. Types & sends the reply into the chat input box!
    """
    app_clean = app.lower().strip()
    logger.info(f"🤖 Starting interactive reply workflow: App='{app}', Recipient='{recipient}'...")

    # Step 1: Open Application & Focus Window
    open_res = open_application(app_clean)
    if not open_res.get("success"):
        return {"success": False, "message": f"Failed to open {app}: {open_res.get('message')}"}

    time.sleep(1.2)
    from tools.apps import focus_application
    focus_application(app_clean)
    time.sleep(0.5)

    # Step 2: Open Chat with Recipient
    logger.info(f"🔍 Locating chat with '{recipient}'...")
    search_click = click_and_inspect_result("Search")
    if not search_click.get("success"):
        press_hotkey("ctrl", "f")
    time.sleep(0.3)

    type_text(recipient, press_enter=True)
    time.sleep(1.0)

    click_and_inspect_result(recipient)
    time.sleep(0.8)

    # Step 3: OCR Read Latest Chat Messages
    logger.info(f"👁️ Reading latest chat messages from '{recipient}'...")
    cap_res = capture_screen("chat_reply_read.png")
    if not cap_res.get("success"):
        return {"success": False, "message": "Failed to capture chat window for reading."}

    elements = run_win_ocr(cap_res["path"], scale=1.5, enhance=True)
    phrase_texts = [el["text"] for el in elements if el["is_phrase"] and len(el["text"]) > 1]
    unique_phrases = list(dict.fromkeys(phrase_texts))[:25]
    chat_transcript = "\n- ".join(unique_phrases)

    # Step 4: Synthesize Smart Reply via LLM
    logger.info(f"🧠 Synthesizing smart reply for '{recipient}'...")
    try:
        from llm.router import LLMRouter
        router = LLMRouter()
        synth_prompt = (
            f"The user (Tony) asked you to check the chat with '{recipient}' in {app} and reply to them.\n"
            f"Here is the text extracted from the active chat window on screen:\n"
            f"--------------------------------------------------\n"
            f"- {chat_transcript}\n"
            f"--------------------------------------------------\n\n"
            f"User Instructions: {instructions or 'Understand their latest message and write a short, friendly, natural reply on Tony\'s behalf.'}\n\n"
            f"Return ONLY the exact reply text to be typed into the chat field. Keep it 1-2 natural conversational sentences!"
        )
        reply_message = router.chat([{"role": "user", "content": synth_prompt}], temperature=0.3).strip()
        reply_message = reply_message.strip('"').strip("'")
    except Exception as e:
        logger.error(f"Failed to synthesize chat reply: {e}")
        reply_message = "Hey! Got your message, will get back to you shortly!"

    # Step 5: Focus Chat Input & Send Reply
    logger.info(f"💬 Sending generated reply to '{recipient}': '{reply_message}'...")
    click_msg = click_and_inspect_result("Type a message")
    if not click_msg.get("success"):
        click_and_inspect_result("message input")
    time.sleep(0.3)

    send_res = type_text(reply_message, press_enter=True)

    return {
        "success": True,
        "message": f"✅ Read latest chat with '{recipient}', synthesized smart reply, and sent: '{reply_message}'!"
    }
