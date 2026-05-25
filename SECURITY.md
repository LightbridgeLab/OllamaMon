# Security

omon is designed for local use alongside Ollama on your own machine. This document covers network exposure and data storage.

## Web dashboard (`omon serve`)

By default, `omon serve` binds to **127.0.0.1** — only reachable from the same machine.

If you pass `--bind 0.0.0.0` (or set `bind = "0.0.0.0"` in config), the dashboard is reachable from your local network. **There is no authentication.** Anyone who can reach the port can read:

- Installed model names and sizes
- Running models and memory usage
- Disk usage and hardware profile
- Benchmark history

The dashboard does not delete models or modify Ollama, but it does expose information about your setup.

**Recommendation:** keep the default bind address unless you need LAN access and understand the exposure.

## Remote Ollama (`--host`)

The `--host` flag (and `host` in config) points omon at any Ollama server address. Communication uses **plain HTTP** with no TLS. Only use `--host` on networks you trust, or when Ollama is behind your own secure tunnel.

## Local data storage

omon stores data locally only:

| Path | Contents |
|---|---|
| `~/.local/share/omon/metrics.db` | Benchmark results, model "last seen" timestamps |
| `~/.config/omon/config.toml` | Your preferences (host, port, bind address) |

No prompt text or inference content is stored. Model names in SQLite may be sensitive in some environments.

## External network calls

omon ships with **zero runtime dependencies** and makes **no outbound network calls** by default. All data comes from your Ollama instance via `localhost:11434` (or your configured host).

Optional external API integration (HuggingFace, OpenRouter, etc.) is planned for a future release and will be opt-in. See [ROADMAP.md](ROADMAP.md).

## Reporting issues

If you find a security vulnerability, please open a [GitHub issue](https://github.com/LightbridgeLab/OllamaMon/issues) rather than a public discussion.
