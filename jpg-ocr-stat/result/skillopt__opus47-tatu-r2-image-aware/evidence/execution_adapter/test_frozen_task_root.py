from __future__ import annotations

from pathlib import Path

import pytest

from adapters.common import executor_api


class _FakeExecutor:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _runtime_task(tmp_path: Path, name: str = "jpg-ocr-stat") -> Path:
    task = tmp_path / name
    task.mkdir()
    (task / "task.md").write_text("# task\n", encoding="utf-8")
    (task / "environment").mkdir()
    (task / "verifier").mkdir()
    return task


def test_frozen_task_root_uses_isolated_parent(monkeypatch, tmp_path: Path) -> None:
    """Guards the isolated group-02 adapter added for the 2026-11-02 run."""
    task = _runtime_task(tmp_path)
    monkeypatch.setenv("BENCHMARK_MODEL", "tatu/claude-opus-4-7")
    monkeypatch.setattr(executor_api, "load_benchmark_executor_class", lambda: _FakeExecutor)

    executor = executor_api.new_executor(
        tmp_path / "jobs",
        task_id="jpg-ocr-stat",
        task_root_override=task,
    )

    assert executor.kwargs["tasks_root"] == tmp_path
    assert executor.kwargs["max_parent_iterations_per_step"] == 65


def test_frozen_task_root_requires_matching_task_name(monkeypatch, tmp_path: Path) -> None:
    """Guards the isolated group-02 adapter added for the 2026-11-02 run."""
    task = _runtime_task(tmp_path, name="wrong-name")
    monkeypatch.setenv("BENCHMARK_MODEL", "tatu/claude-opus-4-7")
    monkeypatch.setattr(executor_api, "load_benchmark_executor_class", lambda: _FakeExecutor)

    with pytest.raises(ValueError, match="directory name must equal task_id"):
        executor_api.new_executor(
            tmp_path / "jobs",
            task_id="jpg-ocr-stat",
            task_root_override=task,
        )
