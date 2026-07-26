# Проверка внешнего аудита Ami Dental и план системных изменений

Дата проверки: 2026-07-19
Целевой run: `053656c35b5d4ef58221c5be7171b625`
Режим: read-only аудит продукта и системы; код сайта, генератор и публикация не изменялись.

## 1. Executive conclusion

Внешний аудит в основном верно диагностирует коммерческую неполноту результата, но неверно описывает статус публикации. Проверенный URL является намеренным изолированным preview с `noindex`; он никогда не был объявлен production-сайтом, не менял custom domain и не проходил production promotion. Поэтому `ISSUE-01` не является дефектом текущего preview scope. Он становится release blocker только если этот URL пытаются выдать за production.

Главная подтверждённая системная ошибка иная: pipeline присвоил контентно неполному результату `Level A`, `full_site`, commercial score `100`, Product Director score `100` и acceptance `90`, хотя исследование того же run перечисляет неизвестными телефон, адрес, часы, полный каталог, команду, отзывы, цены и booking. Существующие проверки принимают Instagram за достаточный contact/conversion path, количество размеченных DOM-ролей — за полный customer journey, а наличие секции — за доказательство её коммерческой работы.

Итоговый статус:

- как технически изолированный preview: сохранённые проверки подтверждают доставку и `noindex`;
- как дизайн: визуально собран, но не проходит усиленный Five-Second/section-purpose gate;
- как контент: не готов из-за отсутствующих бизнес-данных, повторов и слабой trust architecture;
- как функциональный коммерческий сайт: не готов, поскольку весь путь завершается одним Instagram URL;
- как SEO-продукт: для preview `not_required`, для production — не готов;
- как production: не готов и корректно не был promoted.

Код сайта автоматически не исправлялся. Ниже зафиксирован план изменений системы, который сначала должен быть согласован.

## 2. Что было изучено

### Обязательная project memory и workflow

Прочитаны `AGENTS.md`, все обязательные документы `.codex/project_brain/` и все текущие файлы `.codex/workflow/`. Применён `$siteagent-project-director`. `$siteagent-web-studio` не применялся, потому что задача запрещает творческую генерацию и изменение сайта.

### Runtime и артефакты

Проверены:

- intake и queue: `site_agent/telegram_bot.py`, `site_agent/job_queue.py`, `site_agent/cli.py`;
- research/evidence/media: `site_agent/research.py`, `site_agent/instagram.py`, `site_agent/agents.py`, `site_agent/prompts.py`, `site_agent/media.py`;
- readiness/design/studio: `site_agent/design_quality.py`, `site_agent/models.py`, `site_agent/workflow.py`, `site_agent/studio.py`, `site_agent/brand.py`;
- QA/acceptance/release: `site_agent/commercial_usefulness.py`, `site_agent/product_director.py`, `site_agent/critic.py`, `site_agent/acceptance.py`, `site_agent/preview.py`, `site_agent/publisher.py`, `site_agent/orchestrator.py`;
- runtime skills из `.agents/skills/` и отдельный декларативный слой `.codex/skills/siteagent-*`;
- HTML, screenshots, reports, source ledger, queue item и deployment artifacts run `053656...`;
- предыдущий run того же бизнеса `f684eed531f74dd8995b2a58ac77739e` для проверки регрессии evidence discovery;
- исходный внешний аудит. В нём обнаружено только 10 уникальных ID: `01, 02, 03, 04, 05, 07, 08, 10, 11, 12`; `ISSUE-06` и `ISSUE-09` отсутствуют. Полные карточки даны только для `01–03`, остальные описаны в top-10 и общем тексте.

### Публичные источники

В день проверки доступен официальный сайт [Ami Dental](https://amidental.com.ua/), где опубликованы адрес, часы, телефоны и расширенный перечень услуг. Отдельно доступны страницы [специалистов](https://amidental.com.ua/category/specialists/), [оборудования](https://amidental.com.ua/about/oborudovanie/), [отзывов](https://amidental.com.ua/about/otzyvy/), [работ](https://amidental.com.ua/our-works/) и [контактов](https://amidental.com.ua/kontakty/). Это подтверждает наличие публичного источника, но не разрешает автоматически публиковать медицинские данные: часть материалов датирована 2020 годом, поэтому актуальность команды, услуг, цен, отзывов, прав на кейсы и контактов должна быть подтверждена бизнесом перед production.

### Проверки

- выполнена команда `python -m unittest tests.test_design_quality tests.test_commercial_usefulness tests.test_full_site_product_contract tests.test_technical_inspector tests.test_one_link_preview_contract tests.test_acceptance`: 48 tests, `OK`, 56.226 s. Машиночитаемое свидетельство сохранено в `.codex/handoffs/AMIDENTAL_AUDIT_TEST_EVIDENCE.json`;
- сохранённый browser QA run прошёл на `1440×1100`, `768×1024`, `390×844`;
- дополнительная read-only проверка выполнена на `1024×900` и `360×800`; наблюдения сохранены в `.codex/handoffs/AMIDENTAL_BOUNDARY_BROWSER_QA.json`;
- на 1024 px: нет явного horizontal overflow, нет малых tap targets или обрезанных CTA;
- на 360 px: меню раскрывается (`aria-expanded=false → true`, три видимых nav link), малых tap targets и обрезанных CTA не обнаружено, но `document.scrollWidth=369` при viewport `360`; overflow маскируется `body { overflow-x:hidden }`. Независимая изоляция связала overflow с hero typography/layout (`.hero-copy`/H1); причинность media, `service-band`, `route-rail` или caption не доказана. Это новый подтверждённый responsive defect;
- после полного scroll lazy images загрузились; первоначальное отсутствие нескольких natural widths не является broken-image defect;
- все 10 CTA имеют одну уникальную цель, и это Instagram.

## 3. Карта текущей архитектуры

1. Telegram intake извлекает только первый Instagram URL: `site_agent/telegram_bot.py:15-48`.
2. Queue жёстко задаёт `requested_product_type="full_commercial_site"`, не собирая страницы, язык, аудиторию, CTA, функции и SEO scope: `site_agent/job_queue.py:40-77`.
3. One-link research идёт через static Instagram → search → rendered browser → discovered official site: `site_agent/research.py:154-237`.
4. `ResearchStrategist` одним structured call превращает источники в `BusinessResearch`: `site_agent/agents.py:32-49`.
5. `assess_studio_readiness()` выдаёт EvidenceLevel/PageScope: `site_agent/design_quality.py:237-321`.
6. `DesignDirector` одним объектом объединяет структуру, narrative, first viewport, media, copy и responsive direction: `site_agent/models.py:104-129`, `site_agent/agents.py:52-104`.
7. Codex Studio создаёт концепты, выбирает направление по screenshots, строит финал и запускает fixer: `site_agent/studio.py:194-395`.
8. Technical Inspector, critic, commercial checks, Product Director и Acceptance Auditor формируют решение: `site_agent/critic.py:17-113`, `commercial_usefulness.py:197-339`, `product_director.py:105-269`, `acceptance.py:13-140`.
9. Preview verification проверяет маршруты, `noindex`, business marker и robots: `site_agent/preview.py:286-394`.
10. Production promotion отделён от preview и требует authorization, rights и live HTTP verification: `site_agent/cli.py:443-512`, `site_agent/publisher.py:566-651`.

Подтверждённые архитектурные пробелы:

- runtime реально snapshots только `.agents/skills`; более предметные `.codex/skills/siteagent-*` не являются исполняемым council;
- UX/story/copy/media/responsive не имеют отдельных typed artifacts и независимых acceptance gates;
- legacy category patterns всё ещё входят в context для текущих commercial reports;
- accessibility contract шире executable browser gate;
- browser QA не исполняет формы, CTA outcome, hover/focus/active и каждый route;
- current Studio anti-template gate не сравнивает результат с историей других бизнесов;
- evidence проверяется структурно, но не claim-by-claim в финальном DOM;
- Art/Product rejection не входит в fixer loop симметрично Brand rejection.

## 4. Проверка каждого ISSUE

Классы следуют исходному заданию и взаимоисключающи в таблице: A — site-specific defect; B — missing business data; C — reusable quality rule; D — system-level defect. Если у ISSUE есть дополнительные системные причины, они описаны в выводе, но основной класс выбран один.

| ISSUE | Статус | Основной класс | Проверенный вывод |
|---|---|---:|---|
| 01 — preview domain | `OUT_OF_CURRENT_SCOPE` | A | Это намеренный preview: `preview_deployment.json` хранит `environment=preview`, `noindex`, `custom_domain_changed=false`, `production_deployment_started=false`. Для production URL неприемлем, но current preview не выдавался за production. |
| 02 — Instagram-only conversion | `CONFIRMED` | D | CTA в `site/index.html:34,47,55,67,70,73,76,79` ведут к одной Instagram-цели; form, `tel:`, email и booking отсутствуют. Pipeline системно принимает Instagram/Direct за conversion completion, а Product Director не кликает CTA. |
| 03 — нет адреса/телефона/часов/карты | `CONFIRMED` | B | В HTML остаются только «Київ» и Instagram. Текущий research помечает поля неизвестными. Предыдущий run и официальный сайт находили контакты, но production требует business confirmation их актуальности. Потеря official source — отдельный system defect. |
| 04 — generic hero | `CONFIRMED` | C | H1 «Стоматологія для вашого запиту» объясняет нишу, но не формирует специфическое позиционирование. Внутренний critic уже отметил это medium issue, acceptance его не заблокировал; слабый Five-Second gate может повториться на других сайтах. |
| 05 — неполный каталог услуг | `PARTIALLY_CONFIRMED` | B | Текущий сайт показывает пять категорий, официальный источник содержит более широкий набор. Факт неполноты подтверждён, но актуальный продаваемый каталог и приоритеты должен подтвердить бизнес. |
| 07 — нет врачей/команды | `CONFIRMED` | B | Имена, роли, специализации и квалификации отсутствуют. Публичная страница специалистов существует, но её свежесть нельзя предполагать. |
| 08 — нет кейсов/результатов/отзывов | `CONFIRMED` | B | Proof-блок содержит оборудование/материалы и атрибутированный стаж, но не клинические кейсы или reviews. Публичные материалы существуют, однако нужны freshness, rights, privacy и business approval. |
| 10 — слабый FAQ | `CONFIRMED` | C | FAQ повторяет услуги и отправляет за адресом, стоимостью, планом и результатом в Instagram. Это повторяемый section-purpose/content QA defect; часть безопасного содержания ждёт business data. |
| 11 — нет цены первого шага | `CONFIRMED` | B | `visible_prices_offers=[]`; стоимость предлагается выяснить в переписке. Число нельзя выдумывать: нужна подтверждённая цена/диапазон либо честная ненумерическая логика оценки. |
| 12 — local SEO | `PARTIALLY_CONFIRMED` | C | Title/description/lang есть; NAP, canonical, Dentist/LocalBusiness schema и service architecture отсутствуют. Для intentionally noindex preview SEO не входит в scope; для production SEO это reusable release requirement. |

Дополнительные подтверждённые замечания внешнего аудита:

- naming inconsistency: logo `Ami Dental`, copy `Amidental Kiev`, handle `amidental_kiev`; публичное имя требует business decision;
- media используются как Instagram covers с embedded text и слабо адаптированы к роли сайта;
- визуальный polish не компенсирует отсутствие бизнес-данных;
- exact 360 px выявил скрытый horizontal overflow, которого не заметил стандартный gate на 390 px.

Что не подтверждено и не должно превращаться в факты:

- актуальность телефонов, адреса, часов, состава команды и расширенного каталога;
- наличие конкретного микроскопа, рентгена, лицензий, квалификаций и текущих отзывов;
- права на публикацию клинических кейсов и фотографий пациентов;
- точные цены и результат лечения;
- требуемое публичное написание бренда;
- успешное завершение Instagram Direct после авторизации: подтверждены href, не outcome.

## 5. Матрица готовности текущего результата

| Статус | Текущее решение | Почему |
|---|---|---|
| `DESIGN_READY` | `false` | Generic first viewport, повторяющаяся section logic, слабая media adaptation и скрытый overflow на 360 px. |
| `CONTENT_READY` | `false` | Не хватает business facts; FAQ и CTA повторяются; trust content неполон; нет финального claim ledger. |
| `BUSINESS_DATA_COMPLETE` | `false` | Не подтверждены обязательные для full commercial site контакты, hours, full services, team/trust data, first-step pricing logic и CTA destination. |
| `FUNCTIONALLY_READY` | `false` | Один внешний Instagram target, нет no-social-required completion route, CTA outcome не проверяется. |
| `SEO_READY` | `not_required` для preview; `false` для production SEO scope | Preview правильно `noindex`; production canonical/NAP/schema/indexing architecture отсутствуют. |
| `PRODUCTION_READY` | `false` | Предыдущие статусы не пройдены, production rights и business confirmation отсутствуют, custom domain не авторизован. |
| Existing `preview_ready` | `true` как lifecycle state | Preview опубликован и доставлен; этот статус нельзя интерпретировать как качество или production readiness. |

Эти статусы сейчас отсутствуют в runtime. Repo-wide search не нашёл ни одного из шести имён; имеются только `EvidenceLevel`, `PageScope`, `TechnicalGate.passed`, `approved_for_delivery`, `AcceptanceAuditResult.approved`, `is_verified_production` и queue lifecycle states.

## 6. Аудит восьми обязательных quality gates

| Gate | Существующий эквивалент | Реально блокирует? | Вывод |
|---|---|---|---|
| Business Data Completeness | `BusinessResearch`, `missing_content_manifest`, `EvidenceAssessment` | Частично | `content_provenance.production_blocker` не исполняется; Instagram считается contact path; provisional contract синтезирует product/themes и открывает full-site readiness. Усилить. |
| Five-Second | commercial usefulness + art caps | Частично | Берётся весь первый `<section>`, а rendered CTA может подставляться из `SiteSpec`. Нужен реальный viewport artifact. Усилить. |
| Conversion Completion | `conversion_path_present`, `final_conversion`, form/anchor presence | Недостаточно | CTA не кликается; target/outcome не проверяются; любая form может считаться conversion. Добавить machine-readable contract. |
| Trust Architecture | `trust_signals`, roles `proof`/`trust_process` | Формально | Role label проходит без source-bound proof. Усилить существующий gate. |
| Section Purpose | `SectionPlan`, semantic repetition, decision roles | Формально | Final DOM не связан с planned purpose/source; count/labels могут пройти filler. Усилить. |
| Media Adaptation | crop/provenance/naturalWidth | Частично | Права и загрузка контролируются хорошо; focal subject, meaning, responsive crop и text overlays — нет. Усилить. |
| Claims Verification | provenance prompt, forbidden claims, exact-duration gate | Узко | Нет извлечения всех final claims и связи с ledger; production blockers игнорируются. Добавить final claim ledger. |
| Production Release | acceptance + authorization + HTTPS/assets | Сильный lane gate | Preview/production разделены правильно, но нет вычисляемого `PRODUCTION_READY` и live browser journey. Усилить, не дублировать. |

Ключевой regression в evidence path: предыдущий run нашёл `https://amidental.com.ua/`; текущий source ledger потерял официальный сайт и сохранил platform links. `_upgrade_cached_preview_intake()` не считает `meta.ai` и `threads.com` platform URLs и досрочно принимает cache с текущей pipeline version. Затем `_apply_provisional_preview_contract()` синтезирует темы и `full_site`, а `assess_studio_readiness()` считает один Instagram достаточным contact path. Исправление должно быть универсальным: валидировать business linkage и регрессию источников, а не хардкодить Ami Dental.

## 7. Новые и изменяемые правила

## RULE-BDC-01. Вычисляемая полнота бизнес-данных (новое)

- **Проблема, которую предотвращает:** production проходит при unresolved `missing_required_fact`.
- **Этап выполнения:** после research и повторно перед production promotion.
- **Исполнитель:** Research Strategist формирует данные; control plane вычисляет статус.
- **Обязательное действие:** создать `BusinessDataCompletenessReport` с requirement, `required/optional/not_applicable`, value, source IDs, confidence, scope/risk profile и blocker.
- **Запрещённый результат:** `BUSINESS_DATA_COMPLETE=true` без source у required fact или при unresolved blocker.
- **Автоматическая или ручная проверка:** schema/source/checksum validation; ручное подтверждение только недоступных публично фактов.
- **Критерий прохождения:** каждый required item `verified` либо допустимо `not_applicable`.
- **Что блокируется при провале:** `BUSINESS_DATA_COMPLETE`, `PRODUCTION_READY`; `CONTENT_READY`, только если факт обязателен для заявленного content scope. Preview/design могут продолжаться с явным blocker.
- **Связанные ISSUE:** 03, 05, 07, 08, 10, 11.

## RULE-FIVE-SECOND-01. Первый реальный viewport (усиление)

- **Проблема, которую предотвращает:** сайт проходит по spec, хотя offer/CTA не видны или не специфичны.
- **Этап выполнения:** final render и повторно live.
- **Исполнитель:** Browser QA + commercial auditor.
- **Обязательное действие:** сохранить visible text и bounding boxes до fold на desktop/mobile; проверить identity, offer, evidence-backed value и actionable CTA.
- **Запрещённый результат:** использовать весь первый `<section>` или `SiteSpec.primary_cta` как доказательство rendered visibility.
- **Автоматическая или ручная проверка:** Playwright geometry + screenshot-led review.
- **Критерий прохождения:** на обоих viewport видны специфичный offer и работающий CTA, без overlap/crop.
- **Что блокируется при провале:** copy → `CONTENT_READY`; layout → `DESIGN_READY`; в любом случае `PRODUCTION_READY`.
- **Связанные ISSUE:** 04.

## RULE-CONVERSION-01. Проверяемое завершение конверсии (новое)

- **Проблема, которую предотвращает:** ссылка или пустая форма считаются завершённым customer journey.
- **Этап выполнения:** final browser QA и live production QA.
- **Исполнитель:** frontend/browser QA.
- **Обязательное действие:** для каждого primary CTA хранить selector, intent, mode, target, source; click/submit, invalid, success и error проверки.
- **Запрещённый результат:** `href="#"`, неверный бизнес target, форма без backend/честного demo state, ложное сообщение об отправке, CTA только в тексте.
- **Автоматическая или ручная проверка:** Playwright interaction report + review формулировки результата.
- **Критерий прохождения:** каждый CTA приводит к заявленному результату; form states честны и работоспособны.
- **Что блокируется при провале:** `FUNCTIONALLY_READY`, `PRODUCTION_READY`; ложная copy также `CONTENT_READY`.
- **Связанные ISSUE:** 02, 03, 10, 11.

## RULE-TRUST-01. Evidence-bound trust architecture (усиление)

- **Проблема, которую предотвращает:** пустой/общий `proof` role считается доверием.
- **Этап выполнения:** research → brief → content QA → acceptance.
- **Исполнитель:** Research Strategist, Design Director, Product Director.
- **Обязательное действие:** вывести trust requirements из scope/risk; связать каждый item с verified fact, authorised media, процессом или blocker; финальная секция должна ссылаться на IDs.
- **Запрещённый результат:** декоративный role без proof; выдуманные врачи, reviews, licenses, cases, results.
- **Автоматическая или ручная проверка:** source/ID validation + screenshot-led review.
- **Критерий прохождения:** обязательные trust jobs покрыты неповторяющимися source-bound элементами.
- **Что блокируется при провале:** data gap → `BUSINESS_DATA_COMPLETE`; content → `CONTENT_READY`; architecture → `DESIGN_READY`; затем `PRODUCTION_READY`.
- **Связанные ISSUE:** 07, 08, 10.

## RULE-SECTION-PURPOSE-01. Проверяемая работа каждой секции (усиление)

- **Проблема, которую предотвращает:** count/role labels маскируют filler и повторение.
- **Этап выполнения:** brief, final DOM validation, independent review.
- **Исполнитель:** Storytelling/Design Director, control plane, Product Director.
- **Обязательное действие:** checksum-bound `SectionPurposeReport`: section ID, customer question, new message, source IDs, role, CTA relationship, next decision; bind final DOM to stable IDs.
- **Запрещённый результат:** секция без новой информации/доказательства/решения; role-only block; блок вне brief.
- **Автоматическая или ручная проверка:** DOM-to-contract, semantic repetition, screenshot narrative review.
- **Критерий прохождения:** каждая required section выполняет отдельную работу и основана на разрешённых источниках.
- **Что блокируется при провале:** `DESIGN_READY`, `CONTENT_READY`, `PRODUCTION_READY`.
- **Связанные ISSUE:** 04, 05, 10.

## RULE-MEDIA-ADAPT-01. Адаптация media по смыслу и viewport (усиление)

- **Проблема, которую предотвращает:** технически валидная картинка теряет subject, противоречит claim или плохо кадрируется.
- **Этап выполнения:** media prep, implementation, responsive QA.
- **Исполнитель:** Media Director, frontend implementer, responsive reviewer.
- **Обязательное действие:** хранить focal/safe region, aspect ratios, section/claim IDs, alt, permitted uses; собирать rendered geometry/object-fit/object-position/natural size и screenshot crop на boundary viewports.
- **Запрещённый результат:** потеря subject, один случайный center crop, media/claim contradiction, embedded social text вместо адаптации, broken asset.
- **Автоматическая или ручная проверка:** image-layout report + обязательный visual crop review.
- **Критерий прохождения:** media загружается, остаётся читаемым и поддерживает section purpose на каждом viewport.
- **Что блокируется при провале:** meaning/crop → `DESIGN_READY`; load/overflow → `FUNCTIONALLY_READY`; critical/high → `PRODUCTION_READY`.
- **Связанные ISSUE:** замечание об использовании Instagram covers без смысловой адаптации. Дефект 360 px относится к responsive typography/layout и не приписывается media gate.

## RULE-CLAIMS-01. Финальный claim ledger (новое)

- **Проблема, которую предотвращает:** unsupported claim попадает в DOM/meta/JSON-LD, обходя literal forbidden check.
- **Этап выполнения:** после final build и перед reuse/acceptance/promotion.
- **Исполнитель:** Content QA + control plane.
- **Обязательное действие:** извлечь factual claims из HTML/meta/OG/JSON-LD; хранить page, selector, normalized text, class, source IDs, provenance status, checksum; числа сверять строго.
- **Запрещённый результат:** fact без source, numeric drift, demo content как production fact, unresolved missing fact, stale report.
- **Автоматическая или ручная проверка:** DOM extraction + provenance/numeric validation + manual ambiguity review.
- **Критерий прохождения:** каждый factual claim имеет допустимый provenance, blockers разрешены, checksum совпадает с deploy tree.
- **Что блокируется при провале:** `CONTENT_READY`, `PRODUCTION_READY`; missing required source оставляет `BUSINESS_DATA_COMPLETE=false`.
- **Связанные ISSUE:** 03, 05, 07, 08, 11, 12.

## RULE-PRODUCTION-01. Вычисляемая production readiness (усиление)

- **Проблема, которую предотвращает:** authorization booleans и HTTP 200 выдаются за полный production preflight/live QA.
- **Этап выполнения:** до upload, после live deploy, перед Telegram completion.
- **Исполнитель:** production release controller.
- **Обязательное действие:** checksum-bound `ReadinessReport` с шестью независимыми statuses/evidence; promotion вычисляет статусы из artifacts; live Playwright повторяет Five-Second, conversion, media, console/network, claims и applicable SEO.
- **Запрещённый результат:** доверие к вручную выставленным readiness booleans; live completion по одному HTTP/assets report.
- **Автоматическая или ручная проверка:** artifact validation, live browser suite, explicit human approval где требуется.
- **Критерий прохождения:** `DESIGN_READY`, `CONTENT_READY`, `BUSINESS_DATA_COMPLETE`, `FUNCTIONALLY_READY`; `SEO_READY` passed или `not_required`; rights/authorization/human gates; exact deployed bytes прошли live QA.
- **Что блокируется при провале:** `PRODUCTION_READY`, production completion и Telegram production delivery. Upload допускается только для post-deploy checks, но их провал не допускает completion.
- **Связанные ISSUE:** 01, 02, 03, 12.

## 8. Минимальный план системных изменений

### Phase 1 — остановить ложноположительную evidence/readiness оценку

1. `site_agent/research.py`: валидировать official-site candidate по business linkage; исключить platform/about URLs; bounded crawl только релевантных official internal pages.
2. `site_agent/orchestrator.py`: versioned migration должна revalidate cache, отклонять `meta.ai`/`threads.com` и сигнализировать, если previously verified official source исчез; не выдавать синтезированные default themes за sourced content.
3. `site_agent/models.py`, `workflow.py`, `design_quality.py`: добавить `BusinessDataCompletenessReport`, включить provenance/missing manifest в обязательный handoff, вычислять scope по required facts, а не только themes/media/contact.
4. Regression tests: lost official source, platform URL masquerading, missing required facts, preview-with-blockers.

### Phase 2 — сделать commercial acceptance семантическим

1. `commercial_usefulness.py`: реальный first viewport artifact, source-bound trust, section-purpose mapping, conversion contract.
2. `product_director.py`: не принимать DOM role без содержимого/source IDs; проверять CTA outcome и scope-derived requirements.
3. `critic.py`: собирать geometry/visible copy/interactions на boundary viewports, включая 360/1024, focus/menu/form states и все routes.
4. `studio.py`: не подставлять spec CTA как rendered fact; связать final sections/media с typed contracts; art/product rejection направлять в fixer loop.
5. Skills `.agents/skills/`: уточнить `conversion-copy`, `storytelling`, `responsive-review`, `design-critic`, `siteagent-web-studio`; не создавать дублирующий универсальный rule layer.

### Phase 3 — claims, media и release aggregation

1. `media.py`/`studio.py`: focal/safe crop, claim/section binding, embedded-text risk, viewport image report.
2. `acceptance.py`: требовать claim ledger, section purpose, conversion, business completeness и readiness matrix; различать preview acceptance и production readiness.
3. `cli.py`/`publisher.py`: производить preflight booleans из artifacts; после deploy запускать browser journey, только затем production completion/Telegram.
4. Добавить `SEO_READY` как scoped status, не как обязательное требование для каждого noindex preview.

### Phase 4 — тесты и независимая калибровка

Минимальные test seams:

- `tests/test_one_link_intake.py` — official-site regression/platform filtering;
- `tests/test_one_link_preview_contract.py` — missing facts не открывают full-site readiness;
- `tests/test_design_quality.py` — business completeness matrix;
- `tests/test_commercial_usefulness.py` — real viewport и Instagram-only false pass;
- `tests/test_full_site_product_contract.py` — role-only content rejected;
- `tests/test_technical_inspector.py` — 360/1024, menu/focus/form/CTA outcome;
- `tests/test_acceptance.py` — six-status readiness and stale artifact checks;
- новые focused tests для claim ledger и media adaptation.

После реализации требуется отдельный regression fixture не только для стоматологии: минимум social-only business, business с официальным сайтом, content-poor Level B и Level C blocker. Универсальные rules не должны содержать Ami Dental facts.

## 9. Что требуется от бизнеса для production-версии Ami Dental

Обязательные подтверждения:

- официальное публичное имя и допустимые варианты написания;
- актуальный адрес, часы, телефоны, email/booking channel;
- primary conversion: звонок, форма, мессенджер, booking system или подтверждённая комбинация;
- актуальный каталог и приоритетные услуги;
- цена первого шага, диапазон или подтверждённая логика формирования стоимости;
- актуальные врачи/роли/квалификации, только если бизнес хочет их публиковать;
- разрешённые trust signals: оборудование, процессы, лицензии/сертификаты;
- права и consent для cases/before-after/patient media;
- разрешённые reviews и источник;
- production media rights;
- SEO scope, production domain, canonical business name/NAP;
- customer-approved About и CTA copy.

До получения этих данных система может сохранять только честно обозначенный incomplete/blocked preview и не должна маркировать его `BUSINESS_DATA_COMPLETE`, `CONTENT_READY` или `PRODUCTION_READY`. Автоматически уменьшать обычный `full_commercial_site` до micro-site запрещено; compact/campaign/teaser scope допустим только по отдельному явному запросу.

## 10. Решение и границы следующего шага

Внешний аудит не принят автоматически: каждое доступное ISSUE проверено и классифицировано. Его коммерческий вывод подтверждён, утверждение о неудачной production-публикации — отклонено как несоответствующее текущему scope.

Рекомендуемый следующий шаг — сначала реализовать Phase 1 и RULE-BDC-01/FIVE-SECOND-01/CONVERSION-01 с regression tests, затем повторно прогнать Ami Dental как диагностический fixture. Перестройка конкретного сайта должна начинаться только после business confirmation и отдельного разрешения пользователя.

На момент этого отчёта:

- site code: не изменён;
- generator/runtime code: не изменён;
- deployment/custom domain/Telegram production delivery: не изменены;
- остаётся unverified: актуальность business facts, Instagram Direct outcome, production media rights и live production behavior, поскольку production deployment не существует.
