"""System hardware detection."""

from __future__ import annotations

import os
import platform
import subprocess

from omon.models import HardwareInfo


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _detect_macos() -> HardwareInfo:
    chip = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    mem = int(_run(["sysctl", "-n", "hw.memsize"]) or "0")
    cores = int(_run(["sysctl", "-n", "hw.ncpu"]) or "0")
    os_ver = _run(["sw_vers", "-productVersion"])
    return HardwareInfo(
        chip=chip or "Unknown Mac",
        total_memory=mem,
        cpu_cores=cores,
        os=f"macOS {os_ver}" if os_ver else "macOS",
    )


def _detect_linux() -> HardwareInfo:
    # CPU model
    chip = ""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    chip = line.split(":", 1)[1].strip()
                    break
    except FileNotFoundError:
        pass

    # Total memory
    mem = 0
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mem = int(line.split()[1]) * 1024  # kB to bytes
                    break
    except FileNotFoundError:
        pass

    cores = os.cpu_count() or 0
    kernel = _run(["uname", "-r"])
    return HardwareInfo(
        chip=chip or "Unknown CPU",
        total_memory=mem,
        cpu_cores=cores,
        os=f"Linux {kernel}" if kernel else "Linux",
    )


def get_hardware_info() -> HardwareInfo:
    system = platform.system()
    if system == "Darwin":
        return _detect_macos()
    if system == "Linux":
        return _detect_linux()
    return HardwareInfo(
        chip="Unknown",
        total_memory=0,
        cpu_cores=os.cpu_count() or 0,
        os=system,
    )
