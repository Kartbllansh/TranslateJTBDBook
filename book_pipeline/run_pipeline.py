"""Orchestrate pipeline stages for a book project."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from book_pipeline.assemble import assemble_project
from book_pipeline.chat_translate import get_chat_translation_status, write_next_chat_prompt
from book_pipeline.chunk import write_project_chunks
from book_pipeline.extract_opendataloader import ExtractionOptions, extract_project
from book_pipeline.normalize import normalize_project
from book_pipeline.publish import publish_project
from book_pipeline.review import review_project
from book_pipeline.split_chapters import split_project_chapters
from book_pipeline.translate import TranslationMode, translate_project


@dataclass(frozen=True)
class PipelineRunResult:
    completed_stages: list[str]
    stopped_at: str | None


def run_pipeline(
    project_dir: Path,
    until: str = "publish",
    translation_method: str = "chat",
    mode: TranslationMode = TranslationMode.NORMAL,
    provider: str | None = None,
    max_chars: int = 6000,
    force: bool = False,
    pages: str | None = None,
) -> PipelineRunResult:
    completed: list[str] = []

    for stage in stages_until(until):
        if stage == "extract":
            extract_project(
                project_dir,
                ExtractionOptions(pages=pages, image_output="external"),
            )
        elif stage == "normalize":
            normalize_project(project_dir, force=force)
        elif stage == "split":
            split_project_chapters(project_dir, mode="auto", force=force)
        elif stage == "chunk":
            write_project_chunks(project_dir, max_chars=max_chars, force=force)
        elif stage == "translate":
            if translation_method == "chat":
                status = get_chat_translation_status(project_dir)
                if status.pending:
                    packet = write_next_chat_prompt(project_dir, mode=mode)
                    print(f"Chat translation required. Prompt packet: {packet}")
                    print(
                        "Translate this chunk in chat, save it with "
                        "`python -m book_pipeline.chat_translate save`, then rerun this command."
                    )
                    return PipelineRunResult(completed_stages=completed, stopped_at="translate")
                print("All chunks are already translated; continuing.")
            else:
                translate_project(project_dir, mode=mode, provider=provider, force=force)
        elif stage == "assemble":
            assemble_project(project_dir, force=force)
        elif stage == "review":
            review_project(project_dir)
        elif stage == "publish":
            publish_project(project_dir, standalone=True)
        else:
            raise ValueError(f"Unsupported stage: {stage}")
        completed.append(stage)

    return PipelineRunResult(completed_stages=completed, stopped_at=None)


def stages_until(until: str) -> list[str]:
    stages = ["extract", "normalize", "split", "chunk", "translate", "assemble", "review", "publish"]
    if until not in stages:
        raise ValueError(f"Unsupported --until stage: {until}. Expected one of: {', '.join(stages)}")
    return stages[: stages.index(until) + 1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pipeline stages in order for an existing project."
    )
    parser.add_argument("--project-dir", required=True)
    parser.add_argument(
        "--until",
        choices=["extract", "normalize", "split", "chunk", "translate", "assemble", "review", "publish"],
        default="publish",
    )
    parser.add_argument(
        "--translation-method",
        choices=["chat", "api", "echo"],
        default="chat",
        help="chat stops and writes prompt packets; api uses --provider; echo smoke-tests translation.",
    )
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in TranslationMode],
        default=TranslationMode.NORMAL.value,
    )
    parser.add_argument("--provider", choices=["openai", "anthropic", "local"])
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--pages", help='Optional extraction page range, for example "1-10".')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)
    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2

    provider = args.provider
    translation_method = args.translation_method
    if translation_method == "echo":
        provider = "echo"
        translation_method = "api"

    try:
        result = run_pipeline(
            project_dir=project_dir,
            until=args.until,
            translation_method=translation_method,
            mode=TranslationMode(args.mode),
            provider=provider,
            max_chars=args.max_chars,
            force=args.force,
            pages=args.pages,
        )
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    if result.stopped_at:
        print(f"Pipeline paused at: {result.stopped_at}")
        return 0

    print(f"Pipeline complete through: {args.until}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
