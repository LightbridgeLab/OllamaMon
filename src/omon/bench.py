"""Model benchmarking engine."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

from omon.api import GenerateResult, generate, list_running, unload_model

PROMPTS = {
    "short": {
        "prompt": "Explain what a CPU cache is in one paragraph.",
        "num_predict": 100,
        "label": "Short",
    },
    "medium": {
        "prompt": (
            "Compare and contrast the following programming paradigms: "
            "object-oriented programming, functional programming, and "
            "procedural programming. For each paradigm, discuss its core "
            "principles, typical use cases, advantages, and disadvantages. "
            "Provide a brief code example illustrating each paradigm's approach "
            "to solving a common problem like filtering and transforming a list of numbers."
        ),
        "num_predict": 300,
        "label": "Medium",
    },
    "long": {
        "prompt": (
            "You are a computer science professor preparing a comprehensive lecture. "
            "Write a detailed technical explanation covering the following topics:\n\n"
            "1. How modern CPUs execute instructions, including pipelining, branch prediction, "
            "and out-of-order execution.\n"
            "2. The memory hierarchy from registers to main RAM, including L1, L2, and L3 "
            "caches, their typical sizes, latencies, and how cache coherence protocols work "
            "in multi-core systems.\n"
            "3. How virtual memory works, including page tables, TLBs, and the role of the "
            "operating system in memory management.\n"
            "4. The implications of all of the above for writing high-performance software, "
            "with specific examples of how data structure layout and access patterns affect "
            "performance.\n\n"
            "Be thorough and precise. Use concrete numbers for latencies and sizes where "
            "appropriate. This explanation should be suitable for advanced undergraduate students."
        ),
        "num_predict": 500,
        "label": "Long",
    },
}


@dataclass
class PromptResult:
    """Results from a single prompt benchmark."""
    label: str
    prompt_tokens: int
    gen_tokens: int
    prompt_tok_s: float
    gen_tok_s: float
    ttft_ms: float
    total_ms: float


@dataclass
class BenchmarkResult:
    """Complete benchmark results for one model."""
    model: str
    timestamp: str
    cold_load_ms: float
    warm_load_ms: float
    memory_bytes: int
    prompts: list[PromptResult] = field(default_factory=list)

    @property
    def avg_gen_tok_s(self) -> float:
        vals = [p.gen_tok_s for p in self.prompts if p.gen_tok_s > 0]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def avg_prompt_tok_s(self) -> float:
        vals = [p.prompt_tok_s for p in self.prompts if p.prompt_tok_s > 0]
        return sum(vals) / len(vals) if vals else 0.0


def _print_progress(msg: str) -> None:
    sys.stderr.write(f"\r  {msg}...")
    sys.stderr.flush()


def _clear_progress() -> None:
    sys.stderr.write("\r" + " " * 60 + "\r")
    sys.stderr.flush()


def run_benchmark(
    model: str,
    host: str = "localhost:11434",
    prompt_keys: list[str] | None = None,
    verbose: bool = True,
) -> BenchmarkResult:
    """Run a full benchmark suite against a model."""
    keys = prompt_keys or list(PROMPTS.keys())
    timestamp = datetime.now(timezone.utc).isoformat()

    # --- Cold load ---
    if verbose:
        _print_progress("Unloading model for cold start test")
    try:
        unload_model(model, host)
    except Exception:
        pass  # Model might not be loaded

    if verbose:
        _print_progress("Cold load test (this may take a while)")

    cold_result = generate(model, "Hello", num_predict=1, host=host)
    cold_load_ms = cold_result.load_ms

    # --- Get memory footprint ---
    memory_bytes = 0
    try:
        running = list_running(host)
        for r in running:
            if r.name == model:
                memory_bytes = r.size
                break
    except Exception:
        pass

    # --- Warm load ---
    if verbose:
        _print_progress("Warm load test")

    warm_result = generate(model, "Hello", num_predict=1, host=host)
    warm_load_ms = warm_result.load_ms

    # --- Prompt benchmarks ---
    prompt_results: list[PromptResult] = []
    for key in keys:
        spec = PROMPTS.get(key)
        if not spec:
            continue
        if verbose:
            _print_progress(f"{spec['label']} prompt benchmark")

        result = generate(model, spec["prompt"], num_predict=spec["num_predict"], host=host)
        prompt_results.append(PromptResult(
            label=spec["label"],
            prompt_tokens=result.prompt_eval_count,
            gen_tokens=result.eval_count,
            prompt_tok_s=result.prompt_tok_s,
            gen_tok_s=result.gen_tok_s,
            ttft_ms=result.ttft_ms,
            total_ms=result.total_duration_ns / 1e6,
        ))

    if verbose:
        _clear_progress()

    return BenchmarkResult(
        model=model,
        timestamp=timestamp,
        cold_load_ms=cold_load_ms,
        warm_load_ms=warm_load_ms,
        memory_bytes=memory_bytes,
        prompts=prompt_results,
    )


def save_results(result: BenchmarkResult) -> None:
    """Persist benchmark results to SQLite."""
    from omon.store import BenchmarkRecord, save_benchmark

    for p in result.prompts:
        save_benchmark(BenchmarkRecord(
            model=result.model,
            timestamp=result.timestamp,
            prompt_label=p.label,
            prompt_tokens=p.prompt_tokens,
            gen_tokens=p.gen_tokens,
            cold_load_ms=result.cold_load_ms,
            warm_load_ms=result.warm_load_ms,
            prompt_tok_s=p.prompt_tok_s,
            gen_tok_s=p.gen_tok_s,
            ttft_cold_ms=result.cold_load_ms + p.ttft_ms,
            ttft_warm_ms=p.ttft_ms,
            memory_bytes=result.memory_bytes,
        ))
