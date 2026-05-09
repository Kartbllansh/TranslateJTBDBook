"""Shared helpers for the book translation pipeline."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


PIPELINE_STAGES = [
    "init",
    "extract",
    "normalize",
    "split",
    "chunk",
    "translate",
    "assemble",
    "review",
    "publish",
]


class BlockType(Enum):
    """Markdown block types for chunking algorithm."""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    CODE_BLOCK = "code_block"
    QUOTE = "quote"


@dataclass
class MarkdownBlock:
    """Represents a parsed markdown block."""
    type: BlockType
    content: str
    level: int | None = None  # For headings: 1-6


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = value.lower()
    slug = re.sub(r"[^a-z0-9а-яё]+", "-", slug)
    slug = slug.strip("-")
    return slug or "book"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_metadata_file(path)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def backup_metadata_file(path: Path) -> Path | None:
    """Create a timestamped backup for project metadata/state files."""

    if not path.exists() or path.name not in {"metadata.json", "pipeline-state.json"}:
        return None

    timestamp = re.sub(r"[^0-9A-Za-z_-]+", "-", now_iso()).strip("-")
    backup_dir = path.parent / "review" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.stem}-{timestamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    return backup_path


def check_disk_space(path: Path, required_bytes: int) -> None:
    """Fail before writing if the target drive lacks required free space."""

    target = path if path.exists() else path.parent
    while not target.exists() and target != target.parent:
        target = target.parent

    usage = shutil.disk_usage(target)
    if usage.free < required_bytes:
        raise OSError(
            f"Insufficient disk space under {target}: need {required_bytes} bytes, "
            f"available {usage.free} bytes."
        )


def ensure_empty_or_force(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(
            f"{path} already exists. Re-run with --force to reuse it."
        )


def initial_pipeline_state() -> dict[str, Any]:
    stages = {stage: "pending" for stage in PIPELINE_STAGES}
    stages["init"] = "done"
    return {
        "current_stage": "extract",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "stages": stages,
    }


def update_pipeline_stage(project_dir: Path, stage: str, status: str) -> None:
    state_path = project_dir / "pipeline-state.json"
    if not state_path.exists():
        return

    state = read_json(state_path)
    stages = state.setdefault("stages", {})
    stages[stage] = status
    state["updated_at"] = now_iso()

    if status == "done":
        next_stage = next_pending_stage(stages)
        if next_stage:
            state["current_stage"] = next_stage

    write_json(state_path, state)


def next_pending_stage(stages: dict[str, str]) -> str | None:
    for stage in PIPELINE_STAGES:
        if stages.get(stage) == "pending":
            return stage
    return None


def parse_markdown_blocks(text: str) -> list[MarkdownBlock]:
    """
    Parse markdown text into structured blocks.
    
    Identifies block types (heading, paragraph, list, code block, quote)
    for use in the smart chunking algorithm. Preserves block boundaries
    to prevent splitting headings from paragraphs, lists, code blocks, etc.
    
    Args:
        text: Markdown text to parse
    
    Returns:
        List of MarkdownBlock objects with type and content
    
    Examples:
        >>> blocks = parse_markdown_blocks("# Title\\n\\nParagraph text")
        >>> blocks[0].type == BlockType.HEADING
        True
        >>> blocks[1].type == BlockType.PARAGRAPH
        True
    """
    if not text.strip():
        return []
    
    blocks: list[MarkdownBlock] = []
    lines = text.split("\n")
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Code block (fenced with ``` or ~~~)
        if line.strip().startswith("```") or line.strip().startswith("~~~"):
            fence = line.strip()[:3]
            block_lines = [line]
            i += 1
            # Find closing fence
            while i < len(lines):
                block_lines.append(lines[i])
                if lines[i].strip().startswith(fence):
                    i += 1
                    break
                i += 1
            blocks.append(MarkdownBlock(
                type=BlockType.CODE_BLOCK,
                content="\n".join(block_lines)
            ))
            continue
        
        # Heading (ATX style: # Heading)
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            blocks.append(MarkdownBlock(
                type=BlockType.HEADING,
                content=line,
                level=level
            ))
            i += 1
            continue
        
        # Block quote (lines starting with >)
        if line.strip().startswith(">"):
            block_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                block_lines.append(lines[i])
                i += 1
            blocks.append(MarkdownBlock(
                type=BlockType.QUOTE,
                content="\n".join(block_lines)
            ))
            continue
        
        # List (ordered or unordered)
        list_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+", line)
        if list_match:
            block_lines = []
            indent_level = len(list_match.group(1))
            
            # Collect all consecutive list items (including nested)
            while i < len(lines):
                current_line = lines[i]
                
                # Empty line might be part of list (for multi-paragraph items)
                if not current_line.strip():
                    # Peek ahead to see if list continues
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        if re.match(r"^(\s*)([-*+]|\d+\.)\s+", next_line) or \
                           (next_line.startswith(" " * (indent_level + 2)) and next_line.strip()):
                            block_lines.append(current_line)
                            i += 1
                            continue
                    break
                
                # Check if it's a list item or continuation
                item_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+", current_line)
                if item_match:
                    block_lines.append(current_line)
                    i += 1
                elif current_line.startswith(" " * (indent_level + 2)) and current_line.strip():
                    # Continuation of previous item (indented)
                    block_lines.append(current_line)
                    i += 1
                else:
                    break
            
            blocks.append(MarkdownBlock(
                type=BlockType.LIST,
                content="\n".join(block_lines)
            ))
            continue
        
        # Empty line - skip
        if not line.strip():
            i += 1
            continue
        
        # Paragraph (default)
        block_lines = [line]
        i += 1
        # Collect consecutive non-empty lines that aren't other block types
        while i < len(lines):
            next_line = lines[i]
            
            # Stop at empty line
            if not next_line.strip():
                break
            
            # Stop at other block types
            if (next_line.strip().startswith("```") or
                next_line.strip().startswith("~~~") or
                re.match(r"^#{1,6}\s+", next_line) or
                next_line.strip().startswith(">") or
                re.match(r"^(\s*)([-*+]|\d+\.)\s+", next_line)):
                break
            
            block_lines.append(next_line)
            i += 1
        
        blocks.append(MarkdownBlock(
            type=BlockType.PARAGRAPH,
            content="\n".join(block_lines)
        ))
    
    return blocks


def split_list_items(list_block: MarkdownBlock) -> list[str]:
    """
    Split a list block into individual items for chunking large lists.
    
    When a list exceeds the chunk size limit, this function splits it
    at item boundaries while preserving nested structure and multi-line
    items.
    
    Args:
        list_block: MarkdownBlock of type LIST
    
    Returns:
        List of strings, each containing one or more list items
    
    Examples:
        >>> block = MarkdownBlock(BlockType.LIST, "- Item 1\\n- Item 2")
        >>> items = split_list_items(block)
        >>> len(items)
        2
    """
    if list_block.type != BlockType.LIST:
        return [list_block.content]
    
    lines = list_block.content.split("\n")
    items: list[str] = []
    current_item: list[str] = []
    
    for line in lines:
        # Check if this is a new list item (starts with marker)
        if re.match(r"^(\s*)([-*+]|\d+\.)\s+", line):
            # Save previous item if exists
            if current_item:
                items.append("\n".join(current_item))
            # Start new item
            current_item = [line]
        else:
            # Continuation of current item (indented or empty)
            if current_item:
                current_item.append(line)
    
    # Don't forget the last item
    if current_item:
        items.append("\n".join(current_item))
    
    return items


@dataclass
class GlossaryEntry:
    """Represents a single glossary term with translation and usage notes."""
    english: str
    russian: str
    notes: str


def calculate_word_count(text: str) -> int:
    """
    Calculate word count for chapter text.
    
    Counts words in markdown text, excluding markdown syntax elements
    like heading markers, list markers, and code block fences.
    
    Args:
        text: Markdown text content
    
    Returns:
        Word count as integer
    
    Examples:
        >>> calculate_word_count("# Chapter 1\\n\\nThis is a test.")
        5
        >>> calculate_word_count("- Item 1\\n- Item 2")
        4
    """
    if not text:
        return 0
    
    # Remove code blocks (they shouldn't count toward word count)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"~~~[\s\S]*?~~~", "", text)
    
    # Remove markdown syntax
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # Headings
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)  # Unordered lists
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)  # Ordered lists
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)  # Block quotes
    
    # Split on whitespace and count non-empty tokens
    words = text.split()
    return len(words)


def get_chapter_by_id(metadata: dict[str, Any], chapter_id: str) -> dict[str, Any] | None:
    """
    Retrieve chapter metadata by ID from metadata dictionary.
    
    Args:
        metadata: Metadata dictionary (typically from metadata.json)
        chapter_id: Chapter identifier (e.g., "01_chapter")
    
    Returns:
        Chapter metadata dictionary if found, None otherwise
    
    Examples:
        >>> metadata = {"chapters": [{"id": "01_chapter", "title": "Chapter 1"}]}
        >>> chapter = get_chapter_by_id(metadata, "01_chapter")
        >>> chapter["title"]
        'Chapter 1'
        >>> get_chapter_by_id(metadata, "99_chapter") is None
        True
    """
    chapters = metadata.get("chapters", [])
    for chapter in chapters:
        if chapter.get("id") == chapter_id:
            return chapter
    return None


def update_chapter_metadata(
    project_dir: Path,
    chapter_id: str,
    updates: dict[str, Any]
) -> None:
    """
    Update chapter metadata in metadata.json file.
    
    Reads metadata.json, finds the chapter by ID, applies updates,
    and writes back to disk. Updates the metadata.json updated_at
    timestamp automatically.
    
    Args:
        project_dir: Project root directory
        chapter_id: Chapter identifier to update
        updates: Dictionary of fields to update in chapter metadata
    
    Raises:
        FileNotFoundError: If metadata.json doesn't exist
        ValueError: If chapter_id is not found in metadata
    
    Examples:
        >>> update_chapter_metadata(
        ...     Path("projects/my-book"),
        ...     "01_chapter",
        ...     {"status": "translated", "word_count": 3542}
        ... )
    """
    metadata_path = project_dir / "metadata.json"
    
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"metadata.json not found at {metadata_path}. "
            "Ensure the project is initialized."
        )
    
    metadata = read_json(metadata_path)
    chapters = metadata.get("chapters", [])
    
    # Find and update the chapter
    chapter_found = False
    for chapter in chapters:
        if chapter.get("id") == chapter_id:
            chapter.update(updates)
            chapter_found = True
            break
    
    if not chapter_found:
        raise ValueError(
            f"Chapter '{chapter_id}' not found in metadata. "
            f"Available chapters: {[ch.get('id') for ch in chapters]}"
        )
    
    # Update the metadata timestamp
    metadata["updated_at"] = now_iso()
    
    # Write back to disk
    write_json(metadata_path, metadata)


def parse_glossary_table(markdown_text: str) -> list[dict[str, str]]:
    """
    Parse glossary entries from markdown tables.
    
    Extracts terminology mappings from markdown tables with columns:
    - English (or similar)
    - Russian / Русский перевод (or similar)
    - Usage Notes / Правило употребления (or similar)
    
    Handles multi-line usage notes in table cells and ignores markdown
    comments and non-table content.
    
    Args:
        markdown_text: Markdown content containing glossary tables
    
    Returns:
        List of dictionaries with keys 'english', 'russian', 'notes'
    
    Examples:
        >>> text = "| English | Russian | Notes |\\n|---|---|---|\\n| Job | Работа | Key term |"
        >>> entries = parse_glossary_table(text)
        >>> entries[0]['english']
        'Job'
        >>> entries[0]['russian']
        'Работа'
    """
    entries: list[dict[str, str]] = []
    lines = markdown_text.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line or line.startswith("<!--") or line.startswith("#") or "|" not in line:
            i += 1
            continue

        header_cells = split_markdown_table_row(line)
        header_lower = [cell.lower() for cell in header_cells]
        english_idx = -1
        russian_idx = -1
        notes_idx = -1

        for idx, header in enumerate(header_lower):
            if "english" in header:
                english_idx = idx
            elif "russian" in header or "русский" in header:
                russian_idx = idx
            elif "note" in header or "usage" in header or "правило" in header:
                notes_idx = idx

        if english_idx == -1 or russian_idx == -1:
            i += 1
            continue

        i += 1
        if i < len(lines) and is_markdown_table_separator(lines[i]):
            i += 1

        while i < len(lines):
            row = lines[i].strip()
            if not row or "|" not in row or row.startswith("#"):
                break
            if is_markdown_table_separator(row):
                i += 1
                continue

            cells = split_markdown_table_row(row)
            if len(cells) < max(english_idx, russian_idx) + 1:
                i += 1
                continue

            english = cells[english_idx] if english_idx < len(cells) else ""
            russian = cells[russian_idx] if russian_idx < len(cells) else ""
            notes = cells[notes_idx] if notes_idx != -1 and notes_idx < len(cells) else ""

            if english.strip() or russian.strip():
                entries.append(
                    {
                        "english": english.strip(),
                        "russian": russian.strip(),
                        "notes": notes.strip(),
                    }
                )
            i += 1

    return entries


def split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def is_markdown_table_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", line))
