# Art Studio 184 — единый запрос недостающих входов, Stage 2D

Назначение: список файлов и ответов, которые нужно собрать без повторного анализа 205 media assets. Пути ниже — рекомендуемые места для будущей передачи; Stage 2D не создаёт эти каталоги и не изменяет медиа.

## Правило приоритета

- `P0 — до финального дизайна`: без входа нельзя честно зафиксировать media/content composition.
- `P0 — до production-кода`: ранний visual exploration возможен, но production implementation contract неполон.
- `P0 — до публикации`: внутренний build возможен, production release запрещён.
- `P1`: существенно улучшает доказательность и полноту первой версии.
- `P2`: допустимо перенести после первого запуска.

## P0 — до финального дизайна

| Вход | Что требуется | Допустимый формат | Минимальное качество | Куда сохранить/зафиксировать | Что блокируется |
| --- | --- | --- | --- | --- | --- |
| Официальный логотип | Master + доступные варианты и usage permission | Предпочтительно SVG; также PNG transparent | SVG без raster embed или PNG минимум 2000 px по длинной стороне; прозрачный фон; без platform UI | `projects/art-studio-184/media/brand/` в следующем разрешённом этапе + asset register | Финальный header/footer, brand lockup, favicon system, публикация |
| Hero decision | Выбрать H1/H2/H3/temporary/new shoot | Заполненный owner pack | Однозначный вариант и разрешённые assets | `STAGE_02D_HERO_AND_HOME_SELECTION.md`, затем Stage 2E final contract | Финальный hero и responsive media assignment |
| 12 projects | Для каждого `ДА/НЕТ/ЗАМЕНИТЬ`, граница, публичное UA name | Заполненная Markdown/PDF копия матрицы | Все обязательные поля; ни одного silent assumption | `STAGE_02D_PROJECT_APPROVAL_MATRIX.md`, затем Stage 2E record | Галерея, home shortlist, titles/captions |
| Project boundaries | Решить 40 реально спорных groups; минимум все shortlist boundary cases | Заполненная таблица + при необходимости список файлов | Решение `confirm/split/merge/exclude/category/originals` | Stage 2D matrix; originals при необходимости остаются отдельно | Project schema и честный case count |
| Сторонние бренды | Решение по пяти branded/contextual shortlist projects | Decision register + ссылки на evidence | Отдельный статус для каждого project/frame | `STAGE_02D_RIGHTS_AND_BRAND_DECISIONS.md`; evidence позже в `data/rights/` | Branded frames в hero/home/gallery; publication каждого disputed frame |
| Максим и Люда | Реальные фото либо явное решение о non-anthropomorphic варианте | JPEG/PNG originals или owner answer | Portrait: минимум 2400×3000; без фильтров/UI; consent; для placeholder — однозначно выбранный тип | `media/team/` в следующем media stage; owner answer в pack | Финальный дизайн team section |
| Capabilities page | Выбрать один из пяти режимов запуска | Owner answer | Одно явное решение | Owner pack → Stage 2E scope contract | Scope и визуальная архитектура `/capabilities/` |
| Wide hero | Новый wide original либо письменное принятие composed/contained limitation | RAW + full-res JPEG предпочтительно | 4000×2250, с безопасной зоной 21:9/16:9, без dominant third-party mark/clutter | `media/production/hero/` в будущем media stage | Full-bleed/retina hero; без файла остаются только contained/composed варианты |

## Логотип: обязательность по моменту

### Обязательно до финального дизайна

- оригинальный logo master;
- SVG или другой редактируемый vector original;
- PNG с прозрачным фоном;
- разрешение использовать логотип на сайте;
- указание, какая версия основная.

### Желательно до production-кода

- светлая и тёмная версии;
- горизонтальная и компактная версии;
- минимальный размер и safe space, если определены;
- допустимый фон и запретные трансформации.

### Можно предоставить позже, но до публикации соответствующей функции

- favicon/отдельный знак;
- social/OG lockup;
- дополнительные print variants.

Новый логотип и временный постоянный wordmark `184 Art Studio` не создаются.

## P0 — до production-кода

| Вход | Что требуется | Допустимый формат | Минимальное качество | Куда сохранить/зафиксировать | Что блокируется |
| --- | --- | --- | --- | --- | --- |
| Telegram destination | Конкретный bot/chat destination без публикации секретов | Конфигурационный contract; секреты только в защищённом env | Владение, destination ID, test/prod separation, responsible person | Public-safe contract в docs; secret values только вне Git | Form delivery implementation |
| Telegram technical contract | Endpoint/auth, payload, retry/idempotency, abuse protection, timeout, fallback, observability | Markdown + machine-readable schema/tests позже | Success/error semantics; никакого ложного success; secret-safe logs | `docs/`/`data/contracts/` в Stage 3B | Backend и frontend state contract |
| Privacy controller | Фактический controller/имя | Письменный ответ, затем legal text | Однозначное имя без выдуманного юрлица | Stage 2E content/legal register | Consent и privacy implementation |
| Recipients | Кто получает/обрабатывает заявки | Письменный список ролей/сервисов | Все фактические получатели и processors | Stage 2E legal register | Data-flow design |
| Retention | Сколько и где хранить заявку/logs | Письменный срок и deletion rule | Отдельно для заявки, logs и backups | Stage 2E legal register | Storage/data lifecycle |
| Production domain | Domain, ownership, DNS/hosting responsibility | Domain string + access/ownership confirmation | Возможность управлять DNS, HTTPS и canonical | Не хранить credentials в repo; public domain в deployment contract | Canonical, redirects, CSP/hosting и release |
| Media storage | Выбрать managed storage/CDN | Provider decision + access outside Git | Контроль проекта, stable HTTPS, cache/versioning, no hotlink | Stage 3B infrastructure contract | Production image URLs |
| Responsive derivatives | Правила AVIF/WebP/JPEG, widths, quality, `srcset/sizes`, fallback | Media processing specification | Сохранение original, checksums, no upscale, bounded sizes | `data/media/` manifest в media stage | Production media wiring/performance |
| Final gallery metadata | Для каждого approved project: title, category, frame order; optional material/size/date/location only when known | CSV/JSON/Markdown register | Project-level, не file-level; source/status для каждого factual field | `data/gallery/` в Stage 2E/3B | Gallery content model и captions |
| Alt facts | Видимые нейтральные описания без client/material guesses | UA text register | Один alt intent на rendered image; decorative flag where appropriate | Media manifest | Accessibility implementation |
| Focal points | Desktop/tablet/mobile focal coordinates/notes | JSON/CSV + visual QA later | Для каждого cover/hero; coordinates bounded 0–1 или px with dimensions | Media manifest | Honest responsive crops |
| Final hero assignment | Один hero contract и разрешённые alternates | Stage 2E decision | Exact asset IDs, viewport use, eager/lazy priority | Stage 2E media contract | Hero code and performance plan |

## P0 — до публикации

| Вход | Что требуется | Допустимый формат | Минимальное качество | Куда сохранить/зафиксировать | Что блокируется |
| --- | --- | --- | --- | --- | --- |
| Privacy policy | Текст на основании реальных controller/recipients/retention | Проверенный UA legal text + URL | Соответствует реальному data flow; версия/дата | Публичная route/page в Stage 3; source в docs | Production form/consent |
| Form validation | Проверка `Ім’я`, одного `Контакт`, optional fields и consent | Testable UI/backend contract | Keyboard/focus/errors; data preserved on error; no false success | Tests + QA report | Production form |
| Error handling | Transport timeout/error, retry rule, visible fallback `@liu_ryb` | Test cases + copy contract | Проверены offline/4xx/5xx/timeout; no duplicate sends | Tests + live QA evidence | Production form |
| Telegram backend | Развёрнутый и проверенный endpoint/bot | Live service + secret-safe config | End-to-end success/error, idempotency, abuse protection, monitoring | Deployment evidence; secrets вне Git | Form submission |
| Rights register | Selected-asset author/source/rights/brand decision | Asset-level CSV/JSON + evidence links | Каждый rendered asset имеет status и allowed use | `data/rights/` + external evidence store | Любая production media publication |
| Cookies/analytics | Решение GA/cookies/Meta Pixel и consent basis | Written decision + technical config | По умолчанию ничего не устанавливать до решения | Stage 2E/3 publication contract | Analytics и, при необходимости, banner |
| SEO/indexing | Canonical, robots, sitemap, OG, schema, indexability | Deployment/SEO specification | Live verified production domain; no preview indexing | Stage 3 release config/report | Indexable launch |
| Production media delivery | Managed URLs, checksums, dimensions, derivatives, cache/error behavior | Immutable media manifest | Все files load, no source hotlink, no oversized LCP | Production manifest + live QA | Public gallery/hero |
| Domain/live verification | HTTPS, redirects, ownership marker, 404s, forms, headers | Browser/network report | Desktop/tablet/mobile and live functional QA | Release evidence | Production launch |

## P1 — доказательность и полнота

| Материал | Что требуется | Формат и минимальное качество | Куда сохранить | Что блокируется без него |
| --- | --- | --- | --- | --- |
| Мастерская | Clean wide overview | RAW + JPEG, минимум 3000×1688 | `media/production/workshop/` | Documentary Home/Capabilities/Contacts; текстовая версия всё ещё возможна |
| CNC | Машина в реальной работе + detail | JPEG минимум 3000×2000; safe setup; без secret control data | `media/production/capabilities/` | Visual CNC proof |
| 3D-принтер | Printer + print in progress | 2400×3000 и/или 3000×2000 | Там же | Visual 3D-print proof |
| Сварка | Реальная работа с PPE | JPEG минимум 3000×2000 | Там же | Visual welding proof |
| Ручная работа | Hands/tools shaping actual object | JPEG минимум 3000×2000 | Там же | Human-craft proof |
| Покраска | Controlled real paint application | JPEG минимум 3000×2000, PPE/clean zone | Там же | Visual finish/painting proof |
| Монтаж | Реальная установка и общий масштаб | Wide + detail, минимум 3000×2000, consent | `media/production/installation/` | Visual installation proof |
| Команда | Максим и Люда; optional group | Portrait pair 2400×3000 + group 3000×2000, consent | `media/team/` | Реальные portrait cards |
| Location image | Workshop/building/context without private data | Landscape 3000×2000 | `media/production/location/` | Documentary Contacts image |
| Масштаб | Реальный человек рядом с объектом | 2400×3000/3000×2000, consent, honest perspective | `media/production/scale/` | Visual scale proof |
| Surface details | Edge/texture/joint/finish | Detail минимум 2400×1600 | `media/production/details/` | Более сильная philosophy/quality section; не гарантия |

## P2 — можно после первой версии

| Материал | Что требуется | Формат и качество | Куда сохранить | Что блокируется без него |
| --- | --- | --- | --- | --- |
| Доставка/loading | Безопасная загрузка/фиксация объекта | JPEG минимум 3000×2000; убрать номера/адреса при необходимости | `media/production/logistics/` | Только documentary logistics story |
| Упаковка | Реальная защита/ящик/метод упаковки | JPEG минимум 3000×2000; без customer labels | Там же | Только documentary packing section |
| Дополнительные process details | Foam/fiberglass/wood/putty/sanding/priming/coating/assembly | Establishing + detail, long edge от 2400/3000 px, PPE | `media/production/capabilities/` | Глубину capabilities; базовый truthful text остаётся возможен |
| High-resolution originals остальных проектов | Originals вне approved first shortlist | Original JPEG/RAW; no platform UI; source/rights record | `media/source-originals/` | Будущее расширение gallery, не первую утверждённую выборку |

## Правила передачи файлов

- Не отправлять `.env`, tokens, bot secrets или private IDs в Git/Markdown.
- Не переименовывать originals без asset mapping.
- Для каждого файла сохранить source, автора/передавшего, дату получения и разрешённую роль.
- Не редактировать master; crops/derivatives создаются только в отдельном разрешённом media stage.
- Не использовать людей без consent и не генерировать лица.
- Не выдавать finished project за proof конкретного оборудования/процесса.
- Если material отсутствует, записать `НЕ ПРЕДОСТАВЛЕН` вместо выдуманного replacement.

## Краткий P0 checklist владельца

- [ ] logo package;
- [ ] hero decision;
- [ ] решения по 12 projects и спорным boundaries;
- [ ] brand/rights decisions;
- [ ] team decision/photos;
- [ ] capabilities-page decision;
- [ ] wide hero или принятие composed/contained limitation;
- [ ] Telegram destination/technical contract;
- [ ] controller/recipients/retention;
- [ ] production domain;
- [ ] storage/derivatives/gallery metadata/alt facts/focal points;
- [ ] privacy/form/backend/rights/analytics/SEO/media-delivery release package.
