"""Cross-platform path resolution and host path translation utilities for Windows, macOS, and Linux."""

import os
import re
from pathlib import Path, PureWindowsPath, PurePosixPath
from typing import Optional


def is_windows_path(path_str: str) -> bool:
    """Detects if a path string is in Windows format (e.g. C:\\..., D:/..., \\\\server\\..., etc.)."""
    if not path_str:
        return False
    # Check for drive letters like C:\ or C:/ or D:
    if re.match(r"^[a-zA-Z]:[\\/]", path_str):
        return True
    # Check for UNC network share path (\\\\server\\share)
    if path_str.startswith(r"\\"):
        return True
    # Contains backslashes without forward slashes
    if "\\" in path_str:
        return True
    return False


def is_git_bash_windows_path(path_str: str) -> bool:
    """Detects Git Bash / MinGW drive format like /c/Users/... or /d/projects/..."""
    return bool(re.match(r"^/[a-zA-Z]/", path_str))


def format_host_path(
    video_path: Optional[str],
    host_output_dir: Optional[str] = None,
    container_output_dir: Optional[str] = None
) -> Optional[str]:
    """
    Translates an internal container video path into a valid host machine absolute path
    compatible across Windows (PowerShell, CMD, WSL, Git Bash), macOS, and Linux.
    """
    if not video_path:
        return video_path

    v_str = str(video_path).strip()
    if not v_str:
        return v_str

    if not host_output_dir:
        # Running natively on host OS (macOS, Linux, or Windows)
        try:
            return str(Path(v_str).resolve())
        except Exception:
            return v_str

    host_dir = str(host_output_dir).strip()
    container_dir = str(container_output_dir or "/app/output").strip()

    # Determine relative path from container output directory
    rel_path = None
    if v_str.startswith(container_dir):
        rel_path = os.path.relpath(v_str, container_dir)
    elif v_str.startswith("/app/output"):
        rel_path = os.path.relpath(v_str, "/app/output")
    elif v_str.startswith("./output") or v_str.startswith("output"):
        clean_prefix = "./output" if v_str.startswith("./output") else "output"
        rel_path = os.path.relpath(v_str, clean_prefix)

    if rel_path is None:
        # Path is outside known container output dirs, return resolved or raw path
        if is_windows_path(v_str):
            return str(PureWindowsPath(v_str))
        try:
            return str(Path(v_str).resolve())
        except Exception:
            return v_str

    # Normalize relative path components
    rel_parts = [p for p in rel_path.replace("\\", "/").split("/") if p and p != "."]

    # Handle standard Windows host path (C:\..., D:/..., etc.)
    if is_windows_path(host_dir):
        win_path = PureWindowsPath(host_dir)
        for part in rel_parts:
            win_path = win_path / part
        return str(win_path)

    # Handle Git Bash / MSYS2 / MinGW Windows format (e.g. /c/Users/...)
    if is_git_bash_windows_path(host_dir):
        clean_base = host_dir.rstrip("/")
        return f"{clean_base}/{'/'.join(rel_parts)}"

    # Handle POSIX host path (macOS / Linux)
    posix_path = PurePosixPath(host_dir)
    for part in rel_parts:
        posix_path = posix_path / part
    return str(posix_path)
