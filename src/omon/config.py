"""Configuration file support. Reads ~/.config/omon/config.toml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_CONFIG_DIR = Path(os.environ.get("OMON_CONFIG_DIR", os.path.expanduser("~/.config/omon")))
_CONFIG_FILE = _CONFIG_DIR / "config.toml"


@dataclass
class Config:
    host: str = "localhost:11434"
    json: bool = False
    no_pager: bool = False
    # watch
    watch_interval: int = 2
    # serve
    serve_port: int = 11435
    serve_bind: str = "127.0.0.1"
    # cleanup
    stale_days: int = 30


def _parse_toml(text: str) -> dict:
    """Parse TOML using tomllib (3.11+) or a minimal fallback."""
    try:
        import tomllib
        return tomllib.loads(text)
    except ImportError:
        pass

    # Minimal fallback: handles flat key = value and [section] headers.
    # Supports strings, ints, bools. No nested tables or arrays.
    result: dict = {}
    section: dict = result
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            result[name] = {}
            section = result[name]
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        # Parse value type
        if val.lower() == "true":
            section[key] = True
        elif val.lower() == "false":
            section[key] = False
        elif val.startswith('"') and val.endswith('"'):
            section[key] = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            section[key] = val[1:-1]
        else:
            try:
                section[key] = int(val)
            except ValueError:
                try:
                    section[key] = float(val)
                except ValueError:
                    section[key] = val
    return result


def load_config() -> Config:
    """Load config from file, returning defaults if file doesn't exist."""
    cfg = Config()

    if not _CONFIG_FILE.is_file():
        return cfg

    try:
        text = _CONFIG_FILE.read_text(encoding="utf-8")
        data = _parse_toml(text)
    except (OSError, ValueError):
        return cfg

    general = data.get("general", data)  # support flat or [general] section
    if "host" in general:
        cfg.host = str(general["host"])
    if "json" in general:
        cfg.json = bool(general["json"])
    if "no_pager" in general:
        cfg.no_pager = bool(general["no_pager"])

    watch = data.get("watch", {})
    if "interval" in watch:
        cfg.watch_interval = int(watch["interval"])

    serve = data.get("serve", {})
    if "port" in serve:
        cfg.serve_port = int(serve["port"])
    if "bind" in serve:
        cfg.serve_bind = str(serve["bind"])

    cleanup = data.get("cleanup", {})
    if "stale_days" in cleanup:
        cfg.stale_days = int(cleanup["stale_days"])

    return cfg


def generate_default_config() -> str:
    """Generate a default config file as a string."""
    return """\
# omon configuration
# Place this file at ~/.config/omon/config.toml

[general]
# host = "localhost:11434"
# json = false
# no_pager = false

[watch]
# interval = 2

[serve]
# port = 11435
# bind = "127.0.0.1"

[cleanup]
# stale_days = 30
"""
