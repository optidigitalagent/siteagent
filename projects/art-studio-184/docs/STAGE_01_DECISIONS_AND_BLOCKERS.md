# Art Studio 184 — Stage 01 decisions and blockers

Дата: 2026-08-02
Назначение: отделить принятые архитектурные решения от неизвестных фактов, development dependencies и publication blockers.

## 1. Решения, принятые на этапе 1

1. Сайт имеет ровно пять core pages: `Головна`, `Галерея`, `Виробничі можливості`, `Філософія`, `Контакти`.
2. Утверждён один route set: `/`, `/gallery/`, `/capabilities/`, `/philosophy/`, `/contacts/`.
3. Short ASCII slugs выбраны для стабильности и отсутствия конкурирующих вариантов транслитерации; public labels остаются украинскими.
4. Основной путь: `Головна → Галерея → Виробничі можливості → Філософія → Контакти`.
5. Primary CTA на всех страницах: `Обговорити проєкт`.
6. Primary CTA не обещает estimate, цену, срок ответа или принятие заказа.
7. Первые четыре страницы завершаются отдельным переходом к следующей странице; Contacts не получает искусственный next page.
8. Header persistent на всех scrollable pages; mobile menu имеет focus/scroll/Escape contract.
9. Footer содержит navigation, conversion и только подтверждённые contacts; metadata strip не считается footer.
10. Home H1: `Створюємо об’ємні фігури, декорації та брендовані об’єкти`.
11. Gallery H1: `Реальні роботи Art Studio 184`.
12. Capabilities H1: `Виробничі можливості Art Studio 184`.
13. Philosophy H1: `Підхід Art Studio 184 до роботи`.
14. Contacts H1: `Обговорімо ваш проєкт`.
15. Home selected-work target — 8 реальных grouped projects; меньше допустимо при недостатке сильных authorised projects.
16. Gallery V1 editorial target — 6 projects в каждой из трёх categories, 18 total, по 1 cover и до 3 supporting frames; это target, не minimum для filler.
17. Галерея единая; category navigation ведёт к трём неповторяющимся sections.
18. Content unit Gallery — `Project`; image file не является case.
19. Same-object frames группируются, exact duplicates исключаются, filename similarity не заменяет ручную project classification.
20. Lightbox работает внутри одного project и имеет keyboard, swipe, focus, scroll-lock, reduced-motion и lazy-loading contract.
21. Три направления home ведут к gallery anchors, а не к автоматически созданным SEO pages.
22. Capabilities разделены на шесть production groups; каждая публикуется только после подтверждения.
23. Home process — 5 укрупнённых шагов; full capabilities process — 7 шагов без payment/timing/guarantee claims.
24. Philosophy остаётся короткой: Intro + 3 narrative sections, 2–4 images, CTA и transition.
25. Contact form минимальна: required `Ім’я` и `Контакт`; preferred channel и short description — optional/conditional.
26. Team, clients и reviews — conditional; при отсутствии evidence sections удаляются полностью.
27. SEO direction/capability/case routes — backlog candidates, не утверждённые pages.
28. Unique Rabbit используется только как сценарный ориентир, не как структура/дизайн/copy source.
29. Текущий draft не является codebase; будущий сайт создаётся как новый isolated project только в отдельном этапе.
30. Stage 1 не создаёт site code, framework choice, media, design system, preview, deployment или final copy.

## 2. Решения, перенесённые на следующий этап

| Решение | Почему не утверждается сейчас | Нужный input |
| --- | --- | --- |
| официальный logo/wordmark/spelling | Stage 00 не содержит authorised brand package | original brand files + owner confirmation |
| точный green и full palette | `#00c8c0` из draft/portfolio не доказывает бренд Art Studio 184 | logo/media color study + approval |
| визуальная concept/design system | прямо вне Stage 1 scope | approved architecture + brand/media package |
| конкретный hero asset/layout | нет ideal wide asset и rights manifest | high-res originals, rights, crop tests |
| окончательные 8 home projects / 18 gallery projects | 190 files ещё не сгруппированы как projects | owner-assisted project grouping, curation, rights |
| финальные project names/captions | metadata отсутствует | project facts + publication permission |
| primary CTA destination/form mode | contacts/backend/fallback не подтверждены | verified channel или backend contract |
| точный capability copy | in-house/partner и process facts не подтверждены | capability matrix владельца |
| точный process/payment/timing | operational scheme не подтверждена | owner-approved journey/terms |
| Philosophy history/anti-cheap wording | origin и positioning требуют approval | source statement от владельца |
| public contact/location/hours | данных нет | verified current details |
| team/client/review sections | evidence нет | records, media, source, permissions |
| privacy/legal content | form processor/entity/analytics не определены | legal/business data и implementation choices |
| SEO slugs/pages | keyword research запрещён на Stage 1 | separate SEO research + content/evidence |
| redirects со старого draft | нет контроля/источника старого deployment | domain/repository ownership и migration task |

## 3. Блокеры разработки

Stage 2 не начинается без отдельного задания. Для содержательной реализации, а не пустого shell, дополнительно требуются:

### D1 — Brand identity package

- official Ukrainian/public spelling;
- authorised logo/wordmark originals;
- chosen display variant и usage restrictions;
- brand green/palette decision.

**Риск без закрытия:** визуально качественный сайт может оказаться чуждым business identity.

### D2 — CTA/contact route

- minimum один verified contact destination;
- primary channel;
- form mode (`backend`, `mailto`, messenger или другой honest fallback);
- error/success wording и privacy dependency.

**Риск без закрытия:** architecture имеет CTA, но implementation создаст dead action.

### D3 — Project/media shortlist

- grouped project inventory, а не 190 anonymous files;
- exact duplicate cleanup и near-duplicate review;
- rights/provenance per selected asset;
- high-resolution originals и project metadata;
- hero decision или brief на новую wide shoot.

**Риск без закрытия:** Gallery нельзя честно построить как archive реальных проектов.

### D4 — Capability matrix

Для каждой из шести groups:

- available / unavailable;
- in-house / partner / mixed;
- допустимая public wording;
- constraints, которые нужно сообщить;
- available process/equipment media.

**Риск без закрытия:** capabilities page станет списком неподтверждённых claims.

### D5 — Approved business narrative

- short studio description и допустимость `повний цикл`;
- origin story;
- quality/durability/real-conditions wording;
- anti-fast/anti-cheap position;
- neutral full process.

**Риск без закрытия:** Home/Philosophy будут либо пустыми, либо invented.

### Development readiness decision

Stage 2 design/implementation readiness = **blocked** до закрытия D1–D5 на достаточном уровне для выбранного Stage 2 scope. Можно отдельно поручить evidence/media preparation, но нельзя молча компенсировать пробелы placeholder copy/assets.

## 4. Блокеры публикации

### P1 — Нет подтверждённого conversion destination — critical

Production не может показывать `Обговорити проєкт`, если действие не ведёт в реальный канал и не имеет honest state.

### P2 — Нет asset-level media rights/provenance — critical

Публичность GitHub portfolio не равна разрешению. Нужны source, business linkage, rights и intended-use record для каждого rendered asset.

### P3 — Third-party brands и client relationships — critical/high

KitKat, Garnier, Matrix, Victoria’s Secret, Oberig, Mark/Avon и другие marks в кадре не разрешают утверждать client relation или public portfolio rights.

### P4 — Неподтверждённые production claims — high

In-house work, models/sizes/capacity, materials, weather suitability, durability, delivery/install и process не публикуются без source.

### P5 — Form/privacy/legal contract — high

Backend delivery, personal-data processing, consent, retention, business identity и privacy contact должны соответствовать реальной реализации.

### P6 — Contact/location/geography freshness — high

Phone, handles, email, address, hours и service area проверяются непосредственно перед production.

### P7 — Project facts/captions — high

Client, name, material, dimension, date, location и result не выводятся по визуальному предположению.

### P8 — Conditional proof — high

Team, clients, logos, testimonials и reviews публикуются только с evidence и permission.

### P9 — Production media/performance — medium/high

Нельзя hotlink-использовать mutable GitHub Pages archive или eager-load все 190 originals. Нужны managed delivery, checksums, responsive derivatives, dimensions и lazy-loading plan.

### P10 — SEO/legal production state — medium

Production domain, canonical, sitemap, robots, OG, structured data и indexability утверждаются отдельно. Preview всегда noindex и не считается production.

## 5. Материалы, которые можно получить позже

Они не обязательны для фиксации core architecture, но улучшают продукт и могут включить conditional sections:

- team names/roles/bios/portraits;
- workshop, equipment и process photo series;
- delivery/install media и человек для масштаба;
- approved client list и logos;
- original reviews + identity/source/permission;
- full case metadata;
- video и poster frames;
- legal entity, policies и analytics decisions;
- detailed equipment specs, только если полезны customer intent;
- professional wide hero shoot;
- SEO customer-language/competitor/demand research.

Если они не поступают, Team/Clients/Reviews удаляются. Их отсутствие не должно создавать generic alternatives.

## 6. Вопросы владельцу

1. Каково официальное публичное написание `Art Studio 184`; какие logo/wordmark files разрешены?
2. Какой green является брендово правильным, или его следует определить после brand study?
3. Какой phone/email/Instagram/messenger подтверждён и какой канал должен открывать `Обговорити проєкт`?
4. Какой form mode нужен в V1: backend delivery, messenger, email или другой verified fallback?
5. Какой город/address/service geography можно публиковать; кто отвечает за delivery и installation?
6. Какие capability groups выполняются in-house, через partners или не предлагаются?
7. Какие CNC/3D printing/equipment facts можно публиковать; нужны ли buyer-facing sizes/material limits?
8. Подтверждён ли 7-step process; как реально устроены estimate, approvals, payment, timing и handover?
9. Можно ли говорить `майстерня повного циклу`; где проходит граница ответственности?
10. Как owner формулирует origin story и позицию о качестве вместо самого быстрого/дешёвого результата?
11. Какие 8–18 проектов приоритетны, как группируются кадры, какие names/materials/locations разрешены?
12. Есть ли права на выбранные images и third-party branded objects; где находятся high-res originals?
13. Какие team/client/review materials разрешены публично?
14. Какие три top-level direction labels owner принимает окончательно?
15. Какие services/business priorities должны первыми пройти отдельное SEO research?

## 7. Запрещённые claims

До появления отдельного подтверждения запрещено утверждать:

- years in business, team size, names/roles;
- specific clients, partnerships, logos, awards, ratings и reviews;
- equipment models, working sizes, tolerances, capacity и supported materials;
- что все процессы выполняются in-house;
- price, estimate timing, 50/50 payment, number of revisions, guarantees;
- typical production time или response-time promise;
- delivery/installation geography и responsibility;
- exact address, hours и legal identity;
- weather resistance, lifetime или durability guarantee;
- project material, size, date, location, client или result;
- авторство/права на image только по факту public posting;
- quote от лица founder/studio без source;
- `найкращий`, `унікальний`, `преміальний` или другие superiority claims без evidence;
- fake form success.

## 8. Критерии готовности к этапу 2

Все условия обязательны для перехода к полной реализации; отдельный evidence-preparation этап может закрывать их до coding.

- [ ] Пользователь отдельно поручил Stage 2.
- [ ] Утверждены official name/logo/brand package.
- [ ] Подтверждён primary CTA destination и честный form mode.
- [ ] Создан project inventory: images сгруппированы по реальным projects.
- [ ] Выбран initial media set с asset-level rights/provenance и high-res sources.
- [ ] Hero media strategy подтверждена (new wide asset или composed portrait/landscape solution).
- [ ] Владелец заполнил capability matrix с in-house/partner/public wording.
- [ ] Утверждены short/full process и запрещённые operational claims.
- [ ] Утверждены short studio description, origin/quality/durability/anti-cheap narrative либо Philosophy scope честно сокращён.
- [ ] Утверждены three gallery direction labels.
- [ ] Для каждой planned section есть `CONFIRMED`, `CONDITIONAL` или suppression decision.
- [ ] Conditional Team/Clients/Reviews не считаются обязательным filler.
- [ ] Известны form/privacy/legal dependencies.
- [ ] Пять routes/H1/CTA/next-page transitions из Stage 1 приняты как implementation contract.
- [ ] Stage 2 brief подтверждает, что Rabbit/draft не копируются.

## 9. Stop boundary

Этап 1 заканчивается архитектурой. Он не разрешает:

- создавать framework/package/code/components/pages;
- скачивать или генерировать media;
- запускать SiteAgent/Telegram pipeline;
- делать preview/deploy;
- начинать visual design system;
- писать final customer copy;
- создавать SEO candidate pages;
- менять agent code, skills, workflow, tests или references.
