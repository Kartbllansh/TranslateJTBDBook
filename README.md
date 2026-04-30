# TranslateJTBDBook

Локальный проект для перевода книги и экспериментов с пайплайном “PDF → Markdown → перевод → reader → standalone HTML”.

## Быстрый старт с opendataloader-pdf

Требования:

- Python 3.10+
- Java 11+

Установка зависимости:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Создать проект книги:

```bash
.venv/bin/python -m book_pipeline.init_project \
  --book-id wcakc \
  --title "When Coffee and Kale Compete" \
  --author "Alan Klement" \
  --pdf WCAKC.pdf \
  --translator-contact "@mark0vartem"
```

Извлечение PDF:

```bash
.venv/bin/python -m book_pipeline.extract_opendataloader --project-dir projects/wcakc
```

Проверить статус проекта:

```bash
.venv/bin/python -m book_pipeline.project_status projects/wcakc
```

Документ с принципами системы: [docs/SYSTEM_PRINCIPLES.md](docs/SYSTEM_PRINCIPLES.md).

Спецификация целевой структуры репозитория: [docs/REPOSITORY_SPEC.md](docs/REPOSITORY_SPEC.md).

## Публикация текущего перевода

Собрать автономный HTML-файл:

```bash
node tools/build-single-html.mjs
```

Готовый файл:

```text
dist/when-coffee-and-kale-compete-ru.html
```
