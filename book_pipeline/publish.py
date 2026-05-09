"""Publish translated projects as reader assets and standalone HTML."""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from book_pipeline.common import check_disk_space, now_iso, read_json, update_pipeline_stage


MAX_STANDALONE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class PublishResult:
    reader_dir: Path
    standalone_path: Path | None
    warnings: list[str]


def publish_project(project_dir: Path, standalone: bool = True) -> PublishResult:
    metadata_path = project_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.json not found: {metadata_path}")

    metadata = read_json(metadata_path)
    reader_template_dir = Path.cwd() / "reader"
    if not reader_template_dir.exists():
        raise FileNotFoundError(f"Reader template directory not found: {reader_template_dir}")

    dist_dir = project_dir / "dist"
    reader_out_dir = dist_dir / "reader"
    reader_out_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    chapters = load_published_chapters(project_dir, metadata, embed_images=False)
    copy_reader_template(reader_template_dir, reader_out_dir)
    copy_project_images(project_dir, reader_out_dir)

    template_html = (reader_template_dir / "index.html").read_text(encoding="utf-8")
    reader_html = inject_reader_template(template_html, metadata, chapters, inline_script=False)
    (reader_out_dir / "index.html").write_text(reader_html, encoding="utf-8")

    standalone_path = None
    if standalone:
        standalone_chapters = load_published_chapters(project_dir, metadata, embed_images=True)
        css = (reader_template_dir / "styles.css").read_text(encoding="utf-8")
        js = (reader_template_dir / "app.js").read_text(encoding="utf-8")
        cover_path = reader_template_dir / "cover.png"
        standalone_html = generate_standalone_html(
            template_html=template_html,
            css=css,
            js=js,
            chapters=standalone_chapters,
            metadata=metadata,
            cover_image=cover_path if cover_path.exists() else None,
        )
        size = len(standalone_html.encode("utf-8"))
        if size > MAX_STANDALONE_BYTES:
            warnings.append(
                f"Standalone HTML is larger than 10MB: {format_bytes(size)}"
            )
        standalone_path = dist_dir / f"{metadata.get('book_id', project_dir.name)}-ru.html"
        check_disk_space(standalone_path, size + 1024)
        standalone_path.write_text(standalone_html, encoding="utf-8")

    update_pipeline_stage(project_dir, "publish", "done")
    return PublishResult(
        reader_dir=reader_out_dir,
        standalone_path=standalone_path,
        warnings=warnings,
    )


def load_published_chapters(
    project_dir: Path,
    metadata: dict[str, Any],
    embed_images: bool = False,
) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    for index, chapter in enumerate(metadata.get("chapters", []), start=1):
        chapter_id = chapter.get("id")
        if not chapter_id:
            continue

        translated_path = project_dir / chapter.get(
            "translated_path",
            f"translated/{chapter_id}.md",
        )
        if not translated_path.exists():
            raise FileNotFoundError(f"Translated chapter not found: {translated_path}")

        raw = translated_path.read_text(encoding="utf-8")
        if embed_images:
            raw = embed_markdown_images(raw, project_dir, translated_path.parent)

        title = extract_title(raw, fallback=chapter.get("title", chapter_id))
        words = count_words(raw)
        chapters.append(
            {
                "file": f"{chapter_id}.md",
                "id": chapter_id,
                "label": chapter_label(chapter_id, index),
                "kind": chapter_kind(chapter_id),
                "title": title,
                "words": words,
                "raw": raw,
            }
        )
    return chapters


def copy_reader_template(source_dir: Path, target_dir: Path) -> None:
    for path in source_dir.iterdir():
        if path.is_file():
            shutil.copy2(path, target_dir / path.name)


def copy_project_images(project_dir: Path, reader_out_dir: Path) -> None:
    source_images = project_dir / "source" / "images"
    if not source_images.exists():
        return

    target_images = reader_out_dir / "images"
    target_images.mkdir(parents=True, exist_ok=True)
    for path in source_images.rglob("*"):
        if path.is_file():
            relative = path.relative_to(source_images)
            destination = target_images / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def inject_reader_template(
    template_html: str,
    metadata: dict[str, Any],
    chapters: list[dict[str, Any]],
    inline_script: bool,
    js: str | None = None,
) -> str:
    title = str(metadata.get("title", "Translated Book"))
    author = str(metadata.get("author", ""))
    translator = metadata.get("translator", {}).get("contact", "")
    chapters_json = json_for_html(chapters)
    metadata_json = json_for_html(minimal_metadata(metadata))
    embedded_script = (
        "<script>\n"
        f"window.BOOK_METADATA = {metadata_json};\n"
        f"window.EMBEDDED_CHAPTERS = {chapters_json};\n"
        "</script>"
    )

    html_text = template_html
    html_text = re.sub(
        r"<title>.*?</title>",
        f"<title>{html.escape(title)} | Читалка</title>",
        html_text,
        count=1,
        flags=re.DOTALL,
    )
    html_text = re.sub(
        r"<h1>.*?</h1>",
        f"<h1>{html.escape(title)}</h1>",
        html_text,
        count=1,
        flags=re.DOTALL,
    )
    html_text = replace_translator_credit(html_text, translator)
    html_text = html_text.replace(
        '<span id="chapterCount">20 файлов</span>',
        f'<span id="chapterCount">{len(chapters)} файлов</span>',
    )
    html_text = html_text.replace(
        '<span id="wordCount">~53 тыс. слов</span>',
        f'<span id="wordCount">~{round(sum(ch["words"] for ch in chapters) / 1000)} тыс. слов</span>',
    )
    if author:
        html_text = html_text.replace(
            '<p class="eyebrow">Перевод книги</p>',
            f'<p class="eyebrow">{html.escape(author)}</p>',
            1,
        )

    if inline_script:
        if js is None:
            raise ValueError("inline_script=True requires js")
        replacement = f"{embedded_script}\n<script>\n{js}\n</script>"
    else:
        replacement = f'{embedded_script}\n    <script src="./app.js"></script>'

    return html_text.replace('<script src="./app.js"></script>', replacement)


def replace_translator_credit(template_html: str, translator: str) -> str:
    if not translator:
        return template_html

    label = html.escape(translator)
    href = html.escape(translator_href(translator), quote=True)
    return re.sub(
        r'<a href="[^"]*" target="_blank" rel="noreferrer">.*?</a>',
        f'<a href="{href}" target="_blank" rel="noreferrer">{label}</a>',
        template_html,
        count=1,
        flags=re.DOTALL,
    )


def translator_href(value: str) -> str:
    if value.startswith("@"):
        return f"https://t.me/{value[1:]}"
    if value.startswith("http://") or value.startswith("https://") or value.startswith("mailto:"):
        return value
    if "@" in value:
        return f"mailto:{value}"
    return value


def generate_standalone_html(
    template_html: str,
    css: str,
    js: str,
    chapters: list[dict[str, Any]],
    metadata: dict[str, Any],
    cover_image: Path | None,
) -> str:
    standalone = inject_reader_template(
        template_html=template_html,
        metadata=metadata,
        chapters=chapters,
        inline_script=True,
        js=js,
    )
    standalone = standalone.replace(
        '<link rel="stylesheet" href="./styles.css">',
        f"<style>\n{css}\n</style>",
    )
    if cover_image and cover_image.exists():
        cover_data = file_to_data_uri(cover_image)
        standalone = standalone.replace('src="./cover.png"', f'src="{cover_data}"')
    standalone = standalone.replace("</title>", " · один файл</title>")
    return standalone


def embed_markdown_images(text: str, project_dir: Path, base_dir: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        alt_text = match.group(1)
        reference = match.group(2)
        if is_external_reference(reference):
            return match.group(0)
        image_path = resolve_image_path(project_dir, base_dir, reference)
        if not image_path:
            return match.group(0)
        return f"![{alt_text}]({file_to_data_uri(image_path)})"

    return re.sub(r"!\[([^\]]*)]\(([^)]+)\)", replace, text)


def resolve_image_path(project_dir: Path, base_dir: Path, reference: str) -> Path | None:
    reference_path = Path(reference)
    candidates = [
        base_dir / reference_path,
        project_dir / reference_path,
        project_dir / "source" / reference_path,
        project_dir / "source" / "images" / reference_path.name,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def is_external_reference(reference: str) -> bool:
    return reference.startswith(("http://", "https://", "data:", "mailto:"))


def file_to_data_uri(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def json_for_html(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


def minimal_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "book_id": metadata.get("book_id"),
        "title": metadata.get("title"),
        "author": metadata.get("author"),
        "source_language": metadata.get("source_language"),
        "target_language": metadata.get("target_language"),
        "translator": metadata.get("translator", {}),
    }


def extract_title(markdown: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown, flags=re.MULTILINE)
    return match.group(1).strip() if match else fallback


def chapter_label(chapter_id: str, index: int) -> str:
    match = re.match(r"^(\d+)_", chapter_id)
    if match:
        number = match.group(1)
        if "appendix" in chapter_id:
            return f"A{number}"
        if "notes" in chapter_id:
            return f"N{number}"
        return number
    return f"{index:02d}"


def chapter_kind(chapter_id: str) -> str:
    if "foreword" in chapter_id or "acknowledg" in chapter_id:
        return "Вступление"
    if "appendix" in chapter_id:
        return "Приложение"
    if "notes" in chapter_id:
        return "Примечания"
    return "Глава"


def count_words(value: str) -> int:
    return len(re.findall(r"[A-Za-zА-Яа-яЁё0-9-]+", value))


def format_bytes(bytes_count: int) -> str:
    units = ["B", "KB", "MB"]
    size = float(bytes_count)
    unit = 0
    while size >= 1024 and unit < len(units) - 1:
        size /= 1024
        unit += 1
    precision = 0 if size >= 10 or unit == 0 else 1
    return f"{size:.{precision}f} {units[unit]}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish translated chapters as reader assets and standalone HTML."
    )
    parser.add_argument(
        "--project-dir",
        required=True,
        help="Project directory containing translated chapters and metadata.json.",
    )
    parser.add_argument(
        "--standalone",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Generate standalone single-file HTML. Default: true.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(args.project_dir)

    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2

    try:
        result = publish_project(project_dir, standalone=args.standalone)
    except (FileNotFoundError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    print(f"Reader: {result.reader_dir}")
    if result.standalone_path:
        print(f"Standalone: {result.standalone_path}")
    for warning in result.warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    print("Publishing complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
