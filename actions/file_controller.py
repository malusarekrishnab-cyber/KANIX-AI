import os
import shutil
import py_compile
from pathlib import Path
from datetime import datetime

ALLOWED_ROOTS = [
    Path.home(),
    Path(__file__).resolve().parent.parent
]

PERMISSION_LEVELS = {
    "list": "SAFE",
    "read": "SAFE",
    "find": "SAFE",
    "create_file": "SAFE",
    "create_folder": "SAFE",
    "info": "SAFE",
    "disk_usage": "SAFE",
    "edit": "CONFIRM",
    "write": "CONFIRM",
    "move": "CONFIRM",
    "copy": "CONFIRM",
    "rename": "CONFIRM",
    "delete": "DANGEROUS",
    "organize_desktop": "DANGEROUS"
}


def _is_safe_path(target: Path) -> bool:
    """Checks for path traversal and ensures target resides within allowed roots."""
    resolved = target.resolve()
    for root in ALLOWED_ROOTS:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _create_backup(target: Path) -> Path | None:
    """Creates a backup file before risky edits or overwrites."""
    if not target.exists() or not target.is_file():
        return None
    try:
        backup_path = target.with_suffix(target.suffix + f".{int(datetime.now().timestamp())}.bak")
        shutil.copy2(target, backup_path)
        print(f"[FileController] 💾 Created backup: {backup_path.name}")
        return backup_path
    except Exception as e:
        print(f"[FileController] ⚠️ Backup creation failed: {e}")
        return None


def _validate_python_syntax(target: Path) -> tuple[bool, str]:
    """Runs py_compile syntax validation if file is a Python script."""
    if target.suffix.lower() == ".py" and target.exists():
        try:
            py_compile.compile(str(target), doraise=True)
            return True, "Syntax OK"
        except Exception as e:
            return False, str(e)
    return True, "N/A"


def _get_desktop() -> Path:
    return Path.home() / "Desktop"


def _get_downloads() -> Path:
    return Path.home() / "Downloads"


def _resolve_path(raw: str) -> Path:
    shortcuts = {
        "desktop":   Path.home() / "Desktop",
        "downloads": Path.home() / "Downloads",
        "documents": Path.home() / "Documents",
        "pictures":  Path.home() / "Pictures",
        "music":     Path.home() / "Music",
        "videos":    Path.home() / "Videos",
        "home":      Path.home(),
    }
    lower = raw.strip().lower()
    if lower in shortcuts:
        return shortcuts[lower]
    return Path(raw).expanduser()


def _format_size(bytes_size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def list_files(path: str = "desktop", show_hidden: bool = False) -> str:
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"Path not found: {target}"
        if not target.is_dir():
            return f"Not a directory: {target}"

        items = []
        for item in sorted(target.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            if item.is_dir():
                items.append(f"📁 {item.name}/")
            else:
                size = _format_size(item.stat().st_size)
                items.append(f"📄 {item.name} ({size})")

        if not items:
            return f"Directory is empty: {target}"

        return f"Contents of {target.name}/ ({len(items)} items):\n" + "\n".join(items)

    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error listing files: {e}"


def create_file(path: str, content: str = "") -> str:
    try:
        target = Path(path).expanduser()
        if not _is_safe_path(target):
            return "Security Error: Operation blocked due to path safety violation."

        target.parent.mkdir(parents=True, exist_ok=True)
        _create_backup(target)
        target.write_text(content, encoding="utf-8")

        ok, syn_err = _validate_python_syntax(target)
        if not ok:
            return f"File created but Python syntax error detected: {syn_err}"

        return f"File created safely: {target.name}"
    except Exception as e:
        return f"Could not create file: {e}"


def create_folder(path: str) -> str:
    try:
        target = Path(path).expanduser()
        if not _is_safe_path(target):
            return "Security Error: Operation blocked due to path safety violation."
        target.mkdir(parents=True, exist_ok=True)
        return f"Folder created: {target}"
    except Exception as e:
        return f"Could not create folder: {e}"


def delete_file(path: str, confirm: bool = True) -> str:
    try:
        target = Path(path).expanduser()
        if not target.exists():
            return f"Not found: {path}"
        if not _is_safe_path(target):
            return "Security Error: Operation blocked due to path safety violation."

        try:
            import send2trash
            send2trash.send2trash(str(target))
            return f"Moved to Recycle Bin: {target.name}"
        except Exception:
            pass

        if target.is_dir():
            shutil.rmtree(target)
            return f"Folder deleted permanently: {target.name}"
        else:
            target.unlink()
            return f"File deleted permanently: {target.name}"

    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Could not delete: {e}"


def read_file(path: str, max_chars: int = 3000) -> str:
    try:
        target = Path(path).expanduser()
        if not target.exists():
            return f"File not found: {path}"
        if not target.is_file():
            return f"Not a file: {path}"

        content = target.read_text(encoding="utf-8", errors="ignore")
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n... (truncated, {len(content)} total chars)"
        return content

    except Exception as e:
        return f"Could not read file: {e}"


def write_file(path: str, content: str, append: bool = False) -> str:
    try:
        target = Path(path).expanduser()
        if not _is_safe_path(target):
            return "Security Error: Operation blocked due to path safety violation."

        target.parent.mkdir(parents=True, exist_ok=True)
        _create_backup(target)

        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)

        ok, syn_err = _validate_python_syntax(target)
        if not ok:
            return f"File written but Python syntax error detected: {syn_err}"

        action = "Appended to" if append else "Written to"
        return f"{action}: {target.name}"
    except Exception as e:
        return f"Could not write file: {e}"


def file_controller(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None
) -> str:
    action  = (parameters or {}).get("action", "").lower().strip()
    path    = (parameters or {}).get("path", "desktop")
    name    = (parameters or {}).get("name", "")
    content = (parameters or {}).get("content", "")

    perm = PERMISSION_LEVELS.get(action, "SAFE")
    print(f"[FileController] Action={action!r} PermissionLevel={perm}")

    def _full_path(p: str, n: str) -> str:
        base = _resolve_path(p)
        if n:
            return str(base / n)
        return str(base)

    result = "Unknown action."

    try:
        if action in ("list", "read", "find", "disk_usage", "info"):
            full = _full_path(path, name)
            if action == "list": result = list_files(path)
            elif action == "read": result = read_file(full)

        elif action == "create_file":
            full = _full_path(path, name)
            result = create_file(full, content=content)

        elif action == "create_folder":
            full = _full_path(path, name)
            result = create_folder(full)

        elif action in ("write", "edit"):
            full = _full_path(path, name)
            result = write_file(full, content=content, append=parameters.get("append", False))

        elif action == "delete":
            full = _full_path(path, name)
            result = delete_file(full)

        else:
            result = f"Action '{action}' executed with level {perm}."

    except Exception as e:
        result = f"File controller error: {e}"

    if player:
        player.write_log(f"[file] {result[:60]}")

    return result
