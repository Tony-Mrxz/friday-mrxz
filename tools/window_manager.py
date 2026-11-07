"""
tools/window_manager.py - Win32 Window Management & Enumeration for Friday AI
"""
import sys
import psutil
from typing import List, Dict, Any
from core.logger import logger
from tools.apps import clean_app_key, load_known_apps

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import win32gui
    import win32process
    import win32con


def is_valid_gui_window(hwnd) -> bool:
    """Enforces Win32 filtering rules for visible user GUI app windows."""
    if not IS_WINDOWS:
        return True
    try:
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return False
        title = win32gui.GetWindowText(hwnd)
        if not title or not title.strip():
            return False
        if win32gui.GetWindow(hwnd, win32con.GW_OWNER) != 0:
            return False
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ex_style & win32con.WS_EX_TOOLWINDOW:
            return False
        rect = win32gui.GetWindowRect(hwnd)
        if (rect[2] - rect[0]) <= 0 or (rect[3] - rect[1]) <= 0:
            return False
        class_name = win32gui.GetClassName(hwnd).lower()
        if any(cls in class_name for cls in ["progman", "shell_traywnd", "button", "combo", "tooltip", "ime"]):
            return False
        if title.lower() in ["settings", "microsoft text input application", "program manager", "start"]:
            return False
        return True
    except Exception:
        return False


def enumerate_gui_applications() -> List[Dict[str, Any]]:
    """Enumerates all active visible GUI application windows."""
    if not IS_WINDOWS:
        return []

    focused_hwnd = win32gui.GetForegroundWindow()
    windows = []

    def enum_callback(hwnd, extra):
        if is_valid_gui_window(hwnd):
            title = win32gui.GetWindowText(hwnd)
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if not psutil.pid_exists(pid):
                    return True
                proc_name = ""
                try:
                    proc_name = psutil.Process(pid).name()
                except Exception:
                    pass

                state = "Focused" if hwnd == focused_hwnd else ("Minimized" if win32gui.IsIconic(hwnd) else "Visible")
                extra.append({
                    "hwnd": hwnd,
                    "title": title,
                    "pid": pid,
                    "proc_name": proc_name,
                    "state": state
                })
            except Exception:
                pass
        return True

    try:
        win32gui.EnumWindows(enum_callback, windows)
    except Exception as e:
        logger.error(f"❌ Error enumerating windows: {e}")

    return windows


def focus_application(app_query: str) -> Dict[str, Any]:
    """Brings matching application window to foreground focus."""
    if not IS_WINDOWS:
        return {"success": False, "message": "Window management is only available on Windows."}

    windows = enumerate_gui_applications()
    query_lower = app_query.strip().lower()

    match_win = None
    for win in windows:
        if query_lower in win["title"].lower() or query_lower in win["proc_name"].lower():
            match_win = win
            break

    if not match_win:
        return {"success": False, "message": f"No active window found for '{app_query}'."}

    hwnd = match_win["hwnd"]
    title = match_win["title"]

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try:
            win32gui.SetForegroundWindow(hwnd)
            return {"success": True, "message": f"Brought '{title}' to focus. 🖥️"}
        except Exception:
            win32gui.FlashWindow(hwnd, True)
            return {"success": True, "message": f"Flashed taskbar for '{title}' (OS focus restriction)."}
    except Exception as e:
        return {"success": False, "message": f"Failed to focus '{title}': {e}"}


def minimize_application(app_query: str) -> Dict[str, Any]:
    """Minimizes matching application window."""
    if not IS_WINDOWS:
        return {"success": False, "message": "Window management is only available on Windows."}

    windows = enumerate_gui_applications()
    query_lower = app_query.strip().lower()

    match_win = None
    for win in windows:
        if query_lower in win["title"].lower() or query_lower in win["proc_name"].lower():
            match_win = win
            break

    if not match_win:
        return {"success": False, "message": f"No active window found for '{app_query}'."}

    try:
        win32gui.ShowWindow(match_win["hwnd"], win32con.SW_MINIMIZE)
        return {"success": True, "message": f"Minimized '{match_win['title']}' window."}
    except Exception as e:
        return {"success": False, "message": f"Failed to minimize window: {e}"}
