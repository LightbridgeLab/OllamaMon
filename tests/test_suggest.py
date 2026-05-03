"""Tests for the suggestion engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from omon.models import HardwareInfo, ModelInfo
from omon.suggest import (
    build_hardware_profile,
    check_updates,
    estimate_model_size_gb,
    get_cleanup_suggestions,
    get_suggestions,
    max_comfortable_model_gb,
    max_feasible_model_gb,
)


# ─── Size estimation ─────────────────────────────────────


class TestEstimateModelSize:
    def test_q4_7b(self):
        gb = estimate_model_size_gb(7, "q4")
        # 7B * 0.55 bytes/param * 1e9 / 1024^3 ≈ 3.58 GB
        assert 3.0 < gb < 4.0

    def test_fp16_7b(self):
        gb = estimate_model_size_gb(7, "fp16")
        # 7B * 2.0 bytes/param ≈ 13 GB
        assert 12.0 < gb < 14.0

    def test_q8_70b(self):
        gb = estimate_model_size_gb(70, "q8")
        # 70B * 1.0 bytes/param ≈ 65 GB
        assert 60.0 < gb < 70.0

    def test_default_quant(self):
        # Unknown quant falls back to q4 rate
        gb = estimate_model_size_gb(7, "mystery")
        assert 3.0 < gb < 4.0


# ─── Hardware limits ──────────────────────────────────────


class TestHardwareLimits:
    def test_comfortable_64gb(self, hw_64gb):
        gb = max_comfortable_model_gb(hw_64gb)
        assert gb == 48.0

    def test_feasible_64gb(self, hw_64gb):
        gb = max_feasible_model_gb(hw_64gb)
        assert abs(gb - 57.6) < 0.1

    def test_comfortable_8gb(self, hw_8gb):
        gb = max_comfortable_model_gb(hw_8gb)
        assert gb == 6.0


# ─── Hardware profile ────────────────────────────────────


class TestBuildHardwareProfile:
    def test_basic(self, hw_64gb):
        profile = build_hardware_profile(hw_64gb)
        assert profile.comfortable_gb == 48.0
        assert profile.loaded_gb == 0.0
        assert "Q4" in profile.param_estimates
        assert "FP16" in profile.param_estimates
        # 48GB comfortable / (0.55 * 1e9) * 1024^3 -> ~81B params at Q4
        assert profile.param_estimates["Q4"] > 50

    def test_with_loaded(self, hw_64gb):
        loaded = 10 * 1024**3
        profile = build_hardware_profile(hw_64gb, loaded_bytes=loaded)
        assert abs(profile.loaded_gb - 10.0) < 0.01


# ─── Suggestions ──────────────────────────────────────────


class TestGetSuggestions:
    def test_coding_task(self, hw_64gb, model_qwen):
        suggestions = get_suggestions("coding", hw_64gb, [model_qwen])
        # Should return at least some results
        assert len(suggestions) > 0
        # All should be for the coding task
        for s in suggestions:
            assert "coding" in [t.lower() for t in s.tasks]

    def test_installed_first(self, hw_64gb, model_llama2):
        suggestions = get_suggestions("general", hw_64gb, [model_llama2])
        installed = [s for s in suggestions if s.installed]
        not_installed = [s for s in suggestions if not s.installed]
        if installed and not_installed:
            # Installed should sort before not-installed
            first_installed_idx = suggestions.index(installed[0])
            first_not_installed_idx = suggestions.index(not_installed[0])
            assert first_installed_idx < first_not_installed_idx

    def test_constrained_hardware_filters(self, hw_8gb):
        # 8GB machine: very large models should not be suggested
        suggestions = get_suggestions("general", hw_8gb, [])
        for s in suggestions:
            # At least one size must fit comfortably
            assert any(e["fits"] for e in s.size_estimates)

    def test_unknown_task_empty(self, hw_64gb):
        suggestions = get_suggestions("underwater-basket-weaving", hw_64gb, [])
        assert suggestions == []

    def test_successor_detected(self, hw_64gb, model_llama2):
        suggestions = get_suggestions("general", hw_64gb, [model_llama2])
        # llama2 has successor llama3.3, which should be flagged
        successor_suggestions = [s for s in suggestions if s.successor_of]
        assert any(s.successor_of == "llama2" for s in successor_suggestions)


# ─── Update checking ─────────────────────────────────────


class TestCheckUpdates:
    def test_finds_successor(self, model_llama2):
        updates = check_updates([model_llama2])
        assert len(updates) == 1
        assert updates[0].model == "llama2:7b"
        assert updates[0].successor == "llama3.3"

    def test_no_successor(self, model_qwen):
        # qwen3.5 may or may not have a successor — just verify it doesn't crash
        updates = check_updates([model_qwen])
        # If it has no successor, list should be empty
        for u in updates:
            assert u.model == model_qwen.name

    def test_empty_list(self):
        assert check_updates([]) == []


# ─── Cleanup suggestions ─────────────────────────────────


class TestGetCleanupSuggestions:
    def test_stale_model(self, model_llama2):
        stale_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        last_seen = {"llama2:7b": stale_date}
        suggestions = get_cleanup_suggestions([model_llama2], last_seen, stale_days=30)
        assert len(suggestions) >= 1
        reasons = suggestions[0].reasons
        assert any("Not used" in r for r in reasons)

    def test_never_used(self, model_llama2):
        suggestions = get_cleanup_suggestions([model_llama2], {}, stale_days=30)
        assert len(suggestions) >= 1
        reasons = suggestions[0].reasons
        assert any("Never used" in r for r in reasons)

    def test_has_successor(self, model_llama2):
        # llama2 has successor llama3.3 in model_map
        recently = datetime.now(timezone.utc).isoformat()
        suggestions = get_cleanup_suggestions([model_llama2], {"llama2:7b": recently})
        reasons_flat = " ".join(r for s in suggestions for r in s.reasons)
        assert "Successor available" in reasons_flat

    def test_recently_used_no_stale_flag(self, model_qwen):
        recently = datetime.now(timezone.utc).isoformat()
        suggestions = get_cleanup_suggestions(
            [model_qwen], {"qwen3.5:35b-a3b-coding-nvfp4": recently}, stale_days=30,
        )
        # Should not have a "Not used" reason
        for s in suggestions:
            assert not any("Not used" in r for r in s.reasons)

    def test_sorted_by_size(self, model_llama2, model_qwen):
        suggestions = get_cleanup_suggestions(
            [model_llama2, model_qwen], {}, stale_days=30,
        )
        if len(suggestions) >= 2:
            assert suggestions[0].size >= suggestions[1].size

    def test_empty(self):
        assert get_cleanup_suggestions([], {}) == []
