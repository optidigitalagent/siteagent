# Art Studio 184 — Stage 01 SEO page map

Дата: 2026-08-02
Статус: карта кандидатов; keyword research, страницы и финальные metadata не создавались.

## 1. Правила SEO-архитектуры

1. Core site содержит ровно пять утверждённых routes.
2. Один поисковый intent не получает несколько конкурирующих URL.
3. Direction описывает готовый тип результата; capability — производственный метод. Они не смешиваются ради количества страниц.
4. Кандидат становится страницей только при одновременном наличии real service, самостоятельного intent, unique content, media depth и evidence.
5. Case page описывает один реальный проект, а не один image file.
6. Location modifier разрешён только после подтверждения реальной geography и уникального local value.
7. Thin, placeholder, programmatic и copied pages запрещены.
8. Core pages используют выбранные ASCII-slugs; новые slugs утверждаются после Ukrainian keyword research.

### Статусы кандидатов

| Статус | Значение |
| --- | --- |
| `READY FOR RESEARCH` | evidence достаточно, чтобы проверить demand, wording и конкуренцию intent; страница ещё не утверждена |
| `NEEDS CONTENT` | intent правдоподобен, но нет достаточного уникального текста/project depth/media |
| `NEEDS BUSINESS CONFIRMATION` | неизвестно, является ли это реально предлагаемой/публичной услугой или какова её граница |
| `NOT RECOMMENDED` | кандидат дублирует другую страницу, создаёт thin content или требует выдуманных фактов |

## 2. Core indexable pages

Core routes входят в V1, но становятся indexable только после production gate: подтверждённый domain, факты, контакты, права на media, unique Ukrainian copy, canonical, sitemap и отсутствие preview/noindex состояния.

| Route | Основной intent | Уникальная роль | Content/media/evidence gate | Overlap control |
| --- | --- | --- | --- | --- |
| `/` | Art Studio 184 / изготовление объёмных декоративных и branded objects | идентификация, overview offer, selected proof и путь | verified identity, approved offer wording, 8 grouped projects target, real CTA | не ранжировать home как подробную service/capability page |
| `/gallery/` | портфолио / реальные работы Art Studio 184 | единый project archive в трёх направлениях | rights manifest, project grouping, dedupe, safe captions, responsive derivatives | direction anchors не создают отдельные indexable URLs |
| `/capabilities/` | производственные возможности / путь от идеи к объекту | подтверждённые process groups и full process | capability matrix, in-house/partner boundary, process media, prohibited claims | не конкурировать с готовыми product directions |
| `/philosophy/` | подход мастерской к качеству | короткая evidence-backed story и decision rationale | owner-approved history/quality/durability wording, 2–4 authorised images | не повторять home/about/services |
| `/contacts/` | контакты Art Studio 184 / обсудить проект | minimal conversion и verified channels | primary route, form mode, privacy, verified contact/location/hours | не создавать отдельные phone/messenger/location thin pages |

## 3. Direction page candidates

| Рабочее название | Предполагаемый intent | Что подтверждает кандидат | Unique content нужен | Media нужен | Evidence нужен | Overlap risk | Статус |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `Об’ємні фігури та скульптури` | заказать объёмную фигуру/скульптуру | 81 portfolio assets в текущей series + owner taxonomy | виды задач, применимость, ограничения, process, decision guidance, несколько реальных cases | 8–12 grouped projects, details/scale/process | service confirmation, materials/process, rights, project facts | пересечение с large replicas и fiberglass pages | `READY FOR RESEARCH` |
| `Фотозони` | заказать фотозону | часть 56-assets series и owner category | formats/use cases, venue constraints, what client supplies, process | 6–10 distinct confirmed photo-zone projects | отдельная реальная услуга, terminology, delivery/install geography | пересечение с decorations/installations | `READY FOR RESEARCH` |
| `Декорації та інсталяції` | изготовление декораций/инсталляций | текущая combined gallery series | граница с photo zones, event/retail/art contexts, process | минимум 6 distinct non-photo-zone projects | подтвердить самостоятельную service line и taxonomy | высокий cannibalization с `Фотозони` и Gallery | `NEEDS BUSINESS CONFIRMATION` |
| `Вивіски` | изготовление вывесок | часть 53-assets signage/branded series | виды вывесок, условия, material/lighting boundaries, process | 6–10 grouped signage projects | подтвердить offered types, electric/neon claims, install geography | пересечение с branded objects и ad structures | `READY FOR RESEARCH` |
| `Брендовані об’єкти` | заказать branded display/object | часть 53-assets series | product replicas, retail/event display use, brief-to-object logic | 6–10 grouped projects с правами на brand display | подтвердить client/project link и trademark publication rights | пересечение с signs и large replicas | `READY FOR RESEARCH` |
| `Великі копії продуктів` | заказать увеличенную копию товара | visual clusters предположительно существуют | use cases, scale method, structure, finish, transport | минимум 5–6 distinct confirmed replica projects | подтвердить service, project classification, brand rights | subset branded objects / sculptures | `NEEDS BUSINESS CONFIRMATION` |

Research outcome может рекомендовать объединение, а не создание всех кандидатов.

## 4. Capability page candidates

| Рабочее название | Предполагаемый intent | Что должно подтверждать услугу | Unique content нужен | Media нужен | Evidence нужен | Overlap risk | Статус |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `3D-фрезерування пінополістиролу` | заказать CNC milling foam / изготовление формы | реальный offered process | задачи, входные файлы, допустимые материалы/размеры, ограничения, downstream finish | equipment/process/detail + resulting projects | in-house/partner, equipment/working size, public safety, contacts | с `Вироби з пінополістиролу` и general capabilities | `NEEDS BUSINESS CONFIRMATION` |
| `3D-друк` | заказать 3D printing для объектов/деталей | реальная capability | use cases, material/size/finish, integration into larger objects | printer/process/parts + finished use | in-house/partner, models/sizes/materials | generic competitive intent; может не соответствовать core buyer | `NEEDS BUSINESS CONFIRMATION` |
| `Вироби з пінополістиролу` | изготовление foam figures/decor | projects + production method | готовые product types, construction/reinforcement/finish, conditions | 6+ projects + process sequence | service and materials, durability limits, rights | direction/capability смешение; cannibalization sculptures | `NEEDS BUSINESS CONFIRMATION` |
| `Склопластикові скульптури` | изготовление fiberglass sculptures | confirmed material practice | when/why material applies, mould/form/finish, conditions | distinct fiberglass cases + process/detail | material identification per case, in-house/partner, claims | subset sculptures and foam workflow | `NEEDS BUSINESS CONFIRMATION` |
| `Виготовлення рекламних конструкцій` | заказать advertising structure | branded/signage evidence | types, construction, surface, installation, decision criteria | 6+ relevant structures + fabrication/install media | legal/service terminology, in-house/partner, geography | broad overlap signs/branded objects | `NEEDS BUSINESS CONFIRMATION` |

Ни одна capability page не имеет статуса `READY FOR RESEARCH`, потому что Stage 00 не подтверждает фактический публичный scope, equipment details и in-house/partner границы. Сначала нужен capability matrix владельца.

## 5. Case-page model

### Назначение

Case page создаётся только для проекта, где есть достаточно уникальной информации для customer decision, а не только красивый image set.

### Предварительная route model

`/projects/<approved-project-slug>/`

Slug утверждается после получения официального/безопасного названия. До этого страницы и placeholder slugs не создаются.

### Обязательное содержание одного case

1. один verified H1/project label;
2. задача/контекст, который разрешено публиковать;
3. что создала мастерская;
4. применимые подтверждённые process/material facts;
5. grouped gallery с cover и supporting frames;
6. scale/location/date/client только если подтверждены и разрешены;
7. честный result без invented metrics;
8. links к primary Gallery category и relevant Capabilities;
9. `Обговорити проєкт`.

### Media requirements

- ориентир 5–12 отличающихся кадров одного проекта;
- минимум cover, contextual view, detail и scale/process frame, если они реально существуют;
- high-resolution originals, rights/provenance, derivatives и safe alt;
- exact duplicates и near-identical frames не считаются depth;
- third-party marks требуют permission review.

### Evidence requirements

- project identity/grouping подтверждены владельцем;
- право публикации каждого frame;
- client/trademark relation только с разрешением;
- material, size, timing, location и result по источнику;
- no confidential production/customer information.

### Status

Model: `READY FOR RESEARCH`.
Все конкретные case pages: `NEEDS CONTENT` до project shortlist, metadata и rights review.

## 6. Overlap and consolidation rules

- `Фотозони` и `Декорації та інсталяції` остаются одним gallery category в V1; две SEO pages возможны только после доказанного distinct intent и media depth.
- `Вивіски` и `Брендовані об’єкти` остаются одной gallery category; отдельные pages не должны повторять одинаковые проекты/копирайтинг.
- `Великі копії продуктів` может быть case cluster или section, если самостоятельного demand/content недостаточно.
- `3D-фрезерування` и `Вироби з пінополістиролу` различаются technology vs result; без distinct buyer journey их лучше объединить с capabilities.
- `Склопластикові скульптури` не создаётся только ради material keyword, если все доказательства уже раскрыты на sculpture page.
- один project имеет один canonical case URL и может быть contextually linked из нескольких pages без копии case.

## 7. Страницы, которые пока создавать нельзя

| Кандидат | Статус | Причина |
| --- | --- | --- |
| отдельная `Команда` | `NOT RECOMMENDED` сейчас | нет имён, ролей, bios и authorised portraits; conditional home section достаточна |
| отдельная `Клієнти` | `NOT RECOMMENDED` сейчас | нет approved list/logo permissions/project links |
| отдельная `Відгуки` | `NOT RECOMMENDED` сейчас | нет original reviews, identities, sources и permission |
| `Ціни` / `Оплата` | `NOT RECOMMENDED` сейчас | нет confirmed prices, estimate process или payment scheme |
| equipment model/spec pages | `NOT RECOMMENDED` сейчас | models, sizes, materials и public value не подтверждены; высокий thin/technical risk |
| городские/location pages | `NOT RECOMMENDED` сейчас | location и service geography отсутствуют |
| generic `Послуги` | `NOT RECOMMENDED` | дублирует directions и capabilities без самостоятельного intent |
| отдельная page для каждого portfolio image | `NOT RECOMMENDED` | image не равен project/case, создаёт thin index |
| автоматически сгенерированные category/tag archives | `NOT RECOMMENDED` | создают duplicate/thin pages без unique decision support |

## 8. Requirements перед утверждением нового SEO URL

Для каждого кандидата должны быть заполнены:

- Ukrainian query/intent research и SERP classification;
- primary/secondary intent без конкуренции с core page;
- confirmed business priority и offered scope;
- unique outline, который не повторяет Gallery/Capabilities;
- минимум media/project depth из соответствующей строки;
- source-bound claims и prohibited-claims list;
- internal link plan и canonical ownership;
- title/H1/slug decision;
- conversion destination;
- owner/content approval и production media rights.

До этого карта является backlog research, а не sitemap расширения.

## 9. Technical SEO dependencies будущей реализации

- один canonical URL для каждой page;
- XML sitemap только с реальными indexable canonical pages;
- preview: `noindex,nofollow`; production indexability — отдельный gate;
- unique Ukrainian title/description и один H1;
- `BreadcrumbList` на внутренних/case pages после final IA;
- `Organization`/`LocalBusiness` только с verified entity/contact/location data;
- descriptive alt из confirmed visual facts;
- managed responsive media (`srcset`, `sizes`, dimensions, lazy loading ниже первого viewport);
- OG/Twitter image с правами;
- 404/redirect rules без duplicate route variants;
- performance budget: не публиковать все 190 originals eager.
