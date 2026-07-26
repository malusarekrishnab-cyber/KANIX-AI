# actions/send_message.py
# Universal messaging — WhatsApp & Instagram
# Uses window-relative clicks (works for both WhatsApp Desktop app and WhatsApp Web)

import time
import shutil
import subprocess
import pyautogui
import pygetwindow as gw
from pathlib import Path

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.08


def _open_url_in_chrome(url: str):
    """Opens a URL in Chrome specifically. Falls back to default browser if Chrome isn't found."""
    chrome_path = shutil.which("chrome") or shutil.which("google-chrome")
    if chrome_path:
        subprocess.Popen([chrome_path, url])
    else:
        import webbrowser
        webbrowser.open(url)


def _find_open_window(app_name: str):
    """Returns the first open window whose title contains app_name, or None."""
    try:
        matches = [w for w in gw.getAllTitles() if app_name.lower() in w.lower() and w.strip()]
        if matches:
            return gw.getWindowsWithTitle(matches[0])[0]
    except Exception as e:
        print(f"[SendMessage] Window search failed: {e}")
    return None


def _open_app(app_name: str):
    """
    Focuses the app if it's already open, otherwise launches it fresh
    via Windows search. Returns the window object (or None on failure).
    """
    try:
        win = _find_open_window(app_name)
        if win:
            print(f"[SendMessage] 🔎 {app_name} already open — focusing it.")
            if win.isMinimized:
                win.restore()
            win.activate()
            time.sleep(1.0)
            return win

        print(f"[SendMessage] 🚀 {app_name} not open — launching fresh.")
        pyautogui.press("win")
        time.sleep(0.4)
        pyautogui.write(app_name, interval=0.04)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(3.5)

        win = _find_open_window(app_name)
        if not win:
            win = _find_open_window("WhatsApp")  # catches "WhatsApp Web" browser tab too
        return win
    except Exception as e:
        print(f"[SendMessage] Could not open {app_name}: {e}")
        return None


def _click_in_window(win, x_pct: float, y_pct: float):
    """Clicks at a position relative to the given window's bounds."""
    x = win.left + int(win.width * x_pct)
    y = win.top + int(win.height * y_pct)
    pyautogui.click(x, y)


def _send_whatsapp(receiver: str, message: str) -> str:
    """
    Sends a WhatsApp message via Desktop app OR WhatsApp Web (same layout logic).
    Steps: Focus/Open → Click search box → Type contact → Click first result → Type message → Send
    """
    try:
        win = _open_app("WhatsApp")
        if not win:
            return "Could not open WhatsApp."

        already_open_wait = 0.8
        fresh_open_wait    = 2.5
        time.sleep(fresh_open_wait)

        win = _find_open_window("WhatsApp")  # refresh bounds after load
        if not win:
            return "WhatsApp window not found after opening."

        # Click directly into WhatsApp's own search box (top-left of the chat list)
        _click_in_window(win, 0.15, 0.12)
        time.sleep(0.4)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(receiver, interval=0.06)
        time.sleep(1.2)

        # Click the first matching contact in the filtered list
        _click_in_window(win, 0.15, 0.20)
        time.sleep(1.0)

        # Click the message box at the bottom and type
        _click_in_window(win, 0.5, 0.94)
        time.sleep(0.4)
        pyautogui.write(message, interval=0.03)
        time.sleep(0.2)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via WhatsApp."

    except Exception as e:
        return f"WhatsApp error: {e}"


def _send_instagram(receiver: str, message: str) -> str:
    try:
        _open_url_in_chrome("https://www.instagram.com/direct/new/")
        time.sleep(4.0)

        pyautogui.write(receiver, interval=0.05)
        time.sleep(1.5)

        pyautogui.press("down")
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.5)

        for _ in range(3):
            pyautogui.press("tab")
            time.sleep(0.1)
        pyautogui.press("enter")
        time.sleep(1.5)

        pyautogui.write(message, interval=0.04)
        time.sleep(0.2)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via Instagram."

    except Exception as e:
        return f"Instagram error: {e}"


def _send_telegram(receiver: str, message: str) -> str:
    try:
        win = _open_app("Telegram")
        if not win:
            return "Could not open Telegram."

        time.sleep(2.0)
        win = _find_open_window("Telegram")
        if not win:
            return "Telegram window not found after opening."

        _click_in_window(win, 0.15, 0.08)
        time.sleep(0.4)
        pyautogui.write(receiver, interval=0.04)
        time.sleep(1.0)
        pyautogui.press("enter")
        time.sleep(0.8)

        pyautogui.write(message, interval=0.03)
        time.sleep(0.2)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via Telegram."

    except Exception as e:
        return f"Telegram error: {e}"


def _send_generic(platform: str, receiver: str, message: str) -> str:
    try:
        win = _open_app(platform)
        if not win:
            return f"Could not open {platform}."

        time.sleep(2.0)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)
        pyautogui.write(receiver, interval=0.04)
        time.sleep(1.0)
        pyautogui.press("enter")
        time.sleep(0.8)
        pyautogui.write(message, interval=0.03)
        time.sleep(0.2)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via {platform}."

    except Exception as e:
        return f"{platform} error: {e}"


def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None
) -> str:
    params       = parameters or {}
    receiver     = params.get("receiver", "").strip()
    message_text = params.get("message_text", "").strip()
    platform     = params.get("platform", "whatsapp").strip().lower()

    if not receiver:
        return "Please specify who to send the message to, sir."
    if not message_text:
        return "Please specify what message to send, sir."

    print(f"[SendMessage] 📨 {platform} → {receiver}: {message_text[:40]}")
    if player:
        player.write_log(f"[msg] Sending to {receiver} via {platform}...")

    if "whatsapp" in platform or "wp" in platform or "wapp" in platform:
        result = _send_whatsapp(receiver, message_text)

    elif "instagram" in platform or "ig" in platform or "insta" in platform:
        result = _send_instagram(receiver, message_text)

    elif "telegram" in platform or "tg" in platform:
        result = _send_telegram(receiver, message_text)

    else:
        result = _send_generic(platform, receiver, message_text)

    print(f"[SendMessage] ✅ {result}")
    if player:
        player.write_log(f"[msg] {result}")

    return result