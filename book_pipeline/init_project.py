"""Create a book project workspace."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from book_pipeline.common import (
    ensure_empty_or_force,
    initial_pipeline_state,
    now_iso,
    slugify,
    write_json,
)


PROJECT_DIRS = [
    "input",
    "source",
    "source/images",
    "chapters",
    "chunks",
    "translated",
    "review",
    "dist",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a new PDF translation project workspace."
    )
    parser.add_argument("--book-id", help="Stable project id. Defaults to title/PDF slug.")
    parser.add_argument("--title", help="Book title. Defaults to PDF filename stem.")
    parser.add_argument("--author", default="", help="Book author.")
    parser.add_argument("--pdf", required=True, help="Source PDF path.")
    parser.add_argument(
        "--projects-dir",
        default="projects",
        help="Parent directory for projects. Default: projects",
    )
    parser.add_argument(
        "--source-language",
        default="en",
        help="Source language code. Default: en",
    )
    parser.add_argument(
        "--target-language",
        default="ru",
        help="Target language code. Default: ru",
    )
    parser.add_argument(
        "--translator-contact",
        default="",
        help="Translator/editor contact shown in published reader.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reuse an existing project directory and overwrite metadata files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for option_name, language_code in (
        ("--source-language", args.source_language),
        ("--target-language", args.target_language),
    ):
        if not re.fullmatch(r"[a-z]{2}", language_code):
            print(
                f"{option_name} must be a 2-letter ISO language code, got: {language_code}",
                file=sys.stderr,
            )
            return 2

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(
            f"PDF not found: {pdf_path}\n"
            "Check the --pdf path and rerun init_project with an existing PDF file.",
            file=sys.stderr,
        )
        return 2
    if not pdf_path.is_file():
        print(
            f"PDF path is not a file: {pdf_path}\n"
            "Pass the path to a single PDF file, not a directory.",
            file=sys.stderr,
        )
        return 2

    title = args.title or pdf_path.stem
    book_id = args.book_id or slugify(title)
    project_dir = Path(args.projects_dir) / book_id

    try:
        ensure_empty_or_force(project_dir, args.force)
    except FileExistsError as error:
        print(error, file=sys.stderr)
        return 2

    for relative in PROJECT_DIRS:
        (project_dir / relative).mkdir(parents=True, exist_ok=True)

    input_pdf = project_dir / "input" / "book.pdf"
    if input_pdf.exists() and not args.force:
        print(f"{input_pdf} already exists. Re-run with --force to overwrite.", file=sys.stderr)
        return 2
    shutil.copy2(pdf_path, input_pdf)

    metadata = {
        "schema_version": 1,
        "book_id": book_id,
        "title": title,
        "author": args.author,
        "source_language": args.source_language,
        "target_language": args.target_language,
        "input_file": "input/book.pdf",
        "translator": {
            "contact": args.translator_contact,
        },
        "chapters": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    write_json(project_dir / "metadata.json", metadata)
    write_json(project_dir / "pipeline-state.json", initial_pipeline_state())
    write_glossary(project_dir / "glossary.md", title, args.force)
    write_review_notes(project_dir / "review" / "notes.md", title, args.force)

    print(f"Created project: {project_dir}")
    print(f"Next: .venv/bin/python -m book_pipeline.extract_opendataloader {input_pdf} -o {project_dir / 'source'}")
    return 0


def write_glossary(path: Path, title: str, force: bool) -> None:
    if path.exists() and not force:
        return
    path.write_text(
        f"# Глоссарий проекта\n\nКнига: **{title}**\n\n"
        "Добавляйте сюда термины, которые уточняют или расширяют корневой `TERMINOLOGY.md`.\n",
        encoding="utf-8",
    )


def write_review_notes(path: Path, title: str, force: bool) -> None:
    if path.exists() and not force:
        return
    path.write_text(
        f"# Заметки редактора\n\nКнига: **{title}**\n\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
