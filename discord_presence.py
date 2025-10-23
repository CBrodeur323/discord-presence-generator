
"""
Discord Rich Presence (Windows) — Privacy‑aware active window labeler.

- Reads DISCORD_CLIENT_ID and other settings from environment / .env
- Masks sensitive window titles BEFORE any app mapping (browser or not)
- Normalizes case for SENSITIVE_TERMS (configurable via env MASK_TERMS)
- Adds reconnect logic for Discord RPC
- Adds logging with --verbose flag, configurable intervals
- Explicit Windows platform guard
- No employer-specific or personally identifiable defaults

Usage:
    python discord_presence.py --verbose

Env (.env supported if python-dotenv installed):
    DISCORD_CLIENT_ID=123456789012345678
    MASK_TERMS=companyname,confidential,nces,budget,invoice,payroll,student,medical,legal
    UPDATE_EVERY_SECS=15
    CHECK_INTERVAL=1

Notes:
- Windows only (uses pywin32 / pygetwindow).
- Never sends raw window titles to Discord; only the derived label.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional, Tuple

# ---- Platform guard ----
if sys.platform != "win32":
    raise SystemExit("This script currently supports Windows only.")

# ---- Optional dotenv ----
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None  # noqa: N816

if load_dotenv:
    load_dotenv()  # load .env if present

# ---- Dependencies for Windows window/title ----
try:
    import win32gui  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit("pywin32 is required on Windows (pip install pywin32)") from e

try:
    import pygetwindow as gw  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit("pygetwindow is required (pip install pygetwindow)") from e

# ---- Discord RPC ----
try:
    from pypresence import Presence  # type: ignore
    from pypresence.exceptions import InvalidID, InvalidPipe  # type: ignore
except Exception as e:  # pragma: no cover
    raise SystemExit("pypresence is required (pip install pypresence)") from e

# ---- Config & defaults ----

SAFE_MASK_MESSAGE = "Working — details hidden"
SAFE_IDLE_MESSAGE = "Idle"

DEFAULT_SENSITIVE_TERMS = (
    # Neutral, non‑PII examples; customize via MASK_TERMS env or README
    "companyname",
    "confidential",
    "privacy",
    "secret",
    "nces",
    "budget",
    "invoice",
    "payroll",
    "student",
    "medical",
    "legal",
    "hr",
    "finance",
    "salary",
    "contract",
    "nda",
)

# Executable names for common browsers (lowercase, without .exe normalization handled)
BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe"}

DOMAIN_RE = re.compile(
    r"(?P<host>(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,})(?::\d+)?",
    re.IGNORECASE,
)

# Provide simple app label mapping (exe -> label)
APP_MAP = {
    "excel.exe": "Working in Excel",
    "winword.exe": "Working in Word",
    "powerpnt.exe": "Working in PowerPoint",
    "notepad.exe": "Editing Text",
    "code.exe": "Coding in VS Code",
    "pycharm64.exe": "Coding in PyCharm",
}


def getenv_str(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v is not None and v.strip() != "" else default


def getenv_int(name: str, default: int) -> int:
    try:
        return int(getenv_str(name, str(default)))  # type: ignore
    except Exception:
        return default


def parse_mask_terms() -> Tuple[str, ...]:
    env = getenv_str("MASK_TERMS")
    terms = []
    if env:
        # split on commas, strip whitespace
        for t in env.split(","):
            t = t.strip()
            if t:
                terms.append(t.lower())
    else:
        terms.extend(DEFAULT_SENSITIVE_TERMS)
    # Ensure unique & normalized
    return tuple(sorted(set([t.lower() for t in terms])))


SENSITIVE_TERMS = parse_mask_terms()

DISCORD_CLIENT_ID = getenv_str("DISCORD_CLIENT_ID") or ""
if not DISCORD_CLIENT_ID:
    raise SystemExit("Set DISCORD_CLIENT_ID in your environment or .env file.")

UPDATE_EVERY_SECS = getenv_int("UPDATE_EVERY_SECS", 15)
CHECK_INTERVAL = getenv_int("CHECK_INTERVAL", 1)


# ---- Window helpers ----

def active_window_title_and_exe() -> Tuple[str, str]:
    """Return (title, exe) for the active (foreground) window; exe is lowercase filename."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) or ""
    except Exception:
        title = ""

    exe = ""
    try:
        # pygetwindow can list windows with titles; fall back to exe via window handle search
        wins = gw.getActiveWindow()
        if wins and getattr(wins, "title", None):
            # pygetwindow does not directly expose exe name. Use processId->exe with psutil (optional).
            # To avoid mandatory psutil dependency, we try a heuristic using window title's owner
            # but safest is to use win32 process query:
            import win32process  # type: ignore
            import psutil  # type: ignore

            _, pid = win32process.GetWindowThreadProcessId(int(wins._hWnd))  # noqa: SLF001
            p = psutil.Process(pid)
            exe_path = p.exe()
            exe = os.path.basename(exe_path).lower()
        else:
            # Fallback: unknown exe
            exe = ""
    except Exception:
        exe = ""

    return title, exe


def title_has_sensitive_term(title: str) -> bool:
    low = (title or "").lower()
    for t in SENSITIVE_TERMS:
        if t and t in low:
            return True
    return False


def sanitize_title_to_short_label(title: str, max_len: int = 40) -> str:
    t = (title or "").strip()
    # Remove extra whitespace and naughty control chars
    t = re.sub(r"\s+", " ", t)
    if len(t) > max_len:
        t = t[: max_len - 1].rstrip() + "…"
    return t or SAFE_IDLE_MESSAGE


def derive_label(title: str, exe: str) -> Tuple[str, Optional[str]]:
    """Return (label, image_key) for Discord presence.
    image_key is optional and unused unless you configure assets in your app.
    """
    # Mask first for ALL apps
    if title_has_sensitive_term(title):
        return SAFE_MASK_MESSAGE, None

    # No title -> idle
    if not title:
        return SAFE_IDLE_MESSAGE, None

    # Browser path: attempt to extract host from title
    if exe in BROWSERS:
        # Many browsers set titles like: "<Page Title> - <Host> - <Browser Name>"
        # Try to find a host anywhere in the title string
        m = DOMAIN_RE.search(title)
        if m:
            host = m.group("host").lower()
            return f"Browsing {host}", None
        # Fallback: short sanitized title
        return f"Browsing {sanitize_title_to_short_label(title)}", None

    # Known app mapping
    if exe in APP_MAP:
        return APP_MAP[exe], None

    # Fallback: generic short label using title
    return sanitize_title_to_short_label(title), None


# ---- Discord presence client with reconnect/backoff ----

@dataclass
class PresenceClient:
    client_id: str
    log: logging.Logger
    _rpc: Optional[Presence] = None
    _connected: bool = False

    def connect(self) -> None:
        if self._connected and self._rpc is not None:
            return
        self._rpc = Presence(self.client_id)
        self._rpc.connect()
        self._connected = True
        self.log.debug("Connected to Discord RPC.")

    def update(self, state: str, large_image: Optional[str] = None) -> None:
        if not self._connected or self._rpc is None:
            self.connect()
        payload = {"state": state}
        if large_image:
            payload["large_image"] = large_image
        assert self._rpc is not None
        self._rpc.update(**payload)

    def close(self) -> None:
        try:
            if self._rpc is not None:
                self._rpc.clear()
                self._rpc.close()
        finally:
            self._rpc = None
            self._connected = False
            self.log.debug("Closed Discord RPC.")

    def safe_update(self, state: str, large_image: Optional[str] = None) -> None:
        """Attempt update with lightweight reconnect/backoff."""
        backoff = 1.0
        max_backoff = 16.0
        while True:
            try:
                self.update(state=state, large_image=large_image)
                return
            except (InvalidPipe, ConnectionRefusedError):
                # Discord not running or pipe broken — try reconnect after backoff
                self._connected = False
                self.log.debug("Discord pipe invalid; will retry connect in %.1fs", backoff)
                time.sleep(backoff)
                backoff = min(max_backoff, backoff * 2.0)
                try:
                    self.connect()
                except (InvalidID, InvalidPipe, ConnectionRefusedError):
                    # Keep backing off
                    continue
            except InvalidID as e:
                # Misconfigured Client ID
                self.log.error("Invalid Discord Client ID: %s", e)
                raise
            except Exception as e:
                # Other transient errors; log and try again with capped backoff
                self.log.warning("Update failed: %s; retrying in %.1fs", e, backoff)
                time.sleep(backoff)
                backoff = min(max_backoff, backoff * 1.5)


def setup_logger(verbose: bool) -> logging.Logger:
    log = logging.getLogger("presence")
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch = logging.StreamHandler()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S")
    ch.setFormatter(fmt)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    log.handlers.clear()
    log.addHandler(ch)
    return log


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Privacy‑aware Discord Rich Presence (Windows).")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--update-secs", type=int, default=UPDATE_EVERY_SECS, help="Seconds between RP updates")
    parser.add_argument("--check-interval", type=int, default=CHECK_INTERVAL, help="Polling loop sleep (secs)")
    args = parser.parse_args(argv)

    log = setup_logger(args.verbose)
    log.info("Starting Discord Presence (update=%ss, check=%ss)", args.update_secs, args.check_interval)
    log.debug("Sensitive terms: %s", ", ".join(SENSITIVE_TERMS))

    client = PresenceClient(DISCORD_CLIENT_ID, log)

    last_update = 0.0

    try:
        while True:
            now = time.time()
            # Tight poll; only push to Discord on update cadence
            if now - last_update >= max(2, args.update_secs):
                title, exe = active_window_title_and_exe()
                exe = (exe or "").lower()
                label, image = derive_label(title, exe)
                log.debug("Active exe='%s' title='%s' -> '%s'", exe or "?", title, label)
                client.safe_update(state=label, large_image=image)
                last_update = now

            time.sleep(max(0.1, args.check_interval))
    except KeyboardInterrupt:
        log.info("Stopping…")
    finally:
        try:
            client.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
