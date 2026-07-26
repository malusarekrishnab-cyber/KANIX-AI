import sys
import importlib.util
from pathlib import Path

# Load root-level ui.py explicitly to resolve shadowing caused by the ui/ directory
root_dir = Path(__file__).resolve().parent.parent
ui_py_path = root_dir / "ui.py"

if ui_py_path.exists():
    spec = importlib.util.spec_from_file_location("root_ui", str(ui_py_path))
    root_ui = importlib.util.module_from_spec(spec)
    sys.modules["root_ui"] = root_ui
    spec.loader.exec_module(root_ui)
    kanixUI = root_ui.kanixUI
else:
    raise ImportError("Could not locate root-level ui.py")
