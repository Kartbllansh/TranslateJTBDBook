# Book Pipeline

`book_pipeline` is a local-first CLI toolchain for turning an English PDF book into a structured Russian translation project. It stores every artifact on disk, so each stage can be inspected, edited, and rerun.

## Prerequisites

- Python 3.10+
- Java 11+ for `opendataloader-pdf`
- Dependencies from the repository root:

```bash
python -m pip install -r requirements.txt
```

For automated translation, configure one LLM provider. See [docs/LLM_INTEGRATION.md](../docs/LLM_INTEGRATION.md).

## Project Layout

New projects live under `projects/<book-id>/`:

```text
projects/<book-id>/
├── input/book.pdf
├── source/extracted.md
├── source/normalized.md
├── source/images/
├── chapters/
├── chunks/
├── translated/
├── review/
├── dist/
├── metadata.json
├── glossary.md
└── pipeline-state.json
```

The legacy root folders `chapters/`, `translated/`, and `dist/` remain useful for the current sample book.

## Full Workflow

### 1. Create a Project

```bash
python -m book_pipeline.init_project \
  --book-id sample-book \
  --title "Sample Book" \
  --author "Author Name" \
  --pdf path/to/book.pdf \
  --translator-contact "@translator"
```

### 2. Extract PDF Content

```bash
python -m book_pipeline.extract_opendataloader \
  --project-dir projects/sample-book \
  --format markdown,json \
  --image-output external
```

### 3. Normalize Extracted Text

```bash
python -m book_pipeline.normalize --project-dir projects/sample-book
```

Outputs:

- `source/normalized.md`
- `review/normalization-report.md`

### 4. Split Chapters

Automatic mode:

```bash
python -m book_pipeline.split_chapters --project-dir projects/sample-book
```

Manual mode:

```bash
python -m book_pipeline.split_chapters \
  --project-dir projects/sample-book \
  --mode manual \
  --rules-file chapter-rules.json
```

### 5. Create Translation Chunks

```bash
python -m book_pipeline.chunk \
  --project-dir projects/sample-book \
  --max-chars 6000
```

Each chunk gets:

- `chunks/<chapter-id>/0001.source.md`
- `chunks/<chapter-id>/0001.ru.md`
- `chunks/<chapter-id>/0001.meta.json`

### 6. Translate Chunks

Through chat, without an API:

```bash
python -m book_pipeline.run_pipeline \
  --project-dir projects/sample-book \
  --until translate \
  --translation-method chat
```

Then use:

```bash
python -m book_pipeline.chat_translate status --project-dir projects/sample-book
python -m book_pipeline.chat_translate next --project-dir projects/sample-book
python -m book_pipeline.chat_translate save --project-dir projects/sample-book --chunk-id 01_chapter_0001 --file translated.md
```

Full chat workflow: [docs/CHAT_TRANSLATION_WORKFLOW.md](../docs/CHAT_TRANSLATION_WORKFLOW.md).

Via API:

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --mode normal \
  --provider openai
```

Modes:

- `quick`: direct translation
- `normal`: translation with terminology checks in the prompt
- `refined`: translation plus review/polish instructions

Useful flags:

- `--retry-failed`: retry chunks with `status: error`
- `--force`: overwrite existing translated chunk files

### 7. Assemble Chapters

```bash
python -m book_pipeline.assemble --project-dir projects/sample-book
```

Use `--force` if `translated/<chapter-id>.md` already exists and should be regenerated.

### 8. Review Quality

```bash
python -m book_pipeline.review --project-dir projects/sample-book
```

Reports:

- `review/quality-report.md`
- `review/structural-report.md`
- `review/terminology-report.md`
- `review/missing-sections.md`

### 9. Publish Reader

```bash
python -m book_pipeline.publish --project-dir projects/sample-book --standalone
```

Outputs:

- `dist/reader/`
- `dist/<book-id>-ru.html`

The standalone HTML embeds CSS, JavaScript, chapter content, cover image, and markdown image references as data URIs when possible.

## Status and Project Listing

Show one project:

```bash
python -m book_pipeline.project_status projects/sample-book
```

List all projects:

```bash
python -m book_pipeline.list_projects --projects-dir projects
```

## Safety Rules

- Existing chunk translations are not overwritten unless `--force` is used.
- Existing assembled chapters are not overwritten unless `--force` is used.
- `metadata.json` and `pipeline-state.json` are backed up to `review/backups/` before updates.
- Large write operations check available disk space before writing.
- Translation errors are logged to `review/translation-errors.md` and do not stop other chunks from processing.

## Common Troubleshooting

### Java was not found

Install a JDK 11+ and verify:

```bash
java -version
```

### `opendataloader-pdf` is missing

Install repository dependencies:

```bash
python -m pip install -r requirements.txt
```

### A stage refuses to overwrite files

Use the stage-specific `--force` flag only after checking the existing output. This protects manual edits.

### Translation fails because an API key is missing

Set the required environment variable:

```bash
set OPENAI_API_KEY=...
```

or choose another provider:

```bash
python -m book_pipeline.translate --project-dir projects/sample-book --provider local
```
