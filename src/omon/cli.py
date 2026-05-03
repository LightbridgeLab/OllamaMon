"""CLI entry point for omon."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from dataclasses import asdict

from omon import __version__
from omon.api import DEFAULT_HOST, OllamaError, get_server_status, list_models, list_running, show_model
from omon.decoder import decode_model_name
from omon.formatter import (
    format_bench,
    format_bench_compare,
    format_cleanup,
    format_disk,
    format_hw,
    format_list,
    format_pressure,
    format_show,
    format_size,
    format_status,
    format_suggest,
    format_updates,
)
from omon.hardware import get_hardware_info
from omon.models import ModelDetails, ModelInfo
from omon.pressure import get_memory_pressure


# Commands that should never be paged (they manage their own output)
_NO_PAGER = {"watch", "top", "serve", "completions"}


def _should_page(args: argparse.Namespace) -> bool:
    """Determine whether output should be paged."""
    if getattr(args, "no_pager", False):
        return False
    if getattr(args, "json", False):
        return False
    if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
        return False
    if args.command in _NO_PAGER:
        return False
    return True


def _page_output(text: str) -> None:
    """Send text through a pager only if it overflows the terminal."""
    try:
        term_lines = os.get_terminal_size().lines
    except (ValueError, OSError):
        print(text)
        return

    output_lines = text.count("\n") + 1
    if output_lines <= term_lines - 1:
        # Fits on screen — print directly, no pager
        print(text)
        return

    # Overflow — pipe through pager
    pager_cmd = os.environ.get("PAGER", "less -RX")
    try:
        proc = subprocess.Popen(
            pager_cmd,
            shell=True,
            stdin=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
        try:
            proc.communicate(input=text)
        except (OSError, BrokenPipeError):
            pass
        proc.wait()
    except OSError:
        print(text)


def _load_config():
    from omon.config import load_config
    return load_config()


def _get_host(args: argparse.Namespace) -> str:
    return getattr(args, "host", None) or os.environ.get("OLLAMA_HOST", DEFAULT_HOST)


def _error(msg: str) -> int:
    print(f"omon: {msg}", file=sys.stderr)
    return 1


def _fetch_details(models: list[ModelInfo], host: str) -> dict[str, ModelDetails]:
    """Fetch full details for each model. Returns dict keyed by name."""
    result: dict[str, ModelDetails] = {}
    for m in models:
        try:
            det = show_model(m.name, host)
            det.size = m.size  # /api/show doesn't include size
            result[m.name] = det
        except OllamaError:
            pass  # Skip models that fail, show what we can
    return result


def _decode_all(
    models: list[ModelInfo],
    details: dict[str, ModelDetails],
) -> dict[str, object]:
    """Decode all model names. Returns dict keyed by name."""
    from omon.decoder import decode_model_name
    result = {}
    for m in models:
        det = details.get(m.name)
        result[m.name] = decode_model_name(m.name, info=m, details=det)
    return result


def _disk_free() -> int:
    """Get free disk space on the volume where models are stored."""
    # Ollama stores models in ~/.ollama or OLLAMA_MODELS
    models_dir = os.environ.get("OLLAMA_MODELS", os.path.expanduser("~/.ollama"))
    try:
        st = os.statvfs(models_dir)
        return st.f_bavail * st.f_frsize
    except (OSError, AttributeError):
        try:
            st = os.statvfs("/")
            return st.f_bavail * st.f_frsize
        except (OSError, AttributeError):
            return 0


# ─── Commands ───────────────────────────────────────────────

def cmd_status(args: argparse.Namespace) -> int:
    host = _get_host(args)
    server = get_server_status(host)
    hw = get_hardware_info()
    pressure = get_memory_pressure()

    if server.running:
        try:
            models = list_models(host)
            running = list_running(host)
        except OllamaError as e:
            return _error(str(e))
    else:
        models = []
        running = []

    if args.json:
        data = {
            "server": asdict(server),
            "hardware": asdict(hw),
            "memory_pressure": asdict(pressure),
            "models_count": len(models),
            "models_total_size": sum(m.size for m in models),
            "running": [asdict(r) for r in running],
        }
        print(json.dumps(data, indent=2))
    else:
        print(format_status(server, models, running, hw, pressure))

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    host = _get_host(args)

    try:
        models = list_models(host)
        running = list_running(host)
    except OllamaError as e:
        return _error(str(e))

    details = _fetch_details(models, host)
    decoded = _decode_all(models, details)

    # Filter by capability if requested
    cap_filter = getattr(args, "cap", None)
    if cap_filter:
        cap_lower = cap_filter.lower()
        filtered = []
        for m in models:
            det = details.get(m.name)
            if det and cap_lower in [c.lower() for c in det.capabilities]:
                filtered.append(m)
        models = filtered

    if args.json:
        items = []
        for m in models:
            d = decoded.get(m.name)
            det = details.get(m.name)
            item = asdict(m)
            if d:
                item["decoded"] = asdict(d)
            if det:
                item["context_length"] = det.context_length
                item["capabilities"] = det.capabilities
            items.append(item)
        print(json.dumps(items, indent=2))
    else:
        print(format_list(models, decoded, details, running))

    return 0


def cmd_show(args: argparse.Namespace) -> int:
    host = _get_host(args)
    name = args.model

    try:
        models = list_models(host)
    except OllamaError as e:
        return _error(str(e))

    # Find the model info (for size)
    info = None
    for m in models:
        if m.name == name:
            info = m
            break

    if info is None:
        # Try partial match
        matches = [m for m in models if name in m.name]
        if len(matches) == 1:
            info = matches[0]
            name = info.name
        elif len(matches) > 1:
            return _error(
                f"Ambiguous model name '{name}'. Matches:\n"
                + "\n".join(f"  {m.name}" for m in matches)
            )
        # If no match, still try to show — ollama might know it

    try:
        det = show_model(name, host)
        if info:
            det.size = info.size
    except OllamaError as e:
        return _error(f"Model '{name}' not found: {e}")

    decoded = decode_model_name(name, info=info, details=det)

    if args.json:
        data = asdict(det)
        data["decoded"] = asdict(decoded)
        # Don't dump the full license text in JSON by default
        if data.get("license_text") and len(data["license_text"]) > 500:
            data["license_text"] = data["license_text"][:500] + "..."
        print(json.dumps(data, indent=2))
    else:
        print(format_show(det, decoded, info))

    return 0


def cmd_disk(args: argparse.Namespace) -> int:
    host = _get_host(args)

    try:
        models = list_models(host)
    except OllamaError as e:
        return _error(str(e))

    free = _disk_free()

    if args.json:
        data = {
            "models": [
                {"name": m.name, "size": m.size, "size_human": format_size(m.size)}
                for m in sorted(models, key=lambda m: m.size, reverse=True)
            ],
            "total": sum(m.size for m in models),
            "disk_free": free,
        }
        print(json.dumps(data, indent=2))
    else:
        print(format_disk(models, free))

    return 0


def cmd_pressure(args: argparse.Namespace) -> int:
    host = _get_host(args)
    hw = get_hardware_info()
    pressure = get_memory_pressure()

    try:
        running = list_running(host)
    except OllamaError:
        running = []

    if args.json:
        data = asdict(pressure)
        data["running"] = [asdict(r) for r in running]
        data["hardware"] = asdict(hw)
        print(json.dumps(data, indent=2))
    else:
        print(format_pressure(pressure, running, hw))

    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    from omon.bench import run_benchmark, save_results

    host = _get_host(args)
    model = args.model
    compare_model = getattr(args, "compare", None)

    models_to_bench = [model]
    if compare_model:
        models_to_bench.append(compare_model)

    results = []
    for m in models_to_bench:
        try:
            result = run_benchmark(m, host=host, verbose=not args.json)
            save_results(result)
            results.append(result)
        except OllamaError as e:
            return _error(f"Benchmark failed for '{m}': {e}")

    if args.json:
        out = []
        for r in results:
            out.append({
                "model": r.model,
                "timestamp": r.timestamp,
                "cold_load_ms": r.cold_load_ms,
                "warm_load_ms": r.warm_load_ms,
                "memory_bytes": r.memory_bytes,
                "avg_gen_tok_s": r.avg_gen_tok_s,
                "avg_prompt_tok_s": r.avg_prompt_tok_s,
                "prompts": [
                    {
                        "label": p.label,
                        "prompt_tokens": p.prompt_tokens,
                        "gen_tokens": p.gen_tokens,
                        "prompt_tok_s": p.prompt_tok_s,
                        "gen_tok_s": p.gen_tok_s,
                        "ttft_ms": p.ttft_ms,
                    }
                    for p in r.prompts
                ],
            })
        print(json.dumps(out[0] if len(out) == 1 else out, indent=2))
    else:
        if len(results) > 1:
            print(format_bench_compare(results))
        else:
            print(format_bench(results[0]))

    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from omon.tui.watch import run_watch

    host = _get_host(args)
    run_watch(host)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from omon.web.server import run_server

    host = _get_host(args)
    port = getattr(args, "port", 11435)
    run_server(port=port, ollama_host=host)
    return 0


def cmd_hw(args: argparse.Namespace) -> int:
    from omon.suggest import build_hardware_profile

    host = _get_host(args)
    hw = get_hardware_info()

    loaded_bytes = 0
    try:
        running = list_running(host)
        loaded_bytes = sum(r.size for r in running)
    except OllamaError:
        pass

    profile = build_hardware_profile(hw, loaded_bytes)

    if args.json:
        data = {
            "chip": hw.chip,
            "cpu_cores": hw.cpu_cores,
            "total_memory": hw.total_memory,
            "os": hw.os,
            "comfortable_model_gb": round(profile.comfortable_gb, 1),
            "maximum_model_gb": round(profile.maximum_gb, 1),
            "param_estimates": profile.param_estimates,
            "loaded_gb": round(profile.loaded_gb, 1),
        }
        print(json.dumps(data, indent=2))
    else:
        print(format_hw(profile))

    return 0


def cmd_suggest(args: argparse.Namespace) -> int:
    from omon.suggest import TASK_TYPES, get_suggestions

    host = _get_host(args)
    task = getattr(args, "task", None)

    if not task:
        task = "general"
        print(f"Available tasks: {', '.join(TASK_TYPES)}", file=sys.stderr)
        print(f"Defaulting to '{task}'...\n", file=sys.stderr)

    if task.lower() not in TASK_TYPES:
        return _error(
            f"Unknown task '{task}'.\nAvailable tasks: {', '.join(TASK_TYPES)}"
        )

    hw = get_hardware_info()

    try:
        models = list_models(host)
    except OllamaError as e:
        return _error(str(e))

    # Get benchmark speeds for installed models
    from omon.store import get_benchmarks
    bench_records = get_benchmarks(limit=100)
    bench_speeds: dict[str, float] = {}
    for r in bench_records:
        if r.model not in bench_speeds:
            bench_speeds[r.model] = r.gen_tok_s

    suggestions = get_suggestions(task, hw, models, bench_speeds)

    if args.json:
        data = []
        for s in suggestions:
            data.append({
                "family": s.family,
                "description": s.description,
                "publisher": s.publisher,
                "license": s.license,
                "installed": s.installed,
                "installed_name": s.installed_name,
                "bench_tok_s": s.bench_tok_s,
                "size_estimates": s.size_estimates,
                "successor_of": s.successor_of,
            })
        print(json.dumps(data, indent=2))
    else:
        print(format_suggest(task, suggestions, hw))

    return 0


def cmd_updates(args: argparse.Namespace) -> int:
    from omon.suggest import check_updates

    host = _get_host(args)

    try:
        models = list_models(host)
    except OllamaError as e:
        return _error(str(e))

    updates = check_updates(models)

    if args.json:
        data = [
            {
                "model": u.model,
                "successor": u.successor,
                "successor_description": u.successor_description,
            }
            for u in updates
        ]
        print(json.dumps(data, indent=2))
    else:
        print(format_updates(updates))

    return 0


def cmd_completions(args: argparse.Namespace) -> int:
    from omon.completions import bash_completion, fish_completion, zsh_completion

    shell = args.shell
    generators = {"bash": bash_completion, "zsh": zsh_completion, "fish": fish_completion}
    gen = generators.get(shell)
    if not gen:
        return _error(f"Unknown shell '{shell}'. Supported: bash, zsh, fish")
    print(gen())
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    from omon.config import _CONFIG_FILE, generate_default_config, load_config

    init = getattr(args, "init", False)

    if init:
        _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _CONFIG_FILE.exists():
            return _error(f"Config already exists at {_CONFIG_FILE}")
        _CONFIG_FILE.write_text(generate_default_config(), encoding="utf-8")
        print(f"Created config at {_CONFIG_FILE}")
        return 0

    if args.json:
        from dataclasses import asdict
        print(json.dumps({"path": str(_CONFIG_FILE), "exists": _CONFIG_FILE.is_file(), **asdict(load_config())}, indent=2))
    else:
        cfg = load_config()
        exists = _CONFIG_FILE.is_file()
        print(f"Config: {_CONFIG_FILE} {'(exists)' if exists else '(not created yet)'}")
        print(f"  host          {cfg.host}")
        print(f"  json          {cfg.json}")
        print(f"  no_pager      {cfg.no_pager}")
        print(f"  watch.interval {cfg.watch_interval}s")
        print(f"  serve.port    {cfg.serve_port}")
        print(f"  cleanup.days  {cfg.stale_days}")
        if not exists:
            print(f"\nRun 'omon config --init' to create the config file.")
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    from omon.store import get_all_last_seen
    from omon.suggest import get_cleanup_suggestions

    host = _get_host(args)

    try:
        models = list_models(host)
    except OllamaError as e:
        return _error(str(e))

    last_seen = get_all_last_seen()
    stale_days = getattr(args, "days", 30)
    suggestions = get_cleanup_suggestions(models, last_seen, stale_days)

    if args.json:
        data = [
            {
                "model": s.model,
                "size": s.size,
                "size_human": format_size(s.size),
                "reasons": s.reasons,
                "last_seen": s.last_seen,
                "successor": s.successor,
            }
            for s in suggestions
        ]
        print(json.dumps(data, indent=2))
    else:
        print(format_cleanup(suggestions))

    return 0


# ─── Argument parsing ──────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    # Shared flags available on every subcommand
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="Output as JSON")
    shared.add_argument("--host", metavar="HOST", help="Ollama host (default: localhost:11434)")
    shared.add_argument("--no-pager", action="store_true", help="Disable auto-paging of output")

    parser = argparse.ArgumentParser(
        prog="omon",
        description="Ollama Monitor — local-first monitoring and management for Ollama",
        parents=[shared],
    )
    parser.add_argument("--version", action="version", version=f"omon {__version__}")

    sub = parser.add_subparsers(dest="command")

    # list
    list_parser = sub.add_parser("list", aliases=["ls"], parents=[shared], help="List installed models with decoded names")
    list_parser.add_argument("--cap", metavar="CAPABILITY", help="Filter by capability (vision, thinking, tools, etc.)")

    # show
    show_parser = sub.add_parser("show", aliases=["info"], parents=[shared], help="Show detailed info for a model")
    show_parser.add_argument("model", help="Model name (e.g. llama2:7b)")

    # disk
    sub.add_parser("disk", aliases=["du"], parents=[shared], help="Show disk usage breakdown")

    # pressure
    sub.add_parser("pressure", aliases=["mem"], parents=[shared], help="Show memory pressure status")

    # bench
    bench_parser = sub.add_parser("bench", parents=[shared], help="Benchmark a model's performance")
    bench_parser.add_argument("model", help="Model to benchmark (e.g. llama2:7b)")
    bench_parser.add_argument("--compare", metavar="MODEL", help="Second model for side-by-side comparison")

    # watch
    sub.add_parser("watch", aliases=["top"], parents=[shared], help="Live monitoring TUI")

    # serve
    serve_parser = sub.add_parser("serve", parents=[shared], help="Start web dashboard")
    serve_parser.add_argument("--port", type=int, default=11435, help="Port (default: 11435)")

    # hw
    sub.add_parser("hw", parents=[shared], help="Show hardware profile and model sizing guide")

    # suggest
    suggest_parser = sub.add_parser("suggest", parents=[shared], help="Suggest models for a task")
    suggest_parser.add_argument("--task", metavar="TASK", default=None,
                                help="Task type: general, coding, math, vision, chat, embedding, thinking, tools")

    # updates
    sub.add_parser("updates", parents=[shared], help="Check for model updates (successor availability)")

    # cleanup
    cleanup_parser = sub.add_parser("cleanup", parents=[shared], help="Suggest models to remove")
    cleanup_parser.add_argument("--days", type=int, default=30, help="Stale threshold in days (default: 30)")

    # config
    config_parser = sub.add_parser("config", parents=[shared], help="Show or create configuration")
    config_parser.add_argument("--init", action="store_true", help="Create default config file")

    # completions
    comp_parser = sub.add_parser("completions", parents=[shared], help="Print shell completion script")
    comp_parser.add_argument("shell", choices=["bash", "zsh", "fish"], help="Shell type")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Apply config defaults (CLI flags override config, config overrides hardcoded defaults)
    cfg = _load_config()
    if not getattr(args, "host", None):
        args.host = cfg.host
    if not getattr(args, "json", False) and cfg.json:
        args.json = True
    if not getattr(args, "no_pager", False) and cfg.no_pager:
        args.no_pager = True
    if args.command == "serve" and getattr(args, "port", 11435) == 11435:
        args.port = cfg.serve_port
    if args.command == "cleanup" and getattr(args, "days", 30) == 30:
        args.days = cfg.stale_days

    commands = {
        None: cmd_status,
        "list": cmd_list,
        "ls": cmd_list,
        "show": cmd_show,
        "info": cmd_show,
        "disk": cmd_disk,
        "du": cmd_disk,
        "pressure": cmd_pressure,
        "mem": cmd_pressure,
        "bench": cmd_bench,
        "watch": cmd_watch,
        "top": cmd_watch,
        "serve": cmd_serve,
        "hw": cmd_hw,
        "suggest": cmd_suggest,
        "updates": cmd_updates,
        "cleanup": cmd_cleanup,
        "config": cmd_config,
        "completions": cmd_completions,
    }

    handler = commands.get(args.command, cmd_status)
    use_pager = _should_page(args)

    if use_pager:
        # Capture stdout, then page only if it overflows the terminal
        buf = io.StringIO()
        sys.stdout = buf
        try:
            code = handler(args)
        except KeyboardInterrupt:
            sys.exit(130)
        except BrokenPipeError:
            sys.exit(0)
        finally:
            sys.stdout = sys.__stdout__
        _page_output(buf.getvalue().rstrip("\n"))
        sys.exit(code)
    else:
        try:
            sys.exit(handler(args))
        except KeyboardInterrupt:
            sys.exit(130)
        except BrokenPipeError:
            sys.exit(0)
