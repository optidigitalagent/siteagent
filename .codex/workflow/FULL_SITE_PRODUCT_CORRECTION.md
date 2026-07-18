# SiteAgent — full-site product correction

Действуй как `$siteagent-project-director`.

Это продуктовая коррекция после финального human audit.

## Решение human audit

Текущий checkpoint:

```text
AUTONOMOUS_SITEAGENT_READY_FOR_FINAL_PRODUCT_AUDIT
```

НЕ прошёл человеческий продуктовый аудит.

Orange Beauty Studio и Bella Dent Clinic технически стабильны, но как коммерческие сайты отклонены.

Причина не косметическая. Система оптимизировалась под ошибочный продукт:

- Orange фактически состоит из hero, одного proof/media-блока и телефонного CTA.
- Bella фактически является короткой redirect-страницей на официальный сайт.
- Bella была принята с одним concept, тремя semantic sections и двумя media treatments.
- Scope-aware critics оценивали соответствие урезанному `Level B micro_site`, а не качество полноценного сайта бизнеса.
- Итоговые 89/100 и 100/100 являются оценками внутри неверного scope и не подтверждают продуктовую готовность.

Не защищай предыдущую acceptance. Не улучшай эти страницы точечно. Исправь сам продуктовый контракт.

Сохрани существующие artifacts как историю, но установи для обеих calibrations:

```text
technical_status=accepted
product_status=rejected_by_human_audit
rejection_reason=incomplete_commercial_website
```

Не публиковать Orange или Bella.

Новый checkpoint:

```text
FULL_SITE_PRODUCT_CONTRACT_REBUILD_REQUIRED
```

---

## Главная ошибка архитектуры

Evidence level не должен определять тип продукта.

Нельзя делать:

```text
мало подтверждённого контента
→ автоматически micro_site
→ ослабить critic
→ принять три секции
```

Нужно делать:

```text
пользователь заказал сайт бизнеса
→ по умолчанию полноценный коммерческий сайт
→ исследовать бизнес и собрать достаточный content package
→ если данных объективно недостаточно, поставить точный blocker
→ не заменять полный сайт незапрошенным micro-site
```

`micro_site` разрешён только когда пользователь явно заказал:

- campaign landing;
- temporary launch page;
- event page;
- teaser;
- link-in-bio page;
- отдельный узкий lead magnet.

Для обычного сайта салона, клиники, ресторана, СТО, студии, агентства или другого локального бизнеса default:

```text
full_commercial_site
```

---

## Эталон доказанного ручного процесса

Автоматизировать именно эту последовательность:

```text
Instagram/business URL
→ глубокий ChatGPT-level research
→ rich business and brand strategy
→ отдельный ChatGPT-level Design Director
→ подробное narrative design-ТЗ
→ анализ и подготовка всех реальных media
→ один плотный implementation package
→ Codex implementation
→ browser screenshots
→ independent product criticism
→ material redesign
→ human final audit
```

Не заменять этот процесс:

- коротким schema-only `SiteSpec`;
- category template;
- token palette;
- deterministic three-section composition;
- evidence-driven scope shrinking;
- self-rating внутри собственного урезанного scope.

Direct Codex раньше получил:

- полное исследование бизнеса;
- философию и позиционирование;
- анализ конкурентов;
- реальную структуру сайта;
- конкретную визуальную концепцию;
- распределение media;
- подробные правила responsive behavior;
- 24 фотографии и 2 видео;
- прямое требование создать готовый сайт, а не анализ.

Он собрал полноценный Eliz de Fleur site с навигацией, PL/EN, Portfolio, Services, Contact, формой, фильтрами, видео и проектным просмотром.

Это золотой benchmark.

---

# 1. Новый Product Type Contract

Добавь явное поле:

```text
requested_product_type
```

Допустимые значения:

- `full_commercial_site`
- `multi_page_commercial_site`
- `campaign_landing`
- `micro_site`
- `portfolio`
- `catalog`
- `web_app`

Правила:

1. Для обычного входящего business job default:
   `full_commercial_site`.

2. Research Strategist, media analyzer, reference selector, Design Director,
   Builder и Critic не могут самовольно изменить product type.

3. Evidence resolver определяет только:

   - какие claims разрешены;
   - какие секции подтверждены;
   - какие данные отсутствуют;
   - нужен ли blocker.

4. Evidence resolver не имеет права превращать `full_commercial_site` в `micro_site`.

5. Если полноценный продукт невозможно честно собрать:

```text
BLOCKED_INSUFFICIENT_BUSINESS_CONTENT
```

с точным missing-content manifest.

---

# 2. Commercial Completeness Contract

Полноценный коммерческий сайт не означает один шаблон для всех ниш.

Но он обязан закрывать полный пользовательский путь.

Минимальные функции:

1. **Identity / value proposition**
   - кто это;
   - что делает;
   - где работает;
   - для кого;
   - главный CTA.

2. **Offer / services**
   - конкретные направления;
   - понятная группировка;
   - что получает клиент.

3. **Proof**
   - работы;
   - кейсы;
   - проекты;
   - интерьер;
   - оборудование;
   - результаты;
   - подтверждённые media.

4. **Brand / about**
   - философия;
   - подход;
   - пространство;
   - основатель или команда, если подтверждены.

5. **Trust / process**
   - как начинается работа;
   - что происходит дальше;
   - подтверждённые преимущества;
   - гарантии только при наличии источника.

6. **Commercial decision**
   - цена, диапазон, консультация, расчёт или способ получить предложение;
   - нельзя оставлять только абстрактное «узнать подробнее».

7. **Objection handling**
   - FAQ;
   - условия;
   - география;
   - сроки;
   - формат записи;
   - только то, что подтверждено.

8. **Final conversion**
   - контакты;
   - форма;
   - телефон/messenger;
   - карта/адрес, если подтверждены;
   - повторный конкретный CTA.

Реализация может быть:

- 7–12 содержательных секций на одной странице;
- либо 4–6 полноценных страниц;
- либо смешанная архитектура.

Запрещено засчитывать как разные meaningful sections:

- повтор заголовка;
- декоративную цветную панель;
- один и тот же CTA второй раз;
- одну фотографию без новой функции;
- пустой transition block;
- footer.

Если обычный business site содержит только три semantic sections,
он не может пройти product acceptance без явного пользовательского запроса на micro-site.

---

# 3. Category-aware, но не template-driven IA

Design Director обязан построить индивидуальную information architecture.

Примеры coverage, не готовые шаблоны:

## Beauty / salon

- Hero;
- услуги;
- портфолио/работы;
- о студии или пространстве;
- мастера, только если подтверждены;
- процесс записи;
- цены или способ расчёта;
- реальные отзывы, только если есть;
- FAQ;
- контакты и запись.

## Dental / clinic

- Hero и специализация;
- услуги;
- врачи/команда, только если подтверждены;
- клиника, оборудование и подход;
- реальные кейсы, только с разрешёнными media;
- путь пациента;
- цены/консультация;
- реальные отзывы, если подтверждены;
- FAQ;
- контакты и запись.

## Restaurant

- Hero/атмосфера;
- концепция кухни;
- меню;
- интерьер;
- шеф/команда, если подтверждены;
- события/банкеты;
- отзывы;
- бронь;
- контакты.

Агент выбирает порядок и визуальный storytelling самостоятельно.
Он не копирует эти списки буквально.

---

# 4. Rich Research Contract

`business_research.md` должен быть полноценным стратегическим документом, а не коротким JSON summary.

Обязательно:

- точная идентификация бизнеса;
- услуги/продукты;
- аудитории;
- customer intents;
- location/language;
- price/positioning level;
- philosophy;
- differentiators;
- business model;
- conversion goal;
- trust factors;
- available proof;
- public-source findings;
- Instagram findings;
- official-site findings;
- verified facts;
- unknowns;
- contradictions;
- prohibited claims;
- content opportunities;
- recommended site depth;
- content coverage matrix;
- missing-content manifest;
- source provenance.

Research Strategist должен сначала пытаться заполнить пробелы через разрешённые
публичные источники.

Существующий сайт бизнеса можно использовать для:

- фактов;
- услуг;
- контактов;
- команды;
- цен;
- media provenance.

Его нельзя использовать как design/layout/copy template.

---

# 5. ChatGPT-level Design Director Contract

Design Director обязан выдавать полноценное narrative implementation brief.

Не принимать документ, состоящий только из:

- palette;
- fonts;
- tokens;
- component list;
- abstract mood;
- короткого section array.

Обязательно:

## Strategy

- central creative idea;
- positioning;
- emotional goal;
- business goal;
- audience journey;
- why this concept fits this business;
- how it differs from category clichés.

## Information architecture

Для каждой страницы и каждой секции:

- название;
- функция;
- content;
- реальный draft copy;
- CTA;
- media assignment;
- layout/composition;
- visual hierarchy;
- spacing/rhythm;
- interaction;
- desktop behavior;
- tablet behavior;
- mobile behavior;
- acceptance criteria.

## Visual system

- typography with roles and scale;
- palette and contrast;
- grid;
- spacing;
- image treatment;
- video treatment;
- cards;
- buttons;
- navigation;
- motion;
- accessibility;
- responsive transformations.

## Media plan

Для каждого authorised asset:

- asset ID;
- subject;
- project/category;
- orientation;
- quality;
- hero/section/gallery suitability;
- intended usage;
- crop;
- desktop/mobile treatment;
- alt text.

## Commercial system

- CTA hierarchy;
- contact logic;
- form fields;
- trust placement;
- objection handling;
- conversion path.

## Anti-copy

- selected reference principles;
- what can be learned;
- what cannot be copied;
- proof that final concept is original.

Design Director output передавать Builder полностью, без потери narrative detail
при преобразовании в schema.

---

# 6. Implementation Package Contract

Codex должен получать один плотный immutable package:

- raw business research Markdown;
- structured research JSON;
- full Design Director Markdown;
- structured design JSON;
- media catalog;
- authorised Cloudinary URLs;
- selected references and rationale;
- complete content/copy;
- product type;
- commercial completeness contract;
- acceptance rubric;
- prohibited claims;
- no-copy rules.

Нельзя давать Builder только сокращённый `SiteSpec`.

Добавь проверку:

```text
implementation_package_information_loss=false
```

Она должна сравнивать ключевые разделы Markdown и structured package.

---

# 7. Media Sufficiency Contract

Недостаток media не должен автоматически создавать micro-site.

Порядок:

1. Найти все разрешённые business media:
   - Instagram;
   - локальные файлы;
   - связанные repositories;
   - существующие Cloudinary URLs;
   - официальный сайт только для provenance.

2. Очистить Instagram UI.
3. Deduplicate.
4. Классифицировать.
5. Создать media coverage map.
6. Определить, хватает ли assets для planned full site.

Design Director может:

- использовать editorial typography;
- повторно использовать asset осознанно;
- делать разные crops;
- строить текстовые/process sections;
- использовать diagrams/icons;
- уменьшать число gallery items.

Но нельзя:

- выдавать одну работу за большое portfolio;
- использовать stock как работу бизнеса;
- выдумывать team/cases/reviews;
- принимать пустую галерею.

Если media действительно недостаточно для честного полноценного сайта,
ставить blocker с точным числом и типами недостающих assets.

Не принимать урезанный micro-site вместо заказанного сайта.

---

# 8. Independent Product Director

Добавь независимого `ProductDirectorAuditor`.

Он получает:

- исходный business request;
- business research;
- requested product type;
- final screenshots;
- final site;
- content coverage;
- media provenance.

Он НЕ получает:

- внутренние critic scores;
- rationale о том, почему scope был уменьшен;
- просьбу подтвердить существующее решение.

Он отвечает:

1. Это полноценный продукт того типа, который заказал пользователь?
2. Понятно ли, что это за бизнес?
3. Понятно ли, что можно заказать?
4. Есть ли достаточная глубина?
5. Есть ли proof/trust?
6. Есть ли полный conversion journey?
7. Выглядит ли сайт законченным?
8. Выглядит ли он как реальный сайт бизнеса, а не concept page?
9. Соответствует ли качество ручному ChatGPT → Codex benchmark?
10. Какие material changes обязательны?

Жёсткие score caps:

- нет полноценного offer/services coverage → максимум 40;
- нет proof/portfolio/trust coverage → максимум 50;
- только три semantic sections для обычного business site → максимум 45;
- redirect page на другой сайт → product acceptance false;
- повторяющиеся CTA не компенсируют отсутствие content;
- техническая чистота не компенсирует неполный продукт.

---

# 9. Golden calibration: Eliz de Fleur

Следующая calibration — не Orange и не Bella.

Используй Eliz de Fleur как golden benchmark, потому что существует доказанный
ручной workflow и готовый baseline.

Источники:

- существующий manual workflow в project docs;
- сохранённый Eliz research;
- 24 обработанных Instagram photos;
- 2 videos;
- deployed baseline:
  `https://optidigitalagent.github.io/eliz-de-fleur-site-20260711095843/`

Правила blind benchmark:

1. Research Strategist и Design Director не видят готовый baseline site.
2. Они получают только исходный business input и media.
3. Builder не видит baseline.
4. После завершения независимый Product Director сравнивает:
   - completeness;
   - information architecture;
   - media use;
   - visual quality;
   - mobile;
   - language switching;
   - portfolio depth;
   - commercial journey.
5. Новый autonomous result должен быть не слабее manual baseline.

Golden calibration minimum:

- польский язык по умолчанию;
- английская версия;
- полноценная navigation;
- Home;
- Services;
- Portfolio;
- Contact;
- working form;
- все пригодные photos/videos использованы осмысленно;
- no placeholders;
- responsive desktop/tablet/mobile;
- полный critic/fixer cycle.

Если golden calibration не проходит, SiteAgent не готов.

---

# 10. Orange и Bella

Текущие Orange/Bella artifacts сохранить, но не считать доказательством качества.

Повторно запускать их только после успешной Eliz golden calibration.

Перед повторным запуском:

- собрать достаточные реальные media;
- собрать полный research;
- подтвердить content coverage;
- установить `requested_product_type=full_commercial_site`.

Если данных недостаточно:

```text
BLOCKED_INSUFFICIENT_BUSINESS_CONTENT
```

а не Level B micro-site.

---

# 11. Human gate

Оставить:

```text
CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true
```

Human gate нельзя снимать по внутренним оценкам.

Только пользователь может подтвердить, что golden calibration визуально и
продуктово соответствует его ручному процессу.

---

# 12. Tests

Добавь tests:

- full business job defaults to full commercial site;
- evidence resolver cannot downgrade product type;
- generic media count cannot promote or demote product type;
- three-section business page fails completeness gate;
- redirect-only site fails;
- missing services fails;
- missing conversion journey fails;
- technical pass cannot override product fail;
- micro-site passes only when explicitly requested;
- missing content produces blocker, not silent shrink;
- rich Design Director brief is preserved in implementation package;
- ProductDirectorAuditor is independent from internal critic scores;
- Eliz golden calibration contract is enforced.

---

# 13. Required reports

Создай:

```text
.codex/handoffs/FULL_SITE_PRODUCT_CORRECTION_REPORT.md
.codex/handoffs/FULL_SITE_PRODUCT_CORRECTION_REPORT.json
```

Включить:

- root cause;
- invalidated acceptance;
- changed contracts;
- tests;
- golden calibration status;
- screenshots;
- comparison to manual baseline;
- remaining blockers;
- external actions;
- next action;
- secret-safety confirmation.

---

# 14. External actions

Не запускать:

- production `go`;
- Telegram delivery;
- Cloudflare publishing;
- customer production deployment.

Разрешены:

- local builds;
- local screenshots;
- tests;
- calibration artifacts;
- commits;
- push to `origin/main`.

---

# Completion bar

Не останавливаться после обновления документации или tests.

Завершение возможно только когда:

1. Wrong micro-site acceptance invalidated.
2. Full-site product contract реализован.
3. Rich Design Director package реализован.
4. Independent Product Director реализован.
5. Eliz de Fleur golden calibration создана полностью.
6. Новый autonomous result не слабее manual baseline.
7. Full tests/compileall/pip check/smoke/browser QA прошли.
8. Reports созданы.
9. Changes committed and pushed.

Финальный checkpoint:

```text
AUTONOMOUS_FULL_SITE_AGENT_READY_FOR_HUMAN_AUDIT
```

Не выключай компьютер до commit/push и создания handoff reports.
