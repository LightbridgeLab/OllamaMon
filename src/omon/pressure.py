"""Memory pressure monitoring."""

from __future__ import annotations

import platform
import re
import subprocess

from omon.models import MemoryPressure


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _parse_macos() -> MemoryPressure:
    # Get total memory
    mem_total = int(_run(["sysctl", "-n", "hw.memsize"]) or "0")

    # Parse vm_stat for page-level memory info
    vm_out = _run(["vm_stat"])
    pages: dict[str, int] = {}
    page_size = 16384  # default for Apple Silicon
    for line in vm_out.splitlines():
        m = re.match(r"Mach Virtual Memory Statistics: \(page size of (\d+) bytes\)", line)
        if m:
            page_size = int(m.group(1))
            continue
        m = re.match(r'^(.+?):\s+([\d.]+)\.$', line)
        if m:
            pages[m.group(1).strip()] = int(m.group(2))

    free_pages = pages.get("Pages free", 0)
    active_pages = pages.get("Pages active", 0)
    inactive_pages = pages.get("Pages inactive", 0)
    wired_pages = pages.get("Pages wired down", 0)
    compressor_pages = pages.get("Pages occupied by compressor", 0)
    speculative_pages = pages.get("Pages speculative", 0)
    purgeable_pages = pages.get("Pages purgeable", 0)

    mem_free = (free_pages + inactive_pages + speculative_pages + purgeable_pages) * page_size
    mem_used = (active_pages + wired_pages + compressor_pages) * page_size

    # Swap from sysctl
    swap_out = _run(["sysctl", "-n", "vm.swapusage"])
    swap_total = 0
    swap_used = 0
    if swap_out:
        for part in swap_out.split():
            # Format: "total = X.XXM  used = X.XXM  free = X.XXM"
            pass
        m = re.search(r"total\s*=\s*([\d.]+)([MG])", swap_out)
        if m:
            val = float(m.group(1))
            swap_total = int(val * (1024**3 if m.group(2) == "G" else 1024**2))
        m = re.search(r"used\s*=\s*([\d.]+)([MG])", swap_out)
        if m:
            val = float(m.group(1))
            swap_used = int(val * (1024**3 if m.group(2) == "G" else 1024**2))

    # Determine pressure level
    if mem_total > 0:
        free_pct = mem_free / mem_total
        if swap_used > 0 or free_pct < 0.10:
            level = "critical"
        elif free_pct < 0.20:
            level = "warn"
        else:
            level = "normal"
    else:
        level = "unknown"

    return MemoryPressure(
        level=level,
        memory_total=mem_total,
        memory_used=mem_used,
        memory_free=mem_free,
        swap_used=swap_used,
        swap_total=swap_total,
    )


def _parse_linux() -> MemoryPressure:
    mem_info: dict[str, int] = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    mem_info[key] = int(parts[1]) * 1024  # kB to bytes
    except FileNotFoundError:
        return MemoryPressure("unknown", 0, 0, 0, 0, 0)

    mem_total = mem_info.get("MemTotal", 0)
    mem_available = mem_info.get("MemAvailable", 0)
    mem_free = mem_available or mem_info.get("MemFree", 0)
    mem_used = mem_total - mem_free
    swap_total = mem_info.get("SwapTotal", 0)
    swap_free = mem_info.get("SwapFree", 0)
    swap_used = swap_total - swap_free

    if mem_total > 0:
        free_pct = mem_free / mem_total
        if swap_used > 0 or free_pct < 0.10:
            level = "critical"
        elif free_pct < 0.20:
            level = "warn"
        else:
            level = "normal"
    else:
        level = "unknown"

    return MemoryPressure(
        level=level,
        memory_total=mem_total,
        memory_used=mem_used,
        memory_free=mem_free,
        swap_used=swap_used,
        swap_total=swap_total,
    )


def get_memory_pressure() -> MemoryPressure:
    system = platform.system()
    if system == "Darwin":
        return _parse_macos()
    if system == "Linux":
        return _parse_linux()
    return MemoryPressure("unknown", 0, 0, 0, 0, 0)
