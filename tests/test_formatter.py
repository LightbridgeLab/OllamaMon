"""Tests for formatter utility functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from unittest.mock import patch

from omon.formatter import (
    _fmt_ms,
    _fmt_tok_s,
    _rate_performance,
    format_age,
    format_context,
    format_size,
)


# ─── format_size ─────────────────────────────────────────


class TestFormatSize:
    def test_bytes(self):
        assert format_size(512) == "512 B"

    def test_zero(self):
        assert format_size(0) == "0 B"

    def test_kilobytes(self):
        assert format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_size(5 * 1024**2) == "5.0 MB"

    def test_gigabytes(self):
        assert format_size(21 * 1024**3) == "21.0 GB"

    def test_terabytes(self):
        assert format_size(2 * 1024**4) == "2.0 TB"

    def test_fractional_gb(self):
        result = format_size(int(3.8 * 1024**3))
        assert result == "3.8 GB"


# ─── format_context ──────────────────────────────────────


class TestFormatContext:
    def test_zero(self):
        assert format_context(0) == "?"

    def test_negative(self):
        assert format_context(-1) == "?"

    def test_small(self):
        assert format_context(512) == "512"

    def test_4k(self):
        assert format_context(4096) == "4K"

    def test_128k(self):
        assert format_context(131072) == "128K"

    def test_262k(self):
        assert format_context(262144) == "256K"

    def test_1m(self):
        assert format_context(1_048_576) == "1M"


# ─── format_age ──────────────────────────────────────────


class TestFormatAge:
    def _ts(self, **kwargs) -> str:
        """Create an ISO timestamp offset from 'now'."""
        dt = datetime.now(timezone.utc) - timedelta(**kwargs)
        return dt.isoformat()

    def test_just_now(self):
        assert format_age(self._ts(seconds=10)) == "just now"

    def test_minutes(self):
        assert format_age(self._ts(minutes=5)) == "5 minutes ago"

    def test_one_minute(self):
        assert format_age(self._ts(seconds=90)) == "1 minute ago"

    def test_hours(self):
        assert format_age(self._ts(hours=3)) == "3 hours ago"

    def test_one_hour(self):
        assert format_age(self._ts(hours=1, minutes=10)) == "1 hour ago"

    def test_days(self):
        assert format_age(self._ts(days=4)) == "4 days ago"

    def test_weeks(self):
        assert format_age(self._ts(weeks=2)) == "2 weeks ago"

    def test_months(self):
        assert format_age(self._ts(days=60)) == "2 months ago"

    def test_years(self):
        assert format_age(self._ts(days=400)) == "1 year ago"

    def test_empty_string(self):
        assert format_age("") == "unknown"

    def test_garbage(self):
        assert format_age("not-a-date") == "unknown"

    def test_z_suffix(self):
        # Ollama uses "Z" instead of "+00:00"
        ts = datetime.now(timezone.utc) - timedelta(hours=2)
        z_ts = ts.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        assert format_age(z_ts) == "2 hours ago"

    def test_nanosecond_precision(self):
        # Ollama sometimes returns nanosecond timestamps
        base = "2024-06-01T12:00:00"
        micro = base + ".123456+00:00"
        nano = base + ".123456789+00:00"
        assert format_age(nano) == format_age(micro)


# ─── _fmt_ms ─────────────────────────────────────────────


class TestFmtMs:
    def test_milliseconds(self):
        assert _fmt_ms(450) == "450ms"

    def test_seconds(self):
        assert _fmt_ms(2500) == "2.5s"

    def test_boundary(self):
        assert _fmt_ms(1000) == "1.0s"

    def test_small(self):
        assert _fmt_ms(3) == "3ms"


# ─── _fmt_tok_s ──────────────────────────────────────────


class TestFmtTokS:
    def test_low(self):
        assert _fmt_tok_s(37.6) == "37.6 tok/s"

    def test_high(self):
        assert _fmt_tok_s(150) == "150 tok/s"

    def test_boundary(self):
        assert _fmt_tok_s(100) == "100 tok/s"


# ─── _rate_performance ───────────────────────────────────


class TestRatePerformance:
    def test_excellent(self):
        label, _ = _rate_performance(80)
        assert label == "Excellent"

    def test_good(self):
        label, _ = _rate_performance(45)
        assert label == "Good"

    def test_moderate(self):
        label, _ = _rate_performance(20)
        assert label == "Moderate"

    def test_slow(self):
        label, _ = _rate_performance(8)
        assert label == "Slow"

    def test_very_slow(self):
        label, _ = _rate_performance(2)
        assert label == "Very slow"
