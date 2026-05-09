# LLM Integration

The translation stage uses a pluggable LLM adapter. The CLI supports OpenAI, Anthropic, a local HTTP endpoint, and an `echo` adapter for smoke tests.

## Translation Command

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --mode normal \
  --provider openai
```

Modes:

- `quick`: direct translation with markdown preservation.
- `normal`: glossary-aware translation with terminology verification instructions.
- `refined`: translation, review, and polish instructions in one request.

## OpenAI Provider

Required:

```bash
set OPENAI_API_KEY=sk-...
```

Optional:

```bash
set OPENAI_MODEL=gpt-4.1-mini
set OPENAI_BASE_URL=https://api.openai.com/v1
```

Run:

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --provider openai \
  --mode normal
```

## Anthropic Provider

Required:

```bash
set ANTHROPIC_API_KEY=sk-ant-...
```

Optional:

```bash
set ANTHROPIC_MODEL=claude-3-5-sonnet-latest
set ANTHROPIC_BASE_URL=https://api.anthropic.com/v1
```

Run:

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --provider anthropic \
  --mode refined
```

## Local Provider

The local adapter sends:

```json
{
  "prompt": "..."
}
```

The endpoint must return one of these string fields:

```json
{
  "translation": "..."
}
```

or:

```json
{
  "text": "..."
}
```

or:

```json
{
  "response": "..."
}
```

Configure:

```bash
set BOOK_PIPELINE_LLM_ENDPOINT=http://localhost:8000/translate
```

Run:

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --provider local
```

## Echo Provider

Use `echo` only to test the pipeline without calling an LLM:

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --provider echo \
  --mode quick
```

It writes the source text back with an `[ECHO TRANSLATION]` marker.

## Glossary Behavior

Translation loads two glossary sources:

1. Root `TERMINOLOGY.md`
2. Project `projects/<book-id>/glossary.md`

Project entries override root entries when the English term matches case-insensitively. Conflicts are written to:

```text
review/terminology-report.md
```

Glossary tables must use columns like:

```markdown
| English | Russian | Notes |
|---|---|---|
| Job to be Done | Работа, которую нужно выполнить | First use includes JTBD |
```

Russian column names such as `Русский перевод` are also supported.

## Context Behavior

For middle chunks, the prompt includes:

- Last paragraph of the previous chunk
- Current chapter title
- First paragraph of the next chunk

Context is marked as reference-only and limited to 500 characters per boundary.

## Retry and Safety

Skip rules without `--force`:

- Chunks with `status: translated` or `status: approved`
- Chunks whose `.ru.md` file already contains text
- Chunks with `status: error`, unless `--retry-failed` is passed

Retry failed chunks:

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --retry-failed
```

Overwrite existing translations:

```bash
python -m book_pipeline.translate \
  --project-dir projects/sample-book \
  --force
```

Use `--force` carefully because it overwrites translated chunk files.

## Example Environment File

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-latest

# Local
BOOK_PIPELINE_LLM_ENDPOINT=http://localhost:8000/translate
```

Do not commit real API keys.
