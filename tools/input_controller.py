"""
tools/input_controller.py - PyAutoGUI & Low-Level Mouse/Keyboard Controller for Friday AI
"""
import time
import pyautogui
from core.logger import logger

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


def move_mouse(x: int, y: int, duration: float = 0.5) -> dict:
    """Moves mouse cursor smoothly to target (x, y) screen coordinates."""
    try:
        pyautogui.moveTo(x=x, y=y, duration=duration)
        return {"success": True, "message": f"Moved mouse cursor to ({x}, {y}) 🖱️"}
    except Exception as e:
        return {"success": False, "message": f"Mouse move failed: {e}"}


def click(x: int = None, y: int = None, double: bool = False, right: bool = False) -> dict:
    """Clicks at coordinates or current mouse position."""
    try:
        button = "right" if right else "left"
        clicks = 2 if double else 1
        if x is not None and y is not None:
            pyautogui.click(x=x, y=y, clicks=clicks, button=button)
            return {"success": True, "message": f"Clicked ({x}, {y}) 🖱️"}
        else:
            pyautogui.click(clicks=clicks, button=button)
            return {"success": True, "message": "Clicked current mouse position 🖱️"}
    except Exception as e:
        return {"success": False, "message": f"Click action failed: {e}"}


def type_text(text: str, interval: float = 0.01, press_enter: bool = False, target: str = None) -> dict:
    """Types text using fast clipboard paste or keyboard simulation with optional target focusing & Enter press."""
    try:
        if target:
            from tools.screen_vision import click_and_inspect_result
            click_res = click_and_inspect_result(target)
            if not click_res.get("success"):
                return {
                    "success": False,
                    "message": f"❌ Could not locate target input box '{target}' on screen. Please make sure the window or chat box is visible before typing!"
                }
            time.sleep(0.2)

        try:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        except Exception:
            pyautogui.write(text, interval=interval)

        if press_enter:
            time.sleep(0.1)
            pyautogui.press("enter")
            return {"success": True, "message": f"Focused '{target}' and typed '{text}' (pressed Enter) ⌨️" if target else f"Typed '{text}' and pressed Enter ⌨️"}
        return {"success": True, "message": f"Focused '{target}' and typed '{text}' ⌨️" if target else f"Typed '{text}' ⌨️"}
    except Exception as e:
        return {"success": False, "message": f"Type action failed: {e}"}


def press_hotkey(*keys: str) -> dict:
    """Presses key combination (e.g. 'ctrl', 'c' or 'win', 'r')."""
    try:
        pyautogui.hotkey(*keys)
        return {"success": True, "message": f"Pressed hotkey: {'+'.join(keys)} ⌨️"}
    except Exception as e:
        return {"success": False, "message": f"Hotkey action failed: {e}"}
