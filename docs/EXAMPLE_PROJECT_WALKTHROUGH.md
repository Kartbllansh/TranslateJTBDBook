# Example Project Walkthrough

This walkthrough shows the expected outputs for a small book project. Replace `sample-book` and file paths with your real book details.

## 1. Create the Project

```bash
python -m book_pipeline.init_project \
  --book-id sample-book \
  --title "Sample Book" \
  --author "Author Name" \
  --pdf samples/sample.pdf \
  --translator-contact "@translator"
```

Expected output:

```text
Created project: projects/sample-book
```

Expected files:

```text
projects/sample-book/
├── input/book.pdf
├── metadata.json
├── pipeline-state.json
├── glossary.md
└── review/notes.md
```

## 2. Extract the PDF

```bash
python -m book_pipeline.extract_opendataloader \
  --project-dir projects/sample-book \
  --pages 1-10 \
  --image-output external
```

Expected files:

```text
source/extracted.md
source/extracted.json
source/images/
```

Troubleshooting:

- If Java is missing, install JDK 11+.
- If extraction output names differ, rename or copy the markdown to `source/extracted.md` before normalization.

## 3. Normalize Text

```bash
python -m book_pipeline.normalize --project-dir projects/sample-book
```

Expected files:

```text
source/normalized.md
review/normalization-report.md
```

Check `normalization-report.md` for detected headers, footers, and chapter boundary suggestions.

## 4. Split Chapters

```bash
python -m book_pipeline.split_chapters --project-dir projects/sample-book
```

Expected files:

```text
chapters/00_foreword.md
chapters/01_chapter.md
chapters/02_chapter.md
```

If automatic detection is wrong, create `chapter-rules.json`:

```json
{
  "chapters": [
    {
      "id": "01_chapter",
      "title": "Chapter 1",
      "start_pattern": "^# Chapter 1",
      "end_pattern": "^# Chapter 2"
    }
  ]
}
```

Then rerun:

```bash
python -m book_pipeline.split_chapters \
  --project-dir projects/sample-book \
  --mode manual \
  --rules-file chapter-rules.json \
  --force
```

## 5. Create Chunks

```bash
python -m book_pipeline.chunk --project-dir projects/sample-book --max-chars 6000
```

Expected files:

```text
chunks/01_chapter/0001.source.md
chunks/01_chapter/0001.ru.md
chunks/01_chapter/0001.meta.json
```

`0001.ru.md` starts empty. Manual translations can be placed there before assembly.

## 6. Translate

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --mode normal \
  --provider openai
```

Expected behavior:

- Chunks with empty `.ru.md` files are translated.
- Chunks with existing manual translation are skipped unless `--force` is used.
- Failed chunks get `status: error`.
- Errors are written to `review/translation-errors.md`.

Retry failed chunks:

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --mode normal \
  --retry-failed
```

## 7. Assemble Chapters

```bash
python -m book_pipeline.assemble --project-dir projects/sample-book
```

Expected files:

```text
translated/01_chapter.md
review/missing-sections.md
```

If `translated/01_chapter.md` already exists, inspect it before rerunning with:

```bash
python -m book_pipeline.assemble --project-dir projects/sample-book --force
```

## 8. Review

```bash
python -m book_pipeline.review --project-dir projects/sample-book
```

Expected reports:

```text
review/quality-report.md
review/structural-report.md
review/terminology-report.md
```

Common findings:

- Missing translated chapter file
- Empty or pending chunk
- Heading/list/quote mismatch
- Possible untranslated English text
- Missing image reference

## 9. Publish

```bash
python -m book_pipeline.publish --project-dir projects/sample-book --standalone
```

Expected files:

```text
dist/reader/index.html
dist/reader/app.js
dist/reader/styles.css
dist/<book-id>-ru.html
```

Open `dist/<book-id>-ru.html` in a browser. It should work without network access.

## Recovery Scenarios

### Resume after interruption

Rerun the interrupted command. Translation skips chunks whose `.ru.md` file already contains text or whose metadata status is `translated`.

### Regenerate a stage

Use `--force` only for the stage you want to regenerate. For example, `chunk --force` rewrites chunk files and empties translation placeholders.

### Metadata looks wrong

Check backups:

```text
review/backups/metadata-*.json
review/backups/pipeline-state-*.json
```

Restore manually only after comparing the backup with current files.
