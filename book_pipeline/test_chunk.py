"""Tests for chapter chunking."""

from __future__ import annotations

from pathlib import Path

import pytest

from book_pipeline.chunk import chunk_chapter, write_project_chunks
from book_pipeline.common import initial_pipeline_state, read_json, write_json
from book_pipeline.split_chapters import Chapter


def make_chapter(content: str, chapter_id: str = "01_chapter") -> Chapter:
    return Chapter(
        id=chapter_id,
        title="Chapter 1",
        content=content,
        start_line=1,
        end_line=len(content.splitlines()) or 1,
    )


def test_heading_stays_with_following_paragraph():
    content = "# Chapter 1\n\nThis paragraph belongs with the heading.\n\nSecond paragraph."
    chunks = chunk_chapter(make_chapter(content), max_chars=60)

    assert chunks
    assert chunks[0].content.startswith("# Chapter 1\n\nThis paragraph")


def test_keeps_small_list_together():
    content = "Intro.\n\n- First item\n- Second item\n- Third item\n\nOutro."
    chunks = chunk_chapter(make_chapter(content), max_chars=80)

    list_chunks = [
        chunk for chunk in chunks if "- First item" in chunk.content
    ]
    assert len(list_chunks) == 1
    assert "- Third item" in list_chunks[0].content


def test_splits_large_list_at_item_boundaries():
    content = "- Alpha item with detail\n- Beta item with detail\n- Gamma item with detail"
    chunks = chunk_chapter(make_chapter(content), max_chars=30)

    assert len(chunks) == 3
    assert all(chunk.content.lstrip().startswith("- ") for chunk in chunks)


def test_preserves_code_block_as_single_chunk():
    content = "Intro.\n\n```python\nprint('hello')\nprint('world')\n```\n\nOutro."
    chunks = chunk_chapter(make_chapter(content), max_chars=35)

    code_chunks = [chunk for chunk in chunks if "```python" in chunk.content]
    assert len(code_chunks) == 1
    assert "print('world')" in code_chunks[0].content
    assert code_chunks[0].content.count("```") == 2


def test_splits_large_paragraph_under_limit():
    content = " ".join(f"word{i}" for i in range(30))
    chunks = chunk_chapter(make_chapter(content), max_chars=50)

    assert len(chunks) > 1
    assert all(chunk.char_count <= 51 for chunk in chunks)


def test_empty_chapter_creates_no_chunks():
    assert chunk_chapter(make_chapter(""), max_chars=50) == []


def test_invalid_max_chars_raises():
    with pytest.raises(ValueError):
        chunk_chapter(make_chapter("Text"), max_chars=0)


def test_write_project_chunks_creates_files_and_metadata(tmp_path: Path):
    project_dir = tmp_path / "projects" / "sample"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True)
    (project_dir / "chunks").mkdir()
    (project_dir / "review").mkdir()

    (chapters_dir / "01_chapter.md").write_text(
        "# Chapter 1\n\nFirst paragraph.\n\nSecond paragraph.",
        encoding="utf-8",
    )
    write_json(
        project_dir / "metadata.json",
        {
            "schema_version": 1,
            "book_id": "sample",
            "title": "Sample",
            "author": "",
            "source_language": "en",
            "target_language": "ru",
            "chapters": [
                {
                    "id": "01_chapter",
                    "title": "Chapter 1",
                    "source_path": "chapters/01_chapter.md",
                    "translated_path": "translated/01_chapter.md",
                    "status": "pending",
                    "word_count": 5,
                    "chunk_count": 0,
                }
            ],
        },
    )
    write_json(project_dir / "pipeline-state.json", initial_pipeline_state())

    chunks = write_project_chunks(project_dir, max_chars=80)

    assert len(chunks) == 1
    chunk_dir = project_dir / "chunks" / "01_chapter"
    assert (chunk_dir / "0001.source.md").exists()
    assert (chunk_dir / "0001.ru.md").read_text(encoding="utf-8") == ""

    chunk_meta = read_json(chunk_dir / "0001.meta.json")
    assert chunk_meta["chunk_id"] == "01_chapter_0001"
    assert chunk_meta["status"] == "pending"

    metadata = read_json(project_dir / "metadata.json")
    assert metadata["chapters"][0]["chunk_count"] == 1
    assert metadata["chapters"][0]["status"] == "chunked"


def test_write_project_chunks_refuses_existing_files_without_force(tmp_path: Path):
    project_dir = tmp_path / "project"
    chapter_dir = project_dir / "chapters"
    chunk_dir = project_dir / "chunks" / "01_chapter"
    chapter_dir.mkdir(parents=True)
    chunk_dir.mkdir(parents=True)
    (chapter_dir / "01_chapter.md").write_text("# Chapter\n\nText", encoding="utf-8")
    (chunk_dir / "0001.source.md").write_text("old", encoding="utf-8")
    write_json(
        project_dir / "metadata.json",
        {
            "chapters": [
                {
                    "id": "01_chapter",
                    "title": "Chapter",
                    "source_path": "chapters/01_chapter.md",
                }
            ]
        },
    )

    with pytest.raises(FileExistsError):
        write_project_chunks(project_dir, max_chars=80)
