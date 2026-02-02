"""Capture metadata from the active app (Xcode file/line, browser URL, git branch)."""

import subprocess
import sys
from typing import Any, Optional

if sys.platform == "darwin":
    try:
        from AppKit import NSWorkspace  # pylint: disable=invalid-name
    except ImportError:
        NSWorkspace = None  # type: ignore  # pylint: disable=invalid-name
else:
    NSWorkspace = None  # type: ignore  # pylint: disable=invalid-name


def get_frontmost_app_bundle_id() -> Optional[str]:
    """Return the bundle id of the frontmost application, or None."""
    if sys.platform != "darwin" or NSWorkspace is None:
        return None
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return app.bundleIdentifier() if app else None
    except Exception:
        return None


def _run_applescript(script: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def get_xcode_context() -> Optional[dict[str, Any]]:
    """If frontmost app is Xcode, return {app, file, line} from AppleScript."""
    if get_frontmost_app_bundle_id() != "com.apple.dt.Xcode":
        return None
    script = """
    tell application "Xcode" to get the path of the current document
    """
    path = _run_applescript(script)
    if not path:
        return {"app": "Xcode"}
    script2 = """
    tell application "Xcode" to get the current line of the current document
    """
    line_str = _run_applescript(script2)
    line = int(line_str) if line_str and line_str.isdigit() else None
    return {"app": "Xcode", "file": path, "line": line}


def get_browser_url() -> Optional[str]:
    """If frontmost app is Safari or Chrome, return current tab URL."""
    bid = get_frontmost_app_bundle_id()
    if bid == "com.apple.Safari":
        return _run_applescript(
            'tell application "Safari" to get URL of current tab of front window'
        )
    if bid == "com.google.Chrome":
        return _run_applescript(
            'tell application "Google Chrome" to get URL of active tab of front window'
        )
    return None


def get_git_branch(cwd: Optional[str] = None) -> Optional[str]:
    """Return current git branch in cwd (or default)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1,
            cwd=cwd,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def capture_context(cwd: Optional[str] = None) -> dict[str, Any]:
    """
    Capture metadata from the active app: Xcode file/line, browser URL, git branch.
    Store as JSON-serializable dict for meta_payload.
    """
    payload: dict[str, Any] = {}
    xcode = get_xcode_context()
    if xcode:
        payload["xcode"] = xcode
    url = get_browser_url()
    if url:
        payload["browser_url"] = url
    branch = get_git_branch(cwd)
    if branch:
        payload["git_branch"] = branch
    return payload
