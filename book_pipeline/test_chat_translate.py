"""Tests for chat-based translation queue."""

from __future__ import annotations

from pathlib import Path

from book_pipeline.chat_translate import (
    get_chat_translation_status,
    save_chat_translation,
    write_next_chat_prompt,
)
from book_pipeline.common import initial_pipeline_state, read_json, write_json


def create_chat_project(tmp_path: Path, translated: bool = False) -> Path:
    project_dir = tmp_path / "project"
    chunk_dir = project_dir / "chunks" / "01_chapter"
    chunk_dir.mkdir(parents=True)
    (project_dir / "review").mkdir()
    (chunk_dir / "0001.source.md").write_text(
        "# Chapter 1\n\nSource text.",
        encoding="utf-8",
    )
    (chunk_dir / "0001.ru.md").write_text(
        "Перевод.\n" if translated else "",
        encoding="utf-8",
    )
    write_json(
        chunk_dir / "0001.meta.json",
        {
            "chunk_id": "01_chapter_0001",
            "chapter_id": "01_chapter",
            "sequence": 1,
            "char_count": 24,
            "status": "translated" if translated else "pending",
            "source_path": "chunks/01_chapter/0001.source.md",
            "translated_path": "chunks/01_chapter/0001.ru.md",
            "created_at": "2026-01-01T00:00:00+00:00",
            "translated_at": None,
            "translation_mode": None,
            "error": None,
        },
    )
    write_json(
        project_dir / "metadata.json",
        {
            "book_id": "project",
            "title": "Project",
            "chapters": [
                {
                    "id": "01_chapter",
                    "title": "Chapter 1",
                    "source_path": "chapters/01_chapter.md",
                    "translated_path": "translated/01_chapter.md",
                    "status": "chunked",
                    "chunk_count": 1,
                }
            ],
        },
    )
    write_json(project_dir / "pipeline-state.json", initial_pipeline_state())
    return project_dir


def test_chat_translation_status_finds_next_pending_chunk(tmp_path: Path):
    project_dir = create_chat_project(tmp_path)

    status = get_chat_translation_status(project_dir)

    assert status.total == 1
    assert status.pending == 1
    assert status.next_chunk_id == "01_chapter_0001"


def test_write_next_chat_prompt_writes_packet(tmp_path: Path):
    project_dir = create_chat_project(tmp_path)

    packet_path = write_next_chat_prompt(project_dir)

    packet = packet_path.read_text(encoding="utf-8")
    assert "Chat Translation Packet" in packet
    assert "01_chapter_0001" in packet
    assert "SOURCE TEXT:" in packet
    assert "Source text." in packet


def test_save_chat_translation_updates_chunk_and_metadata(tmp_path: Path):
    project_dir = create_chat_project(tmp_path)

    chunk = save_chat_translation(project_dir, "01_chapter_0001", "Переведенный текст.")

    assert chunk.translated_path.read_text(encoding="utf-8") == "Переведенный текст.\n"
    meta = read_json(chunk.meta_path)
    assert meta["status"] == "translated"
    assert meta["translation_mode"] == "chat"
    metadata = read_json(project_dir / "metadata.json")
    assert metadata["chapters"][0]["status"] == "translated"


def test_chat_translation_status_skips_existing_translation(tmp_path: Path):
    project_dir = create_chat_project(tmp_path, translated=True)

    status = get_chat_translation_status(project_dir)

    assert status.translated == 1
    assert status.pending == 0
    assert status.next_chunk_id is None
