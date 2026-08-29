import os
import sys
import socket
import platform

_OS = platform.system()
_lock_socket = None

def ensure_single_instance(port: int = 49152) -> bool:
    """
    Guarantees only a single instance of KANIX is running using a local socket lock.
    Returns True if this is the single instance, False if another instance is running.
    """
    global _lock_socket
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(("127.0.0.1", port))
        _lock_socket.listen(1)
        print(f"[System] Single instance lock acquired on port {port}.")
        return True
    except OSError:
        print("[System] Another KANIX instance is already running!")
        return False

def set_windows_autostart(enable: bool = True, app_name: str = "KANIX_AI") -> bool:
    """
    Enables or disables Windows Auto Start via the Windows Registry.
    """
    if _OS != "Windows":
        print("[System] Auto Start configuration skipped (non-Windows system).")
        return True

    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        exe_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                print(f"[System] Windows Auto Start enabled for {app_name}.")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    print(f"[System] Windows Auto Start disabled for {app_name}.")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"[System] ⚠️ Windows Auto Start configuration error: {e}")
        return False
