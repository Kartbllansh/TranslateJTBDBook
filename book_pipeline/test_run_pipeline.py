"""Tests for pipeline orchestration."""

from __future__ import annotations

from pathlib import Path

from book_pipeline.run_pipeline import run_pipeline, stages_until
from book_pipeline.translate import TranslationMode


def test_stages_until_publish():
    assert stages_until("chunk") == ["extract", "normalize", "split", "chunk"]


def test_run_pipeline_stops_for_chat_translation(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    calls: list[str] = []

    monkeypatch.setattr(
        "book_pipeline.run_pipeline.extract_project",
        lambda project_dir, options: calls.append("extract"),
    )
    monkeypatch.setattr(
        "book_pipeline.run_pipeline.normalize_project",
        lambda project_dir, force=False: calls.append("normalize"),
    )
    monkeypatch.setattr(
        "book_pipeline.run_pipeline.split_project_chapters",
        lambda project_dir, mode="auto", force=False: calls.append("split"),
    )
    monkeypatch.setattr(
        "book_pipeline.run_pipeline.write_project_chunks",
        lambda project_dir, max_chars=6000, force=False: calls.append("chunk"),
    )
    monkeypatch.setattr(
        "book_pipeline.run_pipeline.get_chat_translation_status",
        lambda project_dir: type("Status", (), {"pending": 1})(),
    )
    monkeypatch.setattr(
        "book_pipeline.run_pipeline.write_next_chat_prompt",
        lambda project_dir, mode=TranslationMode.NORMAL: Path("next.md"),
    )

    result = run_pipeline(project_dir, until="translate", translation_method="chat")

    assert calls == ["extract", "normalize", "split", "chunk"]
    assert result.stopped_at == "translate"


def test_run_pipeline_uses_api_translation_and_continues(tmp_path: Path, monkeypatch):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    calls: list[str] = []

    for name in ["extract_project", "normalize_project", "split_project_chapters"]:
        monkeypatch.setattr(
            f"book_pipeline.run_pipeline.{name}",
            lambda *args, _name=name, **kwargs: calls.append(_name),
        )
    monkeypatch.setattr(
        "book_pipeline.run_pipeline.write_project_chunks",
        lambda *args, **kwargs: calls.append("chunk"),
    )
    monkeypatch.setattr(
        "book_pipeline.run_pipeline.translate_project",
        lambda *args, **kwargs: calls.append("translate"),
    )
    monkeypatch.setattr(
        "book_pipeline.run_pipeline.assemble_project",
        lambda *args, **kwargs: calls.append("assemble"),
    )

    result = run_pipeline(project_dir, until="assemble", translation_method="api", provider="echo")

    assert calls == [
        "extract_project",
        "normalize_project",
        "split_project_chapters",
        "chunk",
        "translate",
        "assemble",
    ]
    assert result.stopped_at is None
