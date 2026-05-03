"""Terminal output formatting with ANSI colors."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from omon.models import (
    DecodedName,
    HardwareInfo,
    MemoryPressure,
    ModelDetails,
    ModelInfo,
    RunningModel,
    ServerStatus,
)

# Import types lazily to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from omon.bench import BenchmarkResult
    from omon.suggest import CleanupSuggestion, HardwareProfile, ModelSuggestion, ModelUpdate

# ANSI codes — disabled if not a TTY
_is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

BOLD = "\033[1m" if _is_tty else ""
DIM = "\033[2m" if _is_tty else ""
RESET = "\033[0m" if _is_tty else ""
GREEN = "\033[32m" if _is_tty else ""
YELLOW = "\033[33m" if _is_tty else ""
RED = "\033[31m" if _is_tty else ""
BLUE = "\033[34m" if _is_tty else ""
CYAN = "\033[36m" if _is_tty else ""
MAGENTA = "\033[35m" if _is_tty else ""
WHITE = "\033[37m" if _is_tty else ""


def _term_width() -> int:
    try:
        return os.get_terminal_size().columns
    except (ValueError, OSError):
        return 80


def format_size(n: int) -> str:
    """Format bytes as human-readable size."""
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1024
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
    return f"{n:.1f} TB"


def format_context(n: int) -> str:
    """Format context length: 262144 -> '262K', 1048576 -> '1M'."""
    if n <= 0:
        return "?"
    if n >= 1_048_576:
        return f"{n // 1_048_576}M"
    if n >= 1024:
        return f"{n // 1024}K"
    return str(n)


def format_age(iso_timestamp: str) -> str:
    """Format ISO timestamp as relative time: '2 weeks ago'."""
    if not iso_timestamp:
        return "unknown"
    try:
        # Handle nanosecond precision by truncating to microseconds
        ts = iso_timestamp
        # Remove nanosecond digits beyond 6 decimal places
        if "." in ts:
            dot_idx = ts.index(".")
            # Find where the fractional part ends (before timezone)
            end = dot_idx + 1
            while end < len(ts) and ts[end].isdigit():
                end += 1
            frac = ts[dot_idx + 1:end]
            ts = ts[:dot_idx + 1] + frac[:6] + ts[end:]

        # Handle timezone offset
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"

        dt = datetime.fromisoformat(ts)
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = now - dt
        seconds = int(delta.total_seconds())
    except (ValueError, TypeError):
        return "unknown"

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        m = seconds // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    if seconds < 604800:
        d = seconds // 86400
        return f"{d} day{'s' if d != 1 else ''} ago"
    if seconds < 2_592_000:
        w = seconds // 604800
        return f"{w} week{'s' if w != 1 else ''} ago"
    if seconds < 31_536_000:
        mo = seconds // 2_592_000
        return f"{mo} month{'s' if mo != 1 else ''} ago"
    y = seconds // 31_536_000
    return f"{y} year{'s' if y != 1 else ''} ago"


def _right_pad(left: str, right: str, width: int) -> str:
    """Put left on the left, right on the right, with space padding."""
    # Strip ANSI for length calculation
    import re
    clean_left = re.sub(r"\033\[[0-9;]*m", "", left)
    clean_right = re.sub(r"\033\[[0-9;]*m", "", right)
    padding = max(1, width - len(clean_left) - len(clean_right))
    return left + " " * padding + right


# ─── Status command ─────────────────────────────────────────

def format_status(
    server: ServerStatus,
    models: list[ModelInfo],
    running: list[RunningModel],
    hw: HardwareInfo,
    pressure: MemoryPressure,
) -> str:
    lines = []
    width = _term_width()

    lines.append(f"{BOLD}omon{RESET} {DIM}· Ollama Monitor{RESET}")
    lines.append("")

    # Server
    if server.running:
        ver = server.version or "?"
        lines.append(f"  {BOLD}Server{RESET}    {GREEN}running{RESET} · v{ver} · {server.host}")
    else:
        lines.append(f"  {BOLD}Server{RESET}    {RED}not running{RESET} · {server.host}")
        if server.error:
            lines.append(f"            {DIM}{server.error}{RESET}")
        return "\n".join(lines)

    # Models summary
    total_size = sum(m.size for m in models)
    lines.append(f"  {BOLD}Models{RESET}    {len(models)} installed · {format_size(total_size)} total")

    # Running models
    if running:
        total_mem = sum(r.size for r in running)
        pct = (total_mem / hw.total_memory * 100) if hw.total_memory else 0
        lines.append(
            f"  {BOLD}Loaded{RESET}    {len(running)} model{'s' if len(running) != 1 else ''}"
            f" · {format_size(total_mem)} RAM ({pct:.0f}% of {format_size(hw.total_memory)})"
        )
    else:
        lines.append(f"  {BOLD}Loaded{RESET}    {DIM}none{RESET}")

    # Memory pressure
    level_color = {"normal": GREEN, "warn": YELLOW, "critical": RED}.get(pressure.level, DIM)
    swap_str = format_size(pressure.swap_used) + " swap" if pressure.swap_used else "0 B swap"
    headroom = format_size(pressure.memory_free)
    lines.append(
        f"  {BOLD}Memory{RESET}    {level_color}{pressure.level}{RESET}"
        f" · {swap_str} · {headroom} available"
    )

    # Hardware
    lines.append(f"  {BOLD}System{RESET}    {hw.chip} · {format_size(hw.total_memory)} · {hw.cpu_cores} cores")

    # Active models detail
    if running:
        lines.append("")
        lines.append(f"  {BOLD}Active:{RESET}")
        for r in running:
            lines.append(f"    {r.name}  {DIM}{format_size(r.size)}  ctx:{r.context_length}{RESET}")

    return "\n".join(lines)


# ─── List command ───────────────────────────────────────────

def format_list(
    models: list[ModelInfo],
    decoded: dict[str, DecodedName],
    details: dict[str, ModelDetails],
    running: list[RunningModel],
) -> str:
    if not models:
        return f"{DIM}No models installed.{RESET}"

    lines = []
    width = _term_width()
    total_size = sum(m.size for m in models)
    running_names = {r.name for r in running}

    header = _right_pad(
        f"{BOLD}Models ({len(models)}){RESET}",
        f"{BOLD}Total: {format_size(total_size)}{RESET}",
        width,
    )
    lines.append(header)
    lines.append("")

    for m in models:
        d = decoded.get(m.name)
        det = details.get(m.name)

        # Name line with size
        status = f" {GREEN}[running]{RESET}" if m.name in running_names else ""
        name_line = _right_pad(
            f"  {BOLD}{m.name}{RESET}{status}",
            f"{format_size(m.size)}",
            width,
        )
        lines.append(name_line)

        if d:
            # Decoded info line 1: family, params, fine-tune
            parts: list[str] = [d.family_name]
            if d.parameter_count:
                p = d.parameter_count
                if d.active_params:
                    p += f" ({d.active_params} active)"
                parts.append(p)
            if d.fine_tunes:
                parts.append(" + ".join(d.fine_tunes))
            lines.append(f"  {DIM}│{RESET} {' · '.join(parts)}")

            # Decoded info line 2: quant, context, capabilities
            parts2: list[str] = []
            if d.quantization:
                parts2.append(f"{d.quantization} quant")
            ctx_val = det.context_length if det else 0
            if ctx_val:
                parts2.append(f"{format_context(ctx_val)} context")
            elif d.context_hint:
                parts2.append(f"{d.context_hint} context")
            if d.capabilities:
                parts2.append(", ".join(d.capabilities))
            if parts2:
                lines.append(f"  {DIM}│{RESET} {' · '.join(parts2)}")

            # License line
            if d.license_short:
                lines.append(f"  {DIM}│ {d.license_short}{RESET}")

            # Age + successor
            age = format_age(m.modified_at)
            age_parts = [age]
            if d.successor:
                age_parts.append(f"{YELLOW}successor available: {d.successor}{RESET}")
            lines.append(f"  {DIM}│ {' · '.join(age_parts)}{RESET}")
        else:
            lines.append(f"  {DIM}│ {m.family or '?'} · {m.parameter_size or '?'}{RESET}")
            lines.append(f"  {DIM}│ {format_age(m.modified_at)}{RESET}")

        lines.append("")

    return "\n".join(lines)


# ─── Show command ───────────────────────────────────────────

def format_show(
    det: ModelDetails,
    decoded: DecodedName,
    info: ModelInfo | None,
) -> str:
    lines = []

    lines.append(f"{BOLD}{det.name}{RESET}")
    if decoded.description:
        lines.append(f"{DIM}{decoded.description}{RESET}")
    lines.append("")

    def _row(label: str, value: str) -> str:
        return f"  {BOLD}{label:<16}{RESET}{value}"

    lines.append(_row("Family", decoded.family_name))
    if decoded.publisher:
        lines.append(_row("Publisher", decoded.publisher))
    if decoded.parameter_count:
        p = decoded.parameter_count
        if decoded.active_params:
            p += f" ({decoded.active_params} active per token)"
        if det.parameter_count:
            p += f"  {DIM}({det.parameter_count:,} params){RESET}"
        lines.append(_row("Parameters", p))
    if decoded.quantization:
        q = decoded.quantization
        if decoded.quantization_description:
            q += f"  {DIM}({decoded.quantization_description}){RESET}"
        lines.append(_row("Quantization", q))
    if det.context_length:
        lines.append(_row("Context", f"{det.context_length:,} tokens ({format_context(det.context_length)})"))
    if det.format:
        lines.append(_row("Format", det.format))
    if det.capabilities:
        lines.append(_row("Capabilities", ", ".join(det.capabilities)))
    if decoded.license_short:
        lines.append(_row("License", decoded.license_short))
    if decoded.fine_tunes:
        lines.append(_row("Fine-tune", " + ".join(decoded.fine_tunes)))
    if decoded.successor:
        lines.append(_row("Successor", f"{YELLOW}{decoded.successor}{RESET}"))
    if det.requires:
        lines.append(_row("Requires", f"Ollama >= {det.requires}"))

    # Parameters
    if det.parameters:
        lines.append("")
        lines.append(f"  {BOLD}Parameters{RESET}")
        for k, v in det.parameters.items():
            lines.append(f"    {k:<24}{v}")

    # Template (truncated)
    if det.template and det.template.strip():
        lines.append("")
        lines.append(f"  {BOLD}Template{RESET}")
        tmpl = det.template.strip()
        if len(tmpl) > 200:
            tmpl = tmpl[:200] + "..."
        for tline in tmpl.splitlines()[:5]:
            lines.append(f"    {DIM}{tline}{RESET}")
        total_lines = len(det.template.strip().splitlines())
        if total_lines > 5:
            lines.append(f"    {DIM}... ({total_lines} lines total){RESET}")

    # Size and metadata
    lines.append("")
    size = info.size if info else det.size
    if size:
        lines.append(_row("Size on disk", format_size(size)))
    lines.append(_row("Modified", format_age(det.modified_at)))
    if det.digest:
        lines.append(_row("Digest", det.digest))

    if decoded.unknown_parts:
        lines.append("")
        lines.append(f"  {DIM}Unrecognized tag parts: {', '.join(decoded.unknown_parts)}{RESET}")

    return "\n".join(lines)


# ─── Disk command ───────────────────────────────────────────

def format_disk(models: list[ModelInfo], disk_free: int) -> str:
    if not models:
        return f"{DIM}No models installed.{RESET}"

    lines = []
    width = _term_width()
    total = sum(m.size for m in models)
    sorted_models = sorted(models, key=lambda m: m.size, reverse=True)

    header = _right_pad(
        f"{BOLD}Disk Usage{RESET}",
        f"{BOLD}Total: {format_size(total)}{RESET}",
        width,
    )
    lines.append(header)
    lines.append("")

    bar_width = 24
    max_name_len = max(len(m.name) for m in sorted_models)

    for m in sorted_models:
        pct = m.size / total if total else 0
        filled = int(pct * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        size_str = format_size(m.size)
        pct_str = f"({pct * 100:.1f}%)"
        lines.append(f"  {m.name:<{max_name_len}}  {CYAN}{bar}{RESET}  {size_str:>8}  {DIM}{pct_str}{RESET}")

    lines.append("")
    lines.append(f"  {DIM}Available disk space: {format_size(disk_free)}{RESET}")

    return "\n".join(lines)


# ─── Pressure command ──────────────────────────────────────

def format_pressure(
    pressure: MemoryPressure,
    running: list[RunningModel],
    hw: HardwareInfo,
) -> str:
    lines = []

    level_color = {"normal": GREEN, "warn": YELLOW, "critical": RED}.get(pressure.level, DIM)

    lines.append(f"{BOLD}Memory Pressure{RESET}")
    lines.append("")

    def _row(label: str, value: str) -> str:
        return f"  {BOLD}{label:<16}{RESET}{value}"

    lines.append(_row("Status", f"{level_color}{pressure.level}{RESET}"))
    lines.append(_row("Physical RAM", format_size(pressure.memory_total)))
    lines.append(_row("Used", format_size(pressure.memory_used)))
    lines.append(_row("Free", format_size(pressure.memory_free)))

    swap_str = f"{format_size(pressure.swap_used)} used"
    if pressure.swap_total:
        swap_str += f" / {format_size(pressure.swap_total)} total"
    else:
        swap_str += " / no swap"
    lines.append(_row("Swap", swap_str))

    # Model headroom estimate
    model_mem = sum(r.size for r in running)
    headroom = pressure.memory_free
    lines.append("")
    lines.append(_row("Model Headroom", f"~{format_size(headroom)} available for models"))

    if running:
        lines.append("")
        lines.append(f"  {BOLD}Loaded Models{RESET}")
        for r in running:
            lines.append(f"    {r.name:<40} {format_size(r.size)}")
        lines.append(f"    {DIM}{'Total':<40} {format_size(model_mem)}{RESET}")

    # Rough guidance
    if headroom > 0:
        lines.append("")
        q4_fit = int(headroom * 0.75 / (1024**3))  # rough: Q4 model ~= GB of RAM
        fp16_fit = q4_fit // 2
        if q4_fit > 0:
            lines.append(f"  {DIM}Could fit: ~{q4_fit}B Q4 model or ~{fp16_fit}B FP16 model{RESET}")

    return "\n".join(lines)


# ─── Bench command ─────────────────────────────────────────

def _fmt_ms(ms: float) -> str:
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms:.0f}ms"


def _fmt_tok_s(tok_s: float) -> str:
    if tok_s >= 100:
        return f"{tok_s:.0f} tok/s"
    return f"{tok_s:.1f} tok/s"


def _rate_performance(gen_tok_s: float) -> tuple[str, str]:
    """Return (label, color) rating for generation speed."""
    if gen_tok_s >= 60:
        return "Excellent", GREEN
    if gen_tok_s >= 30:
        return "Good", GREEN
    if gen_tok_s >= 15:
        return "Moderate", YELLOW
    if gen_tok_s >= 5:
        return "Slow", YELLOW
    return "Very slow", RED


def format_bench(result: BenchmarkResult) -> str:
    from omon.bench import BenchmarkResult as _  # noqa: runtime import check

    lines = []

    lines.append(f"{BOLD}Benchmark: {result.model}{RESET}")
    lines.append("")

    def _row(label: str, value: str) -> str:
        return f"  {BOLD}{label:<16}{RESET}{value}"

    lines.append(_row("Cold Load", _fmt_ms(result.cold_load_ms)))
    lines.append(_row("Warm Load", _fmt_ms(result.warm_load_ms)))
    if result.memory_bytes:
        lines.append(_row("Memory", format_size(result.memory_bytes)))

    for p in result.prompts:
        lines.append("")
        lines.append(f"  {BOLD}{p.label} Prompt{RESET} {DIM}({p.prompt_tokens} in → {p.gen_tokens} out){RESET}")
        lines.append(f"    Prompt Speed   {_fmt_tok_s(p.prompt_tok_s)}")
        lines.append(f"    Gen Speed      {_fmt_tok_s(p.gen_tok_s)}")
        lines.append(f"    TTFT           {_fmt_ms(p.ttft_ms)}")

    # Overall rating
    avg = result.avg_gen_tok_s
    if avg > 0:
        label, color = _rate_performance(avg)
        lines.append("")
        lines.append(f"  {BOLD}Rating{RESET}          {color}{label}{RESET} — avg {_fmt_tok_s(avg)} generation")

    return "\n".join(lines)


def format_bench_compare(results: list[BenchmarkResult]) -> str:
    from omon.bench import BenchmarkResult as _  # noqa

    if len(results) < 2:
        return format_bench(results[0]) if results else ""

    lines = []
    width = _term_width()

    lines.append(f"{BOLD}Benchmark Comparison{RESET}")
    lines.append("")

    # Column layout
    col_w = 22
    label_w = 18
    names = [r.model for r in results]

    # Header
    header = " " * label_w
    for name in names:
        display = name if len(name) <= col_w else name[:col_w - 1] + "…"
        header += f"{BOLD}{display:<{col_w}}{RESET}"
    lines.append(header)
    sep = " " * label_w + ("─" * col_w) * len(results)
    lines.append(sep)

    def _cmp_row(label: str, values: list[str]) -> str:
        row = f"  {label:<{label_w - 2}}"
        for v in values:
            row += f"{v:<{col_w}}"
        return row

    # Cold load
    lines.append(_cmp_row("Cold Load", [_fmt_ms(r.cold_load_ms) for r in results]))
    lines.append(_cmp_row("Warm Load", [_fmt_ms(r.warm_load_ms) for r in results]))
    lines.append(_cmp_row("Memory", [format_size(r.memory_bytes) if r.memory_bytes else "?" for r in results]))

    # Find matching prompt labels
    all_labels = []
    for r in results:
        for p in r.prompts:
            if p.label not in all_labels:
                all_labels.append(p.label)

    for label in all_labels:
        lines.append("")
        lines.append(f"  {BOLD}{label}{RESET}")

        prompt_results = []
        for r in results:
            pr = next((p for p in r.prompts if p.label == label), None)
            prompt_results.append(pr)

        lines.append(_cmp_row(
            "  Gen Speed",
            [_fmt_tok_s(p.gen_tok_s) if p else "—" for p in prompt_results],
        ))
        lines.append(_cmp_row(
            "  Prompt Speed",
            [_fmt_tok_s(p.prompt_tok_s) if p else "—" for p in prompt_results],
        ))
        lines.append(_cmp_row(
            "  TTFT",
            [_fmt_ms(p.ttft_ms) if p else "—" for p in prompt_results],
        ))

    # Ratings
    lines.append("")
    ratings = []
    for r in results:
        avg = r.avg_gen_tok_s
        if avg > 0:
            label, color = _rate_performance(avg)
            ratings.append(f"{color}{label}{RESET}")
        else:
            ratings.append("?")
    lines.append(_cmp_row("Rating", ratings))

    return "\n".join(lines)


# ─── Hardware profile ──────────────────────────────────────

def format_hw(profile: HardwareProfile) -> str:
    from omon.suggest import HardwareProfile as _  # noqa

    lines = []
    hw = profile.hw

    lines.append(f"{BOLD}Hardware Profile{RESET}")
    lines.append("")

    def _row(label: str, value: str) -> str:
        return f"  {BOLD}{label:<16}{RESET}{value}"

    lines.append(_row("Chip", hw.chip))
    lines.append(_row("CPU Cores", str(hw.cpu_cores)))
    lines.append(_row("Memory", format_size(hw.total_memory)))
    lines.append(_row("OS", hw.os))

    lines.append("")
    lines.append(f"  {BOLD}Model Sizing Guide{RESET}")
    lines.append(f"    Comfortable     up to ~{profile.comfortable_gb:.0f} GB models (75% of RAM)")
    lines.append(f"    Maximum         up to ~{profile.maximum_gb:.0f} GB models (90% of RAM, may cause pressure)")

    lines.append("")
    lines.append(f"    {DIM}Estimated max parameters (comfortable fit):{RESET}")
    for quant, params in profile.param_estimates.items():
        lines.append(f"      {quant:<8} ~{params}B parameters")

    if profile.loaded_gb > 0:
        lines.append("")
        lines.append(_row("Loaded now", f"{profile.loaded_gb:.1f} GB"))

    return "\n".join(lines)


# ─── Suggest command ───────────────────────────────────────

def format_suggest(
    task: str,
    suggestions: list[ModelSuggestion],
    hw: HardwareInfo,
) -> str:
    from omon.suggest import ModelSuggestion as _  # noqa

    lines = []
    comfortable_gb = hw.total_memory * 0.75 / (1024**3)

    lines.append(f"{BOLD}Model suggestions for {task}{RESET}")
    lines.append(f"{DIM}{hw.chip} · {format_size(hw.total_memory)} · comfortable fit: ~{comfortable_gb:.0f} GB{RESET}")
    lines.append("")

    installed = [s for s in suggestions if s.installed]
    available = [s for s in suggestions if not s.installed]

    if installed:
        lines.append(f"  {BOLD}Already installed:{RESET}")
        for s in installed:
            speed = f"  {GREEN}{s.bench_tok_s:.0f} tok/s{RESET}" if s.bench_tok_s else ""
            lines.append(f"    {GREEN}{s.installed_name}{RESET}{speed}")
            lines.append(f"    {DIM}{s.description}{RESET}")
            lines.append("")

    if available:
        lines.append(f"  {BOLD}Consider:{RESET}")
        for s in available:
            # Show fitting size variants
            fitting = [e for e in s.size_estimates if e["fits"]]
            sizes_str = ""
            if fitting:
                examples = fitting[-3:]  # show up to 3 largest fitting
                sizes_str = " · ".join(f"{e['params']}≈{e['q4_gb']}GB" for e in examples)

            lines.append(f"    {CYAN}{s.family}{RESET}")
            lines.append(f"    {s.description}")

            detail_parts = [s.publisher]
            if s.license:
                detail_parts.append(s.license)
            if sizes_str:
                detail_parts.append(f"Q4 sizes: {sizes_str}")
            lines.append(f"    {DIM}{' · '.join(detail_parts)}{RESET}")

            if s.successor_of:
                lines.append(f"    {YELLOW}Replaces your installed {s.successor_of}{RESET}")

            if s.notes:
                lines.append(f"    {DIM}{s.notes}{RESET}")

            lines.append(f"    Install: {DIM}ollama pull {s.family}{RESET}")
            lines.append("")

    if not installed and not available:
        lines.append(f"  {DIM}No models found for task '{task}'{RESET}")
        lines.append(f"  {DIM}Available tasks: general, coding, math, vision, chat, embedding, thinking, tools{RESET}")

    return "\n".join(lines)


# ─── Updates command ───────────────────────────────────────

def format_updates(updates: list[ModelUpdate]) -> str:
    from omon.suggest import ModelUpdate as _  # noqa

    lines = []
    lines.append(f"{BOLD}Model Updates{RESET}")
    lines.append("")

    if not updates:
        lines.append(f"  {GREEN}All models are up to date.{RESET}")
        return "\n".join(lines)

    for u in updates:
        lines.append(f"  {BOLD}{u.model}{RESET}")
        lines.append(f"    Successor: {CYAN}{u.successor}{RESET}")
        lines.append(f"    {u.successor_description}")
        if u.successor_license:
            lines.append(f"    {DIM}License: {u.successor_license}{RESET}")
        lines.append(f"    Install: {DIM}ollama pull {u.successor}{RESET}")
        lines.append("")

    return "\n".join(lines)


# ─── Cleanup command ───────────────────────────────────────

def format_cleanup(suggestions: list[CleanupSuggestion]) -> str:
    from omon.suggest import CleanupSuggestion as _  # noqa

    lines = []
    total_savings = sum(s.size for s in suggestions)

    header = f"{BOLD}Cleanup Suggestions{RESET}"
    if total_savings > 0:
        header += f"  {DIM}· potential savings: {format_size(total_savings)}{RESET}"
    lines.append(header)
    lines.append("")

    if not suggestions:
        lines.append(f"  {GREEN}Nothing to clean up.{RESET}")
        return "\n".join(lines)

    for s in suggestions:
        lines.append(f"  {BOLD}{s.model}{RESET}  {DIM}{format_size(s.size)}{RESET}")
        for reason in s.reasons:
            lines.append(f"    {YELLOW}· {reason}{RESET}")
        if s.successor:
            lines.append(f"    Replace: {DIM}ollama pull {s.successor} && ollama rm {s.model}{RESET}")
        else:
            lines.append(f"    Remove:  {DIM}ollama rm {s.model}{RESET}")
        lines.append("")

    return "\n".join(lines)
