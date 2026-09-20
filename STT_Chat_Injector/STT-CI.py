import os
import sys
import json
import time
import ctypes
from ctypes import wintypes
import threading
import subprocess
import importlib.util
import numpy as np
import webbrowser

# 1. Automatic Dependency Bootstrap
REQUIRED_PACKAGES = {
    "sounddevice": "sounddevice",
    "numpy": "numpy",
    "pyperclip": "pyperclip",
    "pynput": "pynput",
    "pyautogui": "pyautogui",
    "faster-whisper": "faster_whisper",
    "customtkinter": "customtkinter",
    "pygame": "pygame",
    "psutil": "psutil"
}

missing = [pkg for pkg, mod in REQUIRED_PACKAGES.items() if importlib.util.find_spec(mod) is None]
if missing:
    print(f"Installing missing dependencies: {', '.join(missing)}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
        print("Dependencies installed successfully.\n")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        sys.exit(1)

# Suppress Hugging Face symlink warnings on Windows & allow SDL background joystick events
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

import sounddevice as sd
import pyperclip
import pyautogui
from pynput import keyboard, mouse
from faster_whisper import WhisperModel
import customtkinter as ctk
import pygame
import psutil

# --- Classic WoW Palette ---
WOW_BG_DARK = "#121214"          # Deep stone background
WOW_FRAME_BG = "#1c1b18"         # Charcoal slate parchment
WOW_BORDER_GOLD = "#8a6d2b"      # Blizzard burnished gold border
WOW_ACCENT_GOLD = "#ffd100"      # Blizzard quest yellow
WOW_TEXT_LIGHT = "#f8e7b9"       # Parchment gold/white
WOW_BUTTON_GOLD = "#382c14"      # Heavy plate button base
WOW_BUTTON_HOVER = "#5c4820"     # Plate highlight
WOW_BUTTON_BORDER = "#c69b3d"    # Polished gold stroke
WOW_HORDE_RED = "#8c1616"        # Action red
WOW_HORDE_HOVER = "#b01f1f"
WOW_ALLIANCE_BLUE = "#1a3b68"    # Subtle accent blue


# --- Classic WoW Themed ToolTip Helper ---
class ToolTip:
    def __init__(self, widget, text, delay_ms=350):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip_window = None
        self.schedule_id = None

        self.widget.bind("<Enter>", self._schedule, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")
        self.widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, event=None):
        self._cancel()
        self.schedule_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self):
        if self.schedule_id:
            try:
                self.widget.after_cancel(self.schedule_id)
            except Exception:
                pass
            self.schedule_id = None

    def _show(self):
        if self.tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 15
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

            self.tip_window = tw = ctk.CTkToplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)

            frame = ctk.CTkFrame(
                tw,
                fg_color="#181715",
                border_width=1,
                border_color=WOW_BORDER_GOLD,
                corner_radius=3
            )
            frame.pack()

            lbl = ctk.CTkLabel(
                frame,
                text=self.text,
                font=ctk.CTkFont(family="Georgia", size=10),
                text_color=WOW_ACCENT_GOLD,
                wraplength=280,
                justify="left"
            )
            lbl.pack(padx=8, pady=4)
        except Exception:
            pass

    def _hide(self, event=None):
        self._cancel()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


# --- Human-Readable Input Label Mappings ---
KEY_DISPLAY_NAMES = {
    "enter": "Enter",
    "return": "Enter",
    "escape": "Escape",
    "esc": "Escape",
    "space": "Space",
    "tab": "Tab",
    "backspace": "Backspace",
    "caps_lock": "Caps Lock",
    "shift": "Shift",
    "shift_r": "Right Shift",
    "ctrl_l": "Left Ctrl",
    "ctrl_r": "Right Ctrl",
    "alt_l": "Left Alt",
    "alt_r": "Right Alt",
    "delete": "Delete",
    "insert": "Insert",
    "home": "Home",
    "end": "End",
    "page_up": "Page Up",
    "page_down": "Page Down",
    "up": "Up Arrow",
    "down": "Down Arrow",
    "left": "Left Arrow",
    "right": "Right Arrow",
    # Mouse side buttons
    "x1": "Mouse 4 (x1)",
    "x2": "Mouse 5 (x2)",
    "middle": "Middle Mouse",
    # Controller standard buttons (Xbox / PlayStation)
    "pad_btn_0": "Xbox A / PS Cross",
    "pad_btn_1": "Xbox B / PS Circle",
    "pad_btn_2": "Xbox X / PS Square",
    "pad_btn_3": "Xbox Y / PS Triangle",
    "pad_btn_4": "Xbox LB / PS L1",
    "pad_btn_5": "Xbox RB / PS R1",
    "pad_btn_6": "Xbox Back / PS Share",
    "pad_btn_7": "Xbox Start / PS Options",
    "pad_btn_8": "Xbox L3 / PS L3 (Stick)",
    "pad_btn_9": "Xbox R3 / PS R3 (Stick)",
    "pad_btn_10": "Xbox Guide / PS Home",
    "pad_hat_up": "D-Pad Up",
    "pad_hat_down": "D-Pad Down",
    "pad_hat_left": "D-Pad Left",
    "pad_hat_right": "D-Pad Right",
    "pad_axis_lt": "Xbox LT / PS L2 (Trigger)",
    "pad_axis_rt": "Xbox RT / PS R2 (Trigger)",
}


def _combo_key_sort_order(k):
    k = k.lower().replace("key.", "")
    if "ctrl" in k or "control" in k:
        return (0, k)
    if "shift" in k:
        return (1, k)
    if "alt" in k:
        return (2, k)
    if "win" in k or "cmd" in k or "super" in k:
        return (3, k)
    if "pad" in k:
        return (4, k)
    return (5, k)


def normalize_combo_id(keys_or_str):
    """Returns canonical, deduplicated, sorted combo string joined with '+' (e.g. 'ctrl_l+f8')."""
    if not keys_or_str:
        return ""
    if isinstance(keys_or_str, str):
        raw_keys = [k.strip().lower().replace("key.", "") for k in keys_or_str.split("+") if k.strip()]
    else:
        raw_keys = [str(k).strip().lower().replace("key.", "") for k in keys_or_str if str(k).strip()]

    unique_keys = list(dict.fromkeys(raw_keys))
    unique_keys.sort(key=_combo_key_sort_order)
    return "+".join(unique_keys)


def format_input_label(input_id):
    if not input_id:
        return "None"
    parts = [p.strip() for p in str(input_id).split("+") if p.strip()]
    if not parts:
        return "None"

    formatted_parts = []
    for clean in parts:
        clean = clean.lower().replace("key.", "")
        if clean in KEY_DISPLAY_NAMES:
            formatted_parts.append(KEY_DISPLAY_NAMES[clean])
        elif clean.startswith("f") and clean[1:].isdigit():
            formatted_parts.append(clean.upper())
        else:
            formatted_parts.append(clean.capitalize())
    return " + ".join(formatted_parts)


def get_next_default_binding_name(bindings):
    """Calculates the lowest sequential default binding name 'Input N' (1-indexed) not currently in use."""
    used = set()
    for b in bindings:
        if isinstance(b, dict):
            name = b.get("binding_name", "").strip()
        elif hasattr(b, "get"):
            name = b.get().strip()
        else:
            name = str(b).strip()
        if name:
            used.add(name)
    idx = 1
    while f"Input {idx}" in used:
        idx += 1
    return f"Input {idx}"


# --- Windows Active Window Detection Helper ---
user32 = ctypes.windll.user32
try:
    dwmapi = ctypes.windll.dwmapi
except Exception:
    dwmapi = None

# Declare 64-bit safe Win32 API signatures
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]


def get_window_bounds(hwnd):
    if not hwnd or not user32.IsWindow(hwnd):
        return None
    rect = wintypes.RECT()
    if dwmapi:
        try:
            hr = dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))
            if hr == 0:
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 0 and h > 0:
                    return (rect.left, rect.top, w, h)
        except Exception:
            pass
    try:
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w > 0 and h > 0:
                return (rect.left, rect.top, w, h)
    except Exception:
        pass
    return None


def find_target_window(target_procs=None, target_titles=None):
    """Finds the primary top-level visible window matching target processes or window titles.
    Filters out tooltips, invisible utility frames, and minimized windows."""
    procs = []
    if target_procs:
        for p in target_procs:
            p_clean = os.path.basename(p).strip().lower()
            if p_clean:
                procs.append(p_clean)
                if p_clean.endswith(".exe"):
                    procs.append(p_clean[:-4])
                else:
                    procs.append(f"{p_clean}.exe")

    titles = []
    if target_titles:
        for t in target_titles:
            t_clean = t.strip().lower()
            if t_clean:
                titles.append(t_clean)

    if not procs and not titles:
        return 0, None

    candidates = []

    def _enum_cb(hwnd, lparam):
        try:
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            ex_style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            if ex_style & 0x00000080:  # WS_EX_TOOLWINDOW
                return True

            bounds = get_window_bounds(hwnd)
            if not bounds or bounds[2] < 120 or bounds[3] < 120:
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = ""
            if pid.value:
                try:
                    proc_name = psutil.Process(pid.value).name().strip().lower()
                except Exception:
                    pass

            title_lower = title.lower()

            matched = False
            # 1. Match process name
            if proc_name and any(p == proc_name or p in proc_name or proc_name in p for p in procs):
                matched = True
            # 2. Match window title against explicit titles or process strings (in case user entered title into target_process)
            elif title_lower and (
                any(t in title_lower for t in titles) or
                any(p in title_lower for p in procs)
            ):
                matched = True

            if matched:
                area = bounds[2] * bounds[3]
                candidates.append((hwnd, bounds, area))
        except Exception:
            pass
        return True

    cb = _WNDENUMPROC(_enum_cb)
    user32.EnumWindows(cb, 0)

    if not candidates:
        return 0, None

    # Pick the largest matching visible window (main window rather than dialog/tray child)
    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates[0][0], candidates[0][1]

_cached_fg_hwnd = None
_cached_fg_info = (0, "", "")

def get_active_window_full_info():
    global _cached_fg_hwnd, _cached_fg_info
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return 0, "", ""
        if hwnd == _cached_fg_hwnd:
            return _cached_fg_info

        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = ""
        if pid.value:
            try:
                proc = psutil.Process(pid.value)
                proc_name = proc.name()
            except Exception:
                pass

        _cached_fg_hwnd = hwnd
        _cached_fg_info = (hwnd, title, proc_name)
        return _cached_fg_info
    except Exception:
        return 0, "", ""


def get_active_window_info():
    _, title, proc_name = get_active_window_full_info()
    return title, proc_name


SYSTEM_EXCLUDES = {
    'svchost.exe', 'conhost.exe', 'cmd.exe', 'powershell.exe', 'pwsh.exe',
    'tasklist.exe', 'runtimebroker.exe', 'dllhost.exe', 'sihost.exe',
    'ctfmon.exe', 'shellexperiencehost.exe', 'startmenuexperiencehost.exe',
    'searchhost.exe', 'searchapp.exe', 'smartscreen.exe', 'textinputhost.exe',
    'openconsole.exe', 'wudfhost.exe', 'fontdrvhost.exe', 'dwm.exe',
    'services.exe', 'lsass.exe', 'wininit.exe', 'winlogon.exe', 'csrss.exe',
    'smss.exe', 'gamebarftserver.exe', 'shellhost.exe', 'useroobebroker.exe',
    'filecoauth.exe', 'browser_helper.exe', 'pet.exe', 'crashpad_handler.exe',
    'nvcontainer.exe', 'nvsphelper64.exe', 'taskhostw.exe', 'unsecapp.exe',
    'tabtip.exe', 'securityhealthsystray.exe', 'splwow64.exe', 'lockapp.exe',
    'applicationframehost.exe', 'crossdeviceresume.exe', 'crossdeviceservice.exe',
    'onedrive.sync.service.exe', 'rtkauduservice64.exe', 'widgetboard.exe',
    'widgetservice.exe', 'node20.exe', 'elgatoaudiocontrolserverwatcher.exe'
}

# The transcriber application itself and its parent runners to strictly ignore
SELF_EXCLUDES = {
    'python.exe', 'pythonw.exe', 'agy.exe', 'code.exe', 'openconsole.exe',
    'pwsh.exe', 'powershell.exe', 'cmd.exe'
}


def get_self_pids():
    my_pid = os.getpid()
    pids = {my_pid}
    try:
        p = psutil.Process(my_pid)
        for ancestor in p.parents():
            pids.add(ancestor.pid)
    except Exception:
        pass
    return pids


def get_last_opened_apps(limit=3):
    """Detects the last N opened user applications, explicitly ignoring this app and background system tasks."""
    import getpass
    curr_user = getpass.getuser().lower()
    self_pids = get_self_pids()
    candidates = []

    for proc in psutil.process_iter(['pid', 'name', 'username', 'create_time']):
        try:
            if proc.pid in self_pids:
                continue
            name = proc.info.get('name') or ''
            if not name or not name.endswith('.exe'):
                continue
            name_lower = name.lower()
            if name_lower in SYSTEM_EXCLUDES or name_lower in SELF_EXCLUDES:
                continue
            if name_lower.startswith(('aac', 'armoury', 'elgato', 'asus', 'com.barraider')):
                continue

            # Resolve child voice proxies to their primary parent app (e.g., WowB.exe)
            if 'voiceproxy' in name_lower:
                parent = proc.parent()
                if parent and parent.name():
                    pname_lower = parent.name().lower()
                    if pname_lower not in SYSTEM_EXCLUDES and pname_lower not in SELF_EXCLUDES:
                        name = parent.name()
                        name_lower = pname_lower

            username = proc.info.get('username') or ''
            if curr_user not in username.lower():
                continue

            ctime = proc.info.get('create_time') or 0
            candidates.append((ctime, name, proc.pid))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Sort descending by launch/create time
    candidates.sort(key=lambda x: x[0], reverse=True)

    recent = []
    seen = set()
    for ctime, name, pid in candidates:
        nl = name.lower()
        if nl not in seen:
            seen.add(nl)
            tm_str = time.strftime('%I:%M:%S %p', time.localtime(ctime))
            recent.append({'name': name, 'time': tm_str, 'pid': pid})
        if len(recent) >= limit:
            break

    return recent


def get_running_apps():
    """Lists all active user desktop applications, excluding this app and system services."""
    import getpass
    curr_user = getpass.getuser().lower()
    self_pids = get_self_pids()
    apps = []
    seen = set()

    for p in psutil.process_iter(['pid', 'name', 'username']):
        try:
            if p.pid in self_pids:
                continue
            u = p.info.get('username') or ''
            n = p.info.get('name') or ''
            if not n or not n.endswith('.exe'):
                continue
            if curr_user not in u.lower():
                continue
            n_lower = n.lower()
            if n_lower in SYSTEM_EXCLUDES or n_lower in SELF_EXCLUDES:
                continue
            if n_lower.startswith(('aac', 'armoury', 'elgato', 'asus', 'com.barraider')):
                continue
            if n_lower in seen:
                continue
            seen.add(n_lower)
            apps.append(n)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    apps.sort(key=lambda s: s.lower())
    return apps


# --- Configuration & Migration System ---
CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "global_settings": {
        "device_index": None,
        "model_size": "base",
        "compute_device": "cpu",
        "vad_filter": True
    },
    "active_profile": "World of Warcraft",
    "app_profiles": {
        "World of Warcraft": {
            "name": "World of Warcraft",
            "target_process": "WowB.exe, Wow.exe, WowClassic.exe",
            "window_title": "World of Warcraft",
            "chat_lifecycle": {
                "open_chat_key": "enter",
                "send_message_key": "enter",
                "close_chat_mode": "click_away",
                "close_chat_key": "escape",
                "click_away": {
                    "enabled": True,
                    "target": "center",
                    "custom_x": 960,
                    "custom_y": 540,
                    "mouse_button": "left"
                }
            },
            "overlay": {
                "enabled": True,
                "pos_x": 80,
                "pos_y": 80,
                "bind_to_window": True
            },
            "tos_safe_mode": {
                "enabled": True,
                "auto_open_chat": True
            },
            "bindings": [
                {"binding_name": "Input 1", "input_id": "f8", "display_name": "F8", "prefix": "/say", "suffix": ""},
                {"binding_name": "Input 2", "input_id": "f9", "display_name": "F9", "prefix": "/team ", "suffix": " [over]"}
            ]
        }
    }
}


def migrate_config(cfg):
    if "app_profiles" in cfg and "global_settings" in cfg:
        # Check that active profile exists
        if cfg.get("active_profile") not in cfg.get("app_profiles", {}):
            if cfg.get("app_profiles"):
                cfg["active_profile"] = list(cfg["app_profiles"].keys())[0]
            else:
                cfg["active_profile"] = "World of Warcraft"
                cfg["app_profiles"] = dict(DEFAULT_CONFIG["app_profiles"])
        # Ensure all profiles have tos_safe_mode and binding_name for each binding
        for prof in cfg.get("app_profiles", {}).values():
            if "tos_safe_mode" not in prof:
                prof_name_lower = prof.get("name", "").lower()
                is_wow = "warcraft" in prof_name_lower or "wow" in prof.get("target_process", "").lower()
                prof["tos_safe_mode"] = {
                    "enabled": True if is_wow else False,
                    "auto_open_chat": True
                }
            else:
                if "auto_open_chat" not in prof["tos_safe_mode"]:
                    prof["tos_safe_mode"]["auto_open_chat"] = True
            bindings = prof.get("bindings", [])
            used = {b.get("binding_name", "").strip() for b in bindings if b.get("binding_name", "").strip()}
            for b in bindings:
                if not b.get("binding_name", "").strip():
                    idx = 1
                    while f"Input {idx}" in used:
                        idx += 1
                    def_name = f"Input {idx}"
                    b["binding_name"] = def_name
                    used.add(def_name)
        return cfg

    # Migrate from legacy config
    new_cfg = {
        "global_settings": {
            "device_index": cfg.get("device_index"),
            "model_size": cfg.get("model_size", "base"),
            "compute_device": "cpu",
            "vad_filter": True
        },
        "active_profile": "World of Warcraft",
        "app_profiles": {}
    }

    old_profiles = cfg.get("profiles", [])
    bindings = []
    used_names = set()
    for p in old_profiles:
        raw_key = p.get("hotkey", "f8").lower()
        idx = 1
        while f"Input {idx}" in used_names:
            idx += 1
        b_name = f"Input {idx}"
        used_names.add(b_name)
        bindings.append({
            "binding_name": b_name,
            "input_id": raw_key,
            "display_name": format_input_label(raw_key),
            "prefix": p.get("prefix", ""),
            "suffix": p.get("suffix", "")
        })

    if not bindings:
        bindings = list(DEFAULT_CONFIG["app_profiles"]["World of Warcraft"]["bindings"])

    wow_prof = json.loads(json.dumps(DEFAULT_CONFIG["app_profiles"]["World of Warcraft"]))
    wow_prof["bindings"] = bindings
    new_cfg["app_profiles"]["World of Warcraft"] = wow_prof
    return new_cfg


def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            cfg = json.load(f)
        migrated = migrate_config(cfg)
        save_config(migrated)
        return migrated
    except Exception:
        return DEFAULT_CONFIG


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=4)


# --- Native Windows XInput Support (Xbox 360, Xbox One, Xbox Series X/S, Compatible Gamepads) ---
class XINPUT_GAMEPAD(ctypes.Structure):
    _fields_ = [
        ('wButtons', wintypes.WORD),
        ('bLeftTrigger', wintypes.BYTE),
        ('bRightTrigger', wintypes.BYTE),
        ('sThumbLX', wintypes.SHORT),
        ('sThumbLY', wintypes.SHORT),
        ('sThumbRX', wintypes.SHORT),
        ('sThumbRY', wintypes.SHORT),
    ]

class XINPUT_STATE(ctypes.Structure):
    _fields_ = [
        ('dwPacketNumber', wintypes.DWORD),
        ('Gamepad', XINPUT_GAMEPAD),
    ]

_XINPUT_DLL = None
for _dll in ('xinput1_4.dll', 'xinput1_3.dll', 'xinput9_1_0.dll'):
    try:
        _XINPUT_DLL = ctypes.windll.LoadLibrary(_dll)
        break
    except Exception:
        pass

XINPUT_BUTTON_MAP = {
    0x1000: 'pad_btn_0',  # A
    0x2000: 'pad_btn_1',  # B
    0x4000: 'pad_btn_2',  # X
    0x8000: 'pad_btn_3',  # Y
    0x0100: 'pad_btn_4',  # LB
    0x0200: 'pad_btn_5',  # RB
    0x0020: 'pad_btn_6',  # Back / View
    0x0010: 'pad_btn_7',  # Start / Menu
    0x0040: 'pad_btn_8',  # Left stick click
    0x0080: 'pad_btn_9',  # Right stick click
    0x0001: 'pad_hat_up',
    0x0002: 'pad_hat_down',
    0x0004: 'pad_hat_left',
    0x0008: 'pad_hat_right',
}


# --- Unified Input Manager (Keyboard, Mouse 4/5, Xbox / PlayStation Gamepads) ---
class UnifiedInputManager:
    def __init__(self, on_press, on_release):
        self.on_press = on_press
        self.on_release = on_release
        self.capture_press_cb = None
        self.capture_release_cb = None
        self.held_inputs = set()
        self.capture_start_time = 0.0
        self.running = False

        self.kb_listener = None
        self.mouse_listener = None
        self.xinput_thread = None
        self.joy_thread = None
        self.joysticks = {}
        self.active_xinput_slots = set()

    def rescan_joysticks(self):
        """Safe non-blocking scan for connected Pygame joysticks without device bus re-enumeration."""
        try:
            if pygame.joystick.get_init():
                count = pygame.joystick.get_count()
                for i in range(count):
                    try:
                        joy = pygame.joystick.Joystick(i)
                        inst_id = joy.get_instance_id() if hasattr(joy, "get_instance_id") else i
                        if inst_id not in self.joysticks:
                            joy.init()
                            self.joysticks[inst_id] = joy
                    except Exception:
                        pass
        except Exception:
            pass

    def start(self):
        self.running = True
        self.kb_listener = keyboard.Listener(on_press=self._on_kb_press, on_release=self._on_kb_release)
        self.kb_listener.start()

        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self.mouse_listener.start()

        if _XINPUT_DLL:
            self.xinput_thread = threading.Thread(target=self._xinput_loop, daemon=True)
            self.xinput_thread.start()

        self.joy_thread = threading.Thread(target=self._joy_loop, daemon=True)
        self.joy_thread.start()

    def stop(self):
        self.running = False
        self.held_inputs.clear()
        if self.kb_listener:
            try:
                self.kb_listener.stop()
            except Exception:
                pass
        if self.mouse_listener:
            try:
                self.mouse_listener.stop()
            except Exception:
                pass

    def start_capture(self, on_press, on_release=None):
        self.capture_start_time = time.time()
        self.capture_press_cb = on_press
        self.capture_release_cb = on_release
        self.held_inputs.clear()
        self.rescan_joysticks()

    def cancel_capture(self):
        self.capture_press_cb = None
        self.capture_release_cb = None
        self.held_inputs.clear()

    def _normalize_key(self, key):
        if isinstance(key, keyboard.Key):
            return key.name.lower()
        if hasattr(key, "char") and key.char:
            return key.char.lower()
        return str(key).lower().replace("key.", "")

    def _on_kb_press(self, key):
        k_id = self._normalize_key(key)
        self.held_inputs.add(k_id)
        if self.capture_press_cb:
            self.capture_press_cb(k_id)
            return
        self.on_press(k_id)

    def _on_kb_release(self, key):
        k_id = self._normalize_key(key)
        self.held_inputs.discard(k_id)
        if self.capture_release_cb:
            self.capture_release_cb(k_id)
            return
        self.on_release(k_id)

    def _on_mouse_click(self, x, y, button, pressed):
        b_name = getattr(button, "name", str(button)).lower()
        if b_name == "left":
            # Left click is reserved for UI navigation/Cancel buttons
            return
        if b_name == "right" and not self.capture_press_cb:
            return

        m_id = b_name
        if pressed:
            self.held_inputs.add(m_id)
            if self.capture_press_cb:
                self.capture_press_cb(m_id)
                return
            self.on_press(m_id)
        else:
            self.held_inputs.discard(m_id)
            if self.capture_release_cb:
                self.capture_release_cb(m_id)
                return
            self.on_release(m_id)

    def _dispatch_pad_press(self, btn_id):
        self.held_inputs.add(btn_id)
        if self.capture_press_cb:
            self.capture_press_cb(btn_id)
            return
        self.on_press(btn_id)

    def _dispatch_pad_release(self, btn_id):
        self.held_inputs.discard(btn_id)
        if self.capture_release_cb:
            self.capture_release_cb(btn_id)
            return
        self.on_release(btn_id)

    def _xinput_loop(self):
        """Native Windows XInput polling: ultra-low latency, zero CPU churn, automatic hotplugging."""
        last_buttons = [0, 0, 0, 0]
        last_lt = [False, False, False, False]
        last_rt = [False, False, False, False]

        while self.running:
            try:
                st = XINPUT_STATE()
                for slot in range(4):
                    res = _XINPUT_DLL.XInputGetState(slot, ctypes.byref(st))
                    if res == 0:
                        self.active_xinput_slots.add(slot)
                        cur_b = st.Gamepad.wButtons
                        prev_b = last_buttons[slot]
                        pressed = cur_b & ~prev_b
                        released = prev_b & ~cur_b

                        if pressed:
                            for mask, btn_id in XINPUT_BUTTON_MAP.items():
                                if pressed & mask:
                                    self._dispatch_pad_press(btn_id)

                        if released:
                            for mask, btn_id in XINPUT_BUTTON_MAP.items():
                                if released & mask:
                                    self._dispatch_pad_release(btn_id)

                        last_buttons[slot] = cur_b

                        # Left Trigger (0..255, threshold > 30)
                        lt_down = st.Gamepad.bLeftTrigger > 30
                        if lt_down and not last_lt[slot]:
                            self._dispatch_pad_press("pad_axis_lt")
                        elif not lt_down and last_lt[slot]:
                            self._dispatch_pad_release("pad_axis_lt")
                        last_lt[slot] = lt_down

                        # Right Trigger (0..255, threshold > 30)
                        rt_down = st.Gamepad.bRightTrigger > 30
                        if rt_down and not last_rt[slot]:
                            self._dispatch_pad_press("pad_axis_rt")
                        elif not rt_down and last_rt[slot]:
                            self._dispatch_pad_release("pad_axis_rt")
                        last_rt[slot] = rt_down
                    else:
                        if slot in self.active_xinput_slots:
                            self.active_xinput_slots.remove(slot)
                        last_buttons[slot] = 0
                        last_lt[slot] = False
                        last_rt[slot] = False

                time.sleep(0.01)
            except Exception:
                time.sleep(0.05)

    def _joy_loop(self):
        """DirectInput / Generic Controller Fallback via Pygame (non-blocking, event-driven)."""
        try:
            pygame.init()
            pygame.joystick.init()
        except Exception:
            return

        self.joysticks = {}
        self.rescan_joysticks()

        last_hat_state = (0, 0)
        last_axis_state = {}

        while self.running:
            try:
                # If an XInput controller is actively handled and no extra Pygame joysticks exist,
                # sleep slightly longer to conserve CPU
                if self.active_xinput_slots and len(self.joysticks) <= len(self.active_xinput_slots):
                    for event in pygame.event.get():
                        if event.type == pygame.JOYDEVICEADDED:
                            self.rescan_joysticks()
                        elif event.type == pygame.JOYDEVICEREMOVED:
                            inst_id = getattr(event, "instance_id", None)
                            if inst_id in self.joysticks:
                                del self.joysticks[inst_id]
                    time.sleep(0.04)
                    continue

                for event in pygame.event.get():
                    if event.type == pygame.JOYDEVICEADDED:
                        try:
                            dev_idx = getattr(event, "device_index", getattr(event, "which", 0))
                            joy = pygame.joystick.Joystick(dev_idx)
                            joy.init()
                            self.joysticks[joy.get_instance_id()] = joy
                        except Exception:
                            self.rescan_joysticks()

                    elif event.type == pygame.JOYDEVICEREMOVED:
                        inst_id = getattr(event, "instance_id", getattr(event, "which", None))
                        if inst_id in self.joysticks:
                            del self.joysticks[inst_id]

                    elif event.type == pygame.JOYBUTTONDOWN:
                        if not self.active_xinput_slots:
                            btn_id = f"pad_btn_{event.button}"
                            self._dispatch_pad_press(btn_id)

                    elif event.type == pygame.JOYBUTTONUP:
                        if not self.active_xinput_slots:
                            btn_id = f"pad_btn_{event.button}"
                            self._dispatch_pad_release(btn_id)

                    elif event.type == pygame.JOYHATMOTION:
                        if not self.active_xinput_slots:
                            cur_hat = event.value
                            if cur_hat != last_hat_state:
                                hat_map = {
                                    (0, 1): "pad_hat_up",
                                    (0, -1): "pad_hat_down",
                                    (-1, 0): "pad_hat_left",
                                    (1, 0): "pad_hat_right"
                                }
                                if cur_hat in hat_map:
                                    self._dispatch_pad_press(hat_map[cur_hat])
                                elif last_hat_state in hat_map:
                                    self._dispatch_pad_release(hat_map[last_hat_state])
                                last_hat_state = cur_hat

                    elif event.type == pygame.JOYAXISMOTION:
                        if not self.active_xinput_slots:
                            axis_id = None
                            if event.axis in (4, 2):
                                axis_id = "pad_axis_lt"
                            elif event.axis in (5, 3):
                                axis_id = "pad_axis_rt"

                            if axis_id:
                                inst = getattr(event, "instance_id", 0)
                                key = (inst, axis_id)
                                is_down = event.value > 0.5
                                was_down = last_axis_state.get(key, False)

                                if is_down and not was_down:
                                    last_axis_state[key] = True
                                    self._dispatch_pad_press(axis_id)
                                elif not is_down and was_down and event.value < 0.2:
                                    last_axis_state[key] = False
                                    self._dispatch_pad_release(axis_id)

                time.sleep(0.01)
            except Exception:
                time.sleep(0.05)


# --- Core Speech-to-Text & Macro Injection Engine ---
class STTEngine:
    def __init__(self, config, log_callback=None, hud_callback=None):
        self.config = config
        self.log_callback = log_callback or print
        self.hud_callback = hud_callback

        self.sample_rate = 16000
        self.channels = 1
        self.is_recording = False
        self.is_transcribing = False
        self.audio_chunks = []
        self.active_input_id = None
        self.active_binding = None
        self.current_vu_level = 0.0

        # ToS Safe State: Pending Manual Send
        self.pending_send = False
        self.pending_binding = None
        self.pending_timer = None

        self.stream = None
        self.input_manager = None
        self.kb_controller = keyboard.Controller()
        self.mouse_controller = mouse.Controller()

        # Whisper Model Initialization
        self.model = None
        self._init_model()

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def _set_hud(self, state, detail=""):
        if self.hud_callback:
            self.hud_callback(state, detail)

    def _cancel_pending_timer(self):
        if self.pending_timer:
            try:
                self.pending_timer.cancel()
            except Exception:
                pass
            self.pending_timer = None

    def cancel_active(self):
        self._cancel_pending_timer()
        self.pending_send = False
        self.pending_binding = None
        self.is_recording = False
        self.is_transcribing = False
        self.audio_chunks = []
        self.active_input_id = None
        self.active_binding_keys = None
        self.active_binding = None
        self.log("Standby.")
        self._set_hud("idle")

    def _init_model(self):
        global_cfg = self.config.get("global_settings", {})
        model_size = global_cfg.get("model_size", "base")
        self.log(f"Loading Whisper Engine ({model_size}) on CPU [int8]...")
        try:
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
            self.log("Whisper CPU engine ready [int8].")
        except Exception as e:
            self.log(f"Failed to load Whisper on CPU: {e}")

    def reload_model(self, model_size="base"):
        def _reload():
            self.log(f"Reloading Whisper Engine ({model_size}) on CPU [int8]...")
            try:
                self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
                self.log("Whisper CPU engine successfully reloaded [int8].")
            except Exception as e:
                self.log(f"Whisper reload error: {e}")

        threading.Thread(target=_reload, daemon=True).start()

    def audio_callback(self, indata, frames, time_info, status):
        # Compute RMS volume level for live VU meter
        try:
            rms = np.sqrt(np.mean(indata**2))
            # Smooth level calculation with non-linear boost for clear visualization
            self.current_vu_level = min(1.0, float(rms * 12.0))
        except Exception:
            self.current_vu_level = 0.0

        if self.is_recording:
            self.audio_chunks.append(indata.copy())

    def get_active_profile(self):
        act_name = self.config.get("active_profile", "World of Warcraft")
        profiles = self.config.get("app_profiles", {})
        return profiles.get(act_name, DEFAULT_CONFIG["app_profiles"]["World of Warcraft"])

    def get_binding_for_input(self, input_id):
        profile = self.get_active_profile()
        norm_id = normalize_combo_id(input_id)
        for b in profile.get("bindings", []):
            if normalize_combo_id(b.get("input_id", "")) == norm_id:
                return b
        return None

    def find_matching_binding(self, just_pressed_id):
        profile = self.get_active_profile()
        bindings = profile.get("bindings", [])
        if not bindings:
            return None, None, None

        held = set(self.input_manager.held_inputs) if self.input_manager else set()
        held.add(just_pressed_id)

        matched = []
        for b in bindings:
            raw_id = b.get("input_id", "").strip().lower()
            if not raw_id:
                continue
            b_keys = set(k.strip().lower().replace("key.", "") for k in raw_id.split("+") if k.strip())
            if just_pressed_id in b_keys and b_keys.issubset(held):
                matched.append((b, raw_id, b_keys))

        if not matched:
            return None, None, None

        # Prioritize the most specific combo (highest key count)
        matched.sort(key=lambda item: len(item[2]), reverse=True)
        return matched[0]

    def on_press(self, input_id):
        # Escape cancels any pending message or active recording
        if input_id == "escape":
            if self.pending_send or self.is_recording or self.is_transcribing:
                self.cancel_active()
                return

        # If a message is awaiting confirmation, hitting physical Enter confirms/sends it
        if self.pending_send and input_id in ("enter", "return"):
            self._cancel_pending_timer()
            self.pending_send = False
            self.pending_binding = None
            self.log("Message submitted via Enter key.")
            self._set_hud("idle")
            return

        binding, combo_id, combo_keys = self.find_matching_binding(input_id)
        if not binding:
            return

        profile = self.get_active_profile()
        tos_cfg = profile.get("tos_safe_mode", {})
        is_tos_safe = tos_cfg.get("enabled", True)

        b_name = (binding.get("binding_name") or "").strip() or binding.get("display_name") or format_input_label(combo_id)
        disp_name = format_input_label(combo_id)

        # 1. ToS Safe Mode: Hold to Dictate, Paste into Chat, Tap to Send
        if is_tos_safe:
            if self.pending_send:
                # User tapped hotkey while message is waiting in chat -> Submit message
                self._send_pending_chat(b_name)
                return

            if self.is_recording or self.is_transcribing:
                return

            # Start recording (Hold to talk)
            self.active_input_id = combo_id
            self.active_binding_keys = combo_keys
            self.active_binding = binding
            self.audio_chunks = []
            self.is_recording = True
            self.log(f"Recording voice via [{b_name}] ({disp_name}). Hold to speak...")
            self._set_hud("recording", f"{b_name} [HOLD]")

            # Auto-open chat box on initial press so chat caret is ready
            auto_open = tos_cfg.get("auto_open_chat", True)
            open_k = profile.get("chat_lifecycle", {}).get("open_chat_key", "enter")
            if auto_open and open_k and open_k != "none":
                threading.Thread(target=lambda: self.simulate_key_action(open_k), daemon=True).start()
            return

        # 2. Local Whisper Recording (Macro Mode - Automated Injection)
        if not self.is_recording and not self.is_transcribing:
            self.active_input_id = combo_id
            self.active_binding_keys = combo_keys
            self.active_binding = binding
            self.audio_chunks = []
            self.is_recording = True
            self.log(f"Push-to-Talk active via [{b_name}] ({disp_name})...")
            self._set_hud("recording", b_name)

    def on_release(self, input_id):
        if not self.is_recording:
            return

        is_match = False
        if hasattr(self, "active_binding_keys") and self.active_binding_keys:
            if input_id in self.active_binding_keys:
                is_match = True
        elif input_id == self.active_input_id:
            is_match = True

        if is_match:
            self.is_recording = False
            binding = self.active_binding
            self.active_input_id = None
            self.active_binding_keys = None
            self.active_binding = None
            chunks_copy = list(self.audio_chunks)
            self.audio_chunks = []

            profile = self.get_active_profile()
            tos_cfg = profile.get("tos_safe_mode", {})
            is_tos_safe = tos_cfg.get("enabled", True)

            self.is_transcribing = True
            self.log("Recording complete. Deciphering audio...")
            self._set_hud("transcribing", "DECIPHERING...")

            if is_tos_safe:
                threading.Thread(
                    target=self._process_and_paste_only,
                    args=(chunks_copy, binding),
                    daemon=True
                ).start()
            else:
                threading.Thread(
                    target=self._process_and_full_inject,
                    args=(chunks_copy, binding),
                    daemon=True
                ).start()

    def _send_pending_chat(self, binding_name="Input"):
        self._cancel_pending_timer()
        self.pending_send = False
        active_b = self.pending_binding
        self.pending_binding = None

        profile = self.get_active_profile()
        lifecycle = profile.get("chat_lifecycle", {})
        send_k = lifecycle.get("send_message_key", "enter")
        click_away_cfg = lifecycle.get("click_away", {})
        is_ca = click_away_cfg.get("enabled", True)

        self.log(f"Submitting chat message via [{binding_name}]...")
        self._set_hud("transcribing", "SENDING...")

        def _do_send():
            try:
                if send_k and send_k != "none":
                    self.simulate_key_action(send_k)
                    time.sleep(0.06)

                if is_ca:
                    target_mode = click_away_cfg.get("target", "center")
                    if target_mode == "custom":
                        cx = int(click_away_cfg.get("custom_x", 0))
                        cy = int(click_away_cfg.get("custom_y", 0))
                    else:
                        sw, sh = pyautogui.size()
                        cx, cy = sw // 2, sh // 2
                    self.mouse_controller.position = (cx, cy)
                    time.sleep(0.03)
                    btn = mouse.Button.left if click_away_cfg.get("mouse_button", "left") == "left" else mouse.Button.right
                    self.mouse_controller.click(btn)
                else:
                    close_hotkey = lifecycle.get("close_chat_key", "escape")
                    if close_hotkey and close_hotkey != "none":
                        time.sleep(0.04)
                        self.simulate_key_action(close_hotkey)
            except Exception as e:
                self.log(f"Error sending chat: {e}")
            finally:
                time.sleep(0.2)
                self._set_hud("idle")

        threading.Thread(target=_do_send, daemon=True).start()

    def split_into_chunks(self, full_body, first_chunk_limit=255, normal_limit=255):
        words = full_body.split()
        if not words:
            return []

        chunks = []
        current_chunk = []
        current_len = 0
        limit = first_chunk_limit

        for word in words:
            add_len = len(word) if not current_chunk else len(word) + 1
            if current_len + add_len <= limit:
                current_chunk.append(word)
                current_len += add_len
            else:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                while len(word) > normal_limit:
                    chunks.append(word[:normal_limit])
                    word = word[normal_limit:]

                current_chunk = [word]
                current_len = len(word)
                limit = normal_limit

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def simulate_key_action(self, key_id):
        if not key_id or key_id == "none":
            return
        clean = str(key_id).strip().lower().replace("key.", "")

        if clean in ("x1", "x2", "middle", "left", "right"):
            btn = getattr(mouse.Button, clean, mouse.Button.left)
            self.mouse_controller.click(btn)
            return

        key_mapping = {
            "enter": keyboard.Key.enter,
            "return": keyboard.Key.enter,
            "escape": keyboard.Key.esc,
            "esc": keyboard.Key.esc,
            "space": keyboard.Key.space,
            "tab": keyboard.Key.tab,
            "backspace": keyboard.Key.backspace,
            "shift": keyboard.Key.shift,
            "ctrl": keyboard.Key.ctrl,
            "alt": keyboard.Key.alt,
        }
        if clean in key_mapping:
            key_obj = key_mapping[clean]
        elif clean.startswith("f") and clean[1:].isdigit():
            key_obj = getattr(keyboard.Key, clean, clean)
        else:
            key_obj = clean

        try:
            self.kb_controller.press(key_obj)
            time.sleep(0.03)
            self.kb_controller.release(key_obj)
        except Exception:
            pass

    def paste_clipboard(self):
        with self.kb_controller.pressed(keyboard.Key.ctrl):
            self.kb_controller.press('v')
            self.kb_controller.release('v')

    def _process_and_paste_only(self, chunks, binding):
        try:
            if not chunks:
                self.log("No sound registered.")
                self.is_transcribing = False
                self._set_hud("idle")
                return

            audio_data = np.concatenate(chunks, axis=0).flatten().astype(np.float32)
            if np.max(np.abs(audio_data)) < 0.01:
                self.log("Ignored: Voice signal level too faint.")
                self.is_transcribing = False
                self._set_hud("idle")
                return

            segments, _ = self.model.transcribe(
                audio_data,
                beam_size=3,
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=250)
            )
            transcription = " ".join([seg.text.strip() for seg in segments]).strip()

            if not transcription:
                self.log("No intelligible speech detected.")
                self.is_transcribing = False
                self._set_hud("idle")
                return

            prefix = (binding.get("prefix") or "") if binding else ""
            suffix = (binding.get("suffix") or "") if binding else ""

            clean_prefix = prefix.strip()
            is_slash_cmd = clean_prefix.startswith("/")

            if is_slash_cmd:
                first_limit = max(10, 255 - len(clean_prefix) - 1)
            else:
                first_limit = max(10, 255 - len(prefix))

            message_chunks = self.split_into_chunks(transcription, first_chunk_limit=first_limit, normal_limit=255)
            if not message_chunks:
                self.is_transcribing = False
                self._set_hud("idle")
                return

            if suffix:
                last_chunk = message_chunks[-1] + suffix
                if len(last_chunk) > 255:
                    message_chunks.pop()
                    sub_chunks = self.split_into_chunks(last_chunk, first_chunk_limit=255, normal_limit=255)
                    message_chunks.extend(sub_chunks)
                else:
                    message_chunks[-1] = last_chunk

            # Paste text into open chat box via clipboard
            for i, chunk_text in enumerate(message_chunks):
                if i == 0:
                    if is_slash_cmd:
                        pyperclip.copy(clean_prefix)
                        self.paste_clipboard()
                        time.sleep(0.04)

                        self.simulate_key_action("space")
                        time.sleep(0.04)

                        pyperclip.copy(chunk_text)
                        self.paste_clipboard()
                        time.sleep(0.05)
                    else:
                        full_p1 = f"{prefix}{chunk_text}"
                        pyperclip.copy(full_p1)
                        self.paste_clipboard()
                        time.sleep(0.05)
                else:
                    pyperclip.copy(chunk_text)
                    self.paste_clipboard()
                    time.sleep(0.05)

            b_name = (binding.get("binding_name") or "").strip() if binding else ""
            if not b_name and binding:
                b_name = binding.get("display_name") or "Input"
            if not b_name:
                b_name = "Input"

            self.log(f"Message pasted into chat: \"{transcription}\". Press [{b_name}] or Enter to send.")

            # Arm pending manual send state
            self.pending_send = True
            self.pending_binding = binding
            self.is_transcribing = False

            # Set 60-second auto-cancel safety timer
            self._cancel_pending_timer()
            self.pending_timer = threading.Timer(60.0, self.cancel_active)
            self.pending_timer.daemon = True
            self.pending_timer.start()

            self._set_hud("pasted", f"{b_name} [TAP TO SEND]")

        except Exception as e:
            self.log(f"Error during transcription or pasting: {e}")
            self.cancel_active()
        finally:
            self.is_transcribing = False

    def _process_and_full_inject(self, chunks, binding):
        try:
            if not chunks:
                self.log("No sound registered.")
                self.is_transcribing = False
                self._set_hud("idle")
                return

            audio_data = np.concatenate(chunks, axis=0).flatten().astype(np.float32)
            if np.max(np.abs(audio_data)) < 0.01:
                self.log("Ignored: Voice signal level too faint.")
                self.is_transcribing = False
                self._set_hud("idle")
                return

            segments, _ = self.model.transcribe(
                audio_data,
                beam_size=3,
                language="en",
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=250)
            )
            transcription = " ".join([seg.text.strip() for seg in segments]).strip()

            if not transcription:
                self.log("No intelligible speech detected.")
                self.is_transcribing = False
                self._set_hud("idle")
                return

            prefix = (binding.get("prefix") or "") if binding else ""
            suffix = (binding.get("suffix") or "") if binding else ""

            profile = self.get_active_profile()
            lifecycle = profile.get("chat_lifecycle", {})
            open_key = lifecycle.get("open_chat_key", "enter")
            send_key = lifecycle.get("send_message_key", "enter")
            click_away_cfg = lifecycle.get("click_away", {})
            is_click_away = click_away_cfg.get("enabled", True)
            close_hotkey = lifecycle.get("close_chat_key", "escape")

            clean_prefix = prefix.strip()
            is_slash_cmd = clean_prefix.startswith("/")

            if is_slash_cmd:
                first_limit = max(10, 255 - len(clean_prefix) - 1)
            else:
                first_limit = max(10, 255 - len(prefix))

            message_chunks = self.split_into_chunks(transcription, first_chunk_limit=first_limit, normal_limit=255)
            if not message_chunks:
                self.is_transcribing = False
                self._set_hud("idle")
                return

            if suffix:
                last_chunk = message_chunks[-1] + suffix
                if len(last_chunk) > 255:
                    message_chunks.pop()
                    sub_chunks = self.split_into_chunks(last_chunk, first_chunk_limit=255, normal_limit=255)
                    message_chunks.extend(sub_chunks)
                else:
                    message_chunks[-1] = last_chunk

            self.log(f"Transmitting {len(message_chunks)} chunk(s) to application...")

            for i, chunk_text in enumerate(message_chunks):
                # 1. Open Chat Box
                if open_key and open_key != "none":
                    self.simulate_key_action(open_key)
                    time.sleep(0.06)

                # 2. Inject Payload
                if i == 0:
                    if is_slash_cmd:
                        pyperclip.copy(clean_prefix)
                        self.paste_clipboard()
                        time.sleep(0.04)

                        self.simulate_key_action("space")
                        time.sleep(0.04)

                        pyperclip.copy(chunk_text)
                        self.paste_clipboard()
                        time.sleep(0.05)
                    else:
                        full_p1 = f"{prefix}{chunk_text}"
                        pyperclip.copy(full_p1)
                        self.paste_clipboard()
                        time.sleep(0.05)
                else:
                    pyperclip.copy(chunk_text)
                    self.paste_clipboard()
                    time.sleep(0.05)

                # 3. Send Message
                if send_key and send_key != "none":
                    self.simulate_key_action(send_key)
                    time.sleep(0.06)

            # 4. Close Chat / Restore Focus
            if is_click_away:
                target_mode = click_away_cfg.get("target", "center")
                if target_mode == "custom":
                    cx = int(click_away_cfg.get("custom_x", 0))
                    cy = int(click_away_cfg.get("custom_y", 0))
                else:
                    sw, sh = pyautogui.size()
                    cx, cy = sw // 2, sh // 2
                self.mouse_controller.position = (cx, cy)
                time.sleep(0.03)
                btn = mouse.Button.left if click_away_cfg.get("mouse_button", "left") == "left" else mouse.Button.right
                self.mouse_controller.click(btn)
            else:
                if close_hotkey and close_hotkey != "none":
                    time.sleep(0.04)
                    self.simulate_key_action(close_hotkey)

            self.log("Transmission complete.")
        except Exception as e:
            self.log(f"Error during injection: {e}")
        finally:
            self.is_transcribing = False
            self._set_hud("idle")

    def start(self):
        dev_idx = self.config.get("global_settings", {}).get("device_index")
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            device=dev_idx,
            callback=self.audio_callback
        )
        self.stream.start()

        self.input_manager = UnifiedInputManager(on_press=self.on_press, on_release=self.on_release)
        self.input_manager.start()
        self.log("Unified PTT Listener armed (Keyboard, Mouse 4/5, Gamepads).")
        self._set_hud("idle")

    def stop(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.input_manager:
            self.input_manager.stop()
            self.input_manager = None
        self.log("PTT Listener disarmed.")


# --- Interactive Input Capture Dialog ("Press to Bind") ---
class InputCaptureDialog(ctk.CTkToplevel):
    def __init__(self, parent, input_manager, on_captured):
        super().__init__(parent)
        self.input_manager = input_manager
        self.on_captured = on_captured
        self.is_active = True
        self.currently_held = set()
        self.all_pressed = []

        self.title("Bind Input Combo")
        self.geometry("460x210")
        self.resizable(False, False)
        self.configure(fg_color=WOW_BG_DARK)
        self.attributes("-topmost", True)

        try:
            self.grab_set()
        except Exception:
            pass

        # Center on parent
        px = parent.winfo_x() + (parent.winfo_width() // 2) - 230
        py = parent.winfo_y() + (parent.winfo_height() // 2) - 105
        self.geometry(f"+{px}+{py}")

        frame = ctk.CTkFrame(self, fg_color=WOW_FRAME_BG, border_width=2, border_color=WOW_BORDER_GOLD, corner_radius=4)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(
            frame,
            text="PRESS & HOLD BUTTONS / KEYS",
            font=ctk.CTkFont(family="Georgia", size=13, weight="bold"),
            text_color=WOW_ACCENT_GOLD
        ).pack(pady=(12, 2))

        ctk.CTkLabel(
            frame,
            text="Press and hold all buttons or keys for your combination.\nOnce all keys are released, the combination will be bound.",
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color=WOW_TEXT_LIGHT,
            justify="center"
        ).pack(pady=(0, 6))

        self.combo_label = ctk.CTkLabel(
            frame,
            text="[ Waiting for input... ]",
            font=ctk.CTkFont(family="Georgia", size=13, weight="bold"),
            text_color="#63a4ff"
        )
        self.combo_label.pack(pady=4)

        self.hint_label = ctk.CTkLabel(
            frame,
            text="Works with Keyboard, Mouse (M4/M5), and Gamepads (Xbox / PS)",
            font=ctk.CTkFont(family="Georgia", size=9, slant="italic"),
            text_color="#8c8c8c"
        )
        self.hint_label.pack(pady=(0, 6))

        cancel_btn = ctk.CTkButton(
            frame,
            text="Cancel",
            width=90,
            height=26,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_HORDE_RED,
            hover_color=WOW_HORDE_HOVER,
            command=self.close
        )
        cancel_btn.pack(pady=(2, 8))

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.input_manager.start_capture(self._on_input_press, self._on_input_release)

    def _on_input_press(self, input_id):
        if not self.is_active:
            return

        # If user presses escape when nothing else is pressed, treat as cancel
        if input_id == "escape" and not self.all_pressed:
            self.after(0, self.close)
            return

        already_held = input_id in self.currently_held
        self.currently_held.add(input_id)
        if input_id not in self.all_pressed:
            self.all_pressed.append(input_id)

        if not already_held:
            combo_str = normalize_combo_id(self.all_pressed)
            disp_name = format_input_label(combo_str)
            self.after(0, lambda d=disp_name: self._update_display(d, True))

    def _on_input_release(self, input_id):
        if not self.is_active:
            return

        self.currently_held.discard(input_id)

        # When all pressed buttons have been released, finalize combo
        if len(self.currently_held) == 0 and len(self.all_pressed) > 0:
            combo_id = normalize_combo_id(self.all_pressed)
            display_name = format_input_label(combo_id)
            self.is_active = False
            self.after(0, lambda: self._complete(combo_id, display_name))
        elif len(self.currently_held) > 0:
            combo_str = normalize_combo_id(self.all_pressed)
            disp_name = format_input_label(combo_str)
            self.after(0, lambda d=disp_name: self._update_display(d, False))

    def _update_display(self, disp_name, is_holding):
        if not self.is_active:
            return
        self.combo_label.configure(text=f"[ {disp_name} ]", text_color=WOW_ACCENT_GOLD)
        if is_holding:
            self.hint_label.configure(
                text="Keep holding to add more keys, or release all to confirm.",
                text_color="#63a4ff"
            )
        else:
            self.hint_label.configure(
                text="Releasing... let go of all keys to confirm.",
                text_color="#ffcc00"
            )

    def _complete(self, combo_id, display_name):
        self.close()
        if self.on_captured:
            self.on_captured(combo_id, display_name)

    def close(self):
        self.is_active = False
        if self.input_manager:
            self.input_manager.cancel_capture()
        try:
            self.grab_release()
            self.destroy()
        except Exception:
            pass


# --- Application Selector Dialog with Auto-Detection & Recent Apps ---
class AutoDetectDialog(ctk.CTkToplevel):
    def __init__(self, parent, recent_apps, all_apps, on_selected):
        super().__init__(parent)
        self.on_selected = on_selected
        self.title("Auto-Detect Target Application")
        self.geometry("490x370")
        self.resizable(False, False)
        self.configure(fg_color=WOW_BG_DARK)
        self.attributes("-topmost", True)

        try:
            self.grab_set()
        except Exception:
            pass

        px = parent.winfo_x() + (parent.winfo_width() // 2) - 245
        py = parent.winfo_y() + (parent.winfo_height() // 2) - 185
        self.geometry(f"+{px}+{py}")

        frame = ctk.CTkFrame(self, fg_color=WOW_FRAME_BG, border_width=2, border_color=WOW_BORDER_GOLD, corner_radius=4)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        # 1. User Instruction Note Banner
        note_box = ctk.CTkFrame(frame, fg_color="#241f16", border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        note_box.pack(fill="x", padx=12, pady=(10, 8))

        ctk.CTkLabel(
            note_box,
            text="📌 NOTE: Please open your target game or application\nfirst, then select Auto-Detect.",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color=WOW_ACCENT_GOLD,
            justify="center"
        ).pack(padx=10, pady=8)

        # 2. Header
        ctk.CTkLabel(
            frame,
            text="LAST 3 OPENED APPLICATIONS DETECTED",
            font=ctk.CTkFont(family="Georgia", size=12, weight="bold"),
            text_color=WOW_TEXT_LIGHT
        ).pack(pady=(2, 6))

        # 3. Last 3 Recent Apps Buttons
        if recent_apps:
            for idx, item in enumerate(recent_apps[:3]):
                name = item['name']
                t_str = item.get('time', '')
                btn_text = f"{idx + 1}.  {name}   (Launched: {t_str})"
                btn = ctk.CTkButton(
                    frame,
                    text=btn_text,
                    height=32,
                    font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
                    fg_color=WOW_BUTTON_GOLD,
                    hover_color=WOW_BUTTON_HOVER,
                    border_width=1,
                    border_color=WOW_BUTTON_BORDER,
                    text_color=WOW_ACCENT_GOLD,
                    anchor="w",
                    command=lambda n=name: self._choose(n)
                )
                btn.pack(fill="x", padx=18, pady=3)
        else:
            ctk.CTkLabel(
                frame,
                text="No recently opened user applications detected.",
                font=ctk.CTkFont(family="Georgia", size=11),
                text_color="#888888"
            ).pack(pady=6)

        # 4. Fallback Dropdown of all running processes
        ctk.CTkLabel(
            frame,
            text="Or select from all running processes:",
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color="#a09075"
        ).pack(pady=(10, 2))

        bot_row = ctk.CTkFrame(frame, fg_color="transparent")
        bot_row.pack(fill="x", padx=18, pady=(0, 10))

        display_all = all_apps if all_apps else ["No running apps found"]
        self.all_menu = ctk.CTkOptionMenu(
            bot_row,
            values=display_all,
            width=250,
            fg_color="#0d0d0e",
            button_color=WOW_BORDER_GOLD,
            button_hover_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            dropdown_fg_color=WOW_FRAME_BG,
            dropdown_text_color=WOW_TEXT_LIGHT,
            font=ctk.CTkFont(family="Consolas", size=10)
        )
        self.all_menu.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            bot_row,
            text="Select",
            width=70,
            height=26,
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_ALLIANCE_BLUE,
            hover_color="#24508d",
            text_color="#ffffff",
            command=self._confirm_menu
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            bot_row,
            text="Cancel",
            width=65,
            height=26,
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_HORDE_RED,
            hover_color=WOW_HORDE_HOVER,
            text_color="#ffffff",
            command=self.destroy
        ).pack(side="right")

    def _choose(self, app_name):
        self.on_selected(app_name)
        self.destroy()

    def _confirm_menu(self):
        val = self.all_menu.get()
        if val and val != "No running apps found":
            self.on_selected(val)
        self.destroy()


# --- Blizzard ToS & Accessibility Guide Dialog ---
class ToSGuideDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_apply_safe_settings=None):
        super().__init__(parent)
        self.on_apply_safe_settings = on_apply_safe_settings
        self.title("Speech To Text Chat Injector: Blizzard ToS & Warden Guide")
        self.geometry("680x640")
        self.resizable(False, False)
        self.configure(fg_color=WOW_BG_DARK)
        self.attributes("-topmost", True)

        try:
            self.grab_set()
        except Exception:
            pass

        px = parent.winfo_x() + (parent.winfo_width() // 2) - 340
        py = parent.winfo_y() + (parent.winfo_height() // 2) - 320
        self.geometry(f"+{px}+{py}")

        frame = ctk.CTkFrame(self, fg_color=WOW_FRAME_BG, border_width=2, border_color=WOW_BORDER_GOLD, corner_radius=4)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Header
        hdr = ctk.CTkFrame(frame, fg_color="#181715", border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        hdr.pack(fill="x", padx=10, pady=(8, 4))

        ctk.CTkLabel(
            hdr,
            text="🛡️ BLIZZARD ToS & WARDEN ANTI-CHEAT GUIDE",
            font=ctk.CTkFont(family="Georgia", size=14, weight="bold"),
            text_color=WOW_ACCENT_GOLD
        ).pack(anchor="w", padx=10, pady=(6, 1))

        ctk.CTkLabel(
            hdr,
            text="Warden Anti-Cheat Compliance, 1:1 Hardware Input Standard & Official Blizzard Policy Links",
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color=WOW_TEXT_LIGHT
        ).pack(anchor="w", padx=10, pady=(0, 6))

        # Scrollable Content
        scroll = ctk.CTkScrollableFrame(
            frame,
            fg_color="transparent",
            scrollbar_button_color=WOW_BORDER_GOLD,
            scrollbar_button_hover_color=WOW_BUTTON_BORDER,
            height=490
        )
        scroll.pack(fill="both", expand=True, padx=8, pady=4)

        # Section 0: The "Why" & The 1:1 Rule
        card_why = ctk.CTkFrame(scroll, fg_color="#141312", border_width=1, border_color="#5a451b", corner_radius=3)
        card_why.pack(fill="x", pady=4, padx=2)

        ctk.CTkLabel(
            card_why,
            text="⚖️ BLIZZARD ToS & ANTI-CHEAT CONTEXT (THE \"WHY\")",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color=WOW_ACCENT_GOLD
        ).pack(anchor="w", padx=10, pady=(8, 4))

        why_text = (
            "Blizzard enforces a strict line between internal game modifications and external text injections. "
            "External third-party scripts or applications (like AutoHotkey or automated background software) that "
            "forcefully inject text or bypass game mechanics violate the End User License Agreement (EULA Section 1.C) "
            "and can trigger automated bans via Blizzard's Warden anti-cheat.\n\n"
            "• The 1:1 Rule: Blizzard mandates that 1 human hardware action must correspond to exactly 1 in-game action. "
            "Multi-action automated macros (e.g. automatically opening chat, pasting text, pressing Enter, and clicking away unattended) "
            "are classified as automated botting.\n\n"
            "• The Accessibility Exception: Operating system assistive technologies and native hardware remapping are fully permitted "
            "and recognized by Blizzard as legitimate accessibility frameworks, provided they do not automate multiple gameplay actions per press."
        )
        ctk.CTkLabel(
            card_why,
            text=why_text,
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color=WOW_TEXT_LIGHT,
            wraplength=600,
            justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # Section 1: Active ToS Safe Mode: 3-Step Human Process (Current App State)
        card_opt1 = ctk.CTkFrame(scroll, fg_color="#141312", border_width=1, border_color="#385b2e", corner_radius=3)
        card_opt1.pack(fill="x", pady=4, padx=2)

        ctk.CTkLabel(
            card_opt1,
            text="🎤 ACTIVE ToS SAFE MODE: THE 3-STEP HUMAN PROCESS",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color="#4be361"
        ).pack(anchor="w", padx=10, pady=(8, 4))

        opt1_text = (
            "To remain 100% compliant with Blizzard's anti-cheat framework (Warden) and End User License Agreement (EULA), "
            "this application intentionally decouples speech-to-text chat into 3 distinct, human-initiated physical actions:\n\n"
            "1. ACTION 1: PRESS (Key Down) → Opens Chat Box\n"
            "   • What Happens: Pushing down your PTT key, mouse side button (Mouse 4/5), or controller trigger (LT/RT) "
            "dispatches an Enter keystroke to open the in-game text chat box and begins streaming microphone audio.\n"
            "   • Why It Meets ToS: This is standard 1:1 hardware key remapping (e.g. mapping a controller trigger or mouse button "
            "to act as the Enter key). Blizzard Support Article 13074 explicitly permits hardware remapping.\n\n"
            "2. ACTION 2: RELEASE (Key Up) → Pastes Formatted Text into Chat\n"
            "   • What Happens: Releasing the button stops recording. Faster-Whisper deciphers your voice locally, applies channel prefixes "
            "(/say, /p, /g), copies the payload to the OS clipboard, and pastes it into the open chat editbox (Ctrl + V). "
            "The text sits in the chat bar with the cursor flashing. NO automated Enter is sent!\n"
            "   • Why It Meets ToS: Standard OS clipboard copy-and-paste into an active text caret is 100% permitted. Faster-Whisper "
            "acts as an accessibility virtual keyboard typing characters sequentially. It does NOT modify game memory or inject DLLs. "
            "Crucially, the message is NOT submitted into the world—it sits waiting for your human review.\n\n"
            "3. ACTION 3: CLICK / TAP (Next Input) → Submits Finalized Message\n"
            "   • What Happens: Tapping the hotkey again, clicking, or pressing physical Enter on your keyboard submits the finalized "
            "message into the game world and triggers optional click-away to restore camera control.\n"
            "   • Why It Meets ToS: Submitting text into the game world requires a distinct, conscious human confirmation. "
            "No automated scripts run unattended.\n\n"
            "• SAFETY CANCELLATION: Press Escape at any time to cancel recording or discard pending text. "
            "An automatic 60-second safety timer also auto-cancels abandoned messages."
        )
        ctk.CTkLabel(
            card_opt1,
            text=opt1_text,
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color=WOW_TEXT_LIGHT,
            wraplength=600,
            justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # Section 1B: Why Having "One Button Do All 3" Violates Blizzard ToS
        card_violation = ctk.CTkFrame(scroll, fg_color="#1a1212", border_width=1, border_color="#8c1616", corner_radius=3)
        card_violation.pack(fill="x", pady=4, padx=2)

        ctk.CTkLabel(
            card_violation,
            text="🛑 WHY HAVING \"ONE BUTTON DO ALL 3\" VIOLATES BLIZZARD ToS",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color="#ff5252"
        ).pack(anchor="w", padx=10, pady=(8, 4))

        violation_text = (
            "Many players ask: 'Why can't one button press automatically open chat, paste the text, press Enter to send, "
            "and click away all at once?' Here is why that is strictly prohibited:\n\n"
            "• Violation of the 1:1 Hardware Rule (EULA Section 1.C.ii):\n"
            "  Blizzard mandates that 1 human physical hardware action must correspond to exactly 1 in-game action. "
            "  If one button press triggers: (1) Open Chat + (2) Paste Text + (3) Submit Enter + (4) Click Away, that is "
            "  FOUR in-game actions executed from a SINGLE human input. Under Blizzard's EULA, this is legally classified "
            "  as an unauthorized automated macro / bot.\n\n"
            "• Warden Anti-Cheat Heuristics & Detection Signatures:\n"
            "  Blizzard's Warden anti-cheat monitors programmatic input dispatch. Automated scripts that chain keystrokes "
            "  with uniform artificial pauses (e.g. 50ms delays between Open, Paste, Enter, and Click) exhibit synthetic, "
            "  inhuman timing signatures that trigger automated account suspensions.\n\n"
            "• Human Agency & Review Guarantee:\n"
            "  By enforcing PRESS (Open), RELEASE (Paste), and CLICK/TAP (Send), each stage requires physical human execution. "
            "  The user can visually verify what Whisper transcribed before deliberately choosing to transmit it into the game."
        )
        ctk.CTkLabel(
            card_violation,
            text=violation_text,
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color=WOW_TEXT_LIGHT,
            wraplength=600,
            justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # Section 2: Hardware Controller & Peripheral Integration
        card_opt2 = ctk.CTkFrame(scroll, fg_color="#141312", border_width=1, border_color="#204068", corner_radius=3)
        card_opt2.pack(fill="x", pady=4, padx=2)

        ctk.CTkLabel(
            card_opt2,
            text="🎮 HARDWARE CONTROLLER & PERIPHERAL INTEGRATION (ToS COMPLIANT)",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color="#63a4ff"
        ).pack(anchor="w", padx=10, pady=(8, 4))

        opt2_text = (
            "Blizzard's accessibility stance fully permits hardware key remapping via peripheral driver software (such as Logitech G Hub, "
            "Razer Synapse, Corsair iCUE) or this application's unified input bridge:\n\n"
            "• Mouse Side Buttons: Bind Mouse 4 or Mouse 5 for convenient thumb-activated dictation.\n"
            "• Gamepad & Trigger Support: Seamlessly bind Xbox and PlayStation controllers, including full analog trigger support for "
            "Xbox LT/RT and PlayStation L2/R2.\n"
            "• Dynamic Hotplugging: Controllers turned on after starting the app are instantly detected and ready for binding."
        )
        ctk.CTkLabel(
            card_opt2,
            text=opt2_text,
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color=WOW_TEXT_LIGHT,
            wraplength=600,
            justify="left"
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # Section 3: Official Source Documentation & Hyperlinks
        card_docs = ctk.CTkFrame(scroll, fg_color="#141312", border_width=1, border_color="#8a6d2b", corner_radius=3)
        card_docs.pack(fill="x", pady=4, padx=2)

        ctk.CTkLabel(
            card_docs,
            text="🔗 OFFICIAL SOURCE DOCUMENTATION & HYPERLINKS",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color=WOW_ACCENT_GOLD
        ).pack(anchor="w", padx=10, pady=(8, 2))

        ctk.CTkLabel(
            card_docs,
            text="Click any link below to open the official documentation directly in your web browser:",
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color=WOW_TEXT_LIGHT
        ).pack(anchor="w", padx=10, pady=(0, 6))

        doc_links = [
            (
                "Blizzard End User License Agreement (EULA)",
                "Section 1.C details prohibited automation, bots, hacks, and anti-cheat policies.",
                "https://www.blizzard.com/en-us/legal/fba4d21f-c7a4-4cc8-8546-0205577328b7/blizzard-end-user-license-agreement"
            ),
            (
                "Blizzard Support: Rules for Macros & Hardware Remapping",
                "Official Battle.net support article clarifying the 1:1 hardware rule and multi-action macro restrictions.",
                "https://us.battle.net/support/en/article/13074"
            ),
            (
                "Blizzard In-Game Code of Conduct",
                "Official standards on fair play, cheating, unauthorized software, and player interaction.",
                "https://battle.net/support/article/42673"
            ),
            (
                "Microsoft Support: Use Voice Typing on Windows (Win + H)",
                "Official documentation for native Windows 10/11 speech recognition, dictation shortcuts, and setup.",
                "https://support.microsoft.com/en-us/windows/use-voice-typing-to-talk-instead-of-type-on-your-pc-fec94565-c4bd-329d-e59a-af033fa5689f"
            )
        ]

        for title, desc, url in doc_links:
            self._create_doc_link_row(card_docs, title, desc, url)

        ctk.CTkLabel(card_docs, text="").pack(pady=2)

        # Bottom Action Bar
        bot_bar = ctk.CTkFrame(frame, fg_color="transparent")
        bot_bar.pack(fill="x", padx=10, pady=(6, 8))

        apply_btn = ctk.CTkButton(
            bot_bar,
            text="✔ Apply Recommended ToS Safe Settings",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color="#235c27",
            hover_color="#317d36",
            border_width=1,
            border_color="#45a049",
            text_color="#ffffff",
            height=28,
            command=self._apply_safe
        )
        apply_btn.pack(side="left", padx=(0, 6))

        close_btn = ctk.CTkButton(
            bot_bar,
            text="Close",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_BUTTON_GOLD,
            hover_color=WOW_BUTTON_HOVER,
            border_width=1,
            border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            width=80,
            height=28,
            command=self.destroy
        )
        close_btn.pack(side="right")

    def _open_url(self, url):
        try:
            webbrowser.open_new_tab(url)
        except Exception as e:
            print(f"Failed to open URL: {e}")

    def _create_doc_link_row(self, parent, title, desc, url):
        row = ctk.CTkFrame(parent, fg_color="#18181b", border_width=1, border_color="#383220", corner_radius=3)
        row.pack(fill="x", padx=10, pady=3)

        info_col = ctk.CTkFrame(row, fg_color="transparent")
        info_col.pack(side="left", fill="x", expand=True, padx=8, pady=6)

        title_lbl = ctk.CTkLabel(
            info_col,
            text=title,
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            text_color=WOW_ACCENT_GOLD,
            anchor="w"
        )
        title_lbl.pack(anchor="w")

        desc_lbl = ctk.CTkLabel(
            info_col,
            text=desc,
            font=ctk.CTkFont(family="Georgia", size=9),
            text_color=WOW_TEXT_LIGHT,
            wraplength=450,
            justify="left",
            anchor="w"
        )
        desc_lbl.pack(anchor="w", pady=(1, 0))

        btn = ctk.CTkButton(
            row,
            text="Open Link ↗",
            width=90,
            height=24,
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_ALLIANCE_BLUE,
            hover_color="#24508d",
            border_width=1,
            border_color="#457abf",
            text_color="#ffffff",
            command=lambda u=url: self._open_url(u)
        )
        btn.pack(side="right", padx=(4, 8), pady=6)
        ToolTip(btn, f"Open official documentation in your browser:\n{url}")

    def _apply_safe(self):
        if self.on_apply_safe_settings:
            self.on_apply_safe_settings()
        self.destroy()


# --- Floating HUD Overlay ---
class FloatingHUD(ctk.CTkToplevel):
    def __init__(self, parent, on_pos_changed=None):
        super().__init__(parent)
        self.parent_app = parent
        self.on_pos_changed = on_pos_changed

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-transparentcolor", "#101012")
        except Exception:
            pass
        self.configure(fg_color="#101012")

        self.start_x = 0
        self.start_y = 0
        self.rel_x = 40
        self.rel_y = 40
        self.target_rect = None  # (win_x, win_y, win_w, win_h)
        self.hud_w = 180
        self.hud_h = 34
        self.is_expanded = False
        self._dragging = False
        self.qm_rows = []

        # 1. Compact Standby Pill Frame
        self.pill_frame = ctk.CTkFrame(
            self,
            fg_color=WOW_FRAME_BG,
            border_width=1,
            border_color=WOW_BORDER_GOLD,
            corner_radius=12
        )
        self.pill_frame.pack(fill="both", expand=True, padx=2, pady=2)

        self.dot_label = ctk.CTkLabel(
            self.pill_frame,
            text="●",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#8a6d2b"
        )
        self.dot_label.pack(side="left", padx=(10, 4), pady=4)

        self.status_label = ctk.CTkLabel(
            self.pill_frame,
            text="STANDBY",
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            text_color=WOW_TEXT_LIGHT
        )
        self.status_label.pack(side="left", padx=(2, 10), pady=4)

        ToolTip(self.pill_frame, "Hold Shift + Left-Click to drag.\nDouble-Click to open Quick Access Menu.")
        ToolTip(self.status_label, "Hold Shift + Left-Click to drag.\nDouble-Click to open Quick Access Menu.")

        # 2. Expanded Quick Access Menu Frame (Hidden until double-clicked)
        self.quick_menu_frame = ctk.CTkFrame(
            self,
            fg_color=WOW_FRAME_BG,
            border_width=2,
            border_color=WOW_BORDER_GOLD,
            corner_radius=6
        )

        # Draggable & Double-Click bindings (Shift-drag only, Double-click to expand)
        for w in (self, self.pill_frame, self.dot_label, self.status_label):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._do_drag)
            w.bind("<ButtonRelease-1>", self._end_drag)
            w.bind("<Double-Button-1>", self._on_double_click)

        self.bind("<Escape>", lambda e: self.collapse_quick_menu() if self.is_expanded else None)

    def _is_shift_down(self, event=None):
        if event and (event.state & 0x0001):
            return True
        try:
            if ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000:
                return True
        except Exception:
            pass
        return False

    def ensure_topmost(self):
        try:
            self.lift()
            self.attributes("-topmost", True)
            if hasattr(self, "winfo_id"):
                hwnd = ctypes.windll.user32.GetAncestor(self.winfo_id(), 2)
                if not hwnd:
                    hwnd = self.winfo_id()
                # HWND_TOPMOST = -1, SWP_NOSIZE (1) | SWP_NOMOVE (2) | SWP_NOACTIVATE (16) | SWP_SHOWWINDOW (64)
                ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010 | 0x0040)
        except Exception:
            pass

    def deiconify(self):
        super().deiconify()
        self.ensure_topmost()

    def _start_drag(self, event):
        if self.is_expanded:
            self._dragging = False
            return
        if not self._is_shift_down(event):
            self._dragging = False
            return
        self._dragging = True
        self.start_x = event.x_root - self.winfo_x()
        self.start_y = event.y_root - self.winfo_y()

        if not self.target_rect and hasattr(self.parent_app, "resolve_target_window"):
            _, bounds = self.parent_app.resolve_target_window()
            if bounds:
                self.target_rect = bounds

    def _do_drag(self, event):
        if not self._dragging or self.is_expanded:
            return
        desired_screen_x = event.x_root - self.start_x
        desired_screen_y = event.y_root - self.start_y

        if self.target_rect:
            tx, ty, tw, th = self.target_rect
            cand_rel_x = desired_screen_x - tx
            cand_rel_y = desired_screen_y - ty
            max_rx = max(0, tw - self.hud_w)
            max_ry = max(0, th - self.hud_h)
            self.rel_x = max(0, min(cand_rel_x, max_rx))
            self.rel_y = max(0, min(cand_rel_y, max_ry))
            final_x = tx + self.rel_x
            final_y = ty + self.rel_y
        else:
            self.rel_x = max(0, desired_screen_x)
            self.rel_y = max(0, desired_screen_y)
            final_x = self.rel_x
            final_y = self.rel_y

        self.geometry(f"+{final_x}+{final_y}")

    def _end_drag(self, event):
        if not self._dragging:
            return
        self._dragging = False
        self.ensure_topmost()
        if self.on_pos_changed:
            self.on_pos_changed(self.rel_x, self.rel_y)

    def _on_double_click(self, event=None):
        self._dragging = False
        if not self.is_expanded:
            self.expand_quick_menu()

    def expand_quick_menu(self):
        if self.is_expanded:
            return
        self.is_expanded = True
        self.pill_frame.pack_forget()
        self._build_quick_menu()
        self.quick_menu_frame.pack(fill="both", expand=True, padx=2, pady=2)

        menu_w, menu_h = 580, 450
        cur_x = self.winfo_x()
        cur_y = self.winfo_y()

        if self.target_rect:
            tx, ty, tw, th = self.target_rect
            clamp_x = max(tx, min(cur_x, tx + max(0, tw - menu_w)))
            clamp_y = max(ty, min(cur_y, ty + max(0, th - menu_h)))
        else:
            try:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
            except Exception:
                sw, sh = 1920, 1080
            clamp_x = max(0, min(cur_x, sw - menu_w))
            clamp_y = max(0, min(cur_y, sh - menu_h))

        self.geometry(f"{menu_w}x{menu_h}+{clamp_x}+{clamp_y}")
        self.ensure_topmost()

    def collapse_quick_menu(self):
        if not self.is_expanded:
            return
        self.is_expanded = False
        self.quick_menu_frame.pack_forget()
        self.pill_frame.pack(fill="both", expand=True, padx=2, pady=2)

        if self.target_rect:
            tx, ty, tw, th = self.target_rect
            max_rx = max(0, tw - self.hud_w)
            max_ry = max(0, th - self.hud_h)
            self.rel_x = max(0, min(self.rel_x, max_rx))
            self.rel_y = max(0, min(self.rel_y, max_ry))
            final_x = tx + self.rel_x
            final_y = ty + self.rel_y
        else:
            final_x = self.rel_x
            final_y = self.rel_y

        self.geometry(f"{self.hud_w}x{self.hud_h}+{final_x}+{final_y}")
        self.ensure_topmost()

    def _build_quick_menu(self):
        for w in self.quick_menu_frame.winfo_children():
            w.destroy()
        self.qm_rows = []

        active_prof = self.parent_app.get_current_profile()
        prof_name = self.parent_app.config.get("active_profile", "Default")

        # Top Bar
        top_bar = ctk.CTkFrame(self.quick_menu_frame, fg_color="#181715", border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        top_bar.pack(fill="x", padx=8, pady=(8, 4))

        title_lbl = ctk.CTkLabel(
            top_bar,
            text=f"⚡ QUICK ACCESS: {prof_name.upper()}",
            font=ctk.CTkFont(family="Georgia", size=12, weight="bold"),
            text_color=WOW_ACCENT_GOLD
        )
        title_lbl.pack(side="left", padx=10, pady=6)

        min_btn = ctk.CTkButton(
            top_bar,
            text="Minimize",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_BUTTON_GOLD,
            hover_color=WOW_BUTTON_HOVER,
            border_width=1,
            border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            width=78,
            height=24,
            command=self.collapse_quick_menu
        )
        min_btn.pack(side="right", padx=6, pady=4)
        ToolTip(min_btn, "Collapse Quick Access back to the compact HUD pill.")

        # Hardware Card (Default Mic + Live VU)
        hw_card = ctk.CTkFrame(self.quick_menu_frame, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        hw_card.pack(fill="x", padx=8, pady=3)

        hw_r0 = ctk.CTkFrame(hw_card, fg_color="transparent")
        hw_r0.pack(fill="x", padx=8, pady=(6, 3))

        mic_lbl = ctk.CTkLabel(hw_r0, text="Default Mic:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT)
        mic_lbl.pack(side="left", padx=(0, 6))

        device_names = list(self.parent_app.device_map.keys()) or ["Default Microphone"]
        curr_dev_idx = self.parent_app.config.get("global_settings", {}).get("device_index")
        curr_choice = "Default Microphone"
        for name, idx in self.parent_app.device_map.items():
            if idx == curr_dev_idx:
                curr_choice = name
                break

        self.qm_mic_dropdown = ctk.CTkOptionMenu(
            hw_r0,
            values=device_names,
            width=320,
            fg_color=WOW_BUTTON_GOLD,
            button_color=WOW_BORDER_GOLD,
            button_hover_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            dropdown_fg_color=WOW_FRAME_BG,
            dropdown_text_color=WOW_TEXT_LIGHT,
            dropdown_hover_color=WOW_BUTTON_HOVER,
            font=ctk.CTkFont(family="Consolas", size=10)
        )
        self.qm_mic_dropdown.set(curr_choice)
        self.qm_mic_dropdown.pack(side="left", fill="x", expand=True, padx=(0, 6))

        hw_r1 = ctk.CTkFrame(hw_card, fg_color="transparent")
        hw_r1.pack(fill="x", padx=8, pady=(0, 6))

        vu_lbl = ctk.CTkLabel(hw_r1, text="Live Mic Level:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_ACCENT_GOLD)
        vu_lbl.pack(side="left", padx=(0, 6))

        self.qm_vu_bar = ctk.CTkProgressBar(
            hw_r1,
            progress_color=WOW_ACCENT_GOLD,
            fg_color="#0a0a0c",
            border_width=1,
            border_color=WOW_BORDER_GOLD,
            height=10
        )
        self.qm_vu_bar.set(0.0)
        self.qm_vu_bar.pack(side="left", fill="x", expand=True)

        # Bindings Section Card
        b_card = ctk.CTkFrame(self.quick_menu_frame, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        b_card.pack(fill="both", expand=True, padx=8, pady=3)

        b_top = ctk.CTkFrame(b_card, fg_color="transparent")
        b_top.pack(fill="x", padx=8, pady=(6, 3))

        b_title = ctk.CTkLabel(
            b_top,
            text="Push-to-Talk Bindings",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color=WOW_ACCENT_GOLD
        )
        b_title.pack(side="left")

        add_btn = ctk.CTkButton(
            b_top,
            text="+ Add Binding",
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_ALLIANCE_BLUE,
            hover_color="#24508d",
            width=95,
            height=22,
            command=self._qm_add_binding
        )
        add_btn.pack(side="right")

        # Scrollable container for bindings
        self.qm_scroll = ctk.CTkScrollableFrame(
            b_card,
            fg_color="transparent",
            scrollbar_button_color=WOW_BORDER_GOLD,
            scrollbar_button_hover_color=WOW_BUTTON_BORDER,
            height=180
        )
        self.qm_scroll.pack(fill="both", expand=True, padx=4, pady=(2, 6))

        for b in active_prof.get("bindings", []):
            self._qm_render_binding_row(b)

        # Bottom Bar
        bot_bar = ctk.CTkFrame(self.quick_menu_frame, fg_color="transparent")
        bot_bar.pack(fill="x", padx=8, pady=(4, 8))

        save_btn = ctk.CTkButton(
            bot_bar,
            text="✔ Save Changes",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color="#235c27",
            hover_color="#317d36",
            border_width=1,
            border_color="#45a049",
            text_color="#ffffff",
            width=120,
            height=26,
            command=self.save_quick_menu_changes
        )
        save_btn.pack(side="left", padx=4)

        cancel_btn = ctk.CTkButton(
            bot_bar,
            text="Minimize",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_BUTTON_GOLD,
            hover_color=WOW_BUTTON_HOVER,
            border_width=1,
            border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            width=85,
            height=26,
            command=self.collapse_quick_menu
        )
        cancel_btn.pack(side="right", padx=4)

    def _qm_render_binding_row(self, data):
        row = ctk.CTkFrame(self.qm_scroll, fg_color=WOW_FRAME_BG, border_width=1, border_color="#45381f", corner_radius=2)
        row.pack(fill="x", pady=2, padx=2)

        # Name
        n_lbl = ctk.CTkLabel(row, text="Name:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT)
        n_lbl.pack(side="left", padx=(6, 2))

        b_name = data.get("binding_name", "").strip()
        if not b_name:
            curr_names = [r["name_entry"].get().strip() for r in self.qm_rows]
            idx = 1
            while f"Input {idx}" in curr_names:
                idx += 1
            b_name = f"Input {idx}"

        name_entry = ctk.CTkEntry(row, width=95, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_ACCENT_GOLD, font=ctk.CTkFont(size=10))
        name_entry.insert(0, b_name)
        name_entry.pack(side="left", padx=2, pady=3)

        # Input
        in_lbl = ctk.CTkLabel(row, text="Input:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT)
        in_lbl.pack(side="left", padx=(4, 2))

        key_id = data.get("input_id", "f8")
        disp_name = data.get("display_name", format_input_label(key_id))

        key_entry = ctk.CTkEntry(row, width=105, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_ACCENT_GOLD, font=ctk.CTkFont(size=10))
        key_entry.insert(0, disp_name)
        key_entry._input_id = key_id
        key_entry.pack(side="left", padx=2)

        bind_btn = ctk.CTkButton(
            row, text="Bind", width=42, height=22,
            font=ctk.CTkFont(family="Georgia", size=9, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            command=lambda ke=key_entry: self._qm_launch_binding_capture(ke)
        )
        bind_btn.pack(side="left", padx=(0, 4))

        # Prefix
        pfx_lbl = ctk.CTkLabel(row, text="Pfx:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT)
        pfx_lbl.pack(side="left", padx=(2, 2))

        pfx_entry = ctk.CTkEntry(row, width=75, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_TEXT_LIGHT, font=ctk.CTkFont(size=10))
        pfx_entry.insert(0, data.get("prefix", ""))
        pfx_entry.pack(side="left", padx=2)

        # Suffix
        sfx_lbl = ctk.CTkLabel(row, text="Sfx:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT)
        sfx_lbl.pack(side="left", padx=(2, 2))

        sfx_entry = ctk.CTkEntry(row, width=75, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_TEXT_LIGHT, font=ctk.CTkFont(size=10))
        sfx_entry.insert(0, data.get("suffix", ""))
        sfx_entry.pack(side="left", padx=2)

        # Delete
        del_btn = ctk.CTkButton(
            row, text="✕", width=24, height=22,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=WOW_HORDE_RED, hover_color=WOW_HORDE_HOVER, text_color="#ffffff",
            command=lambda r=row: self._qm_remove_binding_row(r)
        )
        del_btn.pack(side="left", padx=(4, 4))

        self.qm_rows.append({
            "frame": row,
            "name_entry": name_entry,
            "key_entry": key_entry,
            "prefix_entry": pfx_entry,
            "suffix_entry": sfx_entry
        })

    def _qm_add_binding(self):
        curr_bindings = []
        for r in self.qm_rows:
            curr_bindings.append({
                "binding_name": r["name_entry"].get().strip(),
                "input_id": getattr(r["key_entry"], "_input_id", "f10")
            })
        def_name = get_next_default_binding_name(curr_bindings)
        new_data = {
            "binding_name": def_name,
            "input_id": "f10",
            "display_name": "F10",
            "prefix": "",
            "suffix": ""
        }
        self._qm_render_binding_row(new_data)

    def _qm_remove_binding_row(self, row_frame):
        self.qm_rows = [r for r in self.qm_rows if r["frame"] != row_frame]
        row_frame.destroy()

    def _qm_launch_binding_capture(self, key_entry):
        if not self.parent_app.engine or not self.parent_app.engine.input_manager:
            return

        def _on_captured(input_id, display_name):
            key_entry.delete(0, "end")
            key_entry.insert(0, display_name)
            key_entry._input_id = input_id

        InputCaptureDialog(self, self.parent_app.engine.input_manager, _on_captured)

    def save_quick_menu_changes(self):
        # 1. Update microphone if changed
        mic_name = self.qm_mic_dropdown.get()
        dev_idx = self.parent_app.device_map.get(mic_name)
        if "global_settings" not in self.parent_app.config:
            self.parent_app.config["global_settings"] = {}
        self.parent_app.config["global_settings"]["device_index"] = dev_idx

        # 2. Update bindings
        active_prof = self.parent_app.get_current_profile()
        prof_name = self.parent_app.config.get("active_profile", "Default")
        updated = []
        used_names = set()
        for r in self.qm_rows:
            raw_id = normalize_combo_id(getattr(r["key_entry"], "_input_id", r["key_entry"].get().strip().lower()))
            disp_name = format_input_label(raw_id)
            name_val = r["name_entry"].get().strip()
            if not name_val:
                idx = 1
                while f"Input {idx}" in used_names:
                    idx += 1
                name_val = f"Input {idx}"
            used_names.add(name_val)
            updated.append({
                "binding_name": name_val,
                "input_id": raw_id,
                "display_name": disp_name,
                "prefix": r["prefix_entry"].get(),
                "suffix": r["suffix_entry"].get()
            })

        active_prof["bindings"] = updated
        save_config(self.parent_app.config)

        # 3. Synchronize with main window
        self.parent_app.load_profile_ui_data()
        self.parent_app.populate_audio_devices()
        self.parent_app.restart_engine()
        self.parent_app.log(f"Quick Access: Profile [{prof_name}] bindings and mic settings saved.")

        # 4. Collapse back to pill
        self.collapse_quick_menu()

    def realign_to_window(self, win_x, win_y, win_w, win_h):
        self.target_rect = (win_x, win_y, win_w, win_h)
        if self.is_expanded:
            menu_w, menu_h = 580, 450
            cur_x = self.winfo_x()
            cur_y = self.winfo_y()
            clamp_x = max(win_x, min(cur_x, win_x + max(0, win_w - menu_w)))
            clamp_y = max(win_y, min(cur_y, win_y + max(0, win_h - menu_h)))
            self.geometry(f"{menu_w}x{menu_h}+{clamp_x}+{clamp_y}")
        else:
            max_rx = max(0, win_w - self.hud_w)
            max_ry = max(0, win_h - self.hud_h)
            self.rel_x = max(0, min(self.rel_x, max_rx))
            self.rel_y = max(0, min(self.rel_y, max_ry))
            final_x = win_x + self.rel_x
            final_y = win_y + self.rel_y
            self.geometry(f"{self.hud_w}x{self.hud_h}+{final_x}+{final_y}")
        self.ensure_topmost()

    def set_position(self, rel_x, rel_y):
        self.rel_x = int(rel_x)
        self.rel_y = int(rel_y)
        if not self.target_rect and hasattr(self.parent_app, "resolve_target_window"):
            _, bounds = self.parent_app.resolve_target_window()
            if bounds:
                self.target_rect = bounds
        if self.target_rect:
            tx, ty, tw, th = self.target_rect
            max_rx = max(0, tw - self.hud_w)
            max_ry = max(0, th - self.hud_h)
            self.rel_x = max(0, min(self.rel_x, max_rx))
            self.rel_y = max(0, min(self.rel_y, max_ry))
            final_x = tx + self.rel_x
            final_y = ty + self.rel_y
        else:
            final_x = self.rel_x
            final_y = self.rel_y
        if not self.is_expanded:
            self.geometry(f"{self.hud_w}x{self.hud_h}+{final_x}+{final_y}")
        self.ensure_topmost()

    def update_status(self, state, detail=""):
        try:
            if state == "recording":
                self.dot_label.configure(text_color="#ff2b2b")
                self.status_label.configure(text=f"REC [{detail}]" if detail else "RECORDING", text_color="#ff4d4d")
                self.pill_frame.configure(border_color="#ff2b2b")
            elif state == "transcribing":
                text = detail if detail else "DECIPHERING..."
                self.dot_label.configure(text_color="#ffd100")
                self.status_label.configure(text=text, text_color="#ffd100")
                self.pill_frame.configure(border_color="#ffd100")
            elif state == "pasted":
                self.dot_label.configure(text_color="#38ef7d")
                text = f"PASTED [{detail}]" if detail else "PASTED [TAP TO SEND]"
                self.status_label.configure(text=text, text_color="#38ef7d")
                self.pill_frame.configure(border_color="#38ef7d")
            else:
                self.dot_label.configure(text_color="#8a6d2b")
                self.status_label.configure(text="STANDBY", text_color=WOW_TEXT_LIGHT)
                self.pill_frame.configure(border_color=WOW_BORDER_GOLD)
        except Exception:
            pass


# --- Main Application Interface (WoWPTTApp) ---
class WoWPTTApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Register AppUserModelID for Windows Taskbar & Alt+Tab
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("speechtotext.chatinjector.v1")
        except Exception:
            pass

        self.title("Speech To Text Chat Injector")
        self.geometry("880x780")
        self.minsize(820, 680)
        self.configure(fg_color=WOW_BG_DARK)
        ctk.set_appearance_mode("dark")

        self.config = load_config()
        self.engine = None
        self.device_map = {}
        self.hud = None
        self.target_hwnd = 0

        self.profile_rows = []

        self.setup_ui()
        self.setup_hud()
        self.start_engine_thread()

        # Timers
        self.after(50, self.update_vu_loop)
        self.after(75, self.window_tracker_loop)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # --- Thread-Safe Logging ---
    def log(self, text):
        try:
            self.after(0, self._safe_log, text)
        except Exception:
            print(f"> {text}")

    def _safe_log(self, text):
        try:
            if self.winfo_exists():
                self.log_textbox.configure(state="normal")
                self.log_textbox.insert("end", f"> {text}\n")
                self.log_textbox.see("end")
                self.log_textbox.configure(state="disabled")
        except Exception:
            pass

    def setup_hud(self):
        active_prof = self.get_current_profile()
        overlay_cfg = active_prof.get("overlay", {})
        pos_x = overlay_cfg.get("pos_x", 40)
        pos_y = overlay_cfg.get("pos_y", 40)

        self.hud = FloatingHUD(self, on_pos_changed=self.on_hud_pos_changed)
        hwnd, bounds = self.resolve_target_window(force_refresh=True)
        if bounds:
            self.hud.target_rect = bounds
        self.hud.set_position(pos_x, pos_y)
        if not overlay_cfg.get("enabled", True):
            self.hud.withdraw()

    def resolve_target_window(self, force_refresh=False):
        """Resolves and returns (target_hwnd, bounds) for the current active profile.
        If force_refresh is False and self.target_hwnd is still valid and not iconic, returns existing."""
        try:
            if not force_refresh and self.target_hwnd and user32.IsWindow(self.target_hwnd):
                if not user32.IsIconic(self.target_hwnd):
                    bounds = get_window_bounds(self.target_hwnd)
                    if bounds:
                        return self.target_hwnd, bounds

            active_prof = self.get_current_profile()
            raw_procs = active_prof.get("target_process", "")
            raw_titles = active_prof.get("window_title", "")
            target_procs = [p.strip() for p in raw_procs.split(",") if p.strip()]
            target_titles = [t.strip() for t in raw_titles.split(",") if t.strip()]

            found_hwnd, bounds = find_target_window(target_procs, target_titles)
            if found_hwnd and bounds:
                self.target_hwnd = found_hwnd
                return found_hwnd, bounds
            elif force_refresh:
                self.target_hwnd = 0
        except Exception:
            pass
        return 0, None

    def on_hud_pos_changed(self, x, y):
        active_prof = self.get_current_profile()
        if "overlay" not in active_prof:
            active_prof["overlay"] = {}
        active_prof["overlay"]["pos_x"] = x
        active_prof["overlay"]["pos_y"] = y
        save_config(self.config)
        try:
            if hasattr(self, "hud_pos_label") and self.hud_pos_label.winfo_exists():
                self.hud_pos_label.configure(text=f"App-Rel: ({x}, {y})")
            if hasattr(self, "hud_pos_x_entry") and self.hud_pos_x_entry.winfo_exists():
                self.hud_pos_x_entry.delete(0, "end")
                self.hud_pos_x_entry.insert(0, str(x))
            if hasattr(self, "hud_pos_y_entry") and self.hud_pos_y_entry.winfo_exists():
                self.hud_pos_y_entry.delete(0, "end")
                self.hud_pos_y_entry.insert(0, str(y))
        except Exception:
            pass

    def hud_state_callback(self, state, detail=""):
        if self.hud:
            self.after(0, lambda: self.hud.update_status(state, detail))

    def window_tracker_loop(self):
        try:
            active_prof = self.get_current_profile()
            overlay_cfg = active_prof.get("overlay", {})
            if self.hud and overlay_cfg.get("enabled", True):
                fg_hwnd, cur_title, cur_proc = get_active_window_full_info()
                raw_procs = active_prof.get("target_process", "")
                raw_titles = active_prof.get("window_title", "")
                target_procs = [p.strip().lower() for p in raw_procs.split(",") if p.strip()]
                target_titles = [t.strip().lower() for t in raw_titles.split(",") if t.strip()]

                cur_proc_lower = cur_proc.lower() if cur_proc else ""
                cur_title_lower = cur_title.lower() if cur_title else ""

                is_target_focused = False
                if cur_proc_lower and any(tp in cur_proc_lower or cur_proc_lower in tp for tp in target_procs):
                    is_target_focused = True
                    self.target_hwnd = fg_hwnd
                elif cur_title_lower and (
                    any(tt in cur_title_lower or cur_title_lower in tt for tt in target_titles) or
                    any(tp in cur_title_lower for tp in target_procs)
                ):
                    is_target_focused = True
                    self.target_hwnd = fg_hwnd

                # If target_hwnd is not currently set or invalid, actively find the window
                if not self.target_hwnd or not user32.IsWindow(self.target_hwnd):
                    found_hwnd, _ = find_target_window(target_procs, target_titles)
                    if found_hwnd:
                        self.target_hwnd = found_hwnd

                # Real-time window movement tracking: check target_hwnd bounding box
                bounds = None
                is_target_minimized = False
                is_target_visible = False

                if self.target_hwnd and user32.IsWindow(self.target_hwnd):
                    if user32.IsIconic(self.target_hwnd):
                        is_target_minimized = True
                    else:
                        is_target_visible = bool(user32.IsWindowVisible(self.target_hwnd))
                        bounds = get_window_bounds(self.target_hwnd)

                if bounds:
                    tx, ty, tw, th = bounds
                    if self.hud.target_rect != bounds:
                        self.hud.realign_to_window(tx, ty, tw, th)

                # Determine if HUD should be visible
                should_show = False
                if self.hud.is_expanded:
                    should_show = True
                elif not overlay_cfg.get("bind_to_window", True):
                    should_show = True
                elif is_target_minimized:
                    should_show = False
                elif is_target_focused:
                    should_show = True
                elif self.target_hwnd and is_target_visible:
                    # Target application window is open, un-minimized and visible on screen
                    should_show = True
                elif hasattr(self, "settings_view_frame") and self.settings_view_frame.winfo_manager() == "pack":
                    should_show = True
                elif cur_proc_lower in ("python.exe", "pythonw.exe", "agy.exe"):
                    should_show = True
                elif not target_procs and not target_titles:
                    should_show = True

                if should_show:
                    if not self.hud.winfo_viewable():
                        self.hud.deiconify()
                else:
                    if self.hud.winfo_viewable():
                        self.hud.withdraw()
            elif self.hud and self.hud.winfo_viewable():
                self.hud.withdraw()
        except Exception:
            pass
        finally:
            self.after(75, self.window_tracker_loop)

    def update_vu_loop(self):
        try:
            if self.engine:
                lvl = self.engine.current_vu_level
                self.vu_bar.set(lvl)
                if self.hud and self.hud.is_expanded and hasattr(self.hud, "qm_vu_bar"):
                    self.hud.qm_vu_bar.set(lvl)
        except Exception:
            pass
        finally:
            self.after(33, self.update_vu_loop)

    def get_current_profile(self):
        act_name = self.config.get("active_profile", "World of Warcraft")
        profiles = self.config.get("app_profiles", {})
        if act_name not in profiles:
            if profiles:
                act_name = list(profiles.keys())[0]
                self.config["active_profile"] = act_name
            else:
                self.config["app_profiles"] = dict(DEFAULT_CONFIG["app_profiles"])
                act_name = "World of Warcraft"
                self.config["active_profile"] = act_name
        return self.config["app_profiles"][act_name]

    # --- UI Layout Setup ---
    def setup_ui(self):
        self.outer = ctk.CTkFrame(self, fg_color=WOW_FRAME_BG, border_width=2, border_color=WOW_BORDER_GOLD, corner_radius=4)
        self.outer.pack(fill="both", expand=True, padx=10, pady=10)

        # 1. Header Banner
        header = ctk.CTkFrame(self.outer, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 6))

        title_lbl = ctk.CTkLabel(
            header,
            text="SPEECH TO TEXT CHAT INJECTOR",
            font=ctk.CTkFont(family="Georgia", size=18, weight="bold"),
            text_color=WOW_ACCENT_GOLD
        )
        title_lbl.pack(side="left")
        ToolTip(title_lbl, "Speech To Text Chat Injector: Push-to-Talk speech recognition and in-game chat injection.")

        min_btn = ctk.CTkButton(
            header,
            text="Minimize",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_BUTTON_GOLD,
            hover_color=WOW_BUTTON_HOVER,
            border_width=1,
            border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            width=90,
            height=26,
            command=self.iconify
        )
        min_btn.pack(side="right", padx=(6, 0))
        ToolTip(min_btn, "Minimize this window to the taskbar. PTT hotkeys and HUD overlay remain active.")

        self.tos_guide_btn = ctk.CTkButton(
            header,
            text="🛡️ ToS Guide",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color="#1d3b20",
            hover_color="#2c5a31",
            border_width=1,
            border_color="#45a049",
            text_color="#85e89d",
            width=90,
            height=26,
            command=self.open_tos_guide_dialog
        )
        self.tos_guide_btn.pack(side="right", padx=(6, 6))
        ToolTip(self.tos_guide_btn, "Open Blizzard ToS compliance guide and configure Warden-safe voice dictation.")

        self.toggle_hud_btn = ctk.CTkButton(
            header,
            text="Toggle HUD",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_ALLIANCE_BLUE,
            hover_color="#24508d",
            border_width=1,
            border_color="#457abf",
            text_color="#ffffff",
            width=95,
            height=26,
            command=self.toggle_hud_visibility
        )
        self.toggle_hud_btn.pack(side="right")
        ToolTip(self.toggle_hud_btn, "Show or hide the floating on-screen status indicator pill.")

        # 2. Global Hardware Settings Card (Microphone, VU Meter, GPU Acceleration)
        global_frame = ctk.CTkFrame(self.outer, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        global_frame.pack(fill="x", padx=14, pady=6)

        # Row 0: Device Dropdown + GPU switch
        r0 = ctk.CTkFrame(global_frame, fg_color="transparent")
        r0.pack(fill="x", padx=12, pady=(8, 4))

        mic_lbl = ctk.CTkLabel(r0, text="Mic:", font=ctk.CTkFont(family="Georgia", size=12, weight="bold"), text_color=WOW_TEXT_LIGHT)
        mic_lbl.pack(side="left", padx=(0, 6))
        ToolTip(mic_lbl, "Select the active audio input device (microphone) used for speech recording.")

        self.device_dropdown = ctk.CTkOptionMenu(
            r0,
            values=["Default Microphone"],
            width=360,
            fg_color=WOW_BUTTON_GOLD,
            button_color=WOW_BORDER_GOLD,
            button_hover_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            dropdown_fg_color=WOW_FRAME_BG,
            dropdown_text_color=WOW_TEXT_LIGHT,
            dropdown_hover_color=WOW_BUTTON_HOVER,
            font=ctk.CTkFont(family="Consolas", size=11),
            command=self.on_device_changed
        )
        self.device_dropdown.pack(side="left", padx=(0, 16))

        eng_badge = ctk.CTkLabel(
            r0,
            text="⚡ Engine: Faster-Whisper CPU [int8]",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color="#a5d6a7",
            fg_color="#142416",
            corner_radius=4,
            padx=10,
            pady=3
        )
        eng_badge.pack(side="left")
        ToolTip(eng_badge, "Transcribes speech locally on CPU using quantized int8 inference for ultra-fast, lightweight performance without external GPU drivers.")

        # Row 1: Live VU Meter
        r1 = ctk.CTkFrame(global_frame, fg_color="transparent")
        r1.pack(fill="x", padx=12, pady=(2, 8))

        vu_lbl = ctk.CTkLabel(r1, text="Live Mic Level:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_ACCENT_GOLD)
        vu_lbl.pack(side="left", padx=(0, 8))
        ToolTip(vu_lbl, "Real-time audio signal volume. Speak into your microphone to verify audio capture.")

        self.vu_bar = ctk.CTkProgressBar(
            r1,
            progress_color=WOW_ACCENT_GOLD,
            fg_color="#0a0a0c",
            border_width=1,
            border_color=WOW_BORDER_GOLD,
            height=12
        )
        self.vu_bar.set(0.0)
        self.vu_bar.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.populate_audio_devices()

        # 3. Application Profiles Section Header Bar
        prof_bar = ctk.CTkFrame(self.outer, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        prof_bar.pack(fill="x", padx=14, pady=6)

        p_row = ctk.CTkFrame(prof_bar, fg_color="transparent")
        p_row.pack(fill="x", padx=12, pady=8)

        prof_title_lbl = ctk.CTkLabel(p_row, text="App Profile:", font=ctk.CTkFont(family="Georgia", size=13, weight="bold"), text_color=WOW_ACCENT_GOLD)
        prof_title_lbl.pack(side="left", padx=(0, 6))
        ToolTip(prof_title_lbl, "Switch, create, or delete settings profiles tailored to specific games or applications.")

        self.profile_names = list(self.config.get("app_profiles", {}).keys())
        self.profile_menu = ctk.CTkOptionMenu(
            p_row,
            values=self.profile_names,
            width=180,
            fg_color=WOW_BUTTON_GOLD,
            button_color=WOW_BORDER_GOLD,
            button_hover_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            dropdown_fg_color=WOW_FRAME_BG,
            dropdown_text_color=WOW_TEXT_LIGHT,
            dropdown_hover_color=WOW_BUTTON_HOVER,
            font=ctk.CTkFont(family="Georgia", size=12, weight="bold"),
            command=self.on_profile_switched
        )
        self.profile_menu.set(self.config.get("active_profile", "World of Warcraft"))
        self.profile_menu.pack(side="left", padx=(0, 8))

        new_p_btn = ctk.CTkButton(
            p_row, text="+ New", width=60, height=26,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_ALLIANCE_BLUE, hover_color="#24508d",
            command=self.add_new_profile_dialog
        )
        new_p_btn.pack(side="left", padx=3)
        ToolTip(new_p_btn, "Create a brand new application profile with custom hotkeys and settings.")

        del_p_btn = ctk.CTkButton(
            p_row, text="Delete", width=60, height=26,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_HORDE_RED, hover_color=WOW_HORDE_HOVER,
            command=self.delete_current_profile
        )
        del_p_btn.pack(side="left", padx=3)
        ToolTip(del_p_btn, "Delete the currently active application profile.")

        self.tos_status_badge = ctk.CTkLabel(
            p_row,
            text="🛡️ ToS Safe",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color="#38ef7d"
        )
        self.tos_status_badge.pack(side="left", padx=8)
        ToolTip(self.tos_status_badge, "Blizzard ToS Safe Mode: Multi-action injection suppressed. 100% Warden anti-cheat compliant.")

        # Settings button that navigates to the Settings setup page
        self.settings_btn = ctk.CTkButton(
            p_row, text="⚙ Settings", width=105, height=26,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT, command=self.show_settings_view
        )
        self.settings_btn.pack(side="right", padx=(10, 0))
        ToolTip(self.settings_btn, "Configure target application process, chat injection lifecycle, and HUD overlay for this profile.")
        ToolTip(self.settings_btn, "Configure target application process, chat injection lifecycle, and HUD overlay for this profile.")

        # 4. View Container (Holds Main View vs Settings Setup View)
        self.view_container = ctk.CTkFrame(self.outer, fg_color="transparent")
        self.view_container.pack(fill="both", expand=True, padx=0, pady=0)

        # Build Both Views
        self._build_main_view()
        self._build_settings_view()

        # Show Main View by default
        self.show_main_view()

    # --- VIEW 1: Main PTT Bindings & System Log View ---
    def _build_main_view(self):
        self.main_view_frame = ctk.CTkFrame(self.view_container, fg_color="transparent")

        # PTT Bindings Card
        self.bindings_card = ctk.CTkFrame(self.main_view_frame, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        self.bindings_card.pack(fill="both", expand=True, padx=14, pady=4)

        b_header = ctk.CTkFrame(self.bindings_card, fg_color="transparent")
        b_header.pack(fill="x", padx=12, pady=(10, 4))

        bind_header_lbl = ctk.CTkLabel(
            b_header,
            text="Push-to-Talk Bindings (Keys, Mouse 4/5, Gamepads)",
            font=ctk.CTkFont(family="Georgia", size=13, weight="bold"),
            text_color=WOW_ACCENT_GOLD
        )
        bind_header_lbl.pack(side="left")
        ToolTip(bind_header_lbl, "Push-to-Talk triggers: hold down any bound key, mouse side button, or controller button to speak.")

        add_b_btn = ctk.CTkButton(
            b_header,
            text="+ Add Binding",
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_ALLIANCE_BLUE,
            hover_color="#24508d",
            border_width=1,
            border_color="#457abf",
            text_color="#ffffff",
            width=110,
            height=26,
            command=self.add_binding_row
        )
        add_b_btn.pack(side="right")
        ToolTip(add_b_btn, "Add a new Push-to-Talk hotkey or gamepad binding to this profile.")

        # Scrollable container for bindings
        self.scroll_bindings = ctk.CTkScrollableFrame(
            self.bindings_card,
            fg_color="transparent",
            scrollbar_button_color=WOW_BORDER_GOLD,
            scrollbar_button_hover_color=WOW_BUTTON_BORDER
        )
        self.scroll_bindings.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        # Combat Log Console
        log_frame = ctk.CTkFrame(self.main_view_frame, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        log_frame.pack(fill="x", padx=14, pady=(4, 10))

        log_title_lbl = ctk.CTkLabel(log_frame, text="System Log", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_ACCENT_GOLD)
        log_title_lbl.pack(anchor="w", padx=10, pady=(4, 1))
        ToolTip(log_title_lbl, "Live activity and diagnostic console showing input events, Whisper status, and macro injections.")

        self.log_textbox = ctk.CTkTextbox(
            log_frame,
            height=110,
            fg_color="#0a0a0c",
            text_color="#ffd100",
            border_width=1,
            border_color="#363024",
            font=ctk.CTkFont(family="Consolas", size=10),
            state="disabled"
        )
        self.log_textbox.pack(fill="x", padx=8, pady=(0, 8))

    # --- VIEW 2: Settings Setup View ---
    def _build_settings_view(self):
        self.settings_view_frame = ctk.CTkFrame(self.view_container, fg_color="transparent")

        # Top Banner for Settings Page
        st_header = ctk.CTkFrame(self.settings_view_frame, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        st_header.pack(fill="x", padx=14, pady=(4, 6))

        self.st_header_title = ctk.CTkLabel(
            st_header,
            text="PROFILE SETTINGS",
            font=ctk.CTkFont(family="Georgia", size=14, weight="bold"),
            text_color=WOW_ACCENT_GOLD
        )
        self.st_header_title.pack(side="left", padx=14, pady=8)

        # Scrollable Settings Form
        scroll_settings = ctk.CTkScrollableFrame(
            self.settings_view_frame,
            fg_color="transparent",
            scrollbar_button_color=WOW_BORDER_GOLD,
            scrollbar_button_hover_color=WOW_BUTTON_BORDER
        )
        scroll_settings.pack(fill="both", expand=True, padx=14, pady=4)

        # 0. Blizzard ToS Safe Mode & Accessibility Card
        tos_card = ctk.CTkFrame(scroll_settings, fg_color="#101812", border_width=1, border_color="#2e7d32", corner_radius=3)
        tos_card.pack(fill="x", pady=4)

        tos_head = ctk.CTkFrame(tos_card, fg_color="transparent")
        tos_head.pack(fill="x", padx=12, pady=(8, 2))
        tos_title = ctk.CTkLabel(tos_head, text="🛡️ Blizzard ToS Safe Mode & Accessibility", font=ctk.CTkFont(family="Georgia", size=13, weight="bold"), text_color="#4caf50")
        tos_title.pack(side="left")
        ToolTip(tos_title, "Ensures 1:1 hardware compliance with Blizzard Warden anti-cheat rules. Multi-action automated macros are strictly suppressed.")

        view_guide_btn = ctk.CTkButton(
            tos_head,
            text="📖 ToS & Warden Guide",
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color="#1b4d20",
            hover_color="#2e7d32",
            border_width=1,
            border_color="#4caf50",
            text_color="#c8e6c9",
            width=140,
            height=22,
            command=self.open_tos_guide_dialog
        )
        view_guide_btn.pack(side="right")
        ToolTip(view_guide_btn, "Open comprehensive guide on Blizzard ToS, Warden anti-cheat rules, and 3 safe accessibility options.")

        # Subtitle / Description
        desc_lbl = ctk.CTkLabel(
            tos_card,
            text="Warden-Compliant 3-Step Human Process:\n"
                 "• Action 1 (PRESS): Opens chat box (Enter) & records voice locally via Faster-Whisper (1:1 Hardware Remap).\n"
                 "• Action 2 (RELEASE): Transcribes & pastes formatted text into chat via clipboard (Ctrl + V); text sits in chat awaiting confirmation.\n"
                 "• Action 3 (CLICK / TAP): Tap hotkey again (or press Enter) to confirm and send message into game.\n"
                 "⚠️ Why Not 1 Button? Having 1 button automate Open + Type + Send + Click-away executes 4 in-game actions from 1 input, which violates Blizzard's 1:1 Rule and is classified as botting under EULA Section 1.C.",
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color="#a5d6a7",
            wraplength=720,
            justify="left"
        )
        desc_lbl.pack(anchor="w", padx=12, pady=(2, 4))

        # Row 1: Enable checkbox + Auto-Open Chat option
        tos_row1 = ctk.CTkFrame(tos_card, fg_color="transparent")
        tos_row1.pack(fill="x", padx=12, pady=(4, 8))

        self.tos_safe_enabled_var = ctk.BooleanVar(value=True)
        self.tos_safe_enabled_cb = ctk.CTkCheckBox(
            tos_row1,
            text="Enable WoW ToS Safe Mode (Hold to Dictate, Tap to Send)",
            variable=self.tos_safe_enabled_var,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color="#e8f5e9",
            fg_color="#2e7d32",
            hover_color="#388e3c",
            command=self.on_tos_safe_toggle
        )
        self.tos_safe_enabled_cb.pack(side="left", padx=(0, 20))
        ToolTip(self.tos_safe_enabled_cb, "When enabled, transcribes speech via Faster-Whisper, pastes into chat via clipboard, and waits for a 2nd manual tap to send—100% compliant with Blizzard's 1:1 hardware rule.")

        self.tos_auto_open_var = ctk.BooleanVar(value=True)
        self.tos_auto_open_cb = ctk.CTkCheckBox(
            tos_row1,
            text="Auto-Open Chat Box on Hold (Enter)",
            variable=self.tos_auto_open_var,
            font=ctk.CTkFont(family="Georgia", size=10),
            text_color=WOW_TEXT_LIGHT,
            fg_color=WOW_BORDER_GOLD
        )
        self.tos_auto_open_cb.pack(side="left")
        ToolTip(self.tos_auto_open_cb, "When checked, opens the chat box (e.g. Enter) on initial button press so the typing caret is active while speaking.")

        # 1. Target Application Process Card
        target_card = ctk.CTkFrame(scroll_settings, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        target_card.pack(fill="x", pady=4)

        t_head = ctk.CTkFrame(target_card, fg_color="transparent")
        t_head.pack(fill="x", padx=12, pady=(8, 2))
        t_lbl = ctk.CTkLabel(t_head, text="Target Game / Application", font=ctk.CTkFont(family="Georgia", size=13, weight="bold"), text_color=WOW_ACCENT_GOLD)
        t_lbl.pack(side="left")
        ToolTip(t_lbl, "The process name or window title of the application to interact with and bind the HUD overlay to.")

        t_row = ctk.CTkFrame(target_card, fg_color="transparent")
        t_row.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(t_row, text="Target Process:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT).pack(side="left", padx=(0, 6))
        self.target_proc_entry = ctk.CTkEntry(t_row, width=220, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_TEXT_LIGHT)
        self.target_proc_entry.pack(side="left", padx=4)

        detect_btn = ctk.CTkButton(
            t_row, text="Auto-Detect ▾", width=110, height=26,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT, command=self.open_autodetect_dialog
        )
        detect_btn.pack(side="left", padx=6)
        ToolTip(detect_btn, "Auto-detect the last 3 opened applications to choose as your target process.")

        # 2. Chat Injection Lifecycle Actions Card
        lifecycle_card = ctk.CTkFrame(scroll_settings, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        lifecycle_card.pack(fill="x", pady=6)

        lc_header = ctk.CTkFrame(lifecycle_card, fg_color="transparent")
        lc_header.pack(fill="x", padx=12, pady=(8, 2))
        lc_title = ctk.CTkLabel(lc_header, text="Chat Injection Lifecycle Actions", font=ctk.CTkFont(family="Georgia", size=13, weight="bold"), text_color=WOW_ACCENT_GOLD)
        lc_title.pack(side="left")
        ToolTip(lc_title, "Configure how text is injected: opening chat, sending messages, and closing chat or clicking away.")

        # Row 1: Open Chat & Send Message
        lc_row1 = ctk.CTkFrame(lifecycle_card, fg_color="transparent")
        lc_row1.pack(fill="x", padx=12, pady=4)

        open_k_lbl = ctk.CTkLabel(lc_row1, text="Open Chat Key:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT)
        open_k_lbl.pack(side="left", padx=(0, 4))
        ToolTip(open_k_lbl, "Keystroke or button pressed to open the in-game chat box before typing (default: Enter).")

        self.open_key_entry = ctk.CTkEntry(lc_row1, width=110, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_ACCENT_GOLD)
        self.open_key_entry.pack(side="left", padx=4)
        ctk.CTkButton(
            lc_row1, text="Bind", width=50, height=24, font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT, command=lambda: self.bind_single_action(self.open_key_entry, "open_chat_key")
        ).pack(side="left", padx=(2, 20))

        send_k_lbl = ctk.CTkLabel(lc_row1, text="Send Message Key:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT)
        send_k_lbl.pack(side="left", padx=(0, 4))
        ToolTip(send_k_lbl, "Keystroke or button pressed to submit each chat message chunk (default: Enter).")

        self.send_key_entry = ctk.CTkEntry(lc_row1, width=110, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_ACCENT_GOLD)
        self.send_key_entry.pack(side="left", padx=4)
        self.send_key_bind_btn = ctk.CTkButton(
            lc_row1, text="Bind", width=50, height=24, font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT, command=lambda: self.bind_single_action(self.send_key_entry, "send_message_key")
        )
        self.send_key_bind_btn.pack(side="left", padx=(2, 0))

        # Row 2: Close Chat (Click-Away Checkbox vs Hotkey)
        lc_row2 = ctk.CTkFrame(lifecycle_card, fg_color="transparent")
        lc_row2.pack(fill="x", padx=12, pady=4)

        self.click_away_var = ctk.BooleanVar(value=True)
        self.click_away_cb = ctk.CTkCheckBox(
            lc_row2,
            text="Click Away to Restore Focus",
            variable=self.click_away_var,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            text_color=WOW_TEXT_LIGHT,
            fg_color=WOW_BORDER_GOLD,
            hover_color=WOW_ACCENT_GOLD,
            command=self.on_click_away_toggle
        )
        self.click_away_cb.pack(side="left", padx=(0, 20))
        ToolTip(self.click_away_cb, "When enabled, left-clicks the screen after sending to restore camera / mouselook control. Automatically disables the close chat hotkey.")

        close_k_lbl = ctk.CTkLabel(lc_row2, text="Close Chat Hotkey:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT)
        close_k_lbl.pack(side="left", padx=(0, 4))
        ToolTip(close_k_lbl, "Keystroke sent to dismiss or close the chat box (active only when Click Away is unchecked).")

        self.close_key_entry = ctk.CTkEntry(lc_row2, width=110, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_ACCENT_GOLD)
        self.close_key_entry.pack(side="left", padx=4)
        self.close_key_bind_btn = ctk.CTkButton(
            lc_row2, text="Bind", width=50, height=24, font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT, command=lambda: self.bind_single_action(self.close_key_entry, "close_chat_key")
        )
        self.close_key_bind_btn.pack(side="left", padx=4)

        # Row 3: Advanced Click Coordinates
        self.click_coords_frame = ctk.CTkFrame(lifecycle_card, fg_color="#141416", border_width=1, border_color="#363024", corner_radius=3)
        self.click_coords_frame.pack(fill="x", padx=12, pady=(4, 10))

        loc_lbl = ctk.CTkLabel(self.click_coords_frame, text="Click Location:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT)
        loc_lbl.pack(side="left", padx=(10, 4), pady=4)
        ToolTip(loc_lbl, "Position on screen where the focus click is sent (Screen Center or Custom X, Y coordinates).")

        self.click_target_menu = ctk.CTkOptionMenu(
            self.click_coords_frame,
            values=["Screen Center", "Custom Coordinates"],
            width=140,
            fg_color=WOW_BUTTON_GOLD,
            button_color=WOW_BORDER_GOLD,
            text_color=WOW_TEXT_LIGHT,
            dropdown_fg_color=WOW_FRAME_BG,
            font=ctk.CTkFont(family="Georgia", size=10),
            command=self.on_click_target_changed
        )
        self.click_target_menu.pack(side="left", padx=4, pady=4)

        ctk.CTkLabel(self.click_coords_frame, text="X:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT).pack(side="left", padx=(10, 2))
        self.coord_x_entry = ctk.CTkEntry(self.click_coords_frame, width=60, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_TEXT_LIGHT, font=ctk.CTkFont(size=10))
        self.coord_x_entry.pack(side="left", padx=2)

        ctk.CTkLabel(self.click_coords_frame, text="Y:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT).pack(side="left", padx=(6, 2))
        self.coord_y_entry = ctk.CTkEntry(self.click_coords_frame, width=60, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_TEXT_LIGHT, font=ctk.CTkFont(size=10))
        self.coord_y_entry.pack(side="left", padx=2)

        self.pick_coords_btn = ctk.CTkButton(
            self.click_coords_frame, text="Pick Cursor Pos", width=105, height=22,
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT, command=self.pick_current_mouse_pos
        )
        self.pick_coords_btn.pack(side="left", padx=(10, 8))
        ToolTip(self.pick_coords_btn, "Capture your mouse's current screen position as the custom coordinates.")

        # 3. Floating HUD Overlay Options Card
        hud_card = ctk.CTkFrame(scroll_settings, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        hud_card.pack(fill="x", pady=4)

        h_head = ctk.CTkFrame(hud_card, fg_color="transparent")
        h_head.pack(fill="x", padx=12, pady=(8, 2))
        hud_sec_lbl = ctk.CTkLabel(h_head, text="Floating HUD Overlay Configuration", font=ctk.CTkFont(family="Georgia", size=13, weight="bold"), text_color=WOW_ACCENT_GOLD)
        hud_sec_lbl.pack(side="left")
        ToolTip(hud_sec_lbl, "Configure the floating on-screen recording status pill for this profile.")

        h_row = ctk.CTkFrame(hud_card, fg_color="transparent")
        h_row.pack(fill="x", padx=12, pady=(4, 4))

        self.hud_enabled_var = ctk.BooleanVar(value=True)
        self.hud_enabled_cb = ctk.CTkCheckBox(
            h_row, text="Enable Floating HUD Overlay", variable=self.hud_enabled_var,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT,
            fg_color=WOW_BORDER_GOLD
        )
        self.hud_enabled_cb.pack(side="left", padx=(0, 16))
        ToolTip(self.hud_enabled_cb, "Display an on-screen status indicator pill (Standby, Recording, Transcribing).")

        self.hud_bind_win_var = ctk.BooleanVar(value=True)
        self.hud_bind_win_cb = ctk.CTkCheckBox(
            h_row, text="Show Only When Target Game is Focused", variable=self.hud_bind_win_var,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT,
            fg_color=WOW_BORDER_GOLD
        )
        self.hud_bind_win_cb.pack(side="left", padx=(0, 16))
        ToolTip(self.hud_bind_win_cb, "Automatically hide the HUD overlay when your target game is in the background.")

        # HUD Position Controls Sub-Frame
        pos_frame = ctk.CTkFrame(hud_card, fg_color="#141416", border_width=1, border_color="#363024", corner_radius=3)
        pos_frame.pack(fill="x", padx=12, pady=(4, 10))

        pos_title = ctk.CTkLabel(pos_frame, text="HUD Position (App-Relative):", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT)
        pos_title.pack(side="left", padx=(10, 8), pady=6)
        ToolTip(pos_title, "Configure pixel coordinates (X, Y) relative to the top-left of the target application window. The HUD is locked inside the game window boundaries.")

        ctk.CTkLabel(pos_frame, text="X:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT).pack(side="left", padx=(4, 2))
        self.hud_pos_x_entry = ctk.CTkEntry(pos_frame, width=55, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_ACCENT_GOLD, font=ctk.CTkFont(family="Consolas", size=11))
        self.hud_pos_x_entry.pack(side="left", padx=(0, 8))
        ToolTip(self.hud_pos_x_entry, "Horizontal pixel offset from the left edge of your target application window.")

        ctk.CTkLabel(pos_frame, text="Y:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT).pack(side="left", padx=(4, 2))
        self.hud_pos_y_entry = ctk.CTkEntry(pos_frame, width=55, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_ACCENT_GOLD, font=ctk.CTkFont(family="Consolas", size=11))
        self.hud_pos_y_entry.pack(side="left", padx=(0, 10))
        ToolTip(self.hud_pos_y_entry, "Vertical pixel offset from the top edge of your target application window.")

        self.hud_apply_pos_btn = ctk.CTkButton(
            pos_frame, text="Apply Position", width=95, height=24,
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT, command=self.apply_hud_pos_from_entries
        )
        self.hud_apply_pos_btn.pack(side="left", padx=4)
        ToolTip(self.hud_apply_pos_btn, "Immediately move the HUD to these coordinates and bring it forward so you can preview its location.")

        ctk.CTkLabel(pos_frame, text="Preset:", font=ctk.CTkFont(family="Georgia", size=10, weight="bold"), text_color=WOW_TEXT_LIGHT).pack(side="left", padx=(8, 2))
        self.hud_preset_menu = ctk.CTkOptionMenu(
            pos_frame,
            values=["Presets ▾", "Top-Left", "Top-Center", "Top-Right", "Bottom-Left", "Bottom-Center", "Bottom-Right", "Center"],
            width=115, height=24,
            fg_color=WOW_BUTTON_GOLD,
            button_color=WOW_BORDER_GOLD,
            text_color=WOW_TEXT_LIGHT,
            dropdown_fg_color=WOW_FRAME_BG,
            font=ctk.CTkFont(family="Georgia", size=10),
            command=self.on_hud_preset_selected
        )
        self.hud_preset_menu.pack(side="left", padx=4)
        ToolTip(self.hud_preset_menu, "Quickly snap the HUD into any standard screen corner or center position.")

        self.hud_pick_pos_btn = ctk.CTkButton(
            pos_frame, text="Pick Cursor Pos", width=105, height=24,
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT, command=self.pick_hud_cursor_pos
        )
        self.hud_pick_pos_btn.pack(side="left", padx=4)
        ToolTip(self.hud_pick_pos_btn, "Capture your mouse's current screen position as the HUD location.")

        self.hud_pos_label = ctk.CTkLabel(
            pos_frame, text="HUD Pos: (80, 80)",
            font=ctk.CTkFont(family="Consolas", size=10), text_color=WOW_ACCENT_GOLD
        )
        self.hud_pos_label.pack(side="right", padx=10)
        ToolTip(self.hud_pos_label, "Screen coordinates of the draggable HUD overlay (saved per profile).")

        # Bottom Bar for Settings Page: Single Save Button + Back Button
        bot_actions = ctk.CTkFrame(self.settings_view_frame, fg_color=WOW_BG_DARK, border_width=1, border_color=WOW_BORDER_GOLD, corner_radius=3)
        bot_actions.pack(fill="x", padx=14, pady=(8, 10))

        save_btn = ctk.CTkButton(
            bot_actions,
            text="Save Settings",
            width=140,
            height=30,
            font=ctk.CTkFont(family="Georgia", size=12, weight="bold"),
            fg_color=WOW_ALLIANCE_BLUE,
            hover_color="#24508d",
            border_width=1,
            border_color="#457abf",
            text_color="#ffffff",
            command=self.save_settings_page_and_return
        )
        save_btn.pack(side="left", padx=14, pady=8)
        ToolTip(save_btn, "Save all configuration changes for this profile and return to the main display.")

        back_btn = ctk.CTkButton(
            bot_actions,
            text="Back",
            width=100,
            height=30,
            font=ctk.CTkFont(family="Georgia", size=12, weight="bold"),
            fg_color=WOW_BUTTON_GOLD,
            hover_color=WOW_BUTTON_HOVER,
            border_width=1,
            border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            command=self.show_main_view
        )
        back_btn.pack(side="left", padx=6, pady=8)
        ToolTip(back_btn, "Return to the main display.")

    # --- View Switching Methods ---
    def show_main_view(self):
        self.settings_view_frame.pack_forget()
        self.main_view_frame.pack(fill="both", expand=True)
        self.load_profile_ui_data()

    def show_settings_view(self):
        active_prof = self.get_current_profile()
        prof_name = self.config.get("active_profile", "World of Warcraft")
        self.st_header_title.configure(text=f"PROFILE SETTINGS: [{prof_name.upper()}]")

        self.populate_settings_view_data()
        self.main_view_frame.pack_forget()
        self.settings_view_frame.pack(fill="both", expand=True)

    def populate_settings_view_data(self):
        active_prof = self.get_current_profile()

        # 0. Blizzard ToS Safe Mode
        tos = active_prof.get("tos_safe_mode", {
            "enabled": True,
            "auto_open_chat": True
        })
        self.tos_safe_enabled_var.set(tos.get("enabled", True))
        self.tos_auto_open_var.set(tos.get("auto_open_chat", True))

        # Target Process
        self.target_proc_entry.delete(0, "end")
        self.target_proc_entry.insert(0, active_prof.get("target_process", ""))

        # Chat Lifecycle
        lc = active_prof.get("chat_lifecycle", {})
        open_k = lc.get("open_chat_key", "enter")
        send_k = lc.get("send_message_key", "enter")
        close_k = lc.get("close_chat_key", "escape")

        self.open_key_entry.delete(0, "end")
        self.open_key_entry.insert(0, format_input_label(open_k))
        self.open_key_entry._input_id = open_k

        self.send_key_entry.delete(0, "end")
        self.send_key_entry.insert(0, format_input_label(send_k))
        self.send_key_entry._input_id = send_k

        self.close_key_entry.delete(0, "end")
        self.close_key_entry.insert(0, format_input_label(close_k))
        self.close_key_entry._input_id = close_k

        ca = lc.get("click_away", {})
        is_ca = ca.get("enabled", True)
        self.click_away_var.set(is_ca)

        target = ca.get("target", "center")
        self.click_target_menu.set("Screen Center" if target == "center" else "Custom Coordinates")

        self.coord_x_entry.delete(0, "end")
        self.coord_x_entry.insert(0, str(ca.get("custom_x", 960)))

        self.coord_y_entry.delete(0, "end")
        self.coord_y_entry.insert(0, str(ca.get("custom_y", 540)))

        # Overlay Options
        ov = active_prof.get("overlay", {})
        self.hud_enabled_var.set(ov.get("enabled", True))
        self.hud_bind_win_var.set(ov.get("bind_to_window", True))
        px = ov.get("pos_x", 80)
        py = ov.get("pos_y", 80)
        if hasattr(self, "hud_pos_x_entry"):
            self.hud_pos_x_entry.delete(0, "end")
            self.hud_pos_x_entry.insert(0, str(px))
        if hasattr(self, "hud_pos_y_entry"):
            self.hud_pos_y_entry.delete(0, "end")
            self.hud_pos_y_entry.insert(0, str(py))
        self.hud_pos_label.configure(text=f"App-Rel: ({px}, {py})")

        hwnd, bounds = self.resolve_target_window()
        if self.hud:
            if bounds:
                self.hud.target_rect = bounds
                self.hud.realign_to_window(bounds[0], bounds[1], bounds[2], bounds[3])
            else:
                self.hud.set_position(px, py)

        # Update dynamic greying out
        self.on_tos_safe_toggle()

    def save_settings_page_and_return(self):
        active_prof = self.get_current_profile()
        prof_name = self.config.get("active_profile", "World of Warcraft")

        # 0. Blizzard ToS Safe Mode
        if "tos_safe_mode" not in active_prof:
            active_prof["tos_safe_mode"] = {}
        active_prof["tos_safe_mode"]["enabled"] = self.tos_safe_enabled_var.get()
        active_prof["tos_safe_mode"]["auto_open_chat"] = self.tos_auto_open_var.get()

        # 1. Target Process
        active_prof["target_process"] = self.target_proc_entry.get().strip()

        # 2. Chat Lifecycle
        if "chat_lifecycle" not in active_prof:
            active_prof["chat_lifecycle"] = {}

        lc = active_prof["chat_lifecycle"]
        lc["open_chat_key"] = getattr(self.open_key_entry, "_input_id", self.open_key_entry.get().strip().lower())
        lc["send_message_key"] = getattr(self.send_key_entry, "_input_id", self.send_key_entry.get().strip().lower())
        lc["close_chat_key"] = getattr(self.close_key_entry, "_input_id", self.close_key_entry.get().strip().lower())

        is_ca = self.click_away_var.get()
        target_mode = "center" if self.click_target_menu.get() == "Screen Center" else "custom"

        try:
            cx = int(self.coord_x_entry.get().strip())
            cy = int(self.coord_y_entry.get().strip())
        except ValueError:
            cx, cy = 960, 540

        lc["click_away"] = {
            "enabled": is_ca,
            "target": target_mode,
            "custom_x": cx,
            "custom_y": cy,
            "mouse_button": "left"
        }
        lc["close_chat_mode"] = "click_away" if is_ca else "hotkey"

        # 3. HUD Overlay Options
        if "overlay" not in active_prof:
            active_prof["overlay"] = {}
        active_prof["overlay"]["enabled"] = self.hud_enabled_var.get()
        active_prof["overlay"]["bind_to_window"] = self.hud_bind_win_var.get()

        try:
            hx = int(self.hud_pos_x_entry.get().strip())
            hy = int(self.hud_pos_y_entry.get().strip())
        except (ValueError, AttributeError):
            hx, hy = 80, 80

        active_prof["overlay"]["pos_x"] = hx
        active_prof["overlay"]["pos_y"] = hy

        save_config(self.config)
        self.log(f"Profile [{prof_name}] settings updated and saved.")

        # Immediately resolve target window for new settings and lock HUD
        hwnd, bounds = self.resolve_target_window(force_refresh=True)
        if self.hud:
            if bounds:
                self.hud.target_rect = bounds
                self.hud.realign_to_window(bounds[0], bounds[1], bounds[2], bounds[3])
                self.log(f"HUD locked to target window: [{active_prof.get('target_process', '')}] (HWND: {hwnd}).")
            else:
                self.hud.set_position(hx, hy)

            if self.hud_enabled_var.get():
                self.hud.deiconify()
            else:
                self.hud.withdraw()

        # Return to main view
        self.show_main_view()

    # --- Profile Loading and Management ---
    def load_profile_ui_data(self):
        active_prof = self.get_current_profile()

        # Overlay Options visibility and window binding check
        ov = active_prof.get("overlay", {})
        if self.hud:
            px = ov.get("pos_x", 80)
            py = ov.get("pos_y", 80)
            hwnd, bounds = self.resolve_target_window(force_refresh=True)
            if bounds:
                self.hud.target_rect = bounds
                self.hud.realign_to_window(bounds[0], bounds[1], bounds[2], bounds[3])
            else:
                self.hud.set_position(px, py)
            if ov.get("enabled", True):
                self.hud.deiconify()
            else:
                self.hud.withdraw()

        # Update ToS badge
        if hasattr(self, "tos_status_badge"):
            tos = active_prof.get("tos_safe_mode", {})
            if tos.get("enabled", True):
                self.tos_status_badge.configure(text="🛡️ ToS Safe: Hold to Dictate, Tap to Send", text_color="#38ef7d")
            else:
                self.tos_status_badge.configure(text="⚠️ Macro Mode", text_color="#ffb74d")

        # Render Bindings in Main View
        for r in self.profile_rows:
            r["frame"].destroy()
        self.profile_rows.clear()

        for b in active_prof.get("bindings", []):
            self.render_binding_row(b)

    def on_tos_safe_toggle(self):
        is_tos = self.tos_safe_enabled_var.get() if hasattr(self, "tos_safe_enabled_var") else False
        if hasattr(self, "tos_auto_open_cb"):
            self.tos_auto_open_cb.configure(state="normal" if is_tos else "disabled")
        # Ensure chat lifecycle options remain active
        self.on_click_away_toggle()

    def open_tos_guide_dialog(self):
        ToSGuideDialog(self, on_apply_safe_settings=self.apply_tos_safe_defaults)

    def apply_tos_safe_defaults(self):
        active_prof = self.get_current_profile()
        if "tos_safe_mode" not in active_prof:
            active_prof["tos_safe_mode"] = {}
        active_prof["tos_safe_mode"]["enabled"] = True
        active_prof["tos_safe_mode"]["auto_open_chat"] = True
        save_config(self.config)
        self.log("Applied recommended Blizzard ToS Safe Mode settings (Hold to Dictate, Tap to Send).")

        if hasattr(self, "tos_safe_enabled_var"):
            self.tos_safe_enabled_var.set(True)
            self.tos_auto_open_var.set(True)
            self.on_tos_safe_toggle()
        self.load_profile_ui_data()

    def on_click_away_toggle(self):
        is_ca = self.click_away_var.get()
        if is_ca:
            # Grey out close hotkey and its bind button
            self.close_key_entry.configure(state="disabled", text_color="#555555", fg_color="#131316")
            self.close_key_bind_btn.configure(state="disabled", fg_color="#221e16", text_color="#555555")

            # Enable click-away coordinates controls
            self.click_target_menu.configure(state="normal")
            if self.click_target_menu.get() == "Custom Coordinates":
                self.coord_x_entry.configure(state="normal", text_color=WOW_TEXT_LIGHT, fg_color="#0d0d0e")
                self.coord_y_entry.configure(state="normal", text_color=WOW_TEXT_LIGHT, fg_color="#0d0d0e")
                self.pick_coords_btn.configure(state="normal", fg_color=WOW_BUTTON_GOLD, text_color=WOW_TEXT_LIGHT)
            else:
                self.coord_x_entry.configure(state="disabled", text_color="#555555", fg_color="#131316")
                self.coord_y_entry.configure(state="disabled", text_color="#555555", fg_color="#131316")
                self.pick_coords_btn.configure(state="disabled", fg_color="#221e16", text_color="#555555")
        else:
            # Enable close hotkey and bind button
            self.close_key_entry.configure(state="normal", text_color=WOW_ACCENT_GOLD, fg_color="#0d0d0e")
            self.close_key_bind_btn.configure(state="normal", fg_color=WOW_BUTTON_GOLD, text_color=WOW_TEXT_LIGHT)

            # Disable click-away coordinates controls
            self.click_target_menu.configure(state="disabled")
            self.coord_x_entry.configure(state="disabled", text_color="#555555", fg_color="#131316")
            self.coord_y_entry.configure(state="disabled", text_color="#555555", fg_color="#131316")
            self.pick_coords_btn.configure(state="disabled", fg_color="#221e16", text_color="#555555")

    def on_click_target_changed(self, choice):
        self.on_click_away_toggle()

    def pick_current_mouse_pos(self):
        x, y = pyautogui.position()
        self.coord_x_entry.configure(state="normal")
        self.coord_x_entry.delete(0, "end")
        self.coord_x_entry.insert(0, str(x))

        self.coord_y_entry.configure(state="normal")
        self.coord_y_entry.delete(0, "end")
        self.coord_y_entry.insert(0, str(y))
        self.log(f"Captured screen coordinates: ({x}, {y})")

    def apply_hud_pos_from_entries(self):
        try:
            hx = int(self.hud_pos_x_entry.get().strip())
            hy = int(self.hud_pos_y_entry.get().strip())
        except (ValueError, AttributeError):
            hx, hy = 40, 40

        if self.hud:
            self.hud.set_position(hx, hy)
            hx, hy = self.hud.rel_x, self.hud.rel_y
            if self.hud_enabled_var.get():
                self.hud.deiconify()
                self.hud.ensure_topmost()

        self.hud_pos_x_entry.delete(0, "end")
        self.hud_pos_x_entry.insert(0, str(hx))
        self.hud_pos_y_entry.delete(0, "end")
        self.hud_pos_y_entry.insert(0, str(hy))
        self.hud_pos_label.configure(text=f"App-Rel: ({hx}, {hy})")

        active_prof = self.get_current_profile()
        if "overlay" not in active_prof:
            active_prof["overlay"] = {}
        active_prof["overlay"]["pos_x"] = hx
        active_prof["overlay"]["pos_y"] = hy

        self.log(f"HUD positioned at App-Relative: ({hx}, {hy})")

    def on_hud_preset_selected(self, choice):
        if not choice or choice == "Presets ▾":
            return

        hud_w, hud_h = 160, 34
        margin_x, margin_y = 20, 30

        if self.hud and not self.hud.target_rect:
            _, bounds = self.resolve_target_window()
            if bounds:
                self.hud.target_rect = bounds

        if self.hud and self.hud.target_rect:
            _, _, tw, th = self.hud.target_rect
        else:
            try:
                tw = max(800, self.winfo_screenwidth())
                th = max(600, self.winfo_screenheight())
            except Exception:
                tw, th = 1920, 1080

        presets = {
            "Top-Left": (margin_x, margin_y),
            "Top-Center": (max(0, (tw - hud_w) // 2), margin_y),
            "Top-Right": (max(0, tw - hud_w - margin_x), margin_y),
            "Bottom-Left": (margin_x, max(0, th - hud_h - margin_y)),
            "Bottom-Center": (max(0, (tw - hud_w) // 2), max(0, th - hud_h - margin_y)),
            "Bottom-Right": (max(0, tw - hud_w - margin_x), max(0, th - hud_h - margin_y)),
            "Center": (max(0, (tw - hud_w) // 2), max(0, (th - hud_h) // 2)),
        }

        if choice in presets:
            x, y = presets[choice]
            self.hud_pos_x_entry.delete(0, "end")
            self.hud_pos_x_entry.insert(0, str(x))
            self.hud_pos_y_entry.delete(0, "end")
            self.hud_pos_y_entry.insert(0, str(y))
            self.apply_hud_pos_from_entries()

        self.hud_preset_menu.set("Presets ▾")

    def pick_hud_cursor_pos(self):
        try:
            x, y = pyautogui.position()
            if self.hud and not self.hud.target_rect:
                _, bounds = self.resolve_target_window()
                if bounds:
                    self.hud.target_rect = bounds

            if self.hud and self.hud.target_rect:
                tx, ty, tw, th = self.hud.target_rect
                rel_x = max(0, min(x - tx, max(0, tw - 160)))
                rel_y = max(0, min(y - ty, max(0, th - 34)))
            else:
                rel_x, rel_y = max(0, x), max(0, y)

            self.hud_pos_x_entry.delete(0, "end")
            self.hud_pos_x_entry.insert(0, str(rel_x))
            self.hud_pos_y_entry.delete(0, "end")
            self.hud_pos_y_entry.insert(0, str(rel_y))
            self.apply_hud_pos_from_entries()
        except Exception as e:
            self.log(f"Failed to pick cursor position for HUD: {e}")

    def bind_single_action(self, target_entry, action_field):
        if not self.engine or not self.engine.input_manager:
            return

        def _on_captured(input_id, display_name):
            target_entry.configure(state="normal")
            target_entry.delete(0, "end")
            target_entry.insert(0, display_name)
            target_entry._input_id = input_id
            self.log(f"Bound {action_field} to [{display_name}].")

        InputCaptureDialog(self, self.engine.input_manager, _on_captured)

    def render_binding_row(self, data):
        row = ctk.CTkFrame(self.scroll_bindings, fg_color=WOW_FRAME_BG, border_width=1, border_color="#45381f", corner_radius=2)
        row.pack(fill="x", pady=3, padx=2)

        # Name entry
        name_lbl = ctk.CTkLabel(row, text="Name:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT)
        name_lbl.pack(side="left", padx=(8, 2))
        ToolTip(name_lbl, "Custom name for this binding displayed on the floating HUD (e.g. REC [Input 1] or REC [Party Chat]).")

        b_name = data.get("binding_name", "").strip()
        if not b_name:
            curr_names = [r["name"].get().strip() for r in self.profile_rows]
            idx = 1
            while f"Input {idx}" in curr_names:
                idx += 1
            b_name = f"Input {idx}"

        name_entry = ctk.CTkEntry(row, width=105, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_ACCENT_GOLD)
        name_entry.insert(0, b_name)
        name_entry.pack(side="left", padx=4, pady=5)

        in_lbl = ctk.CTkLabel(row, text="Input:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT)
        in_lbl.pack(side="left", padx=(6, 2))
        ToolTip(in_lbl, "The key, mouse button (M4/M5), or controller button held down to speak.")

        key_id = data.get("input_id", "f8")
        disp_name = data.get("display_name", format_input_label(key_id))

        key_entry = ctk.CTkEntry(row, width=115, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_ACCENT_GOLD)
        key_entry.insert(0, disp_name)
        key_entry._input_id = key_id
        key_entry.pack(side="left", padx=4, pady=5)

        bind_btn = ctk.CTkButton(
            row, text="Bind", width=44, height=24,
            font=ctk.CTkFont(family="Georgia", size=10, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT,
            command=lambda e=key_entry: self.launch_binding_capture(e)
        )
        bind_btn.pack(side="left", padx=(0, 6))

        p_lbl = ctk.CTkLabel(row, text="Prefix:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT)
        p_lbl.pack(side="left", padx=(4, 2))
        ToolTip(p_lbl, "In-game slash command or prefix (e.g. /say, /p, /party) prepended to the message.")

        prefix_entry = ctk.CTkEntry(row, width=110, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_TEXT_LIGHT)
        prefix_entry.insert(0, data.get("prefix", ""))
        prefix_entry.pack(side="left", padx=4)

        s_lbl = ctk.CTkLabel(row, text="Suffix:", font=ctk.CTkFont(family="Georgia", size=11, weight="bold"), text_color=WOW_TEXT_LIGHT)
        s_lbl.pack(side="left", padx=(4, 2))
        ToolTip(s_lbl, "Text appended to the end of the transcription (e.g. [over]).")

        suffix_entry = ctk.CTkEntry(row, width=110, fg_color="#0d0d0e", border_color=WOW_BORDER_GOLD, text_color=WOW_TEXT_LIGHT)
        suffix_entry.insert(0, data.get("suffix", ""))
        suffix_entry.pack(side="left", padx=4)

        save_btn = ctk.CTkButton(
            row, text="Save", width=50, height=24,
            font=ctk.CTkFont(family="Georgia", size=11, weight="bold"),
            fg_color=WOW_BUTTON_GOLD, hover_color=WOW_BUTTON_HOVER, border_width=1, border_color=WOW_BUTTON_BORDER,
            text_color=WOW_TEXT_LIGHT, command=self.save_bindings_from_ui
        )
        save_btn.pack(side="left", padx=4)

        del_btn = ctk.CTkButton(
            row, text="✕", width=26, height=24,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=WOW_HORDE_RED, hover_color=WOW_HORDE_HOVER, text_color="#ffffff",
            command=lambda r=row: self.remove_binding_row(r)
        )
        del_btn.pack(side="left", padx=3)

        self.profile_rows.append({
            "frame": row,
            "name": name_entry,
            "key": key_entry,
            "prefix": prefix_entry,
            "suffix": suffix_entry
        })

    def launch_binding_capture(self, key_entry):
        if not self.engine or not self.engine.input_manager:
            return

        def _on_captured(input_id, display_name):
            key_entry.delete(0, "end")
            key_entry.insert(0, display_name)
            key_entry._input_id = input_id
            self.save_bindings_from_ui()

        InputCaptureDialog(self, self.engine.input_manager, _on_captured)

    def add_binding_row(self):
        curr_bindings = []
        for r in self.profile_rows:
            curr_bindings.append({
                "binding_name": r["name"].get().strip(),
                "input_id": getattr(r["key"], "_input_id", "f10")
            })
        def_name = get_next_default_binding_name(curr_bindings)
        new_data = {
            "binding_name": def_name,
            "input_id": "f10",
            "display_name": "F10",
            "prefix": "",
            "suffix": ""
        }
        self.render_binding_row(new_data)
        self.save_bindings_from_ui()

    def remove_binding_row(self, row_frame):
        self.profile_rows = [r for r in self.profile_rows if r["frame"] != row_frame]
        row_frame.destroy()
        self.save_bindings_from_ui()

    def save_bindings_from_ui(self):
        active_prof = self.get_current_profile()
        updated_bindings = []
        used_names = set()
        for r in self.profile_rows:
            raw_id = normalize_combo_id(getattr(r["key"], "_input_id", r["key"].get().strip().lower()))
            disp_name = format_input_label(raw_id)
            name_val = r["name"].get().strip()
            if not name_val:
                idx = 1
                while f"Input {idx}" in used_names:
                    idx += 1
                name_val = f"Input {idx}"
            used_names.add(name_val)
            updated_bindings.append({
                "binding_name": name_val,
                "input_id": raw_id,
                "display_name": disp_name,
                "prefix": r["prefix"].get(),
                "suffix": r["suffix"].get()
            })

        active_prof["bindings"] = updated_bindings
        save_config(self.config)
        self.restart_engine()
        self.log(f"Profile [{self.config['active_profile']}] saved ({len(updated_bindings)} bindings).")

    def on_profile_switched(self, selected_name):
        self.config["active_profile"] = selected_name
        save_config(self.config)
        self.log(f"Switched profile to: [{selected_name}].")
        self.load_profile_ui_data()

    def add_new_profile_dialog(self):
        dialog = ctk.CTkInputDialog(text="Enter name for new application profile:", title="New Profile")
        name = dialog.get_input()
        if name and name.strip():
            name = name.strip()
            if name in self.config.get("app_profiles", {}):
                self.log(f"Profile '{name}' already exists.")
                return
            new_prof = json.loads(json.dumps(DEFAULT_CONFIG["app_profiles"]["World of Warcraft"]))
            new_prof["name"] = name
            new_prof["target_process"] = f"{name}.exe"
            new_prof["window_title"] = name
            self.config["app_profiles"][name] = new_prof
            self.config["active_profile"] = name
            save_config(self.config)

            self.profile_names = list(self.config["app_profiles"].keys())
            self.profile_menu.configure(values=self.profile_names)
            self.profile_menu.set(name)
            self.load_profile_ui_data()
            self.log(f"Created new profile: [{name}].")

    def delete_current_profile(self):
        curr = self.config.get("active_profile", "")
        profs = self.config.get("app_profiles", {})
        if len(profs) <= 1:
            self.log("Cannot delete the only remaining profile.")
            return
        if curr in profs:
            del profs[curr]
            first_rem = list(profs.keys())[0]
            self.config["active_profile"] = first_rem
            save_config(self.config)

            self.profile_names = list(profs.keys())
            self.profile_menu.configure(values=self.profile_names)
            self.profile_menu.set(first_rem)
            self.load_profile_ui_data()
            self.log(f"Deleted profile [{curr}]. Switched to [{first_rem}].")

    def open_autodetect_dialog(self):
        self.log("Auto-Detecting recently opened applications (ignoring this app)...")
        recent = get_last_opened_apps(limit=3)
        all_apps = get_running_apps()
        self.log(f"Detected {len(recent)} recent application(s).")
        AutoDetectDialog(
            self,
            recent_apps=recent,
            all_apps=all_apps,
            on_selected=self.on_app_selected_from_dialog
        )

    def on_app_selected_from_dialog(self, chosen_app):
        self.target_proc_entry.delete(0, "end")
        self.target_proc_entry.insert(0, chosen_app)
        self.log(f"Selected target process: [{chosen_app}]. Click Save Settings to apply.")

    def iconify(self):
        super().iconify()
        if self.hud and self.hud.winfo_exists():
            active_prof = self.get_current_profile()
            if active_prof.get("overlay", {}).get("enabled", True):
                self.after(60, lambda: self.hud.deiconify() if (self.hud and self.hud.winfo_exists()) else None)

    def toggle_hud_visibility(self):
        if self.hud:
            active_prof = self.get_current_profile()
            if "overlay" not in active_prof:
                active_prof["overlay"] = {}
            current_enabled = active_prof["overlay"].get("enabled", True)
            new_enabled = not current_enabled

            self.hud_enabled_var.set(new_enabled)
            active_prof["overlay"]["enabled"] = new_enabled
            save_config(self.config)

            if new_enabled:
                self.hud.deiconify()
                self.log("Floating HUD overlay: [VISIBLE].")
            else:
                self.hud.withdraw()
                self.log("Floating HUD overlay: [HIDDEN].")

    def populate_audio_devices(self):
        self.device_map.clear()
        device_names = []
        default_choice = "Default Microphone"

        devices = sd.query_devices()
        current_cfg_idx = self.config.get("global_settings", {}).get("device_index")

        for idx, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                name = f"[{idx}] {dev['name']}"
                self.device_map[name] = idx
                device_names.append(name)
                if current_cfg_idx == idx:
                    default_choice = name

        self.device_dropdown.configure(values=device_names)
        if default_choice in device_names:
            self.device_dropdown.set(default_choice)
        elif device_names:
            self.device_dropdown.set(device_names[0])

    def on_device_changed(self, selected_name):
        dev_idx = self.device_map.get(selected_name)
        if "global_settings" not in self.config:
            self.config["global_settings"] = {}
        self.config["global_settings"]["device_index"] = dev_idx
        save_config(self.config)
        self.log(f"Switched microphone to: {selected_name}")
        self.restart_engine()

    def start_engine_thread(self):
        def _runner():
            self.engine = STTEngine(self.config, log_callback=self.log, hud_callback=self.hud_state_callback)
            self.engine.start()

        threading.Thread(target=_runner, daemon=True).start()

    def restart_engine(self):
        if self.engine:
            self.engine.stop()
            self.engine.config = self.config
            self.engine.start()

    def on_close(self):
        if self.engine:
            self.engine.stop()
        if self.hud:
            try:
                self.hud.destroy()
            except Exception:
                pass
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    app = WoWPTTApp()
    app.mainloop()
