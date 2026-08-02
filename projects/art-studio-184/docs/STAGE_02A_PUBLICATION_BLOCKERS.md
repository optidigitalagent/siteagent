# Art Studio 184 — блокеры дизайна, кода, наполнения и публикации

Дата подготовки: 2026-08-02
Назначение: отделить стоп-условия разных этапов. Severity используется для порядка закрытия; status — только из системы этапа 2A.

## Реестр блокеров

| ID | Блокер | Severity | Что блокирует | Кто должен закрыть | Доказательство закрытия | Статус |
| --- | --- | --- | --- | --- | --- | --- |
| `D-01` | Официальное написание, logo/wordmark и usage rules не подтверждены | High | Начало visual design | Владелец | Authorised brand files + письменное подтверждение вариантов/ограничений | `NEEDS EVIDENCE` |
| `D-02` | Фирменный green и запрещённые цвета не определены | High | Начало visual design | Владелец + будущий Brand Reviewer | Source-bound palette/brand study + owner approval | `NEEDS EVIDENCE` |
| `D-03` | Hero strategy не подтверждена; нет high-res wide original | High | Финальный дизайн first viewport | Владелец + будущий Media Director | Разрешённый original ≥2000 px или approved composed strategy с crop evidence | `NEEDS EVIDENCE` |
| `D-04` | Project shortlist не подтверждён как реальные grouped projects | High | Portfolio-led design | Владелец | Project IDs, grouped frames, категории и priorities | `NEEDS OWNER ANSWER` |
| `D-05` | Business narrative/positioning не утверждены | Medium | Финальная content art direction | Владелец | Ответы Q63–Q68 + source statements | `NEEDS OWNER ANSWER` |
| `C-01` | Нет реального CTA destination | Critical | Реализацию conversion path | Владелец | Verified reachable primary channel + accepted CTA contract | `BLOCKED FOR PUBLICATION` |
| `C-02` | Form delivery mode/endpoint не выбран и не доказан | Critical | Реализацию production form | Владелец + будущий implementer | Delivery contract + successful and failure-path test evidence | `BLOCKED FOR PUBLICATION` |
| `C-03` | Privacy/controller/retention/consent contract отсутствует | High | Реализацию обработки персональных данных | Владелец + legal reviewer | Approved legal inputs bound to actual form mode | `NEEDS EVIDENCE` |
| `C-04` | Все 17 capability rows незакрыты | High | Реализацию содержательной `/capabilities/` | Владелец | Filled matrix с in-house/partner/not-performed, public wording, evidence | `NEEDS OWNER ANSWER` |
| `C-05` | Equipment facts отсутствуют | Medium | Публичные specs и equipment content | Владелец | Models/datasheets/photos + owner permission | `NEEDS EVIDENCE` |
| `C-06` | Реальный process/payment/change/handover не подтверждён | High | Process content и form expectation | Владелец | Approved operational sequence; payment/timing wording | `NEEDS OWNER ANSWER` |
| `F-01` | Project names, captions, materials, sizes, dates, locations и results неизвестны | High | Наполнение Gallery/cases/alt source facts | Владелец | Project metadata register с sources | `NEEDS EVIDENCE` |
| `F-02` | High-resolution originals shortlist не предоставлены | High | Media processing и финальное наполнение | Владелец | Originals checksum inventory | `NEEDS EVIDENCE` |
| `F-03` | Team content отсутствует | Low | Только optional Team section | Владелец | Names/roles/photos/consents или suppression decision | `NEEDS OWNER ANSWER` |
| `F-04` | Client/logo permissions отсутствуют | Medium | Только optional Clients proof | Владелец | Approved list + project linkage + logo permissions или suppression decision | `NEEDS EVIDENCE` |
| `F-05` | Review originals/sources/permissions отсутствуют | Medium | Только optional Reviews proof | Владелец | Source-bound review records или suppression decision | `NEEDS EVIDENCE` |
| `P-01` | Нет asset-level media rights/provenance | Critical | Любой public render portfolio media | Владелец/rights holder | Per-asset author, owner, business linkage, permission, intended use | `BLOCKED FOR PUBLICATION` |
| `P-02` | Third-party brands/client relations не разрешены | Critical | Branded frames, client names и logos | Владелец/клиент/rights holder | Per-project permission and safe claim decision | `BLOCKED FOR PUBLICATION` |
| `P-03` | Нет минимального verified contact/CTA route | Critical | Production conversion и primary contact action | Владелец | Fresh reachable primary channel + publication permission + CTA binding | `BLOCKED FOR PUBLICATION` |
| `P-04` | CTA/form success и error states не доказаны | Critical | Production conversion | Владелец + будущий QA reviewer | Live functional evidence for selected mode and fallback | `BLOCKED FOR PUBLICATION` |
| `P-05` | Capability/in-house/equipment/material claims не доказаны | High | Production `/capabilities/` и related copy | Владелец | Completed D4 matrix + evidence | `BLOCKED FOR PUBLICATION` |
| `P-06` | Payment, timing, delivery/install responsibility не подтверждены | High | Operational customer-facing claims | Владелец | Approved terms/process source | `BLOCKED FOR PUBLICATION` |
| `P-07` | Legal business/privacy pages не определены | High | Production form/legal footer | Владелец + legal reviewer | Applicable approved policy content and verified entity data | `BLOCKED FOR PUBLICATION` |
| `P-08` | Production domain/canonical/indexability не определены | Medium | Production SEO release | Владелец + future deployment owner | Controlled domain, canonical map, sitemap/robots/OG/schema verification | `NEEDS OWNER ANSWER` |
| `P-09` | Production media storage/derivatives не подготовлены | High | Performant public media delivery | Future implementer/media owner | Managed URLs, checksums, WebP/AVIF, responsive derivatives, dimensions | `BLOCKED FOR PUBLICATION` |
| `P-10` | Analytics/cookies не выбраны | Medium | Analytics/cookie features, но не базовый статический сайт без них | Владелец + legal reviewer | Explicit no-analytics decision или approved tools/consent contract | `NEEDS OWNER ANSWER` |
| `P-11` | Город, адрес, график и service geography не подтверждены | High | Только соответствующие footer/schema/local claims | Владелец | Fresh verified values + permission либо явный suppression decision / `NOT APPLICABLE` | `NEEDS OWNER ANSWER` |

## Блокирует начало дизайна

- `D-01` official brand package;
- `D-02` source-bound green/palette decision;
- `D-03` truthful hero media strategy;
- `D-04` owner-confirmed project grouping/priority;
- `D-05` не запрещает structural exploration, но блокирует финальную narrative art direction.

Архитектура этапа 1 уже утверждена и не является design blocker.

## Блокирует начало кода

- `C-01` рабочий CTA destination;
- `C-02` form mode, если в code scope входит production form;
- `C-03` privacy contract для любой реальной передачи персональных данных;
- `C-04` capability matrix для содержательной страницы;
- `C-06` process facts для customer-facing process;
- `D-03` и `D-04` для media-driven implementation без placeholders.

Framework, package, pages и components на этапе 2A не создаются независимо от статуса блокеров.

## Блокирует наполнение

- `F-01` source-bound project facts;
- `F-02` high-resolution originals;
- `P-01` права и provenance;
- `P-02` third-party brand permissions;
- `P-05` capability evidence;
- `D-05` approved origin/quality/positioning;
- `F-03`–`F-05` блокируют только соответствующие optional sections. При suppression decision они не блокируют остальной сайт.

## Блокирует публикацию

Critical publication blockers:

- `P-01` media rights/provenance;
- `P-02` third-party brands/client relations;
- `P-03` minimum verified contact/CTA route;
- `P-04` working conversion states.

High publication blockers:

- `P-05` capabilities;
- `P-06` payment/timing/delivery/install claims, если они выводятся;
- `P-07` applicable legal/privacy contract;
- `P-09` production media storage/performance;
- `P-11` location/hours/service-area fields only when they are intended to be shown. An explicit suppression decision or `NOT APPLICABLE` closes `P-11` without blocking the rest of the site.

Medium publication blockers:

- `P-08` domain/canonical/indexability;
- `P-10` analytics/cookies only if enabled.

Team, Clients и Reviews не обязательны для публикации. При отсутствии evidence их нужно полностью исключить; создавать generic replacements или fake proof запрещено.

## Стоп-граница 2A

- Дизайн, site code, framework, package, preview и deploy не создаются.
- Stage 01 routes, H1, page order, form scope и CTA architecture не редактируются.
- Публичные portfolio files не скачиваются и не переносятся.
- Следующий допустимый шаг после этого пакета — получить ответы владельца и evidence, затем отдельно решить готовность к этапу 2B.
