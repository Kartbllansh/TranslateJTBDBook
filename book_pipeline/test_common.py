"""Tests for shared pipeline utilities."""

from __future__ import annotations

from book_pipeline.common import (
    BlockType,
    initial_pipeline_state,
    parse_glossary_table,
    parse_markdown_blocks,
    read_json,
    slugify,
    update_pipeline_stage,
    write_json,
)


def test_slugify_handles_unicode_special_chars_and_empty_strings():
    assert slugify("When Coffee & Kale Compete!") == "when-coffee-kale-compete"
    assert slugify("Когда кофе и капуста") == "когда-кофе-и-капуста"
    assert slugify("") == "book"


def test_json_round_trip_and_backup(tmp_path):
    path = tmp_path / "project" / "metadata.json"
    original = {"book_id": "test", "chapters": [{"id": "01_chapter"}]}

    write_json(path, original)
    assert read_json(path) == original

    updated = {"book_id": "test", "chapters": []}
    write_json(path, updated)
    assert read_json(path) == updated
    backups = list((tmp_path / "project" / "review" / "backups").glob("metadata-*.json"))
    assert backups


def test_update_pipeline_stage_creates_state_backup(tmp_path):
    project_dir = tmp_path / "project"
    write_json(project_dir / "pipeline-state.json", initial_pipeline_state())

    update_pipeline_stage(project_dir, "extract", "done")

    state = read_json(project_dir / "pipeline-state.json")
    assert state["stages"]["extract"] == "done"
    backups = list((project_dir / "review" / "backups").glob("pipeline-state-*.json"))
    assert backups


def test_parse_markdown_blocks_with_nested_structures():
    text = """# Title

Paragraph.

- Item 1
  - Nested item
- Item 2

> Quote line

```python
print("x")
```
"""

    blocks = parse_markdown_blocks(text)

    assert [block.type for block in blocks] == [
        BlockType.HEADING,
        BlockType.PARAGRAPH,
        BlockType.LIST,
        BlockType.QUOTE,
        BlockType.CODE_BLOCK,
    ]
    assert "Nested item" in blocks[2].content


def test_parse_glossary_table_with_empty_and_special_cells():
    text = """# Glossary

| English | Русский перевод | Правило употребления |
|---|---|---|
| Job | Работа | Use as JTBD term |
| Progress | прогресс | |
| C++ | C++ | Preserve symbols |
|  |  | empty row |
"""

    entries = parse_glossary_table(text)

    assert entries[0] == {
        "english": "Job",
        "russian": "Работа",
        "notes": "Use as JTBD term",
    }
    assert entries[1]["notes"] == ""
    assert entries[2]["english"] == "C++"
    assert len(entries) == 3
