# Проверка production-аудита Ami Dental: 18 ISSUE

Дата проверки: 2026-07-19
Целевой run: `053656c35b5d4ef58221c5be7171b625`
Режим: read-only product/system audit. Сайт, генератор, deployment, custom domain и Telegram production state не изменялись.

## 1. Executive summary

Внешний аудит правильно отвергает текущий результат как готовый коммерческий production-сайт. Проверенный результат визуально собран и технически стабилен, но коммерчески неполон: он не показывает прямые контакты, врачей, кейсы, цены первого шага, медицинские основания доверия и полный каталог; весь путь обращения заканчивается одним Instagram URL.

Одно замечание находится вне текущего scope. `ISSUE-01` описывает служебный домен как ошибочный production launch, однако фактически URL является намеренным изолированным review preview: `noindex`, отдельный non-production branch, без custom domain и без production promotion. Брендовый домен остаётся обязательным будущим production gate, но не дефектом preview lane.

Подтверждён главный системный false positive. Research того же run перечисляет неизвестными телефон, адрес, часы, полный каталог, команду, отзывы, цены и booking, но система всё равно выставила:

- Evidence Level A / `full_site` / 100;
- commercial usefulness 100;
- Product Director 100;
- acceptance 90 / approved.

Причина не в случайно упавшем тесте. Текущие 48 focused tests проходят. Ошибка находится в самом контракте: Instagram считается достаточным contact/conversion path, три синтетические темы — достаточным content scope, а число секций и `data-decision-role` — доказательством полного customer journey.

Итог по 18 ISSUE: 14 подтверждены, 3 подтверждены частично (`05`, `12`, `16`), 1 находится вне текущего preview scope (`01`). Полностью непроверенных ISSUE нет, но отдельные утверждения аудитора об актуальности внешних данных остаются неподтверждёнными и не могут автоматически попасть в production.

## 2. Изученная архитектура

| Область | Найденный файл или компонент | Текущая функция | Найденная слабость |
|---|---|---|---|
| Telegram intake / queue | `site_agent/telegram_bot.py`, `site_agent/job_queue.py:37-89` | Принимает Instagram URL, создаёт durable job, хранит preview/production lifecycle | Не собирает page scope, business facts, primary CTA, функции и SEO scope; lifecycle state не равен product readiness |
| Preview-default CLI | `site_agent/cli.py:33-179`, `:443-512` | `go` запускает preview; production отделён explicit authorization | Production booleans не вычисляются из независимых readiness artifacts |
| One-link research | `site_agent/research.py:154-237`, `:336-361`, `:505-535` | Instagram → search → browser → discovered official site | Не доказывает business linkage найденного сайта; cache может сохранить platform URL как official source |
| Cached intake / provisional contract | `site_agent/orchestrator.py:143-165`, `:1298-1424` | Повторно использует cache, создаёт preview research contract | Синтезирует темы, считает Instagram контактом и открывает full-site readiness при unresolved blockers |
| Research model | `site_agent/models.py:57-101` | Хранит facts, themes, unknowns, provenance | Нет typed `BusinessDataCompletenessReport`; `production_blocker` не участвует в readiness decision |
| Evidence readiness | `site_agent/design_quality.py:266-320` | Вычисляет Level/PageScope | `contact_path=true` для одного Instagram; full site открывается по 3 темам и 5 изображениям, даже если темы синтетические и required facts отсутствуют |
| Workflow handoff | `site_agent/workflow.py:168-249` | Валидирует обязательные ключи и checksum-bound package | Проверяет наличие структуры, а не достаточность/смысл/provenance содержимого |
| Studio | `site_agent/studio.py:194-395` | Концепты, screenshots, selection, build, fixer | Правильно организован творческий цикл, но наследует ложный Level A и слабые commercial contracts |
| Conversion copy | `.agents/skills/conversion-copy/SKILL.md:8-10` | Запрещает выдумывать факты | Инструкция `use Direct/Instagram for unknown details` конфликтует с запретом превращать missing data в narrative и допускает/поощряет наблюдаемый Direct-only failure mode |
| Story / section QA | `.agents/skills/storytelling/SKILL.md`, `site_agent/commercial_usefulness.py:197-338` | Требует отдельную работу каждой секции; считает commercial path | Runtime использует substring/count checks; весь первый `<section>` принимается за viewport, spec CTA — за rendered CTA |
| Product Director | `site_agent/product_director.py:105-269` | Независимо проверяет полный продукт | Принимает 7+ секций и role labels без проверки customer value, source IDs, CTA outcome и содержимого trust/proof |
| Browser QA | `site_agent/critic.py:17-166`, `:205-275` | 1440/768/390, images, overflow, tap targets, header/footer, CTA geometry | Не проверяет 1024/360, все routes, menu/focus/hover/active, form states и фактическое завершение конверсии |
| Media | `site_agent/media.py:285-473` | Rights, dimensions, dedupe, conservative social crop | Нет focal/safe region, embedded-text risk, semantic alt binding и rendered crop/meaning report |
| Claims | `site_agent/orchestrator.py:870-886` | Exact-duration regression для 20 лет | Нет полного claim extraction/ledger для HTML, meta, OG и JSON-LD; субъект числового claim не валидируется |
| Brand fidelity | `site_agent/brand.py`, `studio/brand_fidelity_report.json` | Проверяет logo checksum и palette presence | Не проверяет canonical public name, slogan и tone consistency; поэтому `Ami Dental`/`Amidental Kiev` прошли |
| Acceptance | `site_agent/acceptance.py:13-140` | Собирает technical/visual/business reports | Доверяет ложным commercial/Product Director booleans; не требует completeness, section purpose, conversion outcome, claim ledger и readiness matrix |
| Preview release | `site_agent/preview.py:56-187`, `:286-393` | Изолированный noindex preview, exact business marker | Для текущего preview работает корректно |
| Production publish | `site_agent/publisher.py:566-653` | HTTPS/HTTP/assets/business marker live verification | Не исполняет live browser journey, forms, keyboard, claims, SEO и multi-route behavior |

Проверенные артефакты включают `site/index.html`, research/evidence/readiness JSON, media manifest и originals, final/live screenshots, critic/product/acceptance reports, preview metadata, queue state и предыдущий same-business run `f684eed531f74dd8995b2a58ac77739e`.

Дополнительно просмотрены официальные публичные страницы Ami Dental. Они показывают более широкий каталог, контакты, специалистов, оборудование, работы и отзывы, но часть материалов датирована 2019–2022 годами. Это источник для повторного research и business confirmation, а не разрешение на автоматическую production-публикацию.

## 3. Verification table по всем ISSUE

Классы: A — дефект конкретного сайта; B — недостающие/неподтверждённые business data; C — повторяемое quality rule; D — системный дефект pipeline. В таблице указан основной класс; дополнительные причины перечислены в выводе.

| ISSUE | Статус | Класс | Доказательство | Реальный приоритет | Действие |
|---|---|---:|---|---:|---|
| 01 — preview domain | `OUT_OF_CURRENT_SCOPE` | A | `preview_deployment.json` фиксирует preview/noindex/non-production/no custom domain/no production start | P0 только при promotion | Сохранить preview; брендовый domain/canonical проверять только в explicit production lane |
| 02 — Instagram-only conversion | `CONFIRMED` | D | `site/index.html:34,47,55,70,76,79`; все 10 CTA имеют одну Instagram-цель; form/tel/booking отсутствуют | P0 | Получить direct contact/booking и внедрить проверяемый conversion outcome |
| 03 — нет NAP/часов/карты | `CONFIRMED` | B | `site/index.html:64,73,79`; research помечает address/phone/hours unknown | P0 | Подтвердить актуальные NAP/hours и только затем публиковать |
| 04 — generic hero | `CONFIRMED` | C | `site/index.html:46-47`, desktop/mobile screenshots | P1 | Category/city/action видны, но отсутствует доказуемая причина выбрать клинику. Усилить real-viewport gate |
| 05 — искусственно узкий каталог | `PARTIALLY_CONFIRMED` | B | `site/index.html:43,52,55,64,73`; target research знает только 5 labels, prior official-source run видел более широкий, но не подтверждённый как текущий, список | P0 | Подтвердить текущую service matrix; не синтезировать catch-all |
| 06 — карточки не помогают решить | `CONFIRMED` | C | `site/index.html:54-55`: situation → procedure → one sentence → Instagram | P1 | Для каждого направления требовать decision support, source и специфичный next step |
| 07 — нет врачей/команды | `CONFIRMED` | B | `site/index.html:63-64`; research прямо помечает staff names/qualifications unknown | P0 | Запросить актуальный состав и разрешённые credentials; без них trust/content remain blocked |
| 08 — нет кейсов/отзывов | `CONFIRMED` | B | `site/index.html:58-64`; социальные изображения и стаж вместо cases/reviews | P0 | Получить актуальные sources, rights и consent; не считать role `proof` доказательством |
| 09 — 20 лет без субъекта | `CONFIRMED` | C | `site/index.html:60,73`; research хранит bare `experience_years=20 years` | P0 | Подтвердить субъект, период и метод; добавить claim-ledger validation |
| 10 — FAQ отправляет в Direct | `CONFIRMED` | C | `site/index.html:72-73`; повторяет services/Instagram/20 лет и выносит address/price наружу | P1 | FAQ обязан самостоятельно закрывать подтверждённые administrative questions |
| 11 — нет цены первого шага | `CONFIRMED` | B | `visible_prices_offers=[]`; `site/index.html:73` отправляет за ценой в Direct | P0 | Подтвердить цену/диапазон/ненумерическую логику расчёта; числа не выдумывать |
| 12 — local SEO architecture | `PARTLY_CONFIRMED` | C | Одна anchor-page, generic H1, нет canonical/JSON-LD/service pages | P0 для production SEO | Для noindex preview `not_required`; для production нужен отдельный SEO readiness gate |
| 13 — нет medical trust basis | `CONFIRMED` | B | `site/index.html:66` называет Instagram steps `trust_process`; license/diagnostics/sterilization/equipment отсутствуют | P0 | Подтвердить актуальные medical trust facts и связать их с patient benefit/source IDs |
| 14 — social media не адаптированы | `CONFIRMED` | C | Использованные originals содержат baked headings; manifest показывает 640 px social assets без смысловой web adaptation | P1 | Focal/safe crop, embedded-text risk и viewport media review должны блокировать design readiness |
| 15 — alt не соответствует смыслу | `CONFIRMED` | C | `site/index.html:49,60,64`; alt опускает врача/пациента и baked-in headlines, HTML-equivalent отсутствует | P1 | Определять функцию media, затем alt; существенный текст переносить в HTML |
| 16 — naming/slogan/tone inconsistency | `PARTLY_CONFIRMED` | A | Официальный logo визуально `Ami Dental`, title/body — `Amidental Kiev`; Brand Fidelity всё равно PASS | P0 | Business утверждает canonical naming; brand gate проверяет name/slogan/tone, не только pixels/colors |
| 17 — semantic repetition | `CONFIRMED` | C | Направления повторяются в hero/band/cards/about/process/FAQ; Instagram CTA — по всей странице | P1 | Bind sections к уникальным customer questions/source IDs; role labels недостаточно |
| 18 — 4 vs 5 направлений | `CONFIRMED` | A | `site/index.html:43` — 4; `:52,55,64,73` — 5 | P2 | Синхронизировать taxonomy или явно назвать верхний список «популярные» |

Сохранённые internal reports противоречат реальности: `commercial_usefulness_report.json` утверждает reason-to-choose/useful information/complete path и ставит 100; `product_director_report.json` принимает продукт со score 100 при `has_form=false` и Instagram-only terminal route, опираясь на role/count coverage; `semantic_repetition_report.json` возвращает `approved=true` и пустой список findings. Диагностика missing pages не используется как нарушение: для этого run multi-page contract не был обязательным.

## 4. Подтверждённые дефекты Amidental

Исправимы без новых медицинских/коммерческих фактов:

- удалить противоречие 4/5 направлений после выбора честной формулировки типа «популярные направления»;
- убрать смысловые повторы и одинаковые CTA как механическую структуру;
- не называть Instagram-инструкцию `trust_process`;
- исправить alt и вынести существенный baked-in text в HTML либо исключить неподходящие изображения;
- исправить 9 px скрытый overflow на 360 px, связанный с hero typography/layout;
- перестать считать generic channel-label результатом конверсии;
- сохранить preview isolation/noindex и не представлять URL как production.

Не могут быть честно завершены без подтверждения бизнеса:

- NAP, hours, map и direct booking;
- полный каталог и приоритеты;
- doctors/credentials;
- cases/reviews/rights/consent;
- first-step pricing;
- medical trust facts;
- субъект 20-летнего опыта;
- canonical brand naming и production CTA;
- production media rights/domain/SEO scope.

## 5. Необходимые данные от бизнеса

| Данные | Почему нужны | Где используются | Кто должен запросить | Что блокируется | Можно ли продолжать без них |
|---|---|---|---|---|---|
| Canonical public name и допустимые варианты | Единая identity | logo/header/title/OG/maps | Business intake | Brand/Content/Production Ready | Preview можно, production нет |
| Адрес, часы, телефоны, email | Логистика, trust, local SEO | header/contact/footer/schema | Business intake | Business Data/Functional/SEO/Production | Только incomplete preview |
| Primary conversion и SLA | Завершение намерения | CTA/form/phone/booking | Business intake | Functional/Production | Нет для commercial production |
| Текущая service matrix | Полный scope и IA | services/navigation/SEO | Research + business confirmation | Business Data/Content/SEO | Нет для full site |
| Цена первого шага или логика оценки | Снижает ценовую неопределённость | service/FAQ/CTA | Business confirmation | Business Data/Content | Честный blocker допустим только в preview |
| Актуальные врачи и credentials | High-risk trust | team/service/cases | Business confirmation | Business Data/Content | Full commercial production не проходит |
| Medical trust facts | Safety/process proof | About/trust/FAQ | Business confirmation | Business Data/Content | Нет для medical production |
| Cases/reviews + source/rights/consent | Проверяемое proof | cases/service/conversion | Business + rights review | Business Data/Content | Не выдумывать; production remains blocked |
| Experience subject/method | Корректный numeric claim | hero/proof/FAQ/meta | Business confirmation | Content/Claims | Claim удалить до подтверждения |
| Production media rights | Законная публикация | all rendered media | Rights owner | Production | Preview-only media не продвигается |
| Production domain/canonical/SEO scope | Публичный release | publisher/meta/sitemap/schema | Business + release owner | SEO/Production | Preview остаётся noindex |

## 6. Отклонённые и неподтверждённые замечания

- `ISSUE-01` отклонён как дефект текущего результата: URL намеренно является isolated preview и не выдавался за production. Требование branded domain верно только для будущей production promotion.
- `ISSUE-04` подтверждён в точном scope аудитора: скриншоты показывают стоматологию, Киев, направления и CTA, но не показывают доказуемую причину выбрать именно эту клинику.
- `ISSUE-05` подтверждён частично: узкая rendered taxonomy объективна, а расхождение с текущим реальным каталогом требует business confirmation; более широкий старый официальный источник доказывает research gap, но не актуальную service matrix.
- `ISSUE-12` не является release defect noindex preview. Он становится blocker при production/SEO scope.
- В `ISSUE-16` подтверждено расхождение имени; точная оценка slogan/tone требует утверждённого brand guide.
- Нельзя считать актуальными без business confirmation сведения старого официального сайта о составе врачей, оборудовании, услугах, ценах, отзывах и контактах.
- Не подтверждены права/consent на clinical cases и patient media.
- Не подтверждено фактическое завершение Instagram Direct; проверен только href.
- Нельзя публиковать предложенные аудитором медицинские и ценовые формулировки как готовый copy: это иллюстрации, не verified facts.

## 7. Системные причины

1. **Evidence regression.** Current source ledger потерял ранее найденный официальный сайт и допустил platform URL как official source; cache migration проверяет версию, но не business linkage и не деградацию source quality.
2. **Synthetic evidence inflation.** Provisional preview contract создаёт default themes и помечает submitted Instagram URL как evidence; readiness считает эти labels полноценными sourced themes.
3. **No business completeness state.** Required facts и `production_blocker` существуют в research, но не агрегируются в вычисляемый блокирующий artifact.
4. **Contact is confused with conversion.** Любой Instagram считается contact path; наличие anchor/form принимается за результат без click/submit/error/success verification.
5. **Spec is confused with rendered reality.** Five-second gate читает весь первый section и может подставить CTA из spec, не проверяя реальный fold.
6. **Role labels are confused with customer value.** `proof`, `trust_process` и другие roles проходят по атрибутам и количеству секций без source-bound content.
7. **Semantic repetition detector is too shallow.** Визуально разные blocks с одинаковыми услугами/Instagram прошли с пустым findings list.
8. **Media gate проверяет права, не пригодность.** Размер/наличие/rights проходят, а baked-in social text, focal point, crop meaning и alt-function не проверяются.
9. **Brand gate слишком визуальный.** Pixel checksum и palette присутствуют, но canonical naming/slogan/tone не входят в acceptance.
10. **Claims validation слишком узкая.** Есть точечная проверка exact 20 years, но нет subject/method/source-bound final claim ledger.
11. **Queue status подменяет readiness.** `preview_ready` корректно означает опубликованный preview, но рядом отсутствуют независимые `DESIGN_READY`, `CONTENT_READY`, `BUSINESS_DATA_COMPLETE`, `FUNCTIONALLY_READY`, `SEO_READY`, `PRODUCTION_READY`.
12. **Live production QA недостаточен.** HTTP/assets/business marker не доказывают реальный customer journey, forms, keyboard, multi-route, claims и SEO behavior.

## 8. Существующие правила, которые нужно усилить

| Файл | Существующее правило | Почему не сработало | Точное изменение |
|---|---|---|---|
| `.codex/project_brain/QUALITY_BAR.md` | Scope соответствует evidence; section не filler; first viewport объясняет offer/CTA | Runtime не исполняет prose contract | Связать с typed completeness/section/viewport artifacts в acceptance |
| `.agents/skills/conversion-copy/SKILL.md` | Verified copy, no invented facts | `use Direct/Instagram for unknown details` стало page narrative | Разрешать Direct как один fallback, но core missing facts блокируют full-site content; caveat максимум один раз |
| `.agents/skills/storytelling/SKILL.md` | У каждой секции customer question/message/proof/decision | Эти поля не привязаны к final DOM | Ввести stable section IDs + `SectionPurposeReport` + source IDs |
| `.agents/skills/accessibility-review/SKILL.md` | Meaningful media alternatives | Technical gate проверяет asset, не смысл alt | Добавить media-function/alt/embedded-text review и regression fixture |
| `.agents/skills/responsive-review/SKILL.md` | No overflow, 44 px, persistent navigation | Проверяет только 1440/768/390 | Добавить 1024/360 и boundary-driven widths; не маскировать overflow `overflow-x:hidden` |
| `.agents/skills/siteagent-web-studio/SKILL.md` | Missing caveat не становится narrative | Studio получил Level A и слабый contract | Сохранять requested `full_commercial_site` и разрешать явно incomplete preview/design build; при core blockers оставлять Business Data/dependent Content/Functional/SEO/Production readiness false и не принимать role labels как evidence |
| `site_agent/design_quality.py` | Level/PageScope readiness | Instagram + 3 themes + media дают full site | Исключить синтетические themes; required facts и risk profile входят в computed completeness |
| `site_agent/commercial_usefulness.py` | Five-second, conversion, full commercial path | Substrings/section counts/spec CTA дают false pass | Использовать browser-visible fold, unique section purpose, source-bound trust и conversion outcomes |
| `site_agent/product_director.py` | Blind independent product audit | Проверяет role/count, не смысл | Требовать source IDs, customer job, unique message, CTA outcome и scope-derived requirements |
| `site_agent/critic.py` | Browser technical gate | Не исполняет states/journey | Click/submit/menu/focus/hover/active/all routes + 360/1024 + console/network report |
| `site_agent/brand.py` и Brand Fidelity | Logo/palette fidelity | Naming mismatch не входит в gate | Добавить canonical name/slogan/tone fields и cross-surface consistency |
| `site_agent/acceptance.py` | Aggregated acceptance | Доверяет upstream booleans | Требовать checksum-bound completeness/section/conversion/claim/readiness artifacts |
| `site_agent/publisher.py` | Live verify | HTTP-only | После deploy запускать Playwright journey; Telegram production только после pass |

## 9. Новые правила, только если аналога нет

### RULE-BDC-01. Вычисляемая полнота бизнес-данных

**Проблема:** full commercial site проходит при unresolved required facts.
**Область:** все commercial sites, с risk/scope profile.
**Этап:** после research и перед production promotion.
**Ответственный:** Research Strategist формирует данные; control plane вычисляет.
**Действие:** `BusinessDataCompletenessReport` хранит requirement, required/optional/not-applicable, value, source IDs, confidence, freshness и blocker.
**Запрещено:** `BUSINESS_DATA_COMPLETE=true` без source у required fact.
**Проверка:** schema/source/checksum validation; manual confirmation только там, где public evidence недостаточен.
**Pass:** каждый required item verified или допустимо not-applicable.
**Блокирует:** Business Data, Content по зависимым фактам, Production Ready.
**Regression:** missing core facts + synthetic themes не дают Business Data/dependent Content/Functional/SEO/Production readiness, но не блокируют честную incomplete preview/design build.
**Связанные ISSUE:** 03, 05, 07, 08, 11, 13, 16.

### RULE-CONVERSION-01. Проверяемое завершение конверсии

**Проблема:** ссылка или пустая форма считаются customer outcome.
**Область:** каждый primary CTA.
**Этап:** local final QA и live production QA.
**Ответственный:** frontend/browser QA.
**Действие:** хранить selector, intent, mode, target/source, click/submit, invalid/success/error result.
**Запрещено:** ложное confirmation, wrong business target, social-only path без явного scope/альтернативы, form без backend или честного demo state.
**Проверка:** Playwright interaction report.
**Pass:** каждый CTA даёт заявленный outcome.
**Блокирует:** Functional/Production Ready; ложная copy также Content Ready.
**Regression:** Instagram-only Amidental fixture не проходит full commercial conversion.
**Связанные ISSUE:** 02, 06, 10.

### RULE-CLAIMS-01. Финальный claim ledger

**Проблема:** factual/numeric claim попадает в final DOM без субъекта/source.
**Область:** HTML, meta, OG, JSON-LD.
**Этап:** после build, перед reuse/acceptance/promotion.
**Ответственный:** Content QA + control plane.
**Действие:** извлечь page/selector/text/class/source IDs/provenance/checksum; для чисел хранить subject, unit, period и method.
**Запрещено:** unsupported claim, numeric drift, demo fact как production fact, stale ledger.
**Проверка:** DOM extraction + provenance/numeric rules + bounded manual ambiguity review.
**Pass:** каждый factual claim имеет допустимый provenance.
**Блокирует:** Content/Production Ready.
**Regression:** bare `20 years` без субъекта не проходит.
**Связанные ISSUE:** 09; factual aspects 03, 05, 07, 08, 11, 13.

### RULE-READINESS-01. Независимая readiness matrix

**Проблема:** lifecycle/authorization/HTTP 200 интерпретируются как product readiness.
**Область:** все preview и production runs.
**Этап:** после каждого соответствующего gate и перед production completion.
**Ответственный:** release controller.
**Действие:** checksum-bound `ReadinessReport` вычисляет `RESEARCH_COMPLETE`, `BUSINESS_DATA_COMPLETE`, `STRUCTURE_READY`, `DESIGN_READY`, `CONTENT_READY`, `FUNCTIONALLY_READY`, `BROWSER_QA_PASSED`, scoped `SEO_READY` и aggregate `PRODUCTION_READY`.
**Запрещено:** вручную выставлять readiness boolean без evidence.
**Проверка:** artifact validation + live browser suite + human gate где требуется.
**Pass:** все applicable statuses true/not-required, rights/authorization/human gates пройдены.
**Блокирует:** production completion и Telegram production delivery.
**Regression:** `preview_ready` не подразумевает ни один production readiness status.
**Связанные ISSUE:** 01–18; особенно 01, 02, 03, 12.

Отдельные новые универсальные rules для FAQ, naming, taxonomy, alt, media и section purpose не создаются: у них уже есть аналоги. Усиливаются существующие content/story/accessibility/brand/media/IA contracts, чтобы избежать дублирования.

## 10. Release-gates и статусы готовности

| Gate | Условия прохождения | Проверка | Что блокируется |
|---|---|---|---|
| `RESEARCH_COMPLETE` | Ledger имеет business-linked sources, без source-quality regression | Schema/linkage/cache-version validation | Design start |
| `BUSINESS_DATA_COMPLETE` | Все required facts verified/not-applicable | `BusinessDataCompletenessReport` | Content/Production Ready |
| `STRUCTURE_READY` | IA покрывает scope; taxonomy едина; каждая секция имеет уникальную работу/source | DOM-to-section contract + Product Director | Design/Content Ready |
| `DESIGN_READY` | First viewport, media, responsive, brand, accessibility и screenshots pass | Desktop/tablet/mobile + 1024/360 visual/browser QA | Production Ready |
| `CONTENT_READY` | Claim ledger, FAQ utility, no repetition, trust/proof source-bound | Content/claim/section reports | Production Ready |
| `FUNCTIONALLY_READY` | CTA/form/menu/routes/states дают ожидаемый outcome | Playwright local + live interaction report | Production Ready |
| `BROWSER_QA_PASSED` | Exact tree/routes/viewports/states без critical/high console, network, overflow, accessibility или interaction defects | Checksum-bound local и live browser report | Production Ready |
| `SEO_READY` | Applicable production scope: domain/canonical/NAP/schema/sitemap/robots/pages | DOM/HTTP/crawl validation | Production Ready; для noindex preview `not_required` |
| `PRODUCTION_READY` | Все applicable gates + rights + authorization + human approval + exact deployed bytes live-tested | Aggregated checksum-bound report | Production completion/Telegram production message |

Текущий Amidental результат:

| Status | Decision |
|---|---|
| `preview_ready` | `true` как lifecycle: isolated preview опубликован и доставлен |
| `RESEARCH_COMPLETE` | `false` по усиленному контракту: source ledger потерял ранее найденный official business source и допустил platform URL |
| `STRUCTURE_READY` | `false`: 4/5 taxonomy conflict, role-only trust/proof и повторяющиеся section purposes |
| `DESIGN_READY` | `false`: generic value, media adaptation/alt, 360 overflow, naming inconsistency |
| `CONTENT_READY` | `false`: missing facts, ambiguous 20 years, weak FAQ, repetition, weak trust/proof |
| `BUSINESS_DATA_COMPLETE` | `false` |
| `FUNCTIONALLY_READY` | `false`: один Instagram target, нет direct completion route |
| `BROWSER_QA_PASSED` | `false` по усиленному gate: 360 overflow подтверждён, а 1024/360 и required interaction/state coverage не входят в сохранённый pass |
| `SEO_READY` | `not_required` для preview; `false` для production |
| `PRODUCTION_READY` | `false` |

## 11. План исправления Amidental

### Подтверждённые исправления без дополнительных данных

1. Исправить 360 px overflow и добавить 1024/360 regression.
2. Убрать противоречивое число направлений или честно назвать shortlist.
3. Удалить semantic repetition и Direct caveat из роли narrative.
4. Исправить media function/alt; убрать ключевые images, смысл которых зависит от baked text.
5. Оставить preview noindex и явно обозначить его review-only status.

### После получения информации от бизнеса

1. Утвердить canonical brand name, service matrix и primary conversion.
2. Добавить проверенные NAP/hours/map/direct contact.
3. Добавить актуальные doctors/credentials, medical trust, cases/reviews и rights.
4. Уточнить subject/method 20 years либо удалить claim.
5. Добавить first-step pricing или подтверждённую ненумерическую pricing logic.
6. Перепроектировать hero, service decision paths, trust/proof, FAQ и final conversion на verified facts.

### Browser QA

- 1440, 1024, 768, 390 и 360;
- sticky header top/middle/footer;
- mobile menu keyboard/touch;
- primary CTA default/hover/focus/active;
- every route and anchor;
- form invalid/success/error или phone/booking outcome;
- no horizontal overflow without masking;
- lazy media after full scroll;
- alt/embedded text/crop review;
- console/network/CLS/reduced-motion checks.

### Production settings

- только explicit `production-promote` после approvals;
- production media rights;
- branded domain, HTTPS, canonical;
- indexable robots/sitemap only after SEO Ready;
- live browser journey exact deployed bytes;
- production Telegram message только после `PRODUCTION_READY=true`.

### Future SEO scope

Отдельно после утверждения business data: service-page matrix, unique H1/title/description, NAP, Dentist/LocalBusiness schema, internal links, canonical/sitemap/robots и content usefulness per query. Не добавлять этот scope в текущий noindex preview задним числом.

## 12. План улучшения SiteAgent

1. **Business research:** business-linkage validation, bounded official-site internal crawl, source-quality regression и cache contract checksum.
2. **Business intake:** typed required facts по product/risk/scope; explicit CTA/domain/SEO/rights; не спрашивать то, что безопасно находится публично, но требовать confirmation для stale/high-risk facts.
3. **Content:** final claim ledger; убрать `Direct for unknowns` как разрешение строить narrative; core gaps не блокируют честную incomplete preview-сборку, но блокируют dependent Content/commercial/product/production readiness.
4. **Structure:** stable section IDs, customer question/new message/source IDs/next decision; taxonomy consistency.
5. **Design:** real viewport geometry; Product/Art rejection входит в fixer loop; anti-template history comparison.
6. **Media:** focal/safe regions, embedded text risk, alt function, section/claim binding, rendered crop report.
7. **Conversion:** typed CTA outcome contract и browser interaction tests.
8. **Trust:** risk-derived trust requirements; role label без evidence не проходит.
9. **Browser QA:** 360/1024, all routes, states/forms, console/network, live parity.
10. **Production QA:** readiness matrix из artifacts, не manual booleans; live Playwright before completion.
11. **Memory:** сохранить универсальный урок о syntactic acceptance, не факты Ami Dental.

Минимальная последовательность реализации после отдельного разрешения:

1. evidence/cache regression + `BusinessDataCompletenessReport`;
2. real first viewport + conversion outcome;
3. section-purpose/source-bound trust + Product Director correction;
4. claim ledger + media adaptation/accessibility;
5. readiness aggregation + live production journey;
6. cross-category regression fixtures: social-only, official-site-rich, explicit micro-site и insufficient-evidence blocker.

## 13. Проверка качества постоянной памяти

- Полный внешний аудит не копировался в project brain или runtime prompts; он сохранён только как audit artifact.
- В универсальные правила не перенесены имя Ami Dental, адреса, телефоны, услуги, изображения, цвета, preview URL и предложенный audit copy.
- Существующие правила first viewport, section purpose, accessibility, responsive, brand fidelity и production isolation не дублируются; для них указано усиление.
- Новые rules созданы только для отсутствующих вычисляемых contracts: business completeness, conversion outcome, final claim ledger и readiness matrix.
- Каждый rule имеет owner, action, forbidden result, verification, binary pass и blocked status.
- Preview/production isolation не ослабляется: исправляется commercial acceptance, а не безопасный preview lane.
- Reusable lesson: синтаксическое наличие contact/section/role/image не доказывает business completeness, customer value или working outcome.

## Следующий рекомендуемый шаг

Не изменять Amidental site и не начинать production promotion. После отдельного разрешения пользователя реализовать первый минимальный slice: исправление source/cache regression, typed business-data completeness, real first-viewport gate и conversion-outcome tests. Затем повторно прогнать точный Amidental fixture и независимый cross-category regression. Перестройку сайта начинать только после подтверждения business facts и прав.

На момент отчёта остаются непроверенными: актуальность business facts, права/consent на medical proof, Instagram Direct outcome, production media rights и live production behavior, поскольку production deployment не существует.
