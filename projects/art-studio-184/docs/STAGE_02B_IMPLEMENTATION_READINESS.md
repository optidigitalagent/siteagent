# Art Studio 184 — implementation readiness этапа 2B

Дата: 2026-08-02
Статус: readiness matrix после ответов владельца. Это оценка допустимости следующих работ, а не разрешение автоматически начинать дизайн, код, публикацию или этап 3.

## Статусы матрицы

- `READY` — contract достаточен для этой области и этапа.
- `READY WITH LIMITATIONS` — работу можно начинать только в явно указанной границе.
- `NOT READY` — существенный input или техническое решение отсутствует.
- `BLOCKED FOR PUBLICATION` — можно готовить внутренне, но нельзя выпускать в production.
- `DEFERRED` — сознательно перенесено и не должно заменяться placeholder content.

## Матрица

| Область | Architecture | Design | Code | Publication | Что осталось |
| --- | --- | --- | --- | --- | --- |
| Routes | `READY` | `READY` | `READY` | `READY` | Использовать ровно `/`, `/gallery/`, `/capabilities/`, `/philosophy/`, `/contacts/`; redirect-map только при отдельной migration задаче. |
| Page blueprints | `READY` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | Подставлять только confirmed content; conditional sections подавлять без filler. |
| Navigation/header/footer | `READY` | `READY` | `READY` | `READY WITH LIMITATIONS` | Final logo asset и production contact/privacy links; выполнить responsive/keyboard/browser QA. |
| Primary CTA | `READY` | `READY` | `READY` | `READY WITH LIMITATIONS` | `Обговорити проєкт` и Contacts/Telegram route подтверждены; form branch нельзя публиковать до backend/privacy. |
| Contact page | `READY` | `READY` | `READY WITH LIMITATIONS` | `BLOCKED FOR PUBLICATION` | Direct contacts/address/hours готовы; production page с утверждённой формой ждёт complete delivery/privacy contract. Suppression формы требует отдельного scope decision. |
| Form UI | `READY` | `READY` | `READY WITH LIMITATIONS` | `BLOCKED FOR PUBLICATION` | Реализовать labels, required name/contact, optional message/channel, consent, success/error; legal policy и backend остаются blockers. |
| Telegram-bot backend | `READY WITH LIMITATIONS` | `READY` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Endpoint/auth, bot destination/config, abuse protection, secret handling, transport contract и live success/error tests. |
| Form validation/states | `READY` | `READY` | `READY WITH LIMITATIONS` | `BLOCKED FOR PUBLICATION` | Точный phone/username validation, focus/error behavior, data retention, live delivery evidence и Telegram fallback verification. |
| Privacy/consent | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Определить controller, recipients, retention, legal model и реальную policy; утверждённая checkbox line одна недостаточна. |
| Brand identity direction | `READY` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | Name/dark direction подтверждены; final identity ждёт logo asset, variants и exact green. |
| Official logo | `READY WITH LIMITATIONS` | `NOT READY` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Получить authorised original, variants и usage rules; `184 Art Studio` не использовать вместо logo. |
| Exact green color | `READY WITH LIMITATIONS` | `NOT READY` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Зафиксировать sampled/brand HEX отдельно; `#00c8c0` не утверждён. |
| Portfolio shortlist | `READY` | `READY WITH LIMITATIONS` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Провести curation 8–15 projects, grouping, dedupe, quality/brand/rights review и selected-asset register. |
| Hero | `READY` | `NOT READY` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Shortlist, asset quality/crop study, final assignment и responsive derivatives; отдельного high-res original пока нет. |
| Gallery content model | `READY` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `BLOCKED FOR PUBLICATION` | `Project` schema подтверждена; нужны selected project records, media pipeline и safe captions. |
| Lightbox | `READY` | `READY` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | Implement keyboard/focus/scroll/reduced-motion/error states; фактические frames/captions зависят от shortlist. |
| Team section | `READY` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | Две карточки/copy/reference/background готовы; разработать честные placeholders, проверить responsive crop/contrast; реальных portraits нет. |
| Clients | `DEFERRED` | `DEFERRED` | `DEFERRED` | `BLOCKED FOR PUBLICATION` | Список, project links и permissions; до этого секцию полностью подавлять. |
| Reviews | `DEFERRED` | `DEFERRED` | `DEFERRED` | `BLOCKED FOR PUBLICATION` | Original text, author/role, source/date, permission и project linkage; не создавать placeholders. |
| Capabilities | `READY` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | Высокоуровневые 16 production capabilities подтверждены; documentary media/evidence pending; запрещены specs и guarantees. |
| Equipment | `READY WITH LIMITATIONS` | `NOT READY` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | Общий состав можно назвать; final section/photo treatment ждёт evidence/media; technical numbers запрещены. |
| Work process | `READY` | `READY` | `READY` | `READY` | Сохранять индивидуальный срок; sketch/3D/construction route описывать условно. |
| Payment model | `READY` | `READY` | `READY` | `READY` | Публиковать только в утверждённой последовательности `50%` до производства / `50%` после завершения и передачи. |
| Contacts | `READY` | `READY` | `READY` | `READY` | Перед production выполнить freshness/link checks; не обещать response time. |
| Address / Google Maps / hours | `READY` | `READY` | `READY` | `READY` | Проверить Maps URL и актуальность непосредственно перед release. |
| Delivery | `READY` | `READY` | `READY` | `READY WITH LIMITATIONS` | Указывать, что оплачивает заказчик и условия индивидуальны; возможен сторонний перевозчик. |
| Installation | `READY` | `READY` | `READY` | `READY WITH LIMITATIONS` | Только команда Art Studio 184 по Украине; международный монтаж запрещён. |
| Media rights | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | Owner permission получена; нужен selected-asset author/rights/mark register и individual brand risk decision. |
| Media storage | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Выбрать managed storage, загрузить selected subset, сохранить checksums/provenance; GitHub Pages не CDN. |
| Responsive images | `READY` | `READY WITH LIMITATIONS` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Нужны actual assets/dimensions, WebP/AVIF, responsive derivatives, focal points, `srcset/sizes` и priority plan. |
| Project captions/cases | `READY WITH LIMITATIONS` | `NOT READY` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Получить names, materials, sizes, dates, locations, clients и results; не выводить visual guesses. |
| Analytics/cookies | `DEFERRED` | `DEFERRED` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Решить, нужен ли Google Analytics; затем определить consent/legal/technical contract. |
| Core SEO architecture | `READY` | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `BLOCKED FOR PUBLICATION` | Unique UA metadata, canonical, sitemap, robots, OG, verified structured data и production indexability. |
| Production domain | `READY WITH LIMITATIONS` | `READY WITH LIMITATIONS` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Domain/control/hosting, canonical ownership, redirects и live verification не определены. |
| Copyright | `READY` | `READY` | `READY` | `READY` | Использовать утверждённую строку; при позднем релизе перепроверить год. |
| Overall production release | `READY WITH LIMITATIONS` | `NOT READY` | `NOT READY` | `BLOCKED FOR PUBLICATION` | Закрыть logo/green/media, Telegram backend, privacy, domain/SEO, responsive media и live QA; требуется отдельное production authorization. |

## 1. Можно ли начинать media curation?

**Да — `READY WITH LIMITATIONS`.** Можно выполнить read-only inventory, visual grouping, exact-deduplication и shortlist 8–15 проектов по визуальной силе, разнообразию, категориям, масштабу и минимальному числу похожих кадров. Нужно работать с текущими опубликованными файлами до появления originals, не скачивать все 190 без отдельной задачи, не выбирать окончательный hero и не делать production import. Результат должен быть project/asset register с dimensions, checksums, owner authorization, visible marks и intended roles.

## 2. Можно ли начинать content system?

**Да — `READY WITH LIMITATIONS`.** Можно проектировать source-bound content schema, статусы, exact-value fields, Ukrainian labels, process/payment records, capability records и conditional suppression rules. Нельзя писать полный page copy, case narratives, client/review proof, legal/privacy text или technical specs без evidence.

## 3. Можно ли начинать design system?

**Только частично — `READY WITH LIMITATIONS`.** Допустимы non-final explorations тёмного направления, typography/spacing/accessibility principles, team placeholder approach и media composition tests. Final color tokens, logo system, hero, equipment/process art direction и окончательная brand approval — `NOT READY` до logo asset, exact green и media curation. Этот этап 2B дизайн не начинает.

## 4. Можно ли начинать code scaffolding?

**Нет — как следующий этап это `NOT READY`.** Route shell, semantic navigation, page skeleton contracts и lightbox behavior уже специфицированы, но code scaffolding нельзя начинать в этапе 2B и не следует начинать до отдельной авторизации после Stage 2C. Сначала нужны brand/logo/color decisions, selected media manifest, hero strategy и form/privacy/backend boundary. Production gallery/media wiring, final branding, Telegram-бот, privacy-enabled form, analytics и deployment пока не готовы.

## 5. Что нельзя начинать

- финальный brand/design system с logo и окончательным green;
- окончательный hero selection;
- production media import/delivery без shortlist, register и derivatives;
- documentary equipment/process design без реальных фотографий;
- production Telegram-bot form без privacy/backend/security contract;
- clients/reviews/case copy без evidence;
- analytics/cookies;
- production SEO/indexability, deployment, custom domain, preview или publication;
- этап 3 без отдельного задания и без результатов следующего evidence/media checkpoint.

## 6. Рекомендуемый следующий этап

Рекомендуется отдельный **Stage 2C — Media curation, brand evidence и production-input closure**:

1. сгруппировать портфолио по реальным projects и выбрать shortlist 8–15;
2. создать selected-asset rights/marks/dimensions/checksum register;
3. получить official logo originals/variants и отдельно утвердить exact green HEX;
4. провести hero candidate/crop study без final page design;
5. получить/спланировать equipment/process photos;
6. определить Telegram-bot backend/security и privacy/controller/retention contract;
7. зафиксировать analytics decision и production domain dependency.

Stage 2C в рамках этого задания **не начинался**.
