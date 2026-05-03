"""Curses-based live monitoring TUI."""

from __future__ import annotations

import curses
import time

from omon.api import DEFAULT_HOST, OllamaError, list_running
from omon.formatter import format_age, format_context, format_size
from omon.hardware import get_hardware_info
from omon.models import HardwareInfo, MemoryPressure, RunningModel
from omon.pressure import get_memory_pressure
from omon.store import record_model_seen

POLL_INTERVAL = 2  # seconds


def _draw_bar(width: int, fraction: float) -> str:
    filled = int(fraction * width)
    return "█" * filled + "░" * (width - filled)


def _draw_header(stdscr: curses.window, hw: HardwareInfo, max_x: int) -> int:
    """Draw header. Returns the next available row."""
    row = 0
    title = "omon watch"
    hw_str = f"{hw.chip} · {format_size(hw.total_memory)} · {hw.cpu_cores} cores"

    stdscr.attron(curses.A_BOLD)
    stdscr.addnstr(row, 2, title, max_x - 4)
    stdscr.attroff(curses.A_BOLD)

    # Right-align hardware info
    if len(hw_str) < max_x - len(title) - 6:
        stdscr.addnstr(row, max_x - len(hw_str) - 2, hw_str, max_x)

    return row + 2


def _draw_memory(
    stdscr: curses.window,
    row: int,
    pressure: MemoryPressure,
    running: list[RunningModel],
    hw: HardwareInfo,
    max_x: int,
    colors: dict[str, int],
) -> int:
    """Draw memory status. Returns next available row."""
    bar_width = min(30, max_x - 40)
    if bar_width < 10:
        bar_width = 10

    # System memory bar
    if pressure.memory_total > 0:
        sys_frac = pressure.memory_used / pressure.memory_total
        sys_pct = sys_frac * 100
        level_color = colors.get(pressure.level, 0)

        label = f"  System Memory "
        bar = _draw_bar(bar_width, sys_frac)
        info = f" {sys_pct:.0f}% ({format_size(pressure.memory_used)} / {format_size(pressure.memory_total)})"

        stdscr.addnstr(row, 0, label, max_x - 1)
        stdscr.attron(curses.color_pair(level_color))
        stdscr.addnstr(row, len(label), bar, max_x - len(label) - 1)
        stdscr.attroff(curses.color_pair(level_color))
        stdscr.addnstr(row, len(label) + bar_width, info, max_x - len(label) - bar_width - 1)
        row += 1

    # Model memory bar
    model_mem = sum(r.size for r in running)
    if hw.total_memory > 0:
        model_frac = model_mem / hw.total_memory
        model_pct = model_frac * 100

        label = f"  Model Memory  "
        bar = _draw_bar(bar_width, model_frac)
        info = f" {model_pct:.1f}% ({format_size(model_mem)} / {format_size(hw.total_memory)})"

        stdscr.addnstr(row, 0, label, max_x - 1)
        stdscr.attron(curses.color_pair(3))  # cyan
        stdscr.addnstr(row, len(label), bar, max_x - len(label) - 1)
        stdscr.attroff(curses.color_pair(3))
        stdscr.addnstr(row, len(label) + bar_width, info, max_x - len(label) - bar_width - 1)
        row += 1

    # Swap warning
    if pressure.swap_used > 0:
        swap_msg = f"  ⚠ Swap in use: {format_size(pressure.swap_used)}"
        stdscr.attron(curses.color_pair(2))  # yellow
        stdscr.addnstr(row, 0, swap_msg, max_x - 1)
        stdscr.attroff(curses.color_pair(2))
        row += 1

    return row + 1


def _draw_models(
    stdscr: curses.window,
    row: int,
    running: list[RunningModel],
    hw: HardwareInfo,
    max_x: int,
    colors: dict[str, int],
) -> int:
    """Draw running model list. Returns next available row."""
    stdscr.attron(curses.A_BOLD)
    stdscr.addnstr(row, 2, "Active Models", max_x - 4)
    stdscr.attroff(curses.A_BOLD)
    row += 1

    separator = "─" * min(max_x - 4, 70)
    stdscr.addnstr(row, 2, separator, max_x - 4)
    row += 1

    if not running:
        stdscr.attron(curses.A_DIM)
        stdscr.addnstr(row, 2, "No models loaded · Waiting for activity...", max_x - 4)
        stdscr.attroff(curses.A_DIM)
        return row + 2

    bar_width = 12

    for r in running:
        if row >= curses.LINES - 3:
            stdscr.addnstr(row, 2, f"... and {len(running) - running.index(r)} more", max_x - 4)
            break

        # Model name + memory
        mem_frac = r.size / hw.total_memory if hw.total_memory else 0
        mem_pct = mem_frac * 100
        bar = _draw_bar(bar_width, mem_frac)

        name_part = f"  {r.name}"
        mem_part = f"{format_size(r.size)} / {format_size(hw.total_memory)}"

        stdscr.attron(curses.A_BOLD)
        stdscr.addnstr(row, 0, name_part, max_x - 1)
        stdscr.attroff(curses.A_BOLD)

        detail_col = max(len(name_part) + 2, 30)
        remaining = max_x - detail_col - 1
        if remaining > 0:
            detail = f"{mem_part}    {bar}  {mem_pct:.1f}%"
            stdscr.addnstr(row, detail_col, detail, remaining)
        row += 1

        # Second line: context, age
        if row < curses.LINES - 3:
            ctx = format_context(r.context_length) if r.context_length else "?"
            expire_str = format_age(r.expires_at).replace(" ago", "") if r.expires_at else "?"
            info_line = f"  ctx: {ctx} · expires in {expire_str}"

            stdscr.attron(curses.A_DIM)
            stdscr.addnstr(row, detail_col, info_line, max_x - detail_col - 1)
            stdscr.attroff(curses.A_DIM)
            row += 1

        row += 1  # blank line between models

    return row


def _draw_footer(stdscr: curses.window, max_y: int, max_x: int) -> None:
    footer = "  q quit · r refresh · Press any key to force refresh"
    stdscr.attron(curses.A_DIM)
    stdscr.addnstr(max_y - 1, 0, footer, max_x - 1)
    stdscr.attroff(curses.A_DIM)


def _main_loop(stdscr: curses.window, host: str) -> None:
    curses.curs_set(0)  # hide cursor
    stdscr.timeout(POLL_INTERVAL * 1000)  # non-blocking getch with timeout

    # Set up colors
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)   # normal
    curses.init_pair(2, curses.COLOR_YELLOW, -1)   # warn
    curses.init_pair(3, curses.COLOR_CYAN, -1)     # info
    curses.init_pair(4, curses.COLOR_RED, -1)      # critical

    colors = {"normal": 1, "warn": 2, "critical": 4}

    hw = get_hardware_info()

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()

        if max_y < 5 or max_x < 40:
            stdscr.addnstr(0, 0, "Terminal too small", max_x - 1)
            stdscr.refresh()
            key = stdscr.getch()
            if key == ord("q"):
                break
            continue

        # Fetch data
        try:
            running = list_running(host)
        except OllamaError:
            running = []
        pressure = get_memory_pressure()

        # Track model usage
        for r in running:
            record_model_seen(r.name)

        # Draw
        row = _draw_header(stdscr, hw, max_x)
        row = _draw_memory(stdscr, row, pressure, running, hw, max_x, colors)
        row = _draw_models(stdscr, row, running, hw, max_x, colors)
        _draw_footer(stdscr, max_y, max_x)

        stdscr.refresh()

        # Wait for input or timeout
        key = stdscr.getch()
        if key == ord("q"):
            break


def run_watch(host: str = DEFAULT_HOST) -> None:
    """Launch the curses TUI."""
    curses.wrapper(lambda stdscr: _main_loop(stdscr, host))
