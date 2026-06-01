# Финальная проверка недопереводов

Дата проверки: 2026-05-31

## Итог

Недопереводы в основном тексте и итоговой HTML-сборке устранены. Английский оставлен только там, где он выполняет роль имени собственного, названия источника, бренда, URL, аббревиатуры или осознанного термина JTBD/смежной методологии.

## Что проверялось

- Все Markdown-файлы в `translated/`.
- Итоговая сборка `dist/when-coffee-and-kale-compete-ru.html`.
- Подозрительные английские фрагменты: роли, должности, бытовые и продуктовые выражения, гибриды через дефис, англоязычные цитаты без русского пояснения, географические названия, термины в примечаниях.

## Что исправлено

- Роли и должности: `product manager`, `CEO`, `COO`, `senior VP of marketing`, `limited partners`.
- Продуктовые и исследовательские фразы: `discovery`, `e-mail`, `on demand`, `bookmarklet`, `adoption`, `empty nesters`.
- Гибриды и бытовые англицизмы: `prelaunch-стресс`, `membership-сайт`, `networking-мероприятие`, `solopreneurs`, `USB-кабель`, `Flash-разработчики`.
- Английские объяснительные термины: `root cause analysis`, `field turf`, `task analysis`, `activity-centered design`, `human-computer interaction`.
- Глава про PC нормализована до `ПК`, кроме названий вроде `PC Magazine` и `IBM PC`.
- Английские цитаты в примечаниях получили русский перевод или пояснение рядом.

## Осознанно оставлено

- Термины ядра книги: `JTBD`, `Customer Jobs`, `Job to be Done`, `Job Stories`, `Jobs-As-Progress`, `Jobs-As-Activities`.
- Названия продуктов и инструментов: `Lean Canvas`, `Lean Stack`, `Validation Plan`, `Experiment Report`.
- Названия книг, статей, конференций, организаций, журналов, брендов и имена людей.
- Английский термин в скобках после русского перевода, когда он нужен для точности или узнаваемости.

## Проверка сборки

- `node --check reader/app.js` — успешно.
- `node --check tools/build-single-html.mjs` — успешно.
- `node tools/build-single-html.mjs` — успешно, HTML пересобран.
- Контрольный поиск по запрещённым паттернам в `translated/` и `dist/when-coffee-and-kale-compete-ru.html` — совпадений нет.
- В HTML встроен 21 Markdown-раздел; найдено 36 русских подписей рисунков.
- `git diff --check` — ошибок пробелов нет; есть только предупреждения Git о будущей CRLF-нормализации.
