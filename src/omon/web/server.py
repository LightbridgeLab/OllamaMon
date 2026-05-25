"""Web dashboard server using http.server."""

from __future__ import annotations

import importlib.resources
import json
import os
import sys
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from omon.api import DEFAULT_HOST, OllamaError, get_server_status, list_models, list_running, show_model
from omon.decoder import decode_model_name
from omon.formatter import format_size
from omon.hardware import get_hardware_info
from omon.pressure import get_memory_pressure
from omon.store import get_all_last_seen, get_benchmarks

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def _static_path() -> str:
    """Resolve the path to the static files directory."""
    ref = importlib.resources.files("omon.web").joinpath("static")
    # For editable installs, this is a PosixPath; for wheel installs, it's a traversable
    return str(ref)


class OmonHandler(BaseHTTPRequestHandler):
    """Request handler for the omon web dashboard."""

    ollama_host: str = DEFAULT_HOST
    static_dir: str = ""

    def log_message(self, format: str, *args) -> None:
        # Suppress default logging to stderr
        pass

    def _send_json(self, data: dict | list, status: int = 200) -> None:
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, message: str) -> None:
        self._send_json({"error": message}, status)

    def _serve_static(self, filename: str) -> None:
        filepath = os.path.join(self.static_dir, filename)
        if not os.path.isfile(filepath):
            self.send_error(404)
            return

        ext = os.path.splitext(filename)[1]
        content_type = CONTENT_TYPES.get(ext, "application/octet-stream")

        with open(filepath, "rb") as f:
            body = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if ext in (".html", ".css", ".js"):
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ─── API endpoints ─────────────────────────────────────

    def _api_status(self) -> None:
        host = self.ollama_host
        server = get_server_status(host)
        hw = get_hardware_info()
        pressure = get_memory_pressure()

        running = []
        models_count = 0
        models_total = 0
        if server.running:
            try:
                models = list_models(host)
                running = list_running(host)
                models_count = len(models)
                models_total = sum(m.size for m in models)
            except OllamaError:
                pass

        self._send_json({
            "server": asdict(server),
            "hardware": asdict(hw),
            "pressure": asdict(pressure),
            "models_count": models_count,
            "models_total_size": models_total,
            "models_total_size_human": format_size(models_total),
            "running": [asdict(r) for r in running],
        })

    def _api_models(self) -> None:
        host = self.ollama_host
        try:
            models = list_models(host)
            running = list_running(host)
        except OllamaError as e:
            self._send_error_json(502, str(e))
            return

        running_names = {r.name for r in running}
        last_seen = get_all_last_seen()
        items = []

        for m in models:
            try:
                det = show_model(m.name, host)
            except OllamaError:
                det = None

            decoded = decode_model_name(m.name, info=m, details=det)

            item = {
                "name": m.name,
                "size": m.size,
                "size_human": format_size(m.size),
                "modified_at": m.modified_at,
                "family": decoded.family_name,
                "description": decoded.description,
                "publisher": decoded.publisher,
                "parameter_count": decoded.parameter_count,
                "active_params": decoded.active_params,
                "quantization": decoded.quantization,
                "fine_tunes": decoded.fine_tunes,
                "capabilities": decoded.capabilities,
                "license": decoded.license_short,
                "successor": decoded.successor,
                "context_length": det.context_length if det else 0,
                "running": m.name in running_names,
                "last_seen": last_seen.get(m.name),
            }
            items.append(item)

        self._send_json(items)

    def _api_disk(self) -> None:
        host = self.ollama_host
        try:
            models = list_models(host)
        except OllamaError as e:
            self._send_error_json(502, str(e))
            return

        models_dir = os.environ.get("OLLAMA_MODELS", os.path.expanduser("~/.ollama"))
        try:
            st = os.statvfs(models_dir)
            disk_free = st.f_bavail * st.f_frsize
        except (OSError, AttributeError):
            disk_free = 0

        total = sum(m.size for m in models)
        self._send_json({
            "models": [
                {"name": m.name, "size": m.size, "size_human": format_size(m.size)}
                for m in sorted(models, key=lambda m: m.size, reverse=True)
            ],
            "total": total,
            "total_human": format_size(total),
            "disk_free": disk_free,
            "disk_free_human": format_size(disk_free),
        })

    def _api_pressure(self) -> None:
        pressure = get_memory_pressure()
        hw = get_hardware_info()

        try:
            running = list_running(self.ollama_host)
        except OllamaError:
            running = []

        model_mem = sum(r.size for r in running)
        self._send_json({
            **asdict(pressure),
            "memory_total_human": format_size(pressure.memory_total),
            "memory_used_human": format_size(pressure.memory_used),
            "memory_free_human": format_size(pressure.memory_free),
            "model_memory": model_mem,
            "model_memory_human": format_size(model_mem),
            "running": [{"name": r.name, "size": r.size, "size_human": format_size(r.size)} for r in running],
        })

    def _api_running(self) -> None:
        try:
            running = list_running(self.ollama_host)
        except OllamaError:
            running = []

        from omon.store import record_model_seen
        for r in running:
            record_model_seen(r.name)

        hw = get_hardware_info()
        self._send_json({
            "models": [
                {
                    **asdict(r),
                    "size_human": format_size(r.size),
                    "memory_pct": (r.size / hw.total_memory * 100) if hw.total_memory else 0,
                }
                for r in running
            ],
            "total_memory": hw.total_memory,
        })

    def _api_benchmarks(self) -> None:
        records = get_benchmarks(limit=100)
        # Group by model and timestamp
        runs: dict[str, dict] = {}
        for r in records:
            key = f"{r.model}|{r.timestamp}"
            if key not in runs:
                runs[key] = {
                    "model": r.model,
                    "timestamp": r.timestamp,
                    "cold_load_ms": r.cold_load_ms,
                    "warm_load_ms": r.warm_load_ms,
                    "memory_bytes": r.memory_bytes,
                    "prompts": [],
                }
            runs[key]["prompts"].append({
                "label": r.prompt_label,
                "prompt_tokens": r.prompt_tokens,
                "gen_tokens": r.gen_tokens,
                "prompt_tok_s": r.prompt_tok_s,
                "gen_tok_s": r.gen_tok_s,
            })

        # Calculate average gen speed per run
        results = []
        for run in runs.values():
            gen_speeds = [p["gen_tok_s"] for p in run["prompts"] if p["gen_tok_s"] > 0]
            run["avg_gen_tok_s"] = sum(gen_speeds) / len(gen_speeds) if gen_speeds else 0
            run["memory_human"] = format_size(run["memory_bytes"]) if run["memory_bytes"] else None
            results.append(run)

        self._send_json(results)

    # ─── Request routing ───────────────────────────────────

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        api_routes = {
            "/api/status": self._api_status,
            "/api/models": self._api_models,
            "/api/disk": self._api_disk,
            "/api/pressure": self._api_pressure,
            "/api/running": self._api_running,
            "/api/benchmarks": self._api_benchmarks,
        }

        if path in api_routes:
            try:
                api_routes[path]()
            except Exception as e:
                self._send_error_json(500, str(e))
            return

        # Static files
        static_routes = {
            "/": "index.html",
            "/index.html": "index.html",
            "/style.css": "style.css",
            "/app.js": "app.js",
        }

        if path in static_routes:
            self._serve_static(static_routes[path])
        else:
            self.send_error(404)


DEFAULT_BIND = "127.0.0.1"


def run_server(
    port: int = 11435,
    ollama_host: str = DEFAULT_HOST,
    bind: str = DEFAULT_BIND,
) -> None:
    """Start the web dashboard server."""
    OmonHandler.ollama_host = ollama_host
    OmonHandler.static_dir = _static_path()

    if bind in ("0.0.0.0", "::"):
        print(
            "Warning: dashboard is reachable on all network interfaces with no authentication.",
            file=sys.stderr,
        )

    server = HTTPServer((bind, port), OmonHandler)
    display_host = "localhost" if bind in ("127.0.0.1", "::1") else bind
    print(f"omon dashboard running at http://{display_host}:{port}")
    print(f"Monitoring Ollama at {ollama_host}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
        server.shutdown()
