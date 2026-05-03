"""SQLite storage for benchmark results and model usage tracking."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_DB_DIR = Path(os.environ.get("OMON_DATA_DIR", os.path.expanduser("~/.local/share/omon")))
_DB_PATH = _DB_DIR / "metrics.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    prompt_label TEXT NOT NULL,
    prompt_tokens INTEGER,
    gen_tokens INTEGER,
    cold_load_ms REAL,
    warm_load_ms REAL,
    prompt_tok_s REAL,
    gen_tok_s REAL,
    ttft_cold_ms REAL,
    ttft_warm_ms REAL,
    memory_bytes INTEGER
);

CREATE TABLE IF NOT EXISTS model_usage (
    model TEXT PRIMARY KEY,
    last_seen TEXT NOT NULL
);
"""


@dataclass
class BenchmarkRecord:
    model: str
    timestamp: str
    prompt_label: str
    prompt_tokens: int
    gen_tokens: int
    cold_load_ms: float
    warm_load_ms: float
    prompt_tok_s: float
    gen_tok_s: float
    ttft_cold_ms: float
    ttft_warm_ms: float
    memory_bytes: int


def _connect() -> sqlite3.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.executescript(_SCHEMA)
    return conn


def save_benchmark(record: BenchmarkRecord) -> None:
    conn = _connect()
    try:
        conn.execute(
            """INSERT INTO benchmarks
               (model, timestamp, prompt_label, prompt_tokens, gen_tokens,
                cold_load_ms, warm_load_ms, prompt_tok_s, gen_tok_s,
                ttft_cold_ms, ttft_warm_ms, memory_bytes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.model, record.timestamp, record.prompt_label,
                record.prompt_tokens, record.gen_tokens,
                record.cold_load_ms, record.warm_load_ms,
                record.prompt_tok_s, record.gen_tok_s,
                record.ttft_cold_ms, record.ttft_warm_ms,
                record.memory_bytes,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_benchmarks(model: str | None = None, limit: int = 20) -> list[BenchmarkRecord]:
    conn = _connect()
    try:
        if model:
            rows = conn.execute(
                "SELECT model, timestamp, prompt_label, prompt_tokens, gen_tokens, "
                "cold_load_ms, warm_load_ms, prompt_tok_s, gen_tok_s, "
                "ttft_cold_ms, ttft_warm_ms, memory_bytes "
                "FROM benchmarks WHERE model = ? ORDER BY timestamp DESC LIMIT ?",
                (model, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT model, timestamp, prompt_label, prompt_tokens, gen_tokens, "
                "cold_load_ms, warm_load_ms, prompt_tok_s, gen_tok_s, "
                "ttft_cold_ms, ttft_warm_ms, memory_bytes "
                "FROM benchmarks ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [BenchmarkRecord(*r) for r in rows]
    finally:
        conn.close()


def record_model_seen(model: str) -> None:
    """Record that a model was seen loaded (for staleness tracking)."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO model_usage (model, last_seen) VALUES (?, ?) "
            "ON CONFLICT(model) DO UPDATE SET last_seen = ?",
            (model, now, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_last_seen(model: str) -> str | None:
    """Get the last time a model was seen loaded."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT last_seen FROM model_usage WHERE model = ?", (model,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_all_last_seen() -> dict[str, str]:
    """Get last-seen timestamps for all tracked models."""
    conn = _connect()
    try:
        rows = conn.execute("SELECT model, last_seen FROM model_usage").fetchall()
        return dict(rows)
    finally:
        conn.close()
