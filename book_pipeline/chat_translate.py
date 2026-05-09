"""Manage manual/chat-based translation of source chunks."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from book_pipeline.common import now_iso, read_json, update_pipeline_stage, write_json
from book_pipeline.translate import (
    SourceChunk,
    TranslationMode,
    build_translation_context,
    build_translation_prompt,
    discover_chunks,
    is_chunk_translated,
    load_glossaries,
    should_translate_chunk,
    update_chapter_translation_statuses,
)


@dataclass(frozen=True)
class ChatTranslationStatus:
    total: int
    translated: int
    pending: int
    error: int
    next_chunk_id: str | None


def get_chat_translation_status(
    project_dir: Path,
    retry_failed: bool = False,
) -> ChatTranslationStatus:
    chunks = discover_chunks(project_dir)
    pending = pending_chat_chunks(project_dir, retry_failed=retry_failed)
    translated = sum(1 for chunk in chunks if is_chunk_translated(chunk))
    error = sum(1 for chunk in chunks if chunk.metadata.get("status") == "error")
    return ChatTranslationStatus(
        total=len(chunks),
        translated=translated,
        pending=len(pending),
        error=error,
        next_chunk_id=pending[0].id if pending else None,
    )


def pending_chat_chunks(
    project_dir: Path,
    retry_failed: bool = False,
) -> list[SourceChunk]:
    return [
        chunk
        for chunk in discover_chunks(project_dir)
        if should_translate_chunk(chunk, force=False, retry_failed=retry_failed)
    ]


def write_next_chat_prompt(
    project_dir: Path,
    mode: TranslationMode = TranslationMode.NORMAL,
    chunk_id: str | None = None,
    retry_failed: bool = False,
    output_path: Path | None = None,
) -> Path:
    metadata_path = project_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json not found: {metadata_path}")

    metadata = read_json(metadata_path)
    chunks = discover_chunks(project_dir)
    if not chunks:
        raise ValueError(
            f"No chunks found in {project_dir / 'chunks'}. "
            "Run: python -m book_pipeline.chunk --project-dir <project-dir>"
        )

    selected = select_chat_chunk(chunks, chunk_id, retry_failed=retry_failed)
    glossary = load_glossaries(project_dir)
    context = build_translation_context(chunks, chunks.index(selected), metadata)
    prompt = build_translation_prompt(selected, glossary, context, mode)

    packet = build_chat_prompt_packet(project_dir, selected, prompt)
    target = output_path or project_dir / "review" / "chat-translation" / "next.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(packet, encoding="utf-8")
    return target


def select_chat_chunk(
    chunks: list[SourceChunk],
    chunk_id: str | None,
    retry_failed: bool = False,
) -> SourceChunk:
    if chunk_id:
        for chunk in chunks:
            if chunk.id == chunk_id:
                return chunk
        raise ValueError(f"Chunk not found: {chunk_id}")

    for chunk in chunks:
        if should_translate_chunk(chunk, force=False, retry_failed=retry_failed):
            return chunk

    raise ValueError("No pending chunks found. The project appears fully translated.")


def build_chat_prompt_packet(
    project_dir: Path,
    chunk: SourceChunk,
    prompt: str,
) -> str:
    return f"""# Chat Translation Packet

Project: `{project_dir}`
Chunk: `{chunk.id}`
Source: `{chunk.source_path}`
Target: `{chunk.translated_path}`

Translate this chunk in chat. Return only the translated markdown content.

After translation, save it with:

```powershell
python -m book_pipeline.chat_translate save --project-dir "{project_dir}" --chunk-id {chunk.id} --file path\\to\\translated.md
```

---

{prompt}
"""


def save_chat_translation(
    project_dir: Path,
    chunk_id: str,
    translated_text: str,
    mode: str = "chat",
) -> SourceChunk:
    chunk = find_chunk(project_dir, chunk_id)
    if not translated_text.strip():
        raise ValueError("Translated text is empty; refusing to mark chunk translated.")

    chunk.translated_path.parent.mkdir(parents=True, exist_ok=True)
    chunk.translated_path.write_text(ensure_trailing_newline(translated_text), encoding="utf-8")
    metadata = read_json(chunk.meta_path)
    metadata.update(
        {
            "status": "translated",
            "translated_at": now_iso(),
            "translation_mode": mode,
            "error": None,
        }
    )
    write_json(chunk.meta_path, metadata)

    project_metadata = read_json(project_dir / "metadata.json")
    refreshed_chunks = discover_chunks(project_dir)
    update_chapter_translation_statuses(project_dir, project_metadata, refreshed_chunks)
    if all(is_chunk_translated(item) for item in refreshed_chunks):
        update_pipeline_stage(project_dir, "translate", "done")

    return find_chunk(project_dir, chunk_id)


def find_chunk(project_dir: Path, chunk_id: str) -> SourceChunk:
    for chunk in discover_chunks(project_dir):
        if chunk.id == chunk_id:
            return chunk
    raise ValueError(f"Chunk not found: {chunk_id}")


def ensure_trailing_newline(text: str) -> str:
    return text if text.endswith("\n") else f"{text}\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and save translations made through a chat session."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Show chat translation progress.")
    status.add_argument("--project-dir", required=True)
    status.add_argument("--retry-failed", action="store_true")

    next_prompt = subparsers.add_parser("next", help="Write prompt packet for next chunk.")
    next_prompt.add_argument("--project-dir", required=True)
    next_prompt.add_argument("--chunk-id")
    next_prompt.add_argument("--retry-failed", action="store_true")
    next_prompt.add_argument(
        "--mode",
        choices=[mode.value for mode in TranslationMode],
        default=TranslationMode.NORMAL.value,
    )
    next_prompt.add_argument(
        "--output",
        help="Prompt packet path. Default: <project>/review/chat-translation/next.md",
    )

    save = subparsers.add_parser("save", help="Save translated markdown for a chunk.")
    save.add_argument("--project-dir", required=True)
    save.add_argument("--chunk-id", required=True)
    save.add_argument("--file", help="Markdown file containing translated content. Reads stdin if omitted.")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)
    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2

    try:
        if args.command == "status":
            status = get_chat_translation_status(project_dir, retry_failed=args.retry_failed)
            print(f"Chunks: {status.translated}/{status.total} translated")
            print(f"Pending: {status.pending}")
            print(f"Errors: {status.error}")
            print(f"Next: {status.next_chunk_id or '-'}")
            return 0

        if args.command == "next":
            output_path = Path(args.output) if args.output else None
            packet_path = write_next_chat_prompt(
                project_dir=project_dir,
                mode=TranslationMode(args.mode),
                chunk_id=args.chunk_id,
                retry_failed=args.retry_failed,
                output_path=output_path,
            )
            print(f"Prompt packet written: {packet_path}")
            return 0

        if args.command == "save":
            if args.file:
                translated_text = Path(args.file).read_text(encoding="utf-8")
            else:
                translated_text = sys.stdin.read()
            chunk = save_chat_translation(project_dir, args.chunk_id, translated_text)
            print(f"Saved translation: {chunk.translated_path}")
            return 0

    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    print(f"Unsupported command: {args.command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
