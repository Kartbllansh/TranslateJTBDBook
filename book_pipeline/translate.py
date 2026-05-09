"""Translate source chunks with glossary and neighbor context."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from book_pipeline.common import (
    get_chapter_by_id,
    now_iso,
    parse_glossary_table,
    read_json,
    update_pipeline_stage,
    write_json,
)


class TranslationMode(Enum):
    QUICK = "quick"
    NORMAL = "normal"
    REFINED = "refined"


@dataclass(frozen=True)
class GlossaryTerm:
    english: str
    russian: str
    notes: str
    source: str


@dataclass(frozen=True)
class Glossary:
    terms: dict[str, GlossaryTerm]
    conflicts: list[str]

    def entries(self) -> list[GlossaryTerm]:
        return sorted(self.terms.values(), key=lambda term: term.english.lower())

    def format_for_prompt(self) -> str:
        if not self.terms:
            return "No glossary entries."

        lines = []
        for term in self.entries():
            note_suffix = f" ({term.notes})" if term.notes else ""
            lines.append(f"- {term.english} -> {term.russian}{note_suffix}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TranslationContext:
    previous_chunk_summary: str | None
    next_chunk_summary: str | None
    chapter_title: str


@dataclass(frozen=True)
class SourceChunk:
    id: str
    chapter_id: str
    sequence: int
    source_path: Path
    translated_path: Path
    meta_path: Path
    content: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class TranslationResult:
    translated_text: str


@dataclass(frozen=True)
class TranslationRunResult:
    translated_count: int
    skipped_count: int
    error_count: int


class LLMService(Protocol):
    def translate(self, prompt: str) -> TranslationResult:
        """Translate prompt content and return final translated markdown."""


class OpenAIService:
    """Minimal OpenAI Chat Completions adapter using stdlib HTTP."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_env(cls) -> "OpenAIService":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Set it or choose another provider with "
                "--provider anthropic|local."
            )
        return cls(
            api_key=api_key,
            model=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )

    def translate(self, prompt: str) -> TranslationResult:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a careful literary and technical translator.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        response = post_json(
            f"{self.base_url}/chat/completions",
            payload,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        text = response["choices"][0]["message"]["content"]
        return TranslationResult(translated_text=text.strip() + "\n")


class AnthropicService:
    """Minimal Anthropic Messages API adapter using stdlib HTTP."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.anthropic.com/v1",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_env(cls) -> "AnthropicService":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Set it or choose another provider "
                "with --provider openai|local."
            )
        return cls(
            api_key=api_key,
            model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
            base_url=os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
        )

    def translate(self, prompt: str) -> TranslationResult:
        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = post_json(
            f"{self.base_url}/messages",
            payload,
            {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        text_parts = [
            item.get("text", "")
            for item in response.get("content", [])
            if item.get("type") == "text"
        ]
        return TranslationResult(translated_text="\n".join(text_parts).strip() + "\n")


class LocalLLMService:
    """Adapter for local HTTP endpoints that accept a JSON prompt."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    @classmethod
    def from_env(cls) -> "LocalLLMService":
        endpoint = (
            os.environ.get("BOOK_PIPELINE_LLM_ENDPOINT")
            or os.environ.get("LOCAL_LLM_ENDPOINT")
        )
        if not endpoint:
            raise ValueError(
                "Local provider requires BOOK_PIPELINE_LLM_ENDPOINT or LOCAL_LLM_ENDPOINT."
            )
        return cls(endpoint=endpoint)

    def translate(self, prompt: str) -> TranslationResult:
        response = post_json(
            self.endpoint,
            {"prompt": prompt},
            {"Content-Type": "application/json"},
        )
        translated_text = (
            response.get("translation")
            or response.get("text")
            or response.get("response")
        )
        if not isinstance(translated_text, str) or not translated_text.strip():
            raise ValueError(
                "Local endpoint response must include non-empty translation, text, or response."
            )
        return TranslationResult(translated_text=translated_text.strip() + "\n")


class EchoLLMService:
    """Testing adapter that writes the source section back with a marker."""

    def translate(self, prompt: str) -> TranslationResult:
        marker = "SOURCE TEXT:"
        source = prompt.split(marker, 1)[1].split("INSTRUCTIONS:", 1)[0].strip()
        return TranslationResult(translated_text=f"[ECHO TRANSLATION]\n\n{source}\n")


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP error {error.code}: {details}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"LLM connection failed: {error}") from error


def create_llm_service(provider: str | None = None) -> LLMService:
    selected = (provider or os.environ.get("BOOK_PIPELINE_LLM_PROVIDER") or "openai").lower()
    match selected:
        case "openai":
            return OpenAIService.from_env()
        case "anthropic":
            return AnthropicService.from_env()
        case "local":
            return LocalLLMService.from_env()
        case "echo":
            return EchoLLMService()
        case _:
            raise ValueError(
                f"Unsupported provider '{selected}'. Expected openai, anthropic, local, or echo."
            )


def load_glossary_file(path: Path, source_name: str) -> list[GlossaryTerm]:
    if not path.exists():
        return []

    entries = parse_glossary_table(path.read_text(encoding="utf-8"))
    return [
        GlossaryTerm(
            english=entry["english"],
            russian=entry["russian"],
            notes=entry.get("notes", ""),
            source=source_name,
        )
        for entry in entries
        if entry.get("english") and entry.get("russian")
    ]


def load_glossaries(project_dir: Path, root_dir: Path | None = None) -> Glossary:
    root = root_dir or Path.cwd()
    root_terms = load_glossary_file(root / "TERMINOLOGY.md", "root")
    project_terms = load_glossary_file(project_dir / "glossary.md", "project")

    merged: dict[str, GlossaryTerm] = {}
    conflicts: list[str] = []

    for term in root_terms:
        merged[term.english.lower()] = term

    for term in project_terms:
        key = term.english.lower()
        previous = merged.get(key)
        if previous and previous.russian != term.russian:
            conflicts.append(
                f"{term.english}: root='{previous.russian}' project='{term.russian}'"
            )
        merged[key] = term

    return Glossary(terms=merged, conflicts=conflicts)


def write_terminology_report(project_dir: Path, glossary: Glossary) -> None:
    report_path = project_dir / "review" / "terminology-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Terminology Report",
        "",
        f"Generated: {now_iso()}",
        "",
        f"Glossary entries loaded: {len(glossary.terms)}",
        "",
        "## Conflicts",
        "",
    ]
    if glossary.conflicts:
        lines.extend(f"- {conflict}" for conflict in glossary.conflicts)
    else:
        lines.append("No glossary conflicts detected.")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def discover_chunks(project_dir: Path) -> list[SourceChunk]:
    chunk_meta_paths = sorted((project_dir / "chunks").glob("*/*.meta.json"))
    chunks: list[SourceChunk] = []

    for meta_path in chunk_meta_paths:
        metadata = read_json(meta_path)
        chapter_id = metadata.get("chapter_id")
        sequence = int(metadata.get("sequence", 0))
        if not chapter_id or sequence <= 0:
            raise ValueError(f"Invalid chunk metadata: {meta_path}")

        source_path = project_dir / metadata.get(
            "source_path",
            f"chunks/{chapter_id}/{sequence:04d}.source.md",
        )
        translated_path = project_dir / metadata.get(
            "translated_path",
            f"chunks/{chapter_id}/{sequence:04d}.ru.md",
        )
        if not source_path.exists():
            raise FileNotFoundError(f"Missing source chunk: {source_path}")

        chunks.append(
            SourceChunk(
                id=metadata.get("chunk_id", f"{chapter_id}_{sequence:04d}"),
                chapter_id=chapter_id,
                sequence=sequence,
                source_path=source_path,
                translated_path=translated_path,
                meta_path=meta_path,
                content=source_path.read_text(encoding="utf-8"),
                metadata=metadata,
            )
        )

    return sorted(chunks, key=lambda chunk: (chunk.chapter_id, chunk.sequence))


def extract_first_paragraph(text: str, max_chars: int = 500) -> str | None:
    for paragraph in markdown_paragraphs(text):
        return truncate_context(paragraph, max_chars)
    return None


def extract_last_paragraph(text: str, max_chars: int = 500) -> str | None:
    paragraphs = markdown_paragraphs(text)
    if not paragraphs:
        return None
    return truncate_context(paragraphs[-1], max_chars)


def markdown_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    for raw in text.split("\n\n"):
        paragraph = raw.strip()
        if not paragraph:
            continue
        if paragraph.startswith("#") or paragraph.startswith("```"):
            continue
        paragraphs.append(" ".join(paragraph.split()))
    return paragraphs


def truncate_context(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def build_translation_context(
    chunks: list[SourceChunk],
    index: int,
    metadata: dict[str, Any],
) -> TranslationContext:
    chunk = chunks[index]
    chapter = get_chapter_by_id(metadata, chunk.chapter_id)
    chapter_title = chapter.get("title", chunk.chapter_id) if chapter else chunk.chapter_id

    previous_summary = None
    if index > 0 and chunks[index - 1].chapter_id == chunk.chapter_id:
        previous_summary = extract_last_paragraph(chunks[index - 1].content)

    next_summary = None
    if index + 1 < len(chunks) and chunks[index + 1].chapter_id == chunk.chapter_id:
        next_summary = extract_first_paragraph(chunks[index + 1].content)

    return TranslationContext(
        previous_chunk_summary=previous_summary,
        next_chunk_summary=next_summary,
        chapter_title=chapter_title,
    )


def build_translation_prompt(
    chunk: SourceChunk,
    glossary: Glossary,
    context: TranslationContext,
    mode: TranslationMode,
) -> str:
    mode_instruction = {
        TranslationMode.QUICK: "Translate directly and preserve markdown.",
        TranslationMode.NORMAL: (
            "Translate naturally, use the glossary consistently, and verify terminology."
        ),
        TranslationMode.REFINED: (
            "Translate, review the result for accuracy and style, then return a polished final version."
        ),
    }[mode]

    previous = context.previous_chunk_summary or "None (first chunk in chapter)."
    next_text = context.next_chunk_summary or "None (last chunk in chapter)."

    return f"""You are translating a technical business book from English to Russian.

GLOSSARY:
{glossary.format_for_prompt()}

CONTEXT (for reference only; do not translate this context):
Previous section: {previous}
Current chapter: {context.chapter_title}
Next section: {next_text}

SOURCE TEXT:
{chunk.content}

INSTRUCTIONS:
1. {mode_instruction}
2. Preserve markdown structure, headings, lists, quotes, links, and code fences.
3. Keep proper nouns, product names, code, and URLs unchanged unless the glossary says otherwise.
4. Return only the Russian translation of SOURCE TEXT.

TRANSLATION:
"""


def should_translate_chunk(chunk: SourceChunk, force: bool, retry_failed: bool) -> bool:
    status = chunk.metadata.get("status", "pending")
    if force:
        return True

    if chunk.translated_path.exists() and chunk.translated_path.read_text(encoding="utf-8").strip():
        return False

    if status in {"translated", "approved"}:
        return False

    if status == "error" and not retry_failed:
        return False

    return True


def translate_project(
    project_dir: Path,
    mode: TranslationMode = TranslationMode.NORMAL,
    force: bool = False,
    retry_failed: bool = False,
    llm_service: LLMService | None = None,
    provider: str | None = None,
) -> TranslationRunResult:
    metadata_path = project_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json not found: {metadata_path}")

    metadata = read_json(metadata_path)
    chunks = discover_chunks(project_dir)
    if not chunks:
        raise ValueError(
            "No chunks found. Run chunking first: "
            f"python -m book_pipeline.chunk --project-dir {project_dir}"
        )

    glossary = load_glossaries(project_dir)
    write_terminology_report(project_dir, glossary)
    service = llm_service or create_llm_service(provider)

    translated_count = 0
    skipped_count = 0
    errors: list[str] = []

    for index, chunk in enumerate(chunks):
        if not should_translate_chunk(chunk, force=force, retry_failed=retry_failed):
            skipped_count += 1
            continue

        try:
            context = build_translation_context(chunks, index, metadata)
            prompt = build_translation_prompt(chunk, glossary, context, mode)
            result = service.translate(prompt)
            chunk.translated_path.parent.mkdir(parents=True, exist_ok=True)
            chunk.translated_path.write_text(result.translated_text, encoding="utf-8")
            update_chunk_metadata(
                chunk.meta_path,
                {
                    "status": "translated",
                    "translated_at": now_iso(),
                    "translation_mode": mode.value,
                    "error": None,
                },
            )
            translated_count += 1
            print(f"Translated {chunk.id}")
        except Exception as error:
            message = f"{chunk.id}: {error}"
            errors.append(message)
            update_chunk_metadata(
                chunk.meta_path,
                {
                    "status": "error",
                    "error": str(error),
                    "translation_mode": mode.value,
                },
            )
            print(f"Translation failed for {chunk.id}: {error}", file=sys.stderr)

    refreshed_chunks = discover_chunks(project_dir)
    update_chapter_translation_statuses(project_dir, metadata, refreshed_chunks)

    if errors:
        write_translation_errors(project_dir, errors)
        update_pipeline_stage(project_dir, "translate", "error")
    elif all(is_chunk_translated(chunk) for chunk in refreshed_chunks):
        update_pipeline_stage(project_dir, "translate", "done")

    return TranslationRunResult(
        translated_count=translated_count,
        skipped_count=skipped_count,
        error_count=len(errors),
    )


def update_chunk_metadata(meta_path: Path, updates: dict[str, Any]) -> None:
    metadata = read_json(meta_path)
    metadata.update(updates)
    write_json(meta_path, metadata)


def update_chapter_translation_statuses(
    project_dir: Path,
    metadata: dict[str, Any],
    chunks: list[SourceChunk],
) -> None:
    chunks_by_chapter: dict[str, list[SourceChunk]] = {}
    for chunk in chunks:
        chunks_by_chapter.setdefault(chunk.chapter_id, []).append(chunk)

    for chapter in metadata.get("chapters", []):
        chapter_id = chapter.get("id")
        chapter_chunks = chunks_by_chapter.get(chapter_id, [])
        if not chapter_chunks:
            continue

        statuses = {chunk.metadata.get("status", "pending") for chunk in chapter_chunks}
        if all(is_chunk_translated(chunk) for chunk in chapter_chunks):
            chapter["status"] = "translated"
        elif "error" in statuses:
            chapter["status"] = "error"
        else:
            chapter["status"] = "chunked"

    metadata["updated_at"] = now_iso()
    write_json(project_dir / "metadata.json", metadata)


def is_chunk_translated(chunk: SourceChunk) -> bool:
    if chunk.metadata.get("status") in {"translated", "approved"}:
        return True
    return (
        chunk.translated_path.exists()
        and bool(chunk.translated_path.read_text(encoding="utf-8").strip())
    )


def write_translation_errors(project_dir: Path, errors: list[str]) -> None:
    report_path = project_dir / "review" / "translation-errors.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Translation Errors",
        "",
        f"Generated: {now_iso()}",
        "",
    ]
    lines.extend(f"- {error}" for error in errors)
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Translate pending source chunks.")
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project directory containing chunks/ and metadata.json.",
    )
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in TranslationMode],
        default=TranslationMode.NORMAL.value,
        help="Translation mode. Default: normal.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "local", "echo"],
        default=None,
        help="LLM provider. Default: BOOK_PIPELINE_LLM_PROVIDER or openai.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing translated chunk files.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry chunks whose metadata status is error.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)

    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2

    try:
        result = translate_project(
            project_dir=project_dir,
            mode=TranslationMode(args.mode),
            force=args.force,
            retry_failed=args.retry_failed,
            provider=args.provider,
        )
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    print(
        "Translation complete: "
        f"{result.translated_count} translated, "
        f"{result.skipped_count} skipped, "
        f"{result.error_count} errors"
    )
    print(f"Next: python -m book_pipeline.assemble --project-dir {project_dir}")
    return 1 if result.error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
