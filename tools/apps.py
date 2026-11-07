"""
tools/apps.py - Dynamic Application Indexing and Process Manager for Friday AI
Discovers Win32, UWP apps, and Windows Registry App Paths, parses shortcuts (.lnk),
manages a local JSON cache, resolves aliases, fuzzy-matches safely,
and verifies app spawns with URL parameters and website fallbacks.
"""
import os
import sys
import json
import re
import subprocess
import time
import datetime
import difflib
import webbrowser
from typing import Dict, Any, List, Tuple
import psutil
from config.settings import DATA_DIR
from core.logger import logger

IS_WINDOWS = sys.platform == "win32"
com_supported = False

if IS_WINDOWS:
    try:
        import win32com.client
        import winreg
        com_supported = True
    except Exception as e:
        logger.warning(f"⚠️ Pywin32 COM libraries failed to load: {e}")

CACHE_PATH = DATA_DIR / "known_apps.json"
SCHEMA_VERSION = 1

JUNK_KEYWORDS = [
    "uninstall", "updater", "helper", "install", "setup",
    "wizard", "uninst", "crashreporter", "diagnostics",
    "maintenance", "remove", "gud", "configuration"
]

KNOWN_WEBSITES = {
    # Social
    "instagram":  "https://www.instagram.com",
    "facebook":   "https://www.facebook.com",
    "twitter":    "https://www.twitter.com",
    "x":          "https://www.x.com",
    "reddit":     "https://www.reddit.com",
    "linkedin":   "https://www.linkedin.com",
    "pinterest":  "https://www.pinterest.com",
    "tiktok":     "https://www.tiktok.com",
    # Browsers
    "opera":      "https://www.opera.com",
    "chrome":     "https://www.google.com/chrome",
    "brave":      "https://www.brave.com",
    "edge":       "https://www.microsoft.com/edge",
    "firefox":    "https://www.mozilla.org/firefox",
    "zen":        "https://www.zen-browser.app",
    # Productivity
    "gmail":      "https://mail.google.com",
    "google":     "https://www.google.com",
    "drive":      "https://drive.google.com",
    "docs":       "https://docs.google.com",
    "sheets":     "https://sheets.google.com",
    "slides":     "https://slides.google.com",
    "calendar":   "https://calendar.google.com",
    "meet":       "https://meet.google.com",
    "notion":     "https://www.notion.so",
    "trello":     "https://www.trello.com",
    "figma":      "https://www.figma.com",
    # Entertainment
    "youtube":    "https://www.youtube.com",
    "netflix":    "https://www.netflix.com",
    "primevideo": "https://www.primevideo.com",
    "spotify":    "https://open.spotify.com",
    "soundcloud": "https://www.soundcloud.com",
    "twitch":     "https://www.twitch.tv",
    # Dev / Tech
    "github":     "https://www.github.com",
    "stackoverflow": "https://www.stackoverflow.com",
    "chatgpt":    "https://chat.openai.com",
    "claude":     "https://claude.ai",
    "gemini":     "https://gemini.google.com",
    # Shopping / Apps
    "amazon":     "https://www.amazon.in",
    "whatsapp":   "https://web.whatsapp.com",
    "telegram":   "https://web.telegram.org",
}


def resolve_lnk_shortcut(lnk_path: str) -> str:
    """Resolves the absolute target path of a Windows Start Menu shortcut (.lnk)."""
    if not IS_WINDOWS or not com_supported:
        return ""
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(lnk_path)
        target = shortcut.TargetPath
        if target:
            return os.path.expandvars(target)
    except Exception:
        pass
    return ""


def scan_windows_registry_app_paths() -> Dict[str, str]:
    """Scans HKLM and HKCU Windows App Paths registry keys for installed exes."""
    if not IS_WINDOWS:
        return {}

    app_paths = {}
    hkeys = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"

    for hkey in hkeys:
        try:
            with winreg.OpenKey(hkey, sub_key) as root_key:
                num_subkeys, _, _ = winreg.QueryInfoKey(root_key)
                for i in range(num_subkeys):
                    try:
                        key_name = winreg.EnumKey(root_key, i)
                        with winreg.OpenKey(root_key, key_name) as app_key:
                            exe_path, _ = winreg.QueryValueEx(app_key, "")
                            if exe_path:
                                clean_path = exe_path.strip('"').strip("'")
                                if os.path.exists(clean_path):
                                    app_paths[key_name.lower()] = clean_path
                    except Exception:
                        pass
        except Exception:
            pass

    return app_paths


def clean_app_key(name: str) -> str:
    """Normalizes an app name into a lowercase, alphanumeric standard key."""
    if not name:
        return ""
    return "".join(char for char in name.lower() if char.isalnum())


def generate_default_aliases(name: str) -> List[str]:
    """Generates user aliases for an app name."""
    aliases = []
    lower_name = name.lower()
    simple = lower_name.replace("google", "").replace("microsoft", "").strip()
    if simple and simple != lower_name:
        aliases.append(simple)
        
    if "visual studio code" in lower_name:
        aliases.extend(["vscode", "vs code", "code"])
    elif "google chrome" in lower_name:
        aliases.extend(["chrome", "google chrome", "browser"])
    elif "opera" in lower_name:
        aliases.extend(["opera", "opera browser", "operagx"])
    elif "whatsapp" in lower_name:
        aliases.extend(["whatsapp", "wa", "whats app"])
    elif "spotify" in lower_name:
        aliases.extend(["spotify", "music"])
    elif "calculator" in lower_name:
        aliases.extend(["calculator", "calc"])
    elif "command prompt" in lower_name:
        aliases.extend(["cmd", "terminal"])
    elif "powershell" in lower_name:
        aliases.extend(["powershell", "ps"])
        
    return list(set(aliases))


def discover_installed_apps(force: bool = False) -> Dict[str, Any]:
    """Scans Start Menu, UWP apps, and Windows Registry App Paths."""
    if not IS_WINDOWS:
        return {}

    logger.info("🔍 Scanning Windows StartApps, UWP, and Registry App Paths...")
    start_time = time.perf_counter()
    discovered = {}

    try:
        ps_cmd = "Get-StartApps | ConvertTo-Json -Compress"
        process = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        
        raw_apps = []
        if process.returncode == 0 and stdout.strip():
            parsed = json.loads(stdout.strip())
            raw_apps = parsed if isinstance(parsed, list) else [parsed]

        for app in raw_apps:
            name = app.get("Name", "").strip()
            app_id = app.get("AppID", "").strip()
            if not name or not app_id:
                continue

            name_lower = name.lower()
            app_id_lower = app_id.lower()
            if any(junk in name_lower or junk in app_id_lower for junk in JUNK_KEYWORDS):
                continue

            app_key = clean_app_key(name)
            if not app_key:
                continue

            if "!" in app_id or (not os.path.exists(app_id) and not app_id.endswith(".lnk") and not app_id.endswith(".exe")):
                discovered[app_key] = {
                    "name": name,
                    "type": "uwp",
                    "source": "uwp",
                    "app_id": app_id,
                    "aliases": generate_default_aliases(name),
                    "launch_count": 0,
                    "last_used": None
                }
            else:
                lnk_path = app_id
                target_path = lnk_path
                if lnk_path.lower().endswith(".lnk") and os.path.exists(lnk_path):
                    target_path = resolve_lnk_shortcut(lnk_path)

                if not target_path or not target_path.lower().endswith(".exe") or not os.path.exists(target_path):
                    continue

                if any(junk in target_path.lower() for junk in JUNK_KEYWORDS):
                    continue

                discovered[app_key] = {
                    "name": name,
                    "type": "exe",
                    "source": "start_menu",
                    "path": target_path,
                    "aliases": generate_default_aliases(name),
                    "launch_count": 0,
                    "last_used": None
                }

        reg_apps = scan_windows_registry_app_paths()
        for exe_name, full_path in reg_apps.items():
            base_name = exe_name.replace(".exe", "").capitalize()
            app_key = clean_app_key(base_name)
            if app_key and app_key not in discovered:
                discovered[app_key] = {
                    "name": base_name,
                    "type": "exe",
                    "source": "registry",
                    "path": full_path,
                    "aliases": generate_default_aliases(base_name),
                    "launch_count": 0,
                    "last_used": None
                }

        meta = {
            "schema_version": SCHEMA_VERSION,
            "last_indexed": datetime.datetime.now().isoformat(),
            "total_apps": len(discovered)
        }
        cache_data = {"_meta": meta}
        cache_data.update(discovered)

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=4)

        elapsed = time.perf_counter() - start_time
        logger.info(f"✅ Friday indexed {len(discovered)} applications in {elapsed:.3f}s.")
        return cache_data

    except Exception as e:
        logger.error(f"❌ Application discovery failed: {e}")
        return {}


def load_known_apps() -> Dict[str, Any]:
    """Loads apps from cache or triggers scan."""
    if not CACHE_PATH.exists():
        return discover_installed_apps(force=True)

    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("_meta", {}).get("schema_version") != SCHEMA_VERSION:
            return discover_installed_apps(force=True)
        return data
    except Exception:
        return discover_installed_apps(force=True)


def match_application(query: str) -> Tuple[str, Dict[str, Any], List[Tuple[str, str]]]:
    """Fuzzy matches query to indexed app."""
    apps_cache = load_known_apps()
    norm_query = clean_app_key(query)
    if not norm_query:
        return "none", {}, []

    keys = [k for k in apps_cache.keys() if k != "_meta"]

    if norm_query in keys:
        return "exact", apps_cache[norm_query], []

    exact_matches = []
    for k in keys:
        app = apps_cache[k]
        app_name = app.get("name", "").lower()
        aliases = [a.lower() for a in app.get("aliases", [])]
        if query.lower() in aliases or norm_query == clean_app_key(app_name):
            exact_matches.append((k, app))

    if len(exact_matches) == 1:
        return "alias", exact_matches[0][1], []
    elif len(exact_matches) > 1:
        candidates = [(k, exact_matches[i][1].get("name")) for i, (k, _) in enumerate(exact_matches)]
        return "ambiguous", {}, candidates

    match_pool = []
    pool_map = {}
    for k in keys:
        app = apps_cache[k]
        name = app.get("name", "")
        match_pool.append(name)
        pool_map[name.lower()] = k
        for alias in app.get("aliases", []):
            match_pool.append(alias)
            pool_map[alias.lower()] = k

    close_matches = difflib.get_close_matches(query, match_pool, n=5, cutoff=0.7)
    if close_matches:
        matched_keys = list(set(pool_map[m.lower()] for m in close_matches if m.lower() in pool_map))
        if len(matched_keys) == 1:
            return "fuzzy", apps_cache[matched_keys[0]], []
        elif len(matched_keys) > 1:
            candidates = [(k, apps_cache[k].get("name")) for k in matched_keys]
            return "ambiguous", {}, candidates

    return "none", {}, []


def open_application(app_query: str) -> Dict[str, Any]:
    """
    Opens a desktop app, UWP app, or website.
    Handles browser launching directly with target URL parameters!
    """
    raw_query = app_query.strip()

    # Clean leading verbs
    clean_query = re.sub(r"^(?:open|launch|start|head\s+to|go\s+to)\s+", "", raw_query, flags=re.IGNORECASE).strip()
    target_lower = clean_query.lower()

    # Handle compound patterns like 'opera and head to youtube', 'youtube in opera', 'opera to youtube'
    target_url = ""
    browser_query = clean_query

    if any(sep in target_lower for sep in [" and ", " in ", " to ", " on "]):
        parts = re.split(r"\b(?:and\s+head\s+to|and\s+go\s+to|and\s+open|and|in|to|on)\b", clean_query, flags=re.IGNORECASE)
        if len(parts) >= 2:
            part1 = parts[0].strip()
            part2 = parts[1].strip()
            if part2.lower() in KNOWN_WEBSITES or "." in part2:
                browser_query = part1
                target_url = KNOWN_WEBSITES.get(part2.lower(), part2 if part2.startswith("http") else f"https://{part2}")
            elif part1.lower() in KNOWN_WEBSITES or "." in part1:
                browser_query = part2
                target_url = KNOWN_WEBSITES.get(part1.lower(), part1 if part1.startswith("http") else f"https://{part1}")

    match_type, app, candidates = match_application(browser_query)

    if match_type == "none":
        # Check if query is a standalone known website
        if target_lower in KNOWN_WEBSITES:
            url = KNOWN_WEBSITES[target_lower]
            webbrowser.open(url)
            return {"success": True, "message": f"Opened {target_lower} website 🌐"}
        
        if "." in target_lower:
            url = target_lower if target_lower.startswith("http") else f"https://{target_lower}"
            webbrowser.open(url)
            return {"success": True, "message": f"Opened {target_lower} 🌐"}

        return {"success": False, "message": f"Application '{app_query}' not found."}

    app_name = app.get("name")
    app_type = app.get("type")

    if app_type == "exe":
        path = app.get("path")
        if not path or not os.path.exists(path):
            return {"success": False, "message": f"Path for {app_name} is invalid."}

        try:
            cmd = [path]
            if target_url:
                cmd.append(target_url)

            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.2)
            if psutil.pid_exists(process.pid):
                if target_url:
                    return {"success": True, "message": f"Opened {app_name} and navigated to {target_url} 🌐"}
                return {"success": True, "message": f"Opened {app_name} successfully! ✅"}
            return {"success": False, "message": f"Failed to start {app_name}."}
        except Exception as e:
            return {"success": False, "message": f"Error opening {app_name}: {e}"}

    elif app_type == "uwp":
        app_id = app.get("app_id")
        try:
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"])
            if target_url:
                time.sleep(1.0)
                webbrowser.open(target_url)
                return {"success": True, "message": f"Opened UWP app {app_name} and loaded {target_url} 🌐"}
            return {"success": True, "message": f"Opened UWP app {app_name} successfully! ✅"}
        except Exception as e:
            return {"success": False, "message": f"Error opening UWP app {app_name}: {e}"}

    return {"success": False, "message": "Unknown application type."}


def close_application(app_query: str) -> Dict[str, Any]:
    """Closes running instances of an app."""
    match_type, app, candidates = match_application(app_query)
    if match_type in ["none", "ambiguous"]:
        return {"success": False, "message": f"Cannot find app '{app_query}' to close."}

    app_name = app.get("name")
    target_names = [app.get("path", "").replace("\\", "/").split("/")[-1].lower()] if app.get("type") == "exe" else [f"{clean_app_key(app_name)}.exe"]

    terminated = 0
    for proc in psutil.process_iter(attrs=["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() in target_names:
                proc.terminate()
                terminated += 1
        except Exception:
            pass

    if terminated > 0:
        return {"success": True, "message": f"Closed {terminated} instance(s) of {app_name}."}
    return {"success": True, "message": f"No running instances of {app_name} found."}


def focus_application(app_query: str) -> Dict[str, Any]:
    """Brings an application window to the foreground on Windows."""
    if not IS_WINDOWS:
        return {"success": False, "message": "Window focusing is supported on Windows."}

    query_lower = app_query.lower().strip()
    try:
        import win32gui
        import win32con

        def enum_handler(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and query_lower in title.lower():
                    results.append((hwnd, title))

        windows = []
        win32gui.EnumWindows(enum_handler, windows)

        if windows:
            hwnd, title = windows[0]
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass
            return {"success": True, "message": f"Brought '{title}' window to foreground 🪟"}
        
        return {"success": False, "message": f"Window for '{app_query}' not found."}
    except Exception as e:
        logger.error(f"Failed to focus window for '{app_query}': {e}")
        return {"success": False, "message": f"Failed to focus window: {e}"}
