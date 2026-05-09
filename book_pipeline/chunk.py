"""Split chapter markdown files into translation-sized chunks."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from book_pipeline.common import (
    BlockType,
    MarkdownBlock,
    check_disk_space,
    now_iso,
    parse_markdown_blocks,
    read_json,
    split_list_items,
    update_pipeline_stage,
    write_json,
)
from book_pipeline.split_chapters import Chapter


DEFAULT_MAX_CHARS = 6000


@dataclass(frozen=True)
class Chunk:
    """A source chunk ready for translation."""

    id: str
    chapter_id: str
    sequence: int
    content: str
    char_count: int
    status: str = "pending"


def validate_max_chars(max_chars: int) -> None:
    if max_chars <= 0:
        raise ValueError("--max-chars must be a positive integer")


def chunk_chapter(chapter: Chapter, max_chars: int = DEFAULT_MAX_CHARS) -> list[Chunk]:
    """Split a chapter into chunks while preserving markdown structure."""

    validate_max_chars(max_chars)
    units = build_chunk_units(parse_markdown_blocks(chapter.content), max_chars)
    chunk_contents = pack_units(units, max_chars)

    return [
        Chunk(
            id=f"{chapter.id}_{sequence:04d}",
            chapter_id=chapter.id,
            sequence=sequence,
            content=content,
            char_count=len(content),
        )
        for sequence, content in enumerate(chunk_contents, start=1)
    ]


def build_chunk_units(blocks: list[MarkdownBlock], max_chars: int) -> list[str]:
    """Convert parsed markdown blocks into indivisible chunking units."""

    units: list[str] = []
    index = 0

    while index < len(blocks):
        block = blocks[index]

        if block.type == BlockType.HEADING:
            if (
                index + 1 < len(blocks)
                and blocks[index + 1].type == BlockType.PARAGRAPH
            ):
                paragraph_units = split_paragraph(blocks[index + 1].content, max_chars)
                if paragraph_units:
                    units.append(join_blocks([block.content, paragraph_units[0]]))
                    units.extend(paragraph_units[1:])
                else:
                    units.append(block.content.strip())
                index += 2
                continue

            units.append(block.content.strip())
            index += 1
            continue

        if block.type == BlockType.LIST and len(block.content) > max_chars:
            units.extend(item.strip() for item in split_list_items(block) if item.strip())
            index += 1
            continue

        if block.type == BlockType.PARAGRAPH and len(block.content) > max_chars:
            units.extend(split_paragraph(block.content, max_chars))
            index += 1
            continue

        units.append(block.content.strip())
        index += 1

    return [unit for unit in units if unit]


def split_paragraph(content: str, max_chars: int) -> list[str]:
    """Split an oversized paragraph on word boundaries."""

    text = " ".join(content.split())
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    words = text.split(" ")
    parts: list[str] = []
    current: list[str] = []

    for word in words:
        if not current:
            current.append(word)
            continue

        candidate = " ".join([*current, word])
        if len(candidate) > max_chars:
            parts.append(" ".join(current))
            current = [word]
        else:
            current.append(word)

    if current:
        parts.append(" ".join(current))

    return parts


def pack_units(units: list[str], max_chars: int) -> list[str]:
    """Pack chunking units into chunk contents."""

    chunks: list[str] = []
    current: list[str] = []

    for unit in units:
        unit = unit.strip()
        if not unit:
            continue

        if len(unit) > max_chars:
            if current:
                chunks.append(join_blocks(current))
                current = []
            chunks.append(unit)
            continue

        candidate = join_blocks([*current, unit])
        if current and len(candidate) > max_chars:
            chunks.append(join_blocks(current))
            current = [unit]
        else:
            current.append(unit)

    if current:
        chunks.append(join_blocks(current))

    return [ensure_trailing_newline(chunk) for chunk in chunks]


def join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(block.strip() for block in blocks if block.strip())


def ensure_trailing_newline(content: str) -> str:
    return content if content.endswith("\n") else f"{content}\n"


def load_project_chapters(project_dir: Path) -> tuple[dict[str, Any], list[Chapter]]:
    metadata_path = project_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"metadata.json not found at {metadata_path}. "
            "Run project initialization and chapter splitting first."
        )

    metadata = read_json(metadata_path)
    chapter_entries = metadata.get("chapters", [])
    if not chapter_entries:
        raise ValueError(
            "No chapters found in metadata.json. "
            "Run chapter splitting first: python -m book_pipeline.split_chapters --project-dir "
            f"{project_dir}"
        )

    chapters: list[Chapter] = []
    for entry in chapter_entries:
        chapter_id = entry.get("id")
        if not chapter_id:
            raise ValueError(f"Chapter metadata entry is missing id: {entry}")

        source_path = project_dir / entry.get("source_path", f"chapters/{chapter_id}.md")
        if not source_path.exists():
            raise FileNotFoundError(
                f"Chapter source not found: {source_path}. "
                "Re-run chapter splitting or fix metadata.json."
            )

        content = source_path.read_text(encoding="utf-8")
        chapters.append(
            Chapter(
                id=chapter_id,
                title=entry.get("title", chapter_id),
                content=content,
                start_line=1,
                end_line=len(content.splitlines()) or 1,
            )
        )

    return metadata, chapters


def write_project_chunks(
    project_dir: Path,
    max_chars: int = DEFAULT_MAX_CHARS,
    force: bool = False,
) -> list[Chunk]:
    """Chunk every chapter in a project and update metadata."""

    validate_max_chars(max_chars)
    metadata, chapters = load_project_chapters(project_dir)
    chunks_root = project_dir / "chunks"
    chunks_root.mkdir(parents=True, exist_ok=True)
    check_disk_space(
        chunks_root,
        sum(len(chapter.content.encode("utf-8")) for chapter in chapters) * 3 + 1024,
    )

    all_chunks: list[Chunk] = []
    chapter_counts: dict[str, int] = {}

    for chapter in chapters:
        chapter_chunks = chunk_chapter(chapter, max_chars=max_chars)
        chapter_dir = chunks_root / chapter.id
        ensure_chunk_dir_writable(chapter_dir, force)
        chapter_dir.mkdir(parents=True, exist_ok=True)

        if force:
            clear_generated_chunk_files(chapter_dir)

        for chunk in chapter_chunks:
            sequence_name = f"{chunk.sequence:04d}"
            source_path = chapter_dir / f"{sequence_name}.source.md"
            translated_path = chapter_dir / f"{sequence_name}.ru.md"
            meta_path = chapter_dir / f"{sequence_name}.meta.json"

            source_path.write_text(chunk.content, encoding="utf-8")
            translated_path.write_text("", encoding="utf-8")
            write_json(meta_path, build_chunk_metadata(chunk))

        chapter_counts[chapter.id] = len(chapter_chunks)
        all_chunks.extend(chapter_chunks)
        print(f"Chunked {chapter.id}: {len(chapter_chunks)} chunk(s)")

    update_chapter_counts(metadata, chapter_counts)
    write_json(project_dir / "metadata.json", metadata)
    update_pipeline_stage(project_dir, "chunk", "done")
    return all_chunks


def ensure_chunk_dir_writable(chapter_dir: Path, force: bool) -> None:
    if force or not chapter_dir.exists():
        return

    generated_files = list(chapter_dir.glob("*.source.md"))
    generated_files.extend(chapter_dir.glob("*.ru.md"))
    generated_files.extend(chapter_dir.glob("*.meta.json"))
    if generated_files:
        file_list = ", ".join(str(path) for path in sorted(generated_files))
        raise FileExistsError(
            f"Chunk files already exist for {chapter_dir.name}: {file_list}\n"
            "Re-run with --force to regenerate chunks and empty translation files."
        )


def clear_generated_chunk_files(chapter_dir: Path) -> None:
    for pattern in ("*.source.md", "*.ru.md", "*.meta.json"):
        for path in chapter_dir.glob(pattern):
            path.unlink()


def build_chunk_metadata(chunk: Chunk) -> dict[str, Any]:
    sequence_name = f"{chunk.sequence:04d}"
    return {
        "chunk_id": chunk.id,
        "chapter_id": chunk.chapter_id,
        "sequence": chunk.sequence,
        "char_count": chunk.char_count,
        "status": chunk.status,
        "source_path": f"chunks/{chunk.chapter_id}/{sequence_name}.source.md",
        "translated_path": f"chunks/{chunk.chapter_id}/{sequence_name}.ru.md",
        "created_at": now_iso(),
        "translated_at": None,
        "translation_mode": None,
        "error": None,
    }


def update_chapter_counts(
    metadata: dict[str, Any],
    chapter_counts: dict[str, int],
) -> None:
    for chapter in metadata.get("chapters", []):
        chapter_id = chapter.get("id")
        if chapter_id in chapter_counts:
            chapter["chunk_count"] = chapter_counts[chapter_id]
            chapter["status"] = "chunked"

    metadata["updated_at"] = now_iso()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split chapter markdown files into translation-sized chunks."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project directory containing chapters/ and metadata.json.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help=f"Maximum characters per chunk. Default: {DEFAULT_MAX_CHARS}.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate chunks and overwrite existing empty translation files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)

    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2

    try:
        chunks = write_project_chunks(
            project_dir=project_dir,
            max_chars=args.max_chars,
            force=args.force,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    print(f"Created {len(chunks)} chunk(s)")
    print(f"Next: python -m book_pipeline.translate --project-dir {project_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
