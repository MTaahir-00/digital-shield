"""
DIGITAL SHIELD - MAIN APP
---------------------------
Run: python digital_shield_app.py

TWO LAYERS:
  1) AUTOMATIC BACKGROUND SCREEN CHECK -> starts the moment the app opens,
     no button press needed. A lightweight loop grabs the screen, skips
     the (relatively expensive) OCR step entirely if the screen hasn't
     visibly changed since the last check, OCRs it when it has, and scores
     the text against risk_engine.py's phishing/scam/popup/gambling
     patterns. "Check My Screen" still exists for an instant on-demand
     check any time. No continuous webcam use, no paid API calls.
  2) GESTURE / BUTTON RESPONSE -> if something suspicious is found, Digital
     Shield shows a bilingual (English + Urdu) on-screen warning overlay
     that floats on top of whatever the user is doing, speaks the Urdu
     warning aloud, and offers three accessible responses (by hand gesture
     OR by tapping a button, whichever is easier for the user):
        ai_help     -> "Explain this to me" (screenshots + opens ChatGPT)
        human_help  -> "Contact human help" (WhatsApp alert)
        ignore      -> "Ignore / continue" (dismiss the warning) - detected
                        two ways: the trained gesture model (once you've
                        collected samples for it) AND a rule-based open
                        flat-palm check (gesture_utils.is_open_palm) that
                        works immediately with zero training data.

The camera/gesture recognizer only needs to run while a warning is on
screen (or if the user manually starts it to test gestures) - not all the
time.
"""

import io
import os
import json
import time
import pickle
import tempfile
import threading
import urllib.parse

import cv2
import mediapipe as mp
import numpy as np
import pyautogui
import pygetwindow as gw
import webbrowser
import win32clipboard
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageGrab

from risk_engine import score_text, detect_context, UNKNOWN_EN_MESSAGE, UNKNOWN_URDU_MESSAGE
from gesture_utils import normalize_landmarks, is_open_palm

# ---- optional dependencies (app still runs without them, with reduced
#      functionality, so a missing pip package never crashes the demo) ----
try:
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

try:
    from gtts import gTTS
    from playsound import playsound
    TTS_AVAILABLE = True
except Exception:
    TTS_AVAILABLE = False

MODEL_FILE = 'digital_shield_model.pkl'
CONFIG_FILE = 'config.json'
HISTORY_FILE = 'activity_history.log'
SCREENSHOT_DIR = 'screenshots'

AI_PROMPT = (
    "You are Digital Shield. The user cannot read well and may not "
    "understand English, so you must respond ONLY in simple, spoken-style "
    "Urdu using short, easy "
    "sentences, as if speaking out loud to someone. Analyze the screenshot "
    "and explain what is happening. Check specifically whether this looks "
    "like a scam, phishing attempt, or otherwise unsafe or suspicious, and "
    "clearly say yes or no plus why, in Urdu. Then clearly explain what "
    "the user should do next, in Urdu. Keep it short and easy to listen to."
)
AI_CHAT_URL = "https://chatgpt.com/"

DEFAULT_CONFIG = {
    "help_contact_phone": "",
    "hold_seconds": 2.5,
    "confidence_threshold": 0.75,
    "cooldown_seconds": 3.0,
    "response_timeout_seconds": 60,
    # Background loop tick rate. Cheap because a screen-change check (a
    # tiny thumbnail diff) runs first and skips the actual OCR call
    # entirely when nothing on screen has changed - see screen_changed().
    "auto_scan_interval_seconds": 2,
}

COLOR_BG = "#15171A"
COLOR_BG_RAISED = "#1B1E22"
COLOR_DIVIDER = "#2A2D31"
COLOR_TEXT = "#E9E7E2"
COLOR_TEXT_MUTED = "#82868D"
COLOR_ACCENT = "#4E8BC9"
COLOR_ACCENT_DIM = "#356089"
COLOR_READY = "#6C9A6E"
COLOR_WARN = "#BD8B41"
COLOR_DANGER = "#D9534F"

FONT_UI = "Segoe UI"
FONT_UI_SEMIBOLD = "Segoe UI Semibold"
FONT_MONO = "Consolas"
FONT_URDU = "Jameel Noori Nastaleeq"  # falls back to system default if missing


def load_config():
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config.update(json.load(f))
        except Exception:
            pass
    return config


def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)


def append_history(line):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] {line}\n")


THUMB_SIZE = (120, 68)


def make_thumb(img):
    """Small grayscale thumbnail used only to cheaply detect 'did the
    screen change at all' before paying for a full OCR pass."""
    return np.asarray(img.convert('L').resize(THUMB_SIZE), dtype=np.int16)


def screen_changed(prev_thumb, img, threshold=4.0):
    """Returns (changed: bool, new_thumb). threshold is the average
    per-pixel brightness difference (0-255 scale) needed to count as a
    real change - small enough to catch a new popup/toast, large enough
    to ignore a blinking cursor or clock tick."""
    new_thumb = make_thumb(img)
    if prev_thumb is None:
        return True, new_thumb
    if prev_thumb.shape != new_thumb.shape:
        return True, new_thumb
    diff = float(np.abs(prev_thumb - new_thumb).mean())
    return diff > threshold, new_thumb


def capture_active_window():
    """Screenshot ONLY the current foreground window's content area -
    NOT the whole desktop. Grabbing the full desktop means OCR also picks
    up text from every other open window/tab (taskbar previews, a
    minimized/background browser tab's title, alt-tab thumbnails, etc.),
    which is what previously made a totally safe page (e.g. Claude or
    ChatGPT) get flagged as suspicious just because an unrelated tab was
    still open somewhere on screen. Restricting the capture to the window
    the user is actually looking at fixes that at the source.

    Returns (image, window_title) or (None, None) if no usable foreground
    window is available (e.g. desktop/taskbar focused, or a rare timing
    issue during alt-tab) - callers should treat that as "skip this check"
    rather than falling back to a full-desktop grab.
    """
    try:
        win = gw.getActiveWindow()
        if win is None or win.width <= 1 or win.height <= 1:
            return None, None
        title = win.title or ""
        if "digital shield" in title.lower():
            # Never analyze our own app/overlay window.
            return None, None
        sw, sh = pyautogui.size()
        left = max(win.left, 0)
        top = max(win.top, 0)
        right = min(win.left + win.width, sw)
        bottom = min(win.top + win.height, sh)
        if right - left <= 1 or bottom - top <= 1:
            return None, None
        bbox = (left, top, right, bottom)
        img = ImageGrab.grab(bbox=bbox)
        return img, title
    except Exception:
        return None, None


_OCR_LANG = {"value": None}


def _ocr_text(img):
    """OCR in English + Urdu when Tesseract's Urdu pack ('urd') is installed,
    otherwise English only. Urdu scam text (and Roman-Urdu, which is Latin
    script) can then be read too. Remembers which mode works."""
    if _OCR_LANG["value"] is None:
        try:
            text = pytesseract.image_to_string(img, lang="eng+urd")
            _OCR_LANG["value"] = "eng+urd"
            return text
        except Exception:
            _OCR_LANG["value"] = "eng"
    return pytesseract.image_to_string(img, lang=_OCR_LANG["value"])


def build_ai_hint(result):
    """Short ASCII sentence appended to the ChatGPT prompt so the AI knows
    what Digital Shield's own check found (typed with pyautogui, so ASCII only)."""
    if not result or result.get("status") != "risky":
        return ""
    kind = (result.get("scam_type") or "scam").replace("_", " ")
    where = result.get("context") or "browser"
    signs = ", ".join(result.get("matched", [])[:4]).replace("_", " ")
    return (f" Digital Shield's automatic check flagged this as a possible {kind} "
            f"({where} window; signs: {signs}). Please say clearly whether it is "
            f"a scam, and what to do.")


def analyze_screenshot_for_risk(img, window_title=None):
    """OCR the screenshot, then hand the text to risk_engine.score_text().
    Returns a dict with status in {"risky", "safe", "unknown"}, English +
    Urdu text to speak/show, and a short English reason (for the activity
    log, not shown loudly)."""
    if img is None:
        return {"status": "unknown", "en_text": UNKNOWN_EN_MESSAGE,
                 "urdu_text": UNKNOWN_URDU_MESSAGE, "reason_en": "screenshot failed"}
    if not OCR_AVAILABLE:
        return {"status": "unknown", "en_text": UNKNOWN_EN_MESSAGE,
                 "urdu_text": UNKNOWN_URDU_MESSAGE,
                 "reason_en": "OCR not installed (pytesseract/Tesseract missing)"}
    try:
        ocr_img = img
        if detect_context(window_title) == "email":
            # skip the left folder/navigation column (Inbox, Sent, Spam...)
            # so only the mail list / message itself is read
            ocr_img = img.crop((int(img.width * 0.15), 0, img.width, img.height))
        text = _ocr_text(ocr_img)
    except Exception as e:
        return {"status": "unknown", "en_text": UNKNOWN_EN_MESSAGE,
                 "urdu_text": UNKNOWN_URDU_MESSAGE, "reason_en": f"OCR error: {e}"}

    result = score_text(text, window_title=window_title)
    return {
        "status": result["status"],
        "severity": result.get("severity"),
        "en_text": result["en_text"],
        "urdu_text": result["ur_text"],
        "reason_en": result["reason_en"],
        "text_hash": result["text_hash"],
        "scam_type": result.get("scam_type"),
        "context": result.get("context"),
        "matched": result.get("matched", []),
        "advice_en": result.get("advice_en", ""),
    }


class DangerOverlay:
    """A borderless, always-on-top window that pops up ON TOP of whatever
    the user is doing (browser, email client, anything) so the danger
    warning is impossible to miss - not just a label tucked inside the
    main app window, which may be minimized or behind something else.
    Shows English + Urdu together and offers the same 3 responses as
    buttons, in case gestures aren't convenient in the moment."""

    def __init__(self, root, en_text, ur_text, reason_en, severity,
                 on_ai_help, on_human_help, on_ignore):
        self.win = tk.Toplevel(root)
        self.win.title("Digital Shield Warning")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", 0.97)
        except Exception:
            pass
        self.win.configure(bg=COLOR_DANGER)

        sw = self.win.winfo_screenwidth()
        width = min(760, sw - 80)
        self.win.update_idletasks()
        x = (sw - width) // 2
        self.win.geometry(f"{width}x420+{x}+40")
        # once the widgets exist, shrink/grow to exactly fit the message
        self.win.after(80, lambda: self.win.geometry(
            f"{width}x{max(260, self.win.winfo_reqheight())}+{x}+40"))

        pad = tk.Frame(self.win, bg=COLOR_DANGER, padx=3, pady=3)
        pad.pack(fill="both", expand=True)
        card = tk.Frame(pad, bg=COLOR_BG_RAISED, padx=22, pady=18)
        card.pack(fill="both", expand=True)

        severity_tag = {"high": "HIGH RISK", "medium": "CAUTION", "low": "NOTICE"}.get(severity, "WARNING")
        tk.Label(card, text=f"\U0001F534 POSSIBLE DANGER \u2014 {severity_tag}",
                  font=(FONT_UI_SEMIBOLD, 16), bg=COLOR_BG_RAISED, fg=COLOR_DANGER,
                  anchor="w").pack(fill="x")
        tk.Label(card, text=en_text, font=(FONT_UI, 12), bg=COLOR_BG_RAISED,
                  fg=COLOR_TEXT, anchor="w", justify="left", wraplength=width - 60).pack(
            fill="x", pady=(8, 2))
        tk.Label(card, text=ur_text, font=(FONT_URDU, 14), bg=COLOR_BG_RAISED,
                  fg=COLOR_TEXT, anchor="e", justify="right", wraplength=width - 60).pack(
            fill="x", pady=(2, 4))
        if reason_en:
            tk.Label(card, text=f"(flagged: {reason_en})", font=(FONT_MONO, 8),
                      bg=COLOR_BG_RAISED, fg=COLOR_TEXT_MUTED, anchor="w").pack(fill="x")

        row = tk.Frame(card, bg=COLOR_BG_RAISED)
        row.pack(fill="x", pady=(14, 0))
        style = ttk.Style()
        ttk.Button(row, text="\u270B Explain / وضاحت", style="Explain.TButton",
                   command=on_ai_help).pack(side="left", padx=(0, 10))
        ttk.Button(row, text="\u270A Human Help / انسانی مدد", style="Human.TButton",
                   command=on_human_help).pack(side="left", padx=(0, 10))
        ttk.Button(row, text="\U0001F590\uFE0F Ignore / جاری رکھیں", style="Ignore.TButton",
                   command=on_ignore).pack(side="left")

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass


class DigitalShieldApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Digital Shield")
        self.root.geometry("1000x700")
        self.root.configure(bg=COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config_data = load_config()
        self.model = None
        self.cap = None
        self.hands = None
        self.mp_drawing = None
        self.mp_hands = None
        self.monitoring = False
        self.current_gesture = None
        self.gesture_start_time = None
        self.cooldown_until = {"ai_help": 0, "human_help": 0, "ignore": 0}
        self.action_busy = False  # true while an action (screenshot/send/scan) runs
        self._ai_help_image_copied = False
        self._human_help_image_copied = False
        self._human_help_caption = ""

        # --- on-demand check / warning-response state ---
        self.warning_active = False
        self.auto_started_monitoring = False
        self._last_scan_img = None
        self._last_scan_path = None
        self._last_scan_text_hash = None
        self._last_scan_hint = ""
        self._pending_ai_hint = ""
        self._last_dismissed_signature = None
        self._response_timeout_job = None
        self._auto_scan_in_progress = False
        self._last_screen_thumb = None  # for cheap screen-change detection
        self.overlay = None

        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        self._build_ui()

        # Automatic background screen checking starts as soon as the app
        # opens - no button press needed. The webcam/gesture camera is NOT
        # part of this, it only turns on via Start Monitoring or when a
        # warning needs a gesture reply. Background checks are cheap local
        # OCR (and skip OCR entirely when the screen hasn't changed), not a
        # webcam feed and not a paid API call, so running them frequently
        # from the start is fine.
        self.root.after(400, self.auto_scan_tick)

    # ---------------- UI ----------------
    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=COLOR_BG)
        style.configure("TEntry", fieldbackground=COLOR_BG_RAISED, foreground=COLOR_TEXT,
                         insertcolor=COLOR_TEXT, padding=5)
        style.configure("Primary.TButton", font=(FONT_UI_SEMIBOLD, 10), background=COLOR_ACCENT,
                         foreground="#0A0F14", padding=(14, 8), borderwidth=0)
        style.map("Primary.TButton", background=[("active", COLOR_ACCENT_DIM), ("disabled", COLOR_DIVIDER)])
        style.configure("Secondary.TButton", font=(FONT_UI, 9), background=COLOR_BG_RAISED,
                         foreground=COLOR_TEXT, padding=(10, 6), borderwidth=1)
        style.configure("Scan.TButton", font=(FONT_UI_SEMIBOLD, 13), background=COLOR_ACCENT,
                         foreground="#0A0F14", padding=(18, 14), borderwidth=0)
        style.map("Scan.TButton", background=[("active", COLOR_ACCENT_DIM), ("disabled", COLOR_DIVIDER)])
        style.configure("Explain.TButton", font=(FONT_UI_SEMIBOLD, 10), background=COLOR_ACCENT,
                         foreground="#0A0F14", padding=(12, 10), borderwidth=0)
        style.map("Explain.TButton", background=[("active", COLOR_ACCENT_DIM), ("disabled", COLOR_DIVIDER)])
        style.configure("Human.TButton", font=(FONT_UI_SEMIBOLD, 10), background=COLOR_WARN,
                         foreground="#0A0F14", padding=(12, 10), borderwidth=0)
        style.map("Human.TButton", background=[("active", "#96662C"), ("disabled", COLOR_DIVIDER)])
        style.configure("Ignore.TButton", font=(FONT_UI_SEMIBOLD, 10), background=COLOR_BG_RAISED,
                         foreground=COLOR_TEXT, padding=(12, 10), borderwidth=1)
        style.map("Ignore.TButton", background=[("active", COLOR_DIVIDER)])

        header = tk.Frame(self.root, bg=COLOR_BG)
        header.pack(fill="x", padx=24, pady=(20, 4))
        tk.Label(header, text="Digital Shield", font=(FONT_UI_SEMIBOLD, 17),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")
        tk.Label(header, text="   Accessible digital safety assistant", font=(FONT_UI, 11),
                 bg=COLOR_BG, fg=COLOR_TEXT_MUTED).pack(side="left")
        self.auto_dot = tk.Canvas(header, width=9, height=9, bg=COLOR_BG, highlightthickness=0)
        self.auto_dot.pack(side="right", padx=(0, 6))
        self.auto_dot.create_oval(1, 1, 8, 8, fill=COLOR_READY, outline="")
        tk.Label(header, text="Auto-Protect: ON", font=(FONT_UI, 9),
                 bg=COLOR_BG, fg=COLOR_TEXT_MUTED).pack(side="right")
        ttk.Separator(self.root).pack(fill="x", padx=24, pady=(10, 14))

        # ---------------- ON-DEMAND CHECK PANEL (Layer 1 + 2) ----------------
        check_panel = tk.Frame(self.root, bg=COLOR_BG_RAISED, padx=20, pady=18)
        check_panel.pack(fill="x", padx=24, pady=(0, 16))

        top_row = tk.Frame(check_panel, bg=COLOR_BG_RAISED)
        top_row.pack(fill="x")
        self.scan_button = ttk.Button(top_row, text="\U0001F50D  Check My Screen",
                                       style="Scan.TButton", command=self.check_screen_now)
        self.scan_button.pack(side="left")
        tk.Label(top_row, text="Tap this any time you see something confusing.\nNo need to leave anything running.",
                 font=(FONT_UI, 9), bg=COLOR_BG_RAISED, fg=COLOR_TEXT_MUTED, justify="left").pack(
            side="left", padx=(16, 0))

        self.result_banner = tk.Label(check_panel, text="", font=(FONT_UI_SEMIBOLD, 15),
                                       bg=COLOR_BG_RAISED, fg=COLOR_TEXT, anchor="w")
        self.result_banner.pack(fill="x", pady=(16, 2))

        self.english_label = tk.Label(check_panel, text="", font=(FONT_UI, 11), bg=COLOR_BG_RAISED,
                                       fg=COLOR_TEXT, anchor="w", justify="left", wraplength=900)
        self.english_label.pack(fill="x", pady=(2, 0))

        self.urdu_label = tk.Label(check_panel, text="", font=(FONT_URDU, 14), bg=COLOR_BG_RAISED,
                                    fg=COLOR_TEXT, anchor="e", justify="right", wraplength=900)
        self.urdu_label.pack(fill="x", pady=(0, 2))

        self.reason_label = tk.Label(check_panel, text="", font=(FONT_MONO, 8), bg=COLOR_BG_RAISED,
                                      fg=COLOR_TEXT_MUTED, anchor="w")
        self.reason_label.pack(fill="x")

        response_row = tk.Frame(check_panel, bg=COLOR_BG_RAISED)
        response_row.pack(fill="x", pady=(14, 0))
        self.explain_btn = ttk.Button(response_row, text="\u270B Explain (AI Help)", style="Explain.TButton",
                                       command=lambda: self._trigger_ai_help(from_warning=True), state="disabled")
        self.explain_btn.pack(side="left", padx=(0, 10))
        self.human_btn = ttk.Button(response_row, text="\u270A Contact Human Help", style="Human.TButton",
                                     command=lambda: self._trigger_human_help(from_warning=True), state="disabled")
        self.human_btn.pack(side="left", padx=(0, 10))
        self.ignore_btn = ttk.Button(response_row, text="\U0001F590\uFE0F Ignore / Continue", style="Ignore.TButton",
                                      command=self._trigger_ignore, state="disabled")
        self.ignore_btn.pack(side="left")
        tk.Label(response_row, text="(same 3 choices also work as hand gestures while the camera is on)",
                 font=(FONT_UI, 8), bg=COLOR_BG_RAISED, fg=COLOR_TEXT_MUTED).pack(side="left", padx=(14, 0))

        # ---------------- MAIN CONTENT: camera + config/log ----------------
        main = tk.Frame(self.root, bg=COLOR_BG)
        main.pack(fill="both", expand=True, padx=24)

        left = tk.Frame(main, bg=COLOR_BG)
        left.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="Manual gesture monitoring (optional / for testing gestures)",
                 font=(FONT_UI_SEMIBOLD, 9), bg=COLOR_BG, fg=COLOR_TEXT_MUTED).pack(anchor="w")

        video_border = tk.Frame(left, bg=COLOR_DIVIDER, padx=1, pady=1, width=482, height=362)
        video_border.pack(anchor="w", pady=(6, 0))
        video_border.pack_propagate(False)
        self.video_label = tk.Label(video_border, bg="#0A0B0C")
        self.video_label.pack(fill="both", expand=True)

        status_row = tk.Frame(left, bg=COLOR_BG)
        status_row.pack(fill="x", pady=(14, 0), anchor="w")
        self.status_dot = tk.Canvas(status_row, width=9, height=9, bg=COLOR_BG, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 8))
        self._draw_dot(COLOR_TEXT_MUTED)
        self.status_label = tk.Label(status_row, text="Camera: OFF  |  System not ready",
                                      font=(FONT_UI, 11), bg=COLOR_BG, fg=COLOR_TEXT)
        self.status_label.pack(side="left")

        self.confidence_label = tk.Label(left, text="", font=(FONT_MONO, 9), bg=COLOR_BG, fg=COLOR_TEXT_MUTED)
        self.confidence_label.pack(anchor="w", pady=(4, 0))
        self.hold_label = tk.Label(left, text="", font=(FONT_MONO, 9), bg=COLOR_BG, fg=COLOR_ACCENT)
        self.hold_label.pack(anchor="w", pady=(2, 0))

        btns = tk.Frame(left, bg=COLOR_BG)
        btns.pack(anchor="w", pady=(18, 0))
        self.start_button = ttk.Button(btns, text="Start Monitoring", style="Primary.TButton",
                                        command=self.toggle_monitoring)
        self.start_button.pack(side="left")

        tk.Label(left, text="The camera also turns itself on automatically when a warning needs a gesture reply,"
                              "\nand turns off again once you respond.",
                 font=(FONT_UI, 8), bg=COLOR_BG, fg=COLOR_TEXT_MUTED, justify="left").pack(anchor="w", pady=(20, 0))

        right = tk.Frame(main, bg=COLOR_BG, width=320)
        right.pack(side="right", fill="y", padx=(28, 0))

        tk.Label(right, text="Configuration", font=(FONT_UI_SEMIBOLD, 10), bg=COLOR_BG,
                 fg=COLOR_TEXT).pack(anchor="w", pady=(0, 8))
        tk.Label(right, text="Cybersecurity / help contact (WhatsApp number)", font=(FONT_UI, 9),
                 bg=COLOR_BG, fg=COLOR_TEXT_MUTED).pack(anchor="w")
        self.phone_entry = ttk.Entry(right, width=34)
        self.phone_entry.insert(0, self.config_data.get("help_contact_phone", ""))
        self.phone_entry.pack(anchor="w", pady=(2, 10))

        save_btn = ttk.Button(right, text="Save Settings", style="Secondary.TButton",
                               command=self.save_settings)
        save_btn.pack(anchor="w", pady=(0, 4))

        ttk.Separator(right).pack(fill="x", pady=14)
        tk.Label(right, text="Activity", font=(FONT_UI_SEMIBOLD, 10), bg=COLOR_BG,
                 fg=COLOR_TEXT).pack(anchor="w", pady=(0, 8))
        log_border = tk.Frame(right, bg=COLOR_DIVIDER, padx=1, pady=1)
        log_border.pack(fill="both", expand=True)
        self.log_text = tk.Text(log_border, width=38, height=18, bg=COLOR_BG_RAISED, fg=COLOR_TEXT_MUTED,
                                 font=(FONT_MONO, 9), wrap="word", relief="flat", padx=8, pady=8)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        self._log("Ready. Automatic background screen checking is on. Tap 'Check My Screen' for an immediate check, or Start Monitoring to test gestures directly.")
        if not OCR_AVAILABLE:
            self._log("NOTE: pytesseract/Tesseract not installed - screen checks will show "
                       "'could not check automatically' until it's installed.")
        if not TTS_AVAILABLE:
            self._log("NOTE: gTTS/playsound not installed - Urdu warnings will show as text only, no voice.")

    def _draw_dot(self, color):
        self.status_dot.delete("all")
        self.status_dot.create_oval(1, 1, 8, 8, fill=color, outline="")

    def _log(self, message, persist=False):
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{ts}   {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        if persist:
            append_history(message)

    def _log_threadsafe(self, message, persist=False):
        self.root.after(0, lambda: self._log(message, persist=persist))

    # ---------------- SETTINGS ----------------
    def save_settings(self):
        phone = self.phone_entry.get().strip()
        if phone and (not phone.startswith('+') or len(phone) < 8):
            messagebox.showwarning("Check the number",
                                    "Enter the help contact with a country code, starting with '+'.")
            return
        self.config_data["help_contact_phone"] = phone
        save_config(self.config_data)
        self._log("Settings saved.")

    # ============================================================
    # LAYER 1 - ON-DEMAND SCREEN CHECK
    # ============================================================
    def check_screen_now(self):
        if self.action_busy or self.warning_active:
            return
        self.action_busy = True
        self.scan_button.configure(state="disabled")
        self.result_banner.configure(text="\U0001F50E Scanning your screen\u2026", fg=COLOR_ACCENT)
        self.english_label.configure(text="")
        self.urdu_label.configure(text="")
        self.reason_label.configure(text="")
        threading.Thread(target=self._analyze_screen_worker, daemon=True).start()

    def _analyze_screen_worker(self):
        path, img, title = self._take_screenshot("scan")
        result = analyze_screenshot_for_risk(img, window_title=title)
        result["path"] = path
        result["img"] = img
        self.root.after(0, lambda: self._on_scan_result(result))

    def _on_scan_result(self, result):
        self.action_busy = False
        self.scan_button.configure(state="normal")
        self._last_scan_img = result.get("img")
        self._last_scan_path = result.get("path")
        self._last_scan_text_hash = result.get("text_hash")
        self._last_scan_hint = build_ai_hint(result)
        status = result["status"]
        self._log(f"Scan result: {status} ({result.get('reason_en', '')})", persist=True)

        if status == "risky":
            self._show_danger_banner(result["en_text"], result["urdu_text"],
                                      result.get("reason_en", ""), result.get("severity", "medium"))
            threading.Thread(target=self._speak_worker, args=(result["urdu_text"],), daemon=True).start()
        elif status == "safe":
            self.result_banner.configure(text="\u2705 Looks Safe", fg=COLOR_READY)
            self.english_label.configure(text=result["en_text"])
            self.urdu_label.configure(text=result["urdu_text"])
            self.reason_label.configure(text="")
        else:
            self.result_banner.configure(text="\u26A0\uFE0F Could not check automatically", fg=COLOR_WARN)
            self.english_label.configure(text=result["en_text"])
            self.urdu_label.configure(text=result["urdu_text"])
            self.reason_label.configure(text=result.get("reason_en", ""))

    def _speak_worker(self, text):
        if not TTS_AVAILABLE:
            self._log_threadsafe("Voice unavailable \u2014 install gTTS + playsound for spoken Urdu warnings.")
            return
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                tmp_path = tf.name
            gTTS(text=text, lang='ur').save(tmp_path)
            playsound(tmp_path)
        except Exception as e:
            self._log_threadsafe(f"Voice playback failed: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _show_danger_banner(self, en_text, urdu_text, reason_en, severity="medium"):
        self.warning_active = True
        self.result_banner.configure(text="\U0001F534 POSSIBLE DANGER", fg=COLOR_DANGER)
        self.english_label.configure(text=en_text)
        self.urdu_label.configure(text=urdu_text)
        self.reason_label.configure(text=f"(flagged: {reason_en})" if reason_en else "")
        self._set_response_buttons(enabled=True)

        # Show it ON the screen itself, on top of whatever the user is
        # doing right now - not just inside the (possibly hidden/minimized)
        # main window.
        if self.overlay is not None:
            self.overlay.close()
        self.overlay = DangerOverlay(
            self.root, en_text, urdu_text, reason_en, severity,
            on_ai_help=lambda: self._trigger_ai_help(from_warning=True),
            on_human_help=lambda: self._trigger_human_help(from_warning=True),
            on_ignore=self._trigger_ignore,
        )

        if not self.monitoring:
            self.start_monitoring()
            self.auto_started_monitoring = True

        timeout_ms = int(self.config_data.get("response_timeout_seconds", 60) * 1000)
        self._response_timeout_job = self.root.after(timeout_ms, self._on_response_timeout)

    def _set_response_buttons(self, enabled):
        state = "normal" if enabled else "disabled"
        self.explain_btn.configure(state=state)
        self.human_btn.configure(state=state)
        self.ignore_btn.configure(state=state)

    def _on_response_timeout(self):
        self._log("No response to the warning \u2014 dismissing automatically.", persist=True)
        self._dismiss_warning()

    def _dismiss_warning(self):
        if self._response_timeout_job is not None:
            try:
                self.root.after_cancel(self._response_timeout_job)
            except Exception:
                pass
            self._response_timeout_job = None
        self.warning_active = False
        # remember this screen's fingerprint so the background scanner
        # doesn't immediately re-alert on the same unchanged page
        self._last_dismissed_signature = self._last_scan_text_hash
        self._set_response_buttons(enabled=False)
        self.result_banner.configure(text="", fg=COLOR_TEXT)
        self.english_label.configure(text="")
        self.urdu_label.configure(text="")
        self.reason_label.configure(text="")
        if self.overlay is not None:
            self.overlay.close()
            self.overlay = None
        if self.auto_started_monitoring:
            self.stop_monitoring()
            self.auto_started_monitoring = False

    # ---------------- AUTOMATIC BACKGROUND SCREEN CHECKING ----------------
    # Runs on a timer from app launch (no button press needed), independent
    # of the webcam. A cheap thumbnail diff (screen_changed) runs first and
    # skips OCR entirely when nothing on screen has visibly changed, so
    # this stays lightweight even at a fast tick rate - not a webcam feed,
    # not a paid API call. Stays silent unless something risky is found; a
    # positive/safe result is not announced to avoid spamming the UI.
    def auto_scan_tick(self):
        if not self.warning_active and not self._auto_scan_in_progress and not self.action_busy:
            self._auto_scan_in_progress = True
            threading.Thread(target=self._auto_scan_worker, daemon=True).start()
        interval_ms = int(self.config_data.get("auto_scan_interval_seconds", 2) * 1000)
        self.root.after(interval_ms, self.auto_scan_tick)

    def _auto_scan_worker(self):
        img, title = capture_active_window()
        if img is None:
            # No usable foreground window right now (desktop/taskbar
            # focused, alt-tab in progress, etc.) - just wait for the next
            # tick instead of falling back to a full-desktop grab, which is
            # what used to sweep in other open tabs/windows and cause
            # false alarms.
            self.root.after(0, self._auto_scan_done)
            return

        changed, thumb = screen_changed(self._last_screen_thumb, img)
        self._last_screen_thumb = thumb
        if not changed:
            # Nothing visibly changed since last check - skip the
            # relatively expensive OCR call entirely this tick.
            self.root.after(0, self._auto_scan_done)
            return

        result = analyze_screenshot_for_risk(img, window_title=title)
        result["img"] = img
        self.root.after(0, lambda: self._on_auto_scan_result(result))

    def _auto_scan_done(self):
        self._auto_scan_in_progress = False

    def _on_auto_scan_result(self, result):
        self._auto_scan_in_progress = False
        if self.warning_active:
            return  # a warning already appeared meanwhile - don't double up

        if result["status"] != "risky":
            return  # stay silent in the background for safe/unknown results

        sig = result.get("text_hash")
        if sig is not None and sig == self._last_dismissed_signature:
            return  # user already responded to this exact screen recently

        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"auto_risk_{ts}.png")
        try:
            result["img"].save(path)
        except Exception:
            pass

        self._last_scan_img = result["img"]
        self._last_scan_path = path
        self._last_scan_text_hash = sig
        self._last_scan_hint = build_ai_hint(result)
        self._log(f"Automatic scan flagged risk: {result.get('reason_en', '')}", persist=True)
        self._show_danger_banner(result["en_text"], result["urdu_text"],
                                  result.get("reason_en", ""), result.get("severity", "medium"))
        threading.Thread(target=self._speak_worker, args=(result["urdu_text"],), daemon=True).start()

    # ============================================================
    # LAYER 2 - GESTURE / BUTTON RESPONSE
    # ============================================================
    # ---------------- MONITORING ----------------
    def toggle_monitoring(self):
        if not self.monitoring:
            self.start_monitoring()
        else:
            self.stop_monitoring()

    def start_monitoring(self):
        if not os.path.exists(MODEL_FILE):
            messagebox.showerror("Missing model", f"{MODEL_FILE} not found. Run 1_collect_data.py "
                                                     f"and 2_train_model.py first.")
            return
        if self.model is None:
            with open(MODEL_FILE, 'rb') as f:
                self.model = pickle.load(f)
        if self.hands is None:
            self.mp_hands = mp.solutions.hands
            self.mp_drawing = mp.solutions.drawing_utils
            self.hands = self.mp_hands.Hands(static_image_mode=False, max_num_hands=1,
                                              min_detection_confidence=0.7, min_tracking_confidence=0.7)
        self.cap = cv2.VideoCapture(0)
        self.monitoring = True
        self.start_button.configure(text="Stop Monitoring")
        self._draw_dot(COLOR_READY)
        self.status_label.configure(text="Camera: ON  |  System ready")
        self._log("Monitoring started.")
        self._update_frame()

    def stop_monitoring(self):
        self.monitoring = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.start_button.configure(text="Start Monitoring")
        self._draw_dot(COLOR_TEXT_MUTED)
        self.status_label.configure(text="Camera: OFF  |  System not ready")
        self.hold_label.configure(text="")
        self.confidence_label.configure(text="")
        self.video_label.configure(image="")
        self._log("Monitoring stopped.")

    # ---------------- MAIN LOOP ----------------
    def _update_frame(self):
        if not self.monitoring or self.cap is None:
            return
        success, frame = self.cap.read()
        if success:
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb)
            predicted_label = 'no hand detected'
            confidence = 0.0

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    self.mp_drawing.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                    features = normalize_landmarks(hand_landmarks)
                    arr = np.array(features).reshape(1, -1)
                    if self.model is not None:
                        proba = self.model.predict_proba(arr)[0]
                        idx = int(np.argmax(proba))
                        confidence = float(proba[idx])
                        raw_label = self.model.classes_[idx]
                        threshold = self.config_data.get("confidence_threshold", 0.75)
                        predicted_label = raw_label if confidence >= threshold else 'uncertain'

                    # "ignore" (flat open palm) may not exist at all in the
                    # trained model's classes_ if gesture_data.csv never got
                    # samples for it - in that case the model can NEVER
                    # predict it, no matter how long you hold it up. This
                    # rule-based geometry check works immediately, with zero
                    # training data, as long as nothing else was confidently
                    # recognized for this frame.
                    if predicted_label in ('uncertain', 'neutral', 'no hand detected'):
                        if is_open_palm(hand_landmarks):
                            predicted_label = 'ignore'
                            confidence = max(confidence, 1.0)

            self._process_trigger_logic(predicted_label)

            display = cv2.resize(frame, (480, 360))
            img = Image.fromarray(cv2.cvtColor(display, cv2.COLOR_BGR2RGB))
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)
            self.confidence_label.configure(text=f"detected: {predicted_label}   confidence {confidence*100:4.0f}%")

        self.root.after(30, self._update_frame)

    # ---------------- TRIGGER LOGIC ----------------
    def _process_trigger_logic(self, predicted_label):
        hold_seconds = self.config_data.get("hold_seconds", 2.5)
        cooldown = self.config_data.get("cooldown_seconds", 3.0)
        now = time.time()

        # "ignore" only does something while a warning is actually showing -
        # otherwise it's treated like any other non-trigger gesture.
        trigger_labels = ("ai_help", "human_help", "ignore") if self.warning_active else ("ai_help", "human_help")

        if self.action_busy or predicted_label not in trigger_labels:
            if predicted_label not in trigger_labels:
                self.current_gesture = None
                self.gesture_start_time = None
                self.hold_label.configure(text="")
            return

        if now < self.cooldown_until.get(predicted_label, 0):
            self.hold_label.configure(text="cooldown active")
            return

        if self.current_gesture != predicted_label:
            self.current_gesture = predicted_label
            self.gesture_start_time = now
        else:
            held = now - self.gesture_start_time
            self.hold_label.configure(text=f"holding {predicted_label} \u2014 {held:.1f}s / {hold_seconds:.1f}s")
            if held >= hold_seconds:
                self.cooldown_until[predicted_label] = now + cooldown
                self.current_gesture = None
                self.gesture_start_time = None
                self.hold_label.configure(text="")
                if predicted_label == "ai_help":
                    self._trigger_ai_help(from_warning=self.warning_active)
                elif predicted_label == "human_help":
                    self._trigger_human_help(from_warning=self.warning_active)
                else:
                    self._trigger_ignore()

    # ---------------- AI HELP ("Explain this to me") ----------------
    def _trigger_ai_help(self, from_warning=False):
        was_warning = self.warning_active
        if was_warning:
            self._dismiss_warning()
        self.action_busy = True
        self._pending_ai_hint = self._last_scan_hint if from_warning else ""
        self._log("AI HELP (Explain) triggered.", persist=True)
        if from_warning and self._last_scan_img is not None:
            path, img = self._last_scan_path, self._last_scan_img
        else:
            path, img, _title = self._take_screenshot("ai_help")
        self._ai_help_image_copied = False
        if img is not None:
            self._ai_help_image_copied = self._copy_image_to_clipboard(img)
        webbrowser.open(AI_CHAT_URL)
        self._log(f"Screenshot used: {path}", persist=True)
        self._log("Opening ChatGPT and pasting screenshot automatically...", persist=True)
        self.root.after(10000, self._ai_help_step2)

    def _ai_help_step2(self):
        try:
            matching = [w for w in gw.getAllWindows() if 'chatgpt' in w.title.lower()]
            if not matching:
                self._log("Could not find the ChatGPT window \u2014 paste the "
                           "screenshot manually (Ctrl+V) instead.", persist=True)
                self._clear_busy()
                return
            win = matching[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            try:
                win.maximize()
            except Exception:
                pass
            self.root.after(400, self._ai_help_step3)
        except Exception as e:
            self._log(f"Failed to switch to ChatGPT: {e}")
            self._clear_busy()

    def _ai_help_step3(self):
        try:
            sw, sh = pyautogui.size()
            pyautogui.click(x=sw // 2, y=sh - 90)
            self.root.after(300, self._ai_help_step4)
        except Exception as e:
            self._log(f"Failed to click the ChatGPT message box: {e}")
            self._clear_busy()

    def _ai_help_step4(self):
        try:
            if self._ai_help_image_copied:
                pyautogui.hotkey('ctrl', 'v')
            self.root.after(800, self._ai_help_step5)
        except Exception as e:
            self._log(f"Failed to paste screenshot into ChatGPT: {e}")
            self._clear_busy()

    def _ai_help_step5(self):
        try:
            pyautogui.write(AI_PROMPT + self._pending_ai_hint, interval=0.01)
            self._log("Screenshot pasted and prompt typed \u2014 review and press "
                       "Enter to send.", persist=True)
            self._log("Once ChatGPT replies, tap the speaker/read-aloud icon "
                       "under its response to hear it spoken in Urdu.", persist=True)
        except Exception as e:
            self._log(f"Failed to type prompt into ChatGPT: {e}")
        finally:
            self._clear_busy()

    # ---------------- HUMAN HELP ----------------
    # NOTE: WhatsApp's "click to chat" URL (web.whatsapp.com/send?...) can
    # only pre-fill TEXT into the compose box - it has no way to attach an
    # image. The old version worked around this by putting the screenshot's
    # local file PATH into that text, but a path on the user's own PC is
    # meaningless to whoever receives it - it's not the picture itself. This
    # version instead copies the actual screenshot image to the clipboard
    # (the same trick used for AI Help) and pastes it into the chat with
    # Ctrl+V, then types a short caption, so the helper actually receives
    # the image.
    def _trigger_human_help(self, from_warning=False):
        if self.warning_active:
            self._dismiss_warning()
        self.action_busy = True
        self._log("HUMAN HELP triggered.", persist=True)
        if from_warning and self._last_scan_img is not None:
            path, img = self._last_scan_path, self._last_scan_img
        else:
            path, img, _title = self._take_screenshot("human_help")
        phone = self.config_data.get("help_contact_phone", "")
        if not phone:
            self._log("No help contact configured \u2014 set one in Configuration.")
            self._clear_busy()
            return
        self._human_help_image_copied = False
        if img is not None:
            self._human_help_image_copied = self._copy_image_to_clipboard(img)
        self._human_help_caption = (
            "DIGITAL SHIELD ALERT: A user has requested cybersecurity/human help. "
            "They may be facing something confusing or suspicious on their screen "
            "(screenshot attached)."
        )
        phone_digits = phone.replace('+', '')
        url = f"https://web.whatsapp.com/send?phone={phone_digits}"
        webbrowser.open(url)
        self._log(f"Screenshot used: {path}", persist=True)
        self._log("Opening WhatsApp and attaching screenshot automatically...", persist=True)
        self.root.after(16000, self._send_human_help_step2)

    def _send_human_help_step2(self):
        try:
            matching = [w for w in gw.getAllWindows() if 'whatsapp' in w.title.lower()]
            if not matching:
                self._log("Could not find WhatsApp window \u2014 paste the "
                           "screenshot manually (Ctrl+V) instead.", persist=True)
                self._clear_busy()
                return
            win = matching[0]
            if win.isMinimized:
                win.restore()
            win.activate()
            try:
                win.maximize()
            except Exception:
                pass
            self.root.after(350, self._send_human_help_step3)
        except Exception as e:
            self._log(f"Failed to send human help alert: {e}")
            self._clear_busy()

    def _send_human_help_step3(self):
        try:
            sw, sh = pyautogui.size()
            pyautogui.click(x=sw // 2, y=sh - 90)
            if self._human_help_image_copied:
                self.root.after(300, self._send_human_help_step3b)
            else:
                self.root.after(200, self._send_human_help_step4)
        except Exception as e:
            self._log(f"Failed to click message box: {e}")
            self._clear_busy()

    def _send_human_help_step3b(self):
        try:
            # Paste the screenshot. WhatsApp opens an image-preview/caption
            # view for this - give it a moment to load before typing.
            pyautogui.hotkey('ctrl', 'v')
            self.root.after(900, self._send_human_help_step4)
        except Exception as e:
            self._log(f"Failed to paste screenshot into WhatsApp: {e}")
            self.root.after(0, self._send_human_help_step4)

    def _send_human_help_step4(self):
        try:
            pyautogui.write(self._human_help_caption, interval=0.01)
            self.root.after(300, self._send_human_help_step5)
        except Exception as e:
            self._log(f"Failed to type caption: {e}")
            self._clear_busy()

    def _send_human_help_step5(self):
        try:
            pyautogui.press('enter')
            self._log("Human help WhatsApp alert sent"
                       + (" with screenshot." if self._human_help_image_copied else " (text only \u2014 no screenshot available)."),
                       persist=True)
        except Exception as e:
            self._log(f"Failed to finish sending: {e}")
        finally:
            self._clear_busy()

    # ---------------- IGNORE / CONTINUE ----------------
    def _trigger_ignore(self):
        self._log("IGNORE / CONTINUE selected.", persist=True)
        self._dismiss_warning()

    def _clear_busy(self):
        self.action_busy = False

    def _take_screenshot(self, tag):
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(SCREENSHOT_DIR, f"{tag}_{ts}.png")
        img, title = capture_active_window()
        if img is None:
            # No usable foreground window (rare) - fall back to a full
            # screen grab only here, since this is an explicit, one-off
            # user action (Check My Screen / AI Help / Human Help), not
            # the continuous background scanner.
            try:
                img = ImageGrab.grab()
            except Exception as e:
                self._log(f"Screenshot failed: {e}")
                img = None
        if img is not None:
            try:
                img.save(filename)
            except Exception as e:
                self._log(f"Screenshot failed: {e}")
        return filename, img, title

    def _copy_image_to_clipboard(self, image):
        try:
            output = io.BytesIO()
            image.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]  # strip BMP file header, keep DIB
            output.close()
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            self._log(f"Could not copy screenshot to clipboard: {e}")
            return False

    # ---------------- CLOSE ----------------
    def on_close(self):
        self.monitoring = False
        if self.cap is not None:
            self.cap.release()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DigitalShieldApp(root)
    root.mainloop()
