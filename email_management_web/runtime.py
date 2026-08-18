#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime helpers for local execution and packaged builds."""

from __future__ import annotations

import os
import secrets
import sys
import traceback
from pathlib import Path


# Keep the product name independent from the Outlook provider.  The legacy
# home-variable name remains supported so existing packaged installations can
# keep using their current data directory.
APP_NAME = "Email Management"
SECRET_KEY_FILE = "secret_key.txt"
DATABASE_FILE = "outlook_accounts.db"
STARTUP_LOG_FILE = "startup-error.log"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


def load_local_environment() -> None:
    """Load a small dependency-free .env file without overriding the shell."""
    if (os.getenv("EMAIL_MANAGEMENT_SKIP_DOTENV") or "").strip().lower() in {"1", "true", "yes"}:
        return
    configured_path = (os.getenv("EMAIL_MANAGEMENT_ENV_FILE") or "").strip()
    env_path = Path(configured_path).expanduser() if configured_path else bundle_root() / ".env"
    if not env_path.is_file():
        return

    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


load_local_environment()


def runtime_root() -> Path:
    override = os.getenv("EMAIL_MANAGEMENT_HOME") or os.getenv("OUTLOOK_EMAIL_HOME")
    if override:
        root = Path(override).expanduser()
    elif is_frozen():
        if os.name == "nt":
            root = Path(os.getenv("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / APP_NAME
        elif sys.platform == "darwin":
            root = Path.home() / "Library" / "Application Support" / APP_NAME
        else:
            xdg_home = os.getenv("XDG_DATA_HOME")
            root = Path(xdg_home).expanduser() / APP_NAME if xdg_home else Path.home() / ".local" / "share" / APP_NAME
    else:
        root = bundle_root()

    root.mkdir(parents=True, exist_ok=True)
    return root


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def default_database_path() -> Path:
    if is_frozen():
        return runtime_root() / "data" / DATABASE_FILE
    return bundle_root() / "data" / DATABASE_FILE


def startup_log_path() -> Path:
    return runtime_root() / STARTUP_LOG_FILE


def resolve_secret_key() -> str | None:
    secret_key = (os.getenv("SECRET_KEY") or "").strip()
    if secret_key:
        return secret_key

    if not is_frozen():
        return None

    secret_key_path = runtime_root() / SECRET_KEY_FILE
    if secret_key_path.exists():
        stored = secret_key_path.read_text(encoding="utf-8").strip()
        if stored:
            return stored

    generated = secrets.token_hex(32)
    secret_key_path.write_text(generated, encoding="utf-8")
    return generated


def record_startup_error(exc: BaseException) -> Path:
    log_path = startup_log_path()
    error_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_path.write_text(error_text, encoding="utf-8")
    return log_path


def notify_startup_error(log_path: Path) -> None:
    message = (
        "Email Management 启动失败。\n\n"
        f"错误日志已写入:\n{log_path}\n\n"
        "请把这个日志发给开发者。"
    )

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, "Email Management", 0x10)
            return
        except Exception:
            pass

    print(message, file=sys.stderr)
