# Спецификация репозитория для перевода PDF-книг

## Статус документа

Версия: `0.1`  
Назначение: рабочая спецификация для развития репозитория в локальную систему перевода PDF-книг на русский язык.  
Аудитория: разработчик системы, переводчик, редактор.

Этот документ описывает целевую структуру репозитория, команды, форматы файлов и правила работы пайплайна. Общие принципы описаны в `docs/SYSTEM_PRINCIPLES.md`.

## Цель

Репозиторий должен позволять:

1. Импортировать PDF-книгу.
2. Извлечь структурированный оригинал через `opendataloader-pdf`.
3. Нормализовать извлеченный текст в главы.
4. Перевести главы на русский язык с учетом глоссария.
5. Проверить перевод и сохранить замечания.
6. Собрать удобную HTML-читалку и автономный HTML-файл для распространения.

## Не цели

На первом этапе система не обязана:

- поддерживать EPUB, DOCX и сканы без настройки OCR;
- быть облачным сервисом;
- иметь многопользовательскую авторизацию;
- полностью исключать ручную редактуру;
- автоматически решать юридические вопросы распространения перевода.

## Целевая структура

```text
.
├── book_pipeline/              # Python-команды пайплайна
├── docs/                       # спецификации и документация
├── reader/                     # шаблон HTML-читалки
├── tools/                      # сборщики и вспомогательные утилиты
├── projects/                   # рабочие проекты книг, не коммитятся по умолчанию
│   └── <book-id>/
│       ├── input/
│       │   └── book.pdf
│       ├── source/
│       │   ├── extracted.md
│       │   ├── extracted.json
│       │   └── images/
│       ├── chapters/
│       │   ├── 00_foreword.md
│       │   └── 01_chapter.md
│       ├── chunks/
│       │   └── 01_chapter/
│       │       ├── 0001.source.md
│       │       ├── 0001.ru.md
│       │       └── 0001.meta.json
│       ├── translated/
│       │   ├── 00_foreword.md
│       │   └── 01_chapter.md
│       ├── review/
│       │   ├── terminology-report.md
│       │   ├── missing-sections.md
│       │   └── notes.md
│       ├── dist/
│       │   ├── reader/
│       │   └── <book-id>-ru.html
│       ├── metadata.json
│       ├── glossary.md
│       └── pipeline-state.json
├── requirements.txt
└── README.md
```

Текущие папки `chapters/`, `translated/` и `dist/` остаются совместимым режимом для уже переведенной книги. Новые книги должны жить в `projects/<book-id>/`.

## Источники правды

### `metadata.json`

Описывает книгу и структуру проекта.

```json
{
  "book_id": "when-coffee-and-kale-compete",
  "title": "When Coffee and Kale Compete",
  "author": "Alan Klement",
  "source_language": "en",
  "target_language": "ru",
  "input_file": "input/book.pdf",
  "chapters": [
    {
      "id": "01_chapter",
      "title": "Chapter 1. Challenges, Hope, and Progress",
      "source_path": "chapters/01_chapter.md",
      "translated_path": "translated/01_chapter.md",
      "status": "translated"
    }
  ]
}
```

`metadata.json` нужен интерфейсу, сборщику reader и командам проверки.

### `glossary.md`

Книга может иметь собственный глоссарий. Если файла нет, система использует корневой `TERMINOLOGY.md`.

Правило: локальный `projects/<book-id>/glossary.md` уточняет, но не должен незаметно противоречить корневому глоссарию.

### `pipeline-state.json`

Хранит техническое состояние пайплайна. Этот файл можно пересоздать из артефактов, но он ускоряет интерфейс.

```json
{
  "current_stage": "translate",
  "updated_at": "2026-04-30T19:00:00Z",
  "stages": {
    "extract": "done",
    "normalize": "done",
    "chunk": "done",
    "translate": "in_progress",
    "review": "pending",
    "publish": "pending"
  }
}
```

## Команды пайплайна

Команды должны быть доступны через Python-модули. Позже можно добавить единый CLI `book`.

### 1. Создать проект

Текущая команда:

```bash
.venv/bin/python -m book_pipeline.init_project \
  --book-id when-coffee-and-kale-compete \
  --title "When Coffee and Kale Compete" \
  --author "Alan Klement" \
  --pdf WCAKC.pdf \
  --translator-contact "@mark0vartem"
```

Результат:

- создается `projects/<book-id>/`;
- PDF копируется в `input/book.pdf`;
- создается первичный `metadata.json`;
- создается `pipeline-state.json`.

### 2. Извлечь PDF

Текущая команда:

```bash
.venv/bin/python -m book_pipeline.extract_opendataloader \
  --project-dir projects/when-coffee-and-kale-compete \
  --format markdown,json \
  --image-output external
```

Результат:

- Markdown в `source/`;
- JSON в `source/`;
- изображения в `source/images/` или рядом, в зависимости от настроек `opendataloader-pdf`.

Требования:

- Java 11+;
- Python 3.10+;
- установленный `opendataloader-pdf`.

### 3. Нормализовать книгу

Целевая команда:

```bash
.venv/bin/python -m book_pipeline.normalize \
  projects/when-coffee-and-kale-compete
```

Результат:

- очищенный Markdown;
- удаленные page headers/footers;
- склеенные переносы строк;
- список потенциальных заголовков глав;
- черновой `metadata.json` с главами.

### 4. Разбить на главы

Целевая команда:

```bash
.venv/bin/python -m book_pipeline.split_chapters \
  projects/when-coffee-and-kale-compete
```

Система должна поддерживать два режима:

- автоматический режим на основе заголовков;
- ручной режим через файл правил.

Файл правил:

```json
{
  "chapters": [
    {
      "id": "01_chapter",
      "title": "Chapter 1. Challenges, Hope, and Progress",
      "start_pattern": "^# Chapter 1",
      "end_pattern": "^# Chapter 2"
    }
  ]
}
```

### 5. Нарезать на чанки

Целевая команда:

```bash
.venv/bin/python -m book_pipeline.chunk \
  projects/when-coffee-and-kale-compete \
  --max-chars 6000
```

Правила:

- чанк не должен разрывать заголовок и следующий за ним первый абзац;
- чанк не должен разрывать список без необходимости;
- каждый чанк хранит ссылку на главу и примерную позицию в источнике;
- чанк должен быть достаточно мал для LLM, но достаточно велик для связного перевода.

### 6. Перевести

Целевая команда:

```bash
.venv/bin/python -m book_pipeline.translate \
  projects/when-coffee-and-kale-compete \
  --mode normal \
  --target ru
```

Режимы:

- `quick`: прямой перевод без подробного анализа;
- `normal`: анализ терминов и перевод;
- `refined`: перевод, ревью и полировка.

Правила:

- уже переведенные чанки не перезаписываются без `--force`;
- промпт всегда включает глоссарий;
- каждый чанк получает `meta.json` со статусом и временем;
- ошибки сохраняются в `review/translation-errors.md`.

### 7. Собрать главы

Целевая команда:

```bash
.venv/bin/python -m book_pipeline.assemble \
  projects/when-coffee-and-kale-compete
```

Результат:

- файлы `translated/*.md`;
- отчет о пропущенных чанках;
- отчет о слишком коротких или подозрительно длинных главах.

### 8. Проверить

Целевая команда:

```bash
.venv/bin/python -m book_pipeline.review \
  projects/when-coffee-and-kale-compete
```

Минимальные проверки:

- все главы из `metadata.json` имеют перевод;
- заголовки оригинала и перевода сопоставимы;
- нет пустых глав;
- нет служебных файлов в публикации;
- ключевые термины из глоссария употреблены последовательно;
- ссылки и примечания не потеряны.

### 9. Опубликовать

Целевая команда:

```bash
.venv/bin/python -m book_pipeline.publish \
  projects/when-coffee-and-kale-compete \
  --standalone
```

Результат:

- `projects/<book-id>/dist/reader/`;
- `projects/<book-id>/dist/<book-id>-ru.html`.

Текущий `tools/build-single-html.mjs` должен стать частью этого этапа или получить параметры проекта.

## Статусы

Допустимые статусы для глав и чанков:

```text
pending       # еще не обработано
extracted     # извлечено из PDF
normalized    # очищено
chunked       # нарезано
translated    # переведено
review_needed # нужно проверить вручную
approved      # принято редактором
published     # вошло в сборку
error         # этап завершился ошибкой
```

Статус не должен быть единственным источником правды. Если файл существует, а статус устарел, команда `review` должна это обнаружить.

## Интерфейс

Первый интерфейс может быть локальным веб-приложением.

Минимальные экраны:

- список проектов;
- карточка проекта со стадиями пайплайна;
- экран источника PDF и результатов извлечения;
- список глав;
- редактор оригинал/перевод;
- экран глоссария;
- экран публикации.

Минимальные действия:

- импортировать PDF;
- запустить извлечение;
- подтвердить или поправить главы;
- запустить перевод выбранных глав;
- отметить главу как проверенную;
- собрать reader;
- открыть standalone HTML.

## Reader

Reader должен быть независим от того, как был получен перевод.

Вход reader-сборки:

- `metadata.json`;
- `translated/*.md`;
- обложка, если есть;
- контакт переводчика, если указан.

Выход:

- папка сайта;
- один HTML-файл.

Standalone HTML должен:

- не зависеть от внешних JS/CSS/изображений;
- открываться через двойной клик;
- содержать встроенный текст книги;
- иметь понятное имя файла;
- не включать служебные главы и технические заметки.

## Проверки качества

### Структурные проверки

- Количество глав в `metadata.json` совпадает с файлами в `chapters/`.
- У каждой публикуемой главы есть перевод.
- Нет файлов с количеством слов ниже заданного порога, кроме явно разрешенных.
- В standalone HTML нет внешних ссылок на локальные ассеты.

### Переводческие проверки

- Термины из глоссария используются последовательно.
- JTBD и другие ключевые аббревиатуры не переведены случайно.
- Английские фразы не остались в русском тексте без причины.
- Списки, цитаты и примечания сохранены.

### Технические проверки

- Python-файлы проходят `py_compile`.
- JS-файлы проходят `node --check`.
- Standalone HTML содержит встроенные скрипты без синтаксических ошибок.
- Сборщик не портит `$&`, `$1` и другие специальные строки при вставке JS.

## Работа с ошибками

Каждая команда должна:

- возвращать ненулевой код при ошибке;
- печатать понятное сообщение;
- не оставлять частично перезаписанные важные файлы;
- по возможности писать отчет в `review/`.

Пример хорошей ошибки:

```text
Java was not found in PATH. opendataloader-pdf requires Java 11+.
Install a JDK first, then verify with:
  java -version
```

## Безопасность и приватность

- PDF и перевод по умолчанию остаются локально.
- Внешние API для перевода должны быть явной настройкой.
- Ключи API не хранятся в репозитории.
- `projects/` не коммитится по умолчанию, потому что может содержать copyrighted PDF.

## Совместимость с текущим проектом

Текущий перевод `When Coffee and Kale Compete` остается рабочим примером.

Переходный план:

1. Оставить корневые `chapters/` и `translated/` как legacy sample.
2. Создать `projects/wcakc/`.
3. Перенести туда `WCAKC.pdf`, главы, перевод, metadata и dist.
4. Научить reader-сборщик работать как с legacy-режимом, так и с `projects/<book-id>/`.
5. После стабилизации убрать одноразовые `extract_pdf*.py` или перенести их в `legacy/`.

## Roadmap

### Milestone 1. Основа пайплайна

- `init_project`
- `extract_opendataloader`
- `metadata.json`
- документация prerequisites

### Milestone 2. Нормализация и главы

- `normalize`
- `split_chapters`
- ручные правила разбиения
- отчеты по подозрительным главам

### Milestone 3. Перевод и чанки

- `chunk`
- `translate`
- статусы чанков
- поддержка глоссария

### Milestone 4. Редактура

- side-by-side editor
- отчеты терминологии
- статусы `review_needed` и `approved`

### Milestone 5. Публикация

- параметризованный reader
- standalone HTML из любого проекта
- проверка публикуемых файлов

## Открытые решения

- Какой LLM-провайдер будет первым для перевода?
- Нужен ли SQLite для индекса интерфейса или достаточно файлов?
- Как хранить изображения: в `source/images/`, `dist/assets/` или inline?
- Нужно ли публиковать оригинал рядом с переводом?
- Как оформлять лицензию и дисклеймер для переводов?
