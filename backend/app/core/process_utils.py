import os
import shutil
import subprocess
import sys
from pathlib import Path


def resolve_binary(binary_name_or_path: str) -> str:
    """
    Resolves binary path across Windows (.exe/.cmd) and Linux.
    Falls back to original string if shutil.which returns None.
    """
    found = shutil.which(binary_name_or_path)
    if found:
        return found

    # Check Python environment directory (Conda / venv / Scripts / bin)
    py_dir = Path(sys.executable).parent
    candidates = [
        py_dir / "Scripts" / f"{binary_name_or_path}.exe",
        py_dir / "Scripts" / binary_name_or_path,
        py_dir / "bin" / binary_name_or_path,
        py_dir / f"{binary_name_or_path}.exe",
        py_dir / binary_name_or_path,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return str(c)
    return binary_name_or_path


def kill_proc_tree(pid: int) -> None:
    """Kills a process and all of its spawned child processes across Windows & Linux."""
    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            try:
                os.killpg(os.getpgid(pid), 9)
            except Exception:
                os.kill(pid, 9)
    except Exception:
        pass
