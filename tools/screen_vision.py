"""
tools/screen_vision.py - High-Precision Windows OCR & Color Computer Vision Engine for Friday AI
Features multi-scale upscaling, dual phrase/word bounding box extraction, patch color classification,
and fuzzy matching for maximum recognition accuracy.
"""
import asyncio
import base64
import concurrent.futures
import difflib
import re
import time
import mss
import mss.tools
from pathlib import Path
from PIL import Image, ImageEnhance
import winocr
from config.settings import TEMP_DIR
from tools.input_controller import click
from core.logger import logger

LAST_LOCATED_COORDS = None
LAST_LOCATED_LABEL = None


def run_async_safe(coro):
    """Executes an async coroutine safely whether an event loop is currently running in the thread or not."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: asyncio.run(coro))
            return future.result()
    else:
        return asyncio.run(coro)


def capture_screen(output_name: str = "screen.png") -> dict:
    """Captures monitor screenshot instantly using mss."""
    try:
        output_path = TEMP_DIR / output_name
        with mss.MSS() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(output_path))
        
        return {
            "success": True,
            "path": str(output_path),
            "width": monitor["width"],
            "height": monitor["height"]
        }
    except Exception as e:
        logger.error(f"❌ Screen capture failed: {e}")
        return {"success": False, "message": f"Screen capture failed: {e}"}


def classify_rgb(r: float, g: float, b: float) -> str:
    """Classifies an (r, g, b) value into human-perceivable color categories."""
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    delta = max_c - min_c

    if max_c < 55:
        return "dark"
    if delta < 25:
        if max_c > 190:
            return "white"
        return "gray"

    if r >= max(g, b) * 1.25:
        if g > r * 0.7:
            return "yellow"
        elif g > r * 0.35:
            return "orange"
        return "red"
    elif g >= max(r, b) * 1.15:
        return "green"
    elif b >= max(r, g) * 1.15:
        return "blue"
    elif r > 110 and b > 110 and g < 95:
        return "purple"

    return "neutral"


def get_patch_color_name(img: Image.Image, x: int, y: int, w: int, h: int) -> str:
    """Samples bounding box region to determine element/background color accurately."""
    try:
        img_w, img_h = img.size
        points = [
            (max(0, min(img_w - 1, x)), max(0, min(img_h - 1, y))),
            (max(0, min(img_w - 1, x + w)), max(0, min(img_h - 1, y))),
            (max(0, min(img_w - 1, x)), max(0, min(img_h - 1, y + h))),
            (max(0, min(img_w - 1, x + w)), max(0, min(img_h - 1, y + h))),
            (max(0, min(img_w - 1, x + w // 2)), max(0, min(img_h - 1, y + h // 2)))
        ]
        rgbs = []
        for px, py in points:
            p = img.getpixel((px, py))
            if isinstance(p, tuple) and len(p) >= 3:
                rgbs.append(p[:3])
        
        if not rgbs:
            return "neutral"

        avg_r = sum(p[0] for p in rgbs) / len(rgbs)
        avg_g = sum(p[1] for p in rgbs) / len(rgbs)
        avg_b = sum(p[2] for p in rgbs) / len(rgbs)

        return classify_rgb(avg_r, avg_g, avg_b)
    except Exception:
        return "neutral"


def clean_text_str(s: str) -> str:
    """Normalizes text by removing non-alphanumeric noise and extra spaces."""
    s = s.lower().strip()
    return re.sub(r"[^\w\s\+\-\/\.]", "", s).strip()


def run_win_ocr(image_path: str, scale: float = 1.5, enhance: bool = True) -> list:
    """
    Runs native Windows Media OCR with multi-scale upscaling & image enhancement.
    Extracts both full line phrases and single words with exact pixel-mapped coordinates.
    """
    try:
        raw_img = Image.open(image_path)
        
        if enhance and scale != 1.0:
            w, h = raw_img.size
            new_size = (int(w * scale), int(h * scale))
            proc_img = raw_img.resize(new_size, Image.Resampling.LANCZOS)
            proc_img = ImageEnhance.Contrast(proc_img).enhance(1.25)
            proc_img = ImageEnhance.Sharpness(proc_img).enhance(1.2)
        else:
            proc_img = raw_img
            scale = 1.0

        ocr_result = run_async_safe(winocr.recognize_pil(proc_img))
        elements_data = []

        for line in ocr_result.lines:
            if not line.words:
                continue

            # Compute bounding rect for full line from words
            l_min_x = min(w.bounding_rect.x for w in line.words)
            l_min_y = min(w.bounding_rect.y for w in line.words)
            l_max_x = max(w.bounding_rect.x + w.bounding_rect.width for w in line.words)
            l_max_y = max(w.bounding_rect.y + w.bounding_rect.height for w in line.words)

            lx = int(l_min_x / scale)
            ly = int(l_min_y / scale)
            lw = int((l_max_x - l_min_x) / scale)
            lh = int((l_max_y - l_min_y) / scale)
            lcx = int(((l_min_x + l_max_x) / 2) / scale)
            lcy = int(((l_min_y + l_max_y) / 2) / scale)
            
            line_text = line.text.strip()
            clean_line = clean_text_str(line_text)
            if clean_line:
                color_name = get_patch_color_name(raw_img, lx, ly, lw, lh)
                elements_data.append({
                    "is_phrase": True,
                    "text": line_text,
                    "clean": clean_line,
                    "cx": lcx,
                    "cy": lcy,
                    "x": lx,
                    "y": ly,
                    "w": lw,
                    "h": lh,
                    "color": color_name
                })

            for word in line.words:
                wb = word.bounding_rect
                wx = int(wb.x / scale)
                wy = int(wb.y / scale)
                ww = int(wb.width / scale)
                wh = int(wb.height / scale)
                wcx = int((wb.x + wb.width / 2) / scale)
                wcy = int((wb.y + wb.height / 2) / scale)
                
                word_text = word.text.strip()
                clean_word = clean_text_str(word_text)
                if clean_word:
                    w_color = get_patch_color_name(raw_img, wx, wy, ww, wh)
                    elements_data.append({
                        "is_phrase": False,
                        "text": word_text,
                        "clean": clean_word,
                        "cx": wcx,
                        "cy": wcy,
                        "x": wx,
                        "y": wy,
                        "w": ww,
                        "h": wh,
                        "color": w_color
                    })

        return elements_data
    except Exception as e:
        logger.error(f"Error running winocr: {e}")
        return []


def score_element_match(clean_target: str, elem_clean: str, requested_color: str, elem_color: str, is_phrase: bool) -> float:
    """Computes a match score (0 - 100) between user target query and OCR element."""
    if not elem_clean or not clean_target:
        return 0.0

    score = 0.0

    # 1. Exact match
    if clean_target == elem_clean:
        score = 100.0
    # 2. Substring containment
    elif clean_target in elem_clean:
        len_ratio = len(clean_target) / len(elem_clean)
        score = 85.0 + (len_ratio * 10.0)
    elif elem_clean in clean_target and len(elem_clean) >= 3:
        len_ratio = len(elem_clean) / len(clean_target)
        score = 80.0 + (len_ratio * 10.0)
    # 3. Fuzzy Sequence Matching
    else:
        seq_ratio = difflib.SequenceMatcher(None, clean_target, elem_clean).ratio()
        if seq_ratio >= 0.70:
            score = seq_ratio * 85.0

    # Plus / Add special cases
    if clean_target in ["plus", "+", "add", "create", "new"] and elem_clean in ["+", "add", "create", "new", "plus"]:
        score = max(score, 95.0)

    # Mic / Audio / Mute special cases
    if any(k in clean_target for k in ["mic", "microphone", "audio", "voice", "mute", "unmute", "talk", "speaker"]) and \
       any(k in elem_clean for k in ["mic", "microphone", "audio", "voice", "mute", "unmute", "talk", "speaker"]):
        score = max(score, 95.0)

    if score < 50.0:
        return 0.0

    # Bonus for multi-word phrase matching
    if is_phrase and " " in clean_target:
        score += 8.0

    # Color match adjustment
    if requested_color:
        if elem_color == requested_color or (requested_color in ["blue", "dark"] and elem_color != "neutral"):
            score += 15.0
        elif elem_color != "neutral" and elem_color != requested_color:
            score -= 25.0

    return min(100.0, score)


def locate_ui_element(target_description: str) -> dict:
    """
    High-Precision UI Element Finder:
    Locates elements on screen by text or color using multi-scale OCR & fuzzy matching.
    Saves (x, y) coordinates for subsequent click actions!
    """
    global LAST_LOCATED_COORDS, LAST_LOCATED_LABEL

    cap_res = capture_screen("ocr_locate.png")
    if not cap_res.get("success"):
        return {"success": False, "message": "Failed to capture screen."}

    # Pass 1: Enhanced 1.5x upscaled pass
    elements = run_win_ocr(cap_res["path"], scale=1.5, enhance=True)

    # Pass 2: Fallback to 1.0x native pass if pass 1 produced no items
    if not elements:
        elements = run_win_ocr(cap_res["path"], scale=1.0, enhance=False)

    if not elements:
        return {"success": False, "message": "No readable elements or text detected on screen."}

    query_lower = target_description.lower().strip()

    requested_color = None
    for color in ["blue", "red", "green", "yellow", "orange", "purple", "dark", "white", "gray"]:
        if color in query_lower:
            requested_color = color
            break

    clean_target = clean_text_str(query_lower)
    if requested_color:
        clean_target = clean_text_str(
            clean_target.replace(requested_color, "").replace("color", "").replace("coloured", "").replace("button", "").replace("icon", "")
        )

    if not clean_target and requested_color:
        clean_target = requested_color

    best_match = None
    best_score = 0.0

    for el in elements:
        s = score_element_match(clean_target, el["clean"], requested_color, el["color"], el["is_phrase"])
        if s > best_score:
            best_score = s
            best_match = el

    if best_match and best_score >= 50.0:
        x, y = best_match["cx"], best_match["cy"]
        LAST_LOCATED_COORDS = (x, y)
        LAST_LOCATED_LABEL = best_match["text"]
        color_str = f" ({best_match['color']})" if best_match['color'] != "neutral" else ""
        return {
            "success": True,
            "coords": (x, y),
            "label": best_match["text"],
            "message": f"Yes! I located the '{best_match['text']}' element{color_str} at coordinates ({x}, {y}) on your screen."
        }

    # Fallback suggestion list from phrase elements
    phrases = [el["text"] for el in elements if el["is_phrase"] and len(el["text"]) > 2]
    unique_phrases = list(dict.fromkeys(phrases))[:8]
    summary_str = ", ".join(unique_phrases) if unique_phrases else "None"

    return {
        "success": False,
        "coords": None,
        "label": target_description,
        "message": f"I scanned the screen but couldn't locate '{target_description}'. Visible text elements include: {summary_str}."
    }


def click_and_inspect_result(target_description: str = None) -> dict:
    """
    Action + Re-Perception Loop:
    1. Automatically locates target_description on screen if not already located.
    2. Clicks at coordinates (x, y).
    3. Re-captures screen and computes newly appeared text/elements!
    """
    global LAST_LOCATED_COORDS, LAST_LOCATED_LABEL

    coords = None
    label = target_description or LAST_LOCATED_LABEL or "element"

    if target_description:
        loc = locate_ui_element(target_description)
        if loc.get("success") and loc.get("coords"):
            coords = loc["coords"]
            label = loc.get("label", label)
        else:
            # Try stripping descriptors like 'button', 'icon', 'that'
            stripped = re.sub(r"\b(that|the|button|icon|tab|link|menu|option|box|field|input)\b", "", target_description, flags=re.IGNORECASE).strip()
            if stripped and stripped != target_description:
                loc = locate_ui_element(stripped)
                if loc.get("success") and loc.get("coords"):
                    coords = loc["coords"]
                    label = loc.get("label", label)

    if not coords:
        coords = LAST_LOCATED_COORDS

    if not coords:
        return {
            "success": False,
            "message": f"I scanned your screen but couldn't locate '{target_description or 'that button'}'. Make sure it is visible on screen!"
        }

    x, y = coords

    cap_before = capture_screen("screen_before.png")
    before_elements = set(el["clean"] for el in run_win_ocr(cap_before["path"], scale=1.5)) if cap_before.get("success") else set()

    click(x, y)
    time.sleep(0.5)

    cap_after = capture_screen("screen_after.png")
    if not cap_after.get("success"):
        return {"success": True, "message": f"🖱️ Clicked '{label}' at coordinates ({x}, {y})!"}

    after_elements = run_win_ocr(cap_after["path"], scale=1.5)
    new_phrases = [
        el["text"] for el in after_elements 
        if el["is_phrase"] and el["clean"] not in before_elements and len(el["text"]) > 1
    ]

    LAST_LOCATED_COORDS = None
    LAST_LOCATED_LABEL = None

    if new_phrases:
        appeared_str = ", ".join(list(dict.fromkeys(new_phrases))[:6])
        return {
            "success": True,
            "message": f"🖱️ **Clicked '{label}' at ({x}, {y})!**\n\n👁️ **UI Update:** New elements appeared: **{appeared_str}**."
        }

    return {
        "success": True,
        "message": f"🖱️ **Clicked '{label}' at ({x}, {y})!** Screen updated successfully."
    }


def get_active_window_title() -> str:
    """Returns the title of the active foreground window on Windows."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or "Unknown Window"
    except Exception:
        return "Unknown Window"


def analyze_screen_with_vision(prompt: str = "Describe what is currently visible on the screen in detail.") -> dict:
    """Scans screen with high-accuracy OCR and active window detection, then synthesizes a natural conversational description via LLM."""
    cap_res = capture_screen("screen_summary.png")
    if not cap_res.get("success"):
        return {"success": False, "message": "Failed to capture screen."}

    elements = run_win_ocr(cap_res["path"], scale=1.5, enhance=True)
    if not elements:
        elements = run_win_ocr(cap_res["path"], scale=1.0, enhance=False)

    if not elements:
        return {"success": False, "message": "I scanned your screen, but no text or open windows were detected."}

    phrase_texts = [el["text"] for el in elements if el["is_phrase"] and len(el["text"]) > 1]
    unique_phrases = list(dict.fromkeys(phrase_texts))[:20]
    active_title = get_active_window_title()

    screen_state_str = (
        f"Active Foreground Window: {active_title}\n"
        f"Visible Screen Text & Elements:\n- " + "\n- ".join(unique_phrases)
    )

    try:
        from llm.router import LLMRouter
        router = LLMRouter()
        synth_prompt = (
            f"The user asked: '{prompt}'\n\n"
            f"Here is the visual perception data captured from the user's PC screen:\n"
            f"--------------------------------------------------\n"
            f"{screen_state_str}\n"
            f"--------------------------------------------------\n\n"
            f"Synthesize a natural, human-friendly, concise response as Friday describing what is open and visible on the user's screen "
            f"(such as active applications, open websites like Spotify, active browser tabs, documents, or main windows). "
            f"Speak naturally in 1-3 conversational sentences as Friday. DO NOT print raw OCR lists or debug tags!"
        )
        description = router.chat([{"role": "user", "content": synth_prompt}], temperature=0.3)
        return {
            "success": True,
            "message": description.strip()
        }
    except Exception as e:
        logger.error(f"Failed to synthesize screen description: {e}")
        summary = "\n- ".join(unique_phrases[:10])
        return {
            "success": True,
            "message": f"Active Window: {active_title}\nVisible Elements:\n- {summary}"
        }
