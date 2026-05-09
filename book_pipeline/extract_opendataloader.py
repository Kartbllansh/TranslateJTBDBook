"""Extract book source files from PDF with opendataloader-pdf.

This module is intentionally small: opendataloader-pdf owns PDF parsing, while
the rest of this repository owns book normalization, translation, review, and
publishing.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from book_pipeline.common import read_json, update_pipeline_stage, write_json


DEFAULT_FORMAT = "markdown,json"


@dataclass(frozen=True)
class ExtractionOptions:
    format: str = DEFAULT_FORMAT
    image_output: str = "external"
    use_struct_tree: bool = False
    pages: str | None = None
    use_cli: bool = False
    hybrid: str | None = None
    sanitize: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract Markdown/JSON from PDF using opendataloader-pdf."
    )
    parser.add_argument(
        "input",
        nargs="*",
        help="PDF file(s) or directories to extract. Optional with --project-dir.",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Project directory. If set, defaults input to input/book.pdf and output to source/.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=None,
        help="Directory for extracted files. Default: <project-dir>/source or projects/imported/source",
    )
    parser.add_argument(
        "--format",
        default=DEFAULT_FORMAT,
        help=f"opendataloader output format. Default: {DEFAULT_FORMAT}",
    )
    parser.add_argument(
        "--hybrid",
        default=None,
        help="Hybrid backend name, for example: docling-fast.",
    )
    parser.add_argument(
        "--pages",
        default=None,
        help='Pages to extract, for example: "1,3,5-7". Default: all pages.',
    )
    parser.add_argument(
        "--image-output",
        default="external",
        choices=["off", "embedded", "external"],
        help="How to store extracted images. Default: external.",
    )
    parser.add_argument(
        "--use-struct-tree",
        action="store_true",
        help="Use native PDF structure tags when available.",
    )
    parser.add_argument(
        "--sanitize",
        action="store_true",
        help="Sanitize emails, phone numbers, IPs, credit cards, and URLs.",
    )
    parser.add_argument(
        "--use-cli",
        action="store_true",
        help="Use the opendataloader-pdf CLI instead of the Python API.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir) if args.project_dir else None
    input_paths = resolve_input_paths(args.input, project_dir)
    if not input_paths:
        print(
            "No input PDF provided.\n"
            "Pass a PDF path directly or use --project-dir so the command can read "
            "<project-dir>/input/book.pdf.",
            file=sys.stderr,
        )
        return 2

    output_dir = resolve_output_dir(args.output_dir, project_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not shutil.which("java"):
        print(
            "Java was not found in PATH. opendataloader-pdf requires Java 11+.\n"
            "Install a JDK first, then verify with:\n"
            "  java -version",
            file=sys.stderr,
        )
        return 2

    if args.use_cli:
        result = run_cli(args, input_paths, output_dir)
    else:
        result = run_python_api(args, input_paths, output_dir)

    if result == 0:
        if args.image_output == "external":
            try:
                image_count = record_extracted_images(output_dir)
                if image_count:
                    print(f"Recorded {image_count} extracted image reference(s)")
            except Exception as error:
                print(f"Warning: failed to record extracted images: {error}", file=sys.stderr)
        if project_dir:
            update_pipeline_stage(project_dir, "extract", "done")

    return result


def extract_project(
    project_dir: Path,
    options: ExtractionOptions | None = None,
) -> None:
    options = options or ExtractionOptions()
    input_paths = resolve_input_paths([], project_dir)
    output_dir = resolve_output_dir(None, project_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_paths or not Path(input_paths[0]).exists():
        raise FileNotFoundError(
            f"Project input PDF not found: {project_dir / 'input' / 'book.pdf'}"
        )

    if not shutil.which("java"):
        raise ValueError(
            "Java was not found in PATH. opendataloader-pdf requires Java 11+."
        )

    args = argparse.Namespace(
        format=options.format,
        image_output=options.image_output,
        use_struct_tree=options.use_struct_tree,
        sanitize=options.sanitize,
        hybrid=options.hybrid,
        pages=options.pages,
        use_cli=options.use_cli,
    )
    result = run_cli(args, input_paths, output_dir) if options.use_cli else run_python_api(args, input_paths, output_dir)
    if result != 0:
        raise RuntimeError(f"PDF extraction failed with exit code {result}")

    if options.image_output == "external":
        record_extracted_images(output_dir)
    update_pipeline_stage(project_dir, "extract", "done")


def resolve_input_paths(raw_inputs: list[str], project_dir: Path | None) -> list[str]:
    if raw_inputs:
        return [str(Path(item)) for item in raw_inputs]
    if project_dir:
        return [str(project_dir / "input" / "book.pdf")]
    return []


def resolve_output_dir(raw_output_dir: str | None, project_dir: Path | None) -> Path:
    if raw_output_dir:
        return Path(raw_output_dir)
    if project_dir:
        return project_dir / "source"
    return Path("projects/imported/source")


def run_python_api(args: argparse.Namespace, input_paths: list[str], output_dir: Path) -> int:
    try:
        import opendataloader_pdf
    except ModuleNotFoundError:
        print(
            "opendataloader-pdf is not installed. Install prerequisites first:\n"
            "  python3 -m venv .venv\n"
            "  .venv/bin/python -m pip install -r requirements.txt\n"
            "  java -version  # Java 11+ is required by opendataloader-pdf\n\n"
            "You can also retry with --use-cli after installing the CLI.",
            file=sys.stderr,
        )
        return 2

    options = {
        "input_path": input_paths,
        "output_dir": str(output_dir),
        "format": args.format,
        "image_output": args.image_output,
        "use_struct_tree": args.use_struct_tree,
        "sanitize": args.sanitize,
    }
    if args.hybrid:
        options["hybrid"] = args.hybrid
    if args.pages:
        options["pages"] = args.pages

    opendataloader_pdf.convert(**options)
    print(f"Extracted {len(input_paths)} input(s) into {output_dir}")
    return 0


def run_cli(args: argparse.Namespace, input_paths: list[str], output_dir: Path) -> int:
    executable = shutil.which("opendataloader-pdf")
    if not executable:
        print(
            "opendataloader-pdf CLI was not found in PATH. Install it with:\n"
            "  .venv/bin/python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 2

    command = [
        executable,
        "-f",
        args.format,
        "--output-dir",
        str(output_dir),
        "--image-output",
        args.image_output,
    ]
    if args.hybrid:
        command.extend(["--hybrid", args.hybrid])
    if args.pages:
        command.extend(["--pages", args.pages])
    if args.use_struct_tree:
        command.append("--use-struct-tree")
    if args.sanitize:
        command.append("--sanitize")
    command.extend(input_paths)

    completed = subprocess.run(command, check=False)
    return completed.returncode


def record_extracted_images(output_dir: Path) -> int:
    """Record externally extracted images in extraction metadata."""

    images_dir = output_dir / "images"
    if not images_dir.exists():
        return 0

    images = [
        {
            "filename": path.name,
            "path": str(Path("images") / path.relative_to(images_dir)).replace("\\", "/"),
        }
        for path in sorted(images_dir.rglob("*"))
        if path.is_file()
    ]
    if not images:
        return 0

    metadata_path = resolve_extraction_metadata_path(output_dir)
    metadata = read_json(metadata_path) if metadata_path.exists() else {}
    if not isinstance(metadata, dict):
        metadata = {"opendataloader_payload": metadata}

    book_pipeline_meta = metadata.setdefault("book_pipeline", {})
    book_pipeline_meta["images"] = images
    book_pipeline_meta["image_count"] = len(images)
    write_json(metadata_path, metadata)
    return len(images)


def resolve_extraction_metadata_path(output_dir: Path) -> Path:
    preferred = output_dir / "extracted.json"
    if preferred.exists():
        return preferred
    json_files = sorted(output_dir.glob("*.json"))
    if json_files:
        return json_files[0]
    return preferred


if __name__ == "__main__":
    raise SystemExit(main())
