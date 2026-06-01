# TranslateJTBDBook

Локальный проект для перевода книги и экспериментов с пайплайном “PDF → Markdown → перевод → reader → standalone HTML / Next.js site”.

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

### Next.js сайт для GitHub Pages

Требования:

- Node.js 22+
- npm

Локальный запуск:

```bash
npm install
npm run dev
```

Статическая сборка для GitHub Pages:

```bash
npm run pages:build
```

Готовый сайт появится в `out/`. При пуше в `main` workflow `.github/workflows/deploy-pages.yml` сам соберёт Next.js static export и опубликует его в GitHub Pages. Для project pages base path вычисляется автоматически из имени репозитория.

### Автономный HTML

Собрать автономный HTML-файл:

```bash
npm run build:single-html
```

Готовый файл:

```text
dist/when-coffee-and-kale-compete-ru.html
```
