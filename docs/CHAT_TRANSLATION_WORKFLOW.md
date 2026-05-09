# Chat-Driven Book Translation Workflow

This workflow is for translating books through a chat session instead of calling an LLM API directly.

The pipeline still owns extraction, normalization, chapter splitting, chunking, assembly, review, and publishing. The chat session owns the actual translation of each chunk.

## Mental Model

```text
PDF
  ↓
run_pipeline prepares project through chunking
  ↓
chat_translate next writes the next prompt packet
  ↓
Codex/chat translates the packet
  ↓
chat_translate save stores the translation and updates chunk metadata
  ↓
repeat until all chunks are translated
  ↓
run_pipeline continues assembly, review, publish
```

## 1. Create a Project

```powershell
python -m book_pipeline.init_project `
  --book-id my-book `
  --title "My Book" `
  --author "Author" `
  --pdf "C:\path\to\book.pdf" `
  --translator-contact "@mark0vartem"
```

## 2. Prepare the Book for Chat Translation

Run the pipeline until the translation stage:

```powershell
python -m book_pipeline.run_pipeline `
  --project-dir projects/my-book `
  --until translate `
  --translation-method chat
```

The command runs:

1. `extract`
2. `normalize`
3. `split`
4. `chunk`

Then it pauses at `translate` and writes:

```text
projects/my-book/review/chat-translation/next.md
```

## 3. Translate the Next Chunk in Chat

Open:

```text
projects/my-book/review/chat-translation/next.md
```

Paste or reference that packet in the chat and ask:

```text
Переведи этот chunk и сохрани результат.
```

The translation should preserve markdown and return only translated markdown content.

## 4. Save a Chat Translation

If the translated markdown is in a file:

```powershell
python -m book_pipeline.chat_translate save `
  --project-dir projects/my-book `
  --chunk-id 01_chapter_0001 `
  --file "C:\path\to\translated.md"
```

The command writes:

```text
chunks/01_chapter/0001.ru.md
```

and updates:

```text
chunks/01_chapter/0001.meta.json
metadata.json
pipeline-state.json
```

## 5. Check Progress

```powershell
python -m book_pipeline.chat_translate status --project-dir projects/my-book
```

Example:

```text
Chunks: 12/48 translated
Pending: 36
Errors: 0
Next: 03_chapter_0004
```

## 6. Get the Next Packet

```powershell
python -m book_pipeline.chat_translate next --project-dir projects/my-book
```

This overwrites:

```text
review/chat-translation/next.md
```

with the next untranslated chunk.

You can request a specific chunk:

```powershell
python -m book_pipeline.chat_translate next `
  --project-dir projects/my-book `
  --chunk-id 03_chapter_0004
```

## 7. Continue After All Chunks Are Translated

When status shows no pending chunks:

```powershell
python -m book_pipeline.run_pipeline `
  --project-dir projects/my-book `
  --until publish `
  --translation-method chat
```

The pipeline sees that translation is complete and continues:

1. `assemble`
2. `review`
3. `publish`

Final output:

```text
projects/my-book/dist/my-book-ru.html
```

## Smoke Test Without Real Translation

Use `echo` to test the entire technical pipeline:

```powershell
python -m book_pipeline.run_pipeline `
  --project-dir projects/my-book `
  --until publish `
  --translation-method echo `
  --force
```

This writes source chunks back as fake translations with an `[ECHO TRANSLATION]` marker.

## Recommended Chat Prompt

```text
Открой projects/my-book/review/chat-translation/next.md.
Переведи SOURCE TEXT на русский.
Сохрани перевод в chunks/<chapter>/<sequence>.ru.md через chat_translate save.
Сохраняй markdown, заголовки, списки, ссылки и code fences.
Не переводи контекст, он только для справки.
```

## Why This Exists

This mode is useful when translation should happen inside an interactive chat rather than through API keys. It keeps the long-running book state on disk, so the process is resumable and safe even if the chat is interrupted.
