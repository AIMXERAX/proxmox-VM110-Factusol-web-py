import os
import sys
from pathlib import Path


def ensure_venv() -> None:
    """Relaunch the current script with the project virtualenv when needed."""
    project_dir = Path(__file__).resolve().parent
    venv_python = project_dir / ".venv" / "Scripts" / "python.exe"

    if not venv_python.exists():
        return

    current = Path(sys.executable).resolve()
    target = venv_python.resolve()
    if current == target:
        return

    os.execv(str(target), [str(target), *sys.argv])
