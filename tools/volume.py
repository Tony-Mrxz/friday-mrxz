"""
tools/volume.py - Master Audio Volume Control using pycaw
"""
import sys
from core.logger import logger

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        pycaw_supported = True
    except Exception as e:
        pycaw_supported = False
        logger.warning(f"⚠️ pycaw audio library initialization failed: {e}")
else:
    pycaw_supported = False


def set_volume(level: int) -> dict:
    """Sets system master volume percentage (0 - 100)."""
    if not IS_WINDOWS or not pycaw_supported:
        return {"success": False, "message": "Volume control is only supported on Windows."}

    level = max(0, min(100, level))
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        # Scalar volume control (0.0 to 1.0)
        volume.SetMasterScalarVolumeLevel(level / 100.0, None)
        return {"success": True, "message": f"Set system volume to {level}% 🔊"}
    except Exception as e:
        return {"success": False, "message": f"Failed to set volume: {e}"}


def toggle_mute(mute: bool = None) -> dict:
    """Toggles or sets master audio mute state."""
    if not IS_WINDOWS or not pycaw_supported:
        return {"success": False, "message": "Volume control is only supported on Windows."}

    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        current_mute = volume.GetMute()
        new_state = (not current_mute) if mute is None else mute
        volume.SetMute(int(new_state), None)
        
        status = "Muted 🔇" if new_state else "Unmuted 🔊"
        return {"success": True, "message": f"Audio {status}"}
    except Exception as e:
        return {"success": False, "message": f"Failed to toggle mute: {e}"}
