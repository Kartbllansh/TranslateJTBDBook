"""Tests for translation pipeline helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from book_pipeline.common import initial_pipeline_state, read_json, write_json
from book_pipeline.translate import (
    Glossary,
    GlossaryTerm,
    SourceChunk,
    TranslationContext,
    TranslationMode,
    TranslationResult,
    build_translation_context,
    build_translation_prompt,
    discover_chunks,
    load_glossaries,
    translate_project,
)


class FakeLLMService:
    def __init__(self, text: str = "Переведенный текст.\n") -> None:
        self.text = text
        self.prompts: list[str] = []

    def translate(self, prompt: str) -> TranslationResult:
        self.prompts.append(prompt)
        return TranslationResult(translated_text=self.text)


class FailingLLMService:
    def translate(self, prompt: str) -> TranslationResult:
        raise RuntimeError("boom")


def create_project_with_chunks(
    tmp_path: Path,
    statuses: list[str] | None = None,
    translated_texts: list[str] | None = None,
) -> Path:
    statuses = statuses or ["pending"]
    translated_texts = translated_texts or ["" for _ in statuses]

    project_dir = tmp_path / "project"
    chunks_dir = project_dir / "chunks" / "01_chapter"
    chunks_dir.mkdir(parents=True)
    (project_dir / "review").mkdir()

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
                    "status": "chunked",
                    "chunk_count": len(statuses),
                }
            ],
        },
    )
    write_json(project_dir / "pipeline-state.json", initial_pipeline_state())

    for index, status in enumerate(statuses, start=1):
        sequence = f"{index:04d}"
        source_path = chunks_dir / f"{sequence}.source.md"
        translated_path = chunks_dir / f"{sequence}.ru.md"
        source_path.write_text(
            f"Source paragraph {index}.\n\nMore source text {index}.",
            encoding="utf-8",
        )
        translated_path.write_text(translated_texts[index - 1], encoding="utf-8")
        write_json(
            chunks_dir / f"{sequence}.meta.json",
            {
                "chunk_id": f"01_chapter_{sequence}",
                "chapter_id": "01_chapter",
                "sequence": index,
                "char_count": source_path.stat().st_size,
                "status": status,
                "source_path": f"chunks/01_chapter/{sequence}.source.md",
                "translated_path": f"chunks/01_chapter/{sequence}.ru.md",
                "created_at": "2026-01-01T00:00:00+00:00",
                "translated_at": None,
                "translation_mode": None,
                "error": None,
            },
        )

    return project_dir


def test_load_glossaries_project_overrides_root_and_reports_conflict(tmp_path: Path):
    root = tmp_path / "root"
    project = tmp_path / "project"
    root.mkdir()
    project.mkdir()
    (root / "TERMINOLOGY.md").write_text(
        "| English | Russian | Notes |\n|---|---|---|\n| Job | Работа | root |\n",
        encoding="utf-8",
    )
    (project / "glossary.md").write_text(
        "| English | Russian | Notes |\n|---|---|---|\n| Job | Дело | project |\n",
        encoding="utf-8",
    )

    glossary = load_glossaries(project, root_dir=root)

    assert glossary.terms["job"].russian == "Дело"
    assert glossary.conflicts == ["Job: root='Работа' project='Дело'"]


def test_build_translation_context_uses_neighbor_paragraphs(tmp_path: Path):
    project_dir = create_project_with_chunks(tmp_path, statuses=["pending", "pending", "pending"])
    chunks = discover_chunks(project_dir)
    metadata = read_json(project_dir / "metadata.json")

    context = build_translation_context(chunks, 1, metadata)

    assert context.chapter_title == "Chapter 1"
    assert context.previous_chunk_summary == "More source text 1."
    assert context.next_chunk_summary == "Source paragraph 3."


def test_build_translation_prompt_includes_glossary_and_context(tmp_path: Path):
    project_dir = create_project_with_chunks(tmp_path)
    chunk = discover_chunks(project_dir)[0]
    glossary = Glossary(
        terms={
            "job": GlossaryTerm(
                english="Job",
                russian="Работа",
                notes="JTBD term",
                source="root",
            )
        },
        conflicts=[],
    )
    context = TranslationContext(
        previous_chunk_summary="Previous paragraph.",
        next_chunk_summary="Next paragraph.",
        chapter_title="Chapter 1",
    )

    prompt = build_translation_prompt(chunk, glossary, context, TranslationMode.NORMAL)

    assert "Job -> Работа" in prompt
    assert "for reference only" in prompt
    assert "Previous paragraph." in prompt
    assert "Translate naturally" in prompt
    assert "SOURCE TEXT:" in prompt


def test_translate_project_translates_pending_chunk(tmp_path: Path):
    project_dir = create_project_with_chunks(tmp_path)
    service = FakeLLMService()

    result = translate_project(project_dir, llm_service=service)

    assert result.translated_count == 1
    assert result.error_count == 0
    assert service.prompts
    assert (project_dir / "chunks" / "01_chapter" / "0001.ru.md").read_text(
        encoding="utf-8"
    ) == "Переведенный текст.\n"
    meta = read_json(project_dir / "chunks" / "01_chapter" / "0001.meta.json")
    assert meta["status"] == "translated"


def test_translate_project_preserves_existing_manual_translation(tmp_path: Path):
    project_dir = create_project_with_chunks(
        tmp_path,
        statuses=["pending"],
        translated_texts=["Ручной перевод.\n"],
    )
    service = FakeLLMService()

    result = translate_project(project_dir, llm_service=service)

    assert result.skipped_count == 1
    assert service.prompts == []
    assert (project_dir / "chunks" / "01_chapter" / "0001.ru.md").read_text(
        encoding="utf-8"
    ) == "Ручной перевод.\n"


def test_translate_project_skips_error_without_retry(tmp_path: Path):
    project_dir = create_project_with_chunks(tmp_path, statuses=["error"])
    service = FakeLLMService()

    result = translate_project(project_dir, llm_service=service)

    assert result.skipped_count == 1
    assert service.prompts == []


def test_translate_project_retries_failed_chunk(tmp_path: Path):
    project_dir = create_project_with_chunks(tmp_path, statuses=["error"])
    service = FakeLLMService()

    result = translate_project(project_dir, retry_failed=True, llm_service=service)

    assert result.translated_count == 1
    assert service.prompts


def test_translate_project_logs_errors(tmp_path: Path):
    project_dir = create_project_with_chunks(tmp_path)

    result = translate_project(project_dir, llm_service=FailingLLMService())

    assert result.error_count == 1
    assert (project_dir / "review" / "translation-errors.md").exists()
    meta = read_json(project_dir / "chunks" / "01_chapter" / "0001.meta.json")
    assert meta["status"] == "error"
    assert "boom" in meta["error"]


def test_unsupported_mode_enum_rejected():
    with pytest.raises(ValueError):
        TranslationMode("slow")
