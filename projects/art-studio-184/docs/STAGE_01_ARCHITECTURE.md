# Art Studio 184 — Stage 01 site architecture

Дата: 2026-08-02
Статус: архитектура утверждена для подготовки следующего этапа; исходный код, дизайн-система, финальный копирайтинг и SEO-страницы не создавались.

## 1. Executive summary

Будущий сайт Art Studio 184 — украинский пятистраничный коммерческий сайт, в котором реальные проекты ведут пользователя от визуального доказательства к пониманию производства, подхода к качеству и простому первому контакту.

Основной путь:

`Головна → Галерея → Виробничі можливості → Філософія → Контакти`

Архитектура опирается на Stage 00 и фиксирует ровно пять core routes. Она не переносит структуру Unique Rabbit буквально и не использует текущий placeholder-черновик как исходник. Единица галереи — проект, а не файл. Отсутствующие контакты, права на медиа, факты о производстве, команда, клиенты и отзывы не заполняются выдуманным контентом.

Главное архитектурное ограничение: сайт можно спроектировать сейчас, но публичная реализация не может честно конвертировать или показывать портфолио до подтверждения контактного маршрута и asset-level прав на выбранные изображения.

## 2. Архитектурные принципы

1. **Работы раньше технологии.** Сначала посетитель видит реальные объекты, затем проверяет возможности мастерской.
2. **Один вопрос — одна секция.** Каждая секция добавляет новую информацию, доказательство, решение возражения или действие.
3. **Пять самостоятельных страниц.** Каждая объясняет свою функцию без обязательного прохождения предыдущих страниц.
4. **Один основной conversion-язык.** Primary CTA везде называется `Обговорити проєкт`.
5. **Следующий логичный шаг не заменяет CTA.** Первые четыре страницы завершаются и primary CTA, и отдельным переходом к следующей странице.
6. **Факты отделены от структуры.** Наличие архитектурного блока не разрешает публиковать неподтверждённый текст.
7. **Проект, не фотография.** Несколько кадров одного объекта входят в одну проектную запись.
8. **Conditional означает возможность удаления.** Если материалы не появятся, условная секция исчезает без placeholder и без разрыва повествования.
9. **Украинский — основной язык.** Все будущие публичные labels, H1, CTA и названия секций зафиксированы на украинском.
10. **Responsive поведение проектируется заранее.** Mobile — отдельная функциональная композиция, а не уменьшенный desktop.
11. **Референс не является шаблоном.** От Unique Rabbit используется только преобразованный сценарий `роботи → можливості → підхід → контакт`.
12. **Первый meaningful viewport продаёт смысл.** На desktop и mobile одновременно видны H1, объяснение, primary CTA, переход к работам и реальное изображение/композиция.

## 3. Content status system

| Статус | Значение | Правило реализации |
| --- | --- | --- |
| `CONFIRMED` | Архитектура и смысл опираются на задание или Stage 00 | Можно проектировать; фактические формулировки всё равно проходят provenance-check |
| `CONDITIONAL` | Блок нужен только при наличии указанных материалов | Не создавать пустую оболочку; при отсутствии данных блок полностью исключается |
| `TBD` | Решение влияет на следующий этап и требует согласования/исследования | Не маскировать предположением; зафиксировать dependency |
| `BLOCKED FOR PUBLICATION` | Архитектурно допустимо, но публичный вывод создаст неподтверждённый claim или неработающее действие | Разрешён только как внутреннее требование; в public build не выводится до закрытия blocker |
| `NOT RECOMMENDED` | Страница/секция ухудшает путь, дублирует смысл или не имеет evidence | Не создавать |

Статус относится к конкретному смыслу. Например, страница `Виробничі можливості` — `CONFIRMED` как часть IA, но модель станка и рабочий размер — `BLOCKED FOR PUBLICATION`.

## 4. Окончательная карта основных маршрутов

Выбран один набор коротких ASCII-slugs. Он устойчив к разным системам, не создаёт конкурирующих украинских транслитераций и остаётся понятным команде. Публичные labels и весь видимый контент остаются украинскими.

| № | Украинское название | Menu label | URL | Основной поисковый intent | H1 | Conversion-задача | Следующий переход |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Головна | `Головна` | `/` | понять, что создаёт Art Studio 184, и оценить уровень работ | `Створюємо об’ємні фігури, декорації та брендовані об’єкти` | открыть диалог или перейти к доказательствам | `Переглянути галерею` → `/gallery/` |
| 2 | Галерея | `Галерея` | `/gallery/` | увидеть реальные проекты по основным направлениям | `Реальні роботи Art Studio 184` | найти релевантный тип проекта и начать разговор | `Дізнатися про виробничі можливості` → `/capabilities/` |
| 3 | Виробничі можливості | `Можливості` | `/capabilities/` | понять, как мастерская превращает идею в физический объект | `Виробничі можливості Art Studio 184` | проверить применимость процессов к своей задаче | `Дізнатися про наш підхід` → `/philosophy/` |
| 4 | Філософія | `Філософія` | `/philosophy/` | понять подход к качеству, материалам и долговечности | `Підхід Art Studio 184 до роботи` | снять сомнение о выборе мастерской не по критерию минимальной цены/срока | `Перейти до контактів` → `/contacts/` |
| 5 | Контакти | `Контакти` | `/contacts/` | быстро начать разговор о проекте | `Обговорімо ваш проєкт` | отправить минимальный запрос или выбрать подтверждённый прямой канал | финальная страница; secondary возврат в `/gallery/` |

Другие URL для этих страниц не создаются. Если старые draft routes когда-либо будут мигрироваться, redirect-map проектируется отдельно на этапе реализации; в Stage 1 он не утверждает существование контролируемого старого домена.

## 5. Глобальная навигация

### Desktop

- persistent header остаётся доступным при прокрутке на всех пяти страницах;
- порядок: logo → `Головна` → `Галерея` → `Можливості` → `Філософія` → `Контакти` → компактный `Обговорити проєкт`;
- текущая страница имеет одновременно семантический `aria-current="page"` и видимое состояние, не зависящее только от цвета;
- над hero header может иметь прозрачное состояние только при достаточном контрасте; после прокрутки получает непрозрачный фон;
- изменение состояния не должно сдвигать контент, скрывать CTA или изменять размер hit area;
- primary CTA ведёт на `/contacts/` или к подтверждённой форме/контактному anchor на текущей странице, если он реально существует.

### Tablet

- при достаточной ширине сохраняется desktop-порядок с сокращённым label `Можливості`;
- если пять ссылок и CTA не помещаются без сжатия, включается mobile-menu pattern до возникновения переноса/перекрытия;
- touch targets не меньше 44×44 CSS px;
- sticky gallery anchors всегда располагаются ниже persistent header.

### Mobile

- в закрытом состоянии: logo и menu button с понятным accessible name;
- меню открывается как управляемая панель или полноэкранный слой; конкретная визуальная форма относится к следующему этапу;
- порядок ссылок совпадает с основным путём; primary CTA расположен после ссылок;
- при открытии focus переходит в меню, Tab остаётся внутри, Escape и close button закрывают меню, focus возвращается на trigger;
- background scroll блокируется; после перехода меню закрывается;
- активная страница видна текстово/графически, не только цветом;
- menu button, close и links имеют минимум 44×44 CSS px.

## 6. Футер

Состав первой версии:

- logo/wordmark, только после подтверждения официального asset;
- одно короткое factual описание мастерской;
- навигация по пяти core pages;
- три направления как ссылки-якоря на соответствующие секции `/gallery/`, а не дубликаты страниц;
- только подтверждённые контакты и Instagram;
- город только после подтверждения;
- primary action `Обговорити проєкт`;
- privacy link после определения form/analytics contract;
- copyright с подтверждённым публичным названием.

Не выводятся пустые contact slots, неподтверждённый адрес/география, несуществующие social networks, список оборудования или большой повторяющийся slogan. Footer остаётся полноценной semantic navigation landmark на каждой странице.

## 7. Общие компоненты будущего сайта

Это архитектурный inventory, не перечень созданных файлов.

| Компонент | Назначение и страницы | Входные данные | Состояния | Accessibility | V1 |
| --- | --- | --- | --- | --- | --- |
| `SiteHeader` | persistent global shell; все страницы | logo, nav items, current route, CTA | top/scroll, light/dark surface, menu breakpoint | landmark, skip-link target relationship, visible focus, 44×44 targets | да |
| `MobileMenu` | mobile navigation; все страницы | nav items, current route, CTA | closed/opening/open/closing | labelled trigger, focus trap/return, Escape, scroll lock | да |
| `SiteFooter` | navigation и conversion closure; все страницы | description, routes, gallery anchors, verified contacts, legal links | full/contacts-limited | semantic footer/nav, descriptive links, keyboard order | да |
| `PortfolioHero` | offer + real work; home | H1, explanation, image set, CTA, work link | single image/composed images, loading/error | ordered heading, useful alt or decorative handling, no autoplay dependency | да |
| `PageIntro` | самостоятельное объяснение внутренних страниц | eyebrow, H1, summary, optional media | with/without media | один H1, logical reading order | да |
| `SectionHeading` | единая heading hierarchy | label, title, summary, id | default/compact | H2/H3 по контексту, anchor focus offset | да |
| `ProjectCard` | одна проектная сущность; home/gallery | project id, verified title/category, cover, frame count, safe metadata | default/focus/unavailable metadata | button/link semantics, alt, visible focus, no hover-only info | да |
| `ProjectGallery` | curated project archive; gallery | project groups, categories, image derivatives | loading/ready/empty-filter/error | list/grid semantics, announced state changes, keyboard reachability | да |
| `GalleryCategory` | одна неповторяющаяся category section | id, intro, projects | active/inactive anchor, insufficient confirmed projects | labelled section, focusable target, sticky offset | да |
| `GalleryCategoryNav` | якорная навигация по категориям | anchors, active id | normal/sticky/scrollable | nav label, `aria-current` or equivalent, keyboard scroll visibility | да |
| `Lightbox` | кадры одного проекта | frames, caption, index, project title | closed/open/loading/error | dialog semantics, focus trap/return, Escape, prev/next labels, reduced motion, scroll lock | да |
| `CapabilitySection` | доказанная группа процессов; capabilities/home preview | title, verified facts, constraints, media | confirmed/conditional/suppressed | semantic heading, truthful alt, no inaccessible diagram-only meaning | да |
| `ProcessSteps` | short home или full capabilities process | ordered steps, status per claim | 4–5 short / 6–8 full | ordered list, no meaning by color alone | да |
| `CompactInquiryForm` | единственная low-friction form; Contacts | name, contact, preferred channel, optional message, delivery mode | idle/invalid/submitting/success/error/fallback | labels, error summary, focus management, status announcement, no fake success | да, только Contacts |
| `PageCTA` | compact action panel на первых четырёх страницах | heading, context, CTA destination | link/fallback/blocked | descriptive label, 44×44, intact label geometry | да |
| `NextPageLink` | последовательный переход первых четырёх страниц | next title, reason, URL | default/focus | descriptive purpose beyond generic “далі” | да |
| `Breadcrumbs` | orientation на будущих nested direction/capability/case pages | route hierarchy | visible/compact | nav label, ordered list, current item non-link | нет для пяти flat core routes; позже |

Дополнительные implementation primitives, которые потребуются V1: `SkipLink`, `ResponsiveImage`, `FormField`, `FormStatus`, `VerifiedContactList` и `LegalNav`. Они не являются отдельными контентными секциями.

Team, Clients и Reviews не объединяются в generic `ConditionalProofSection`: conditional rendering является content-policy, а каждый доказанный тип proof получает собственную семантику. `StructuredData` также не является визуальным компонентом.

### Общие behavior/policy primitives

| Primitive | Назначение и страницы | Входные данные | Состояния | Accessibility / integrity | V1 |
| --- | --- | --- | --- | --- | --- |
| `SkipLink` | переход к `main`; все страницы | target id, label | hidden/focused | становится видимым при focus, переводит keyboard focus к main | да |
| `ResponsiveImage` | truthful performant media; все страницы с images | authorised source, derivatives, dimensions, crop, alt, provenance | loading/loaded/error | alt/decorative contract, no layout shift, no content only in image | да |
| `FormField` | controls Contact form | name, label, type, required, value, hint, error | idle/focus/invalid/disabled | explicit label, described errors, predictable autocomplete | да |
| `FormStatus` | result Contact form | mode, message, next action | idle/busy/success/error/fallback | live announcement, focus management, no false success | да |
| `VerifiedContactList` | direct channels; Contacts/footer | channel, label, destination, verification status | omitted/ready | descriptive links, no empty icon-only items | да при наличии data |
| `LegalNav` | auxiliary legal links в footer после появления реальных policies | verified label, canonical route, applicability | omitted/ready | отдельный labelled nav или понятная часть footer nav; no dead links | условно |
| `ConditionalProofPolicy` | omission/eligibility Team, Clients, Reviews | evidence records, permission, provenance | omitted/eligible/blocked | правильная семантика каждого proof type; не generic carousel | да как policy, не visual component |
| `StructuredData` | SEO serialization; применимые pages | verified page/business/project facts | omitted/valid/blocked | точное совпадение с visible facts; unsupported entity fields запрещены | условно |

## 8. Desktop/tablet/mobile functional contract

### Общие viewport-цели

Следующий этап проверяет минимум 1440, 1024, 768, 390 и 360 CSS px. На каждой ширине обязательны:

- отсутствие горизонтального overflow;
- доступный persistent header;
- первый meaningful viewport с понятным H1 и primary CTA;
- tap targets минимум 44×44;
- отсутствие clipped CTA labels;
- сохранённый reading order и heading hierarchy;
- footer с navigation и реальным conversion route;
- no content loss при zoom/reflow и reduced motion.

### Hero/media

- desktop не требует full-bleed landscape, которого нет в evidence; допустима split/composed схема из portrait и landscape assets;
- mobile использует отдельный crop/sequence, не прячет offer/CTA под высоким изображением;
- конкретный hero asset не утверждён; нужен разрешённый high-resolution original и crop test;
- ни один auto-rotating media element не используется без pause и reduced-motion поведения.

### Gallery

- desktop: проектная grid/composition с cover и доступом к grouped frames;
- tablet: сохраняется проектная целостность; кадры одного проекта не распадаются на отдельные cards;
- mobile: одна основная card/строка за раз или компактная grid только при читаемом caption; category nav горизонтально прокручивается с видимым активным item;
- lazy loading не откладывает LCP/первый проект; размеры media заранее известны, чтобы исключить layout shift.

### Forms и actions

- server delivery не предполагается автоматически; реальная форма V1 находится только на Contacts, а первые четыре страницы используют `PageCTA`;
- до подключения backend допустим только честный подтверждённый fallback (`mailto`, messenger, copy-to-clipboard или direct contact), указанный в interface state;
- validation errors видимы, связаны с fields и переводят focus к summary/первому ошибочному полю;
- success state появляется только после доказанного результата соответствующего mode.

## 9. Что входит в первую версию

- ровно пять core pages и один URL для каждой;
- persistent header, mobile menu, active state, complete footer;
- portfolio-led home;
- единая gallery page с тремя категориями, проектной группировкой и lightbox;
- capabilities page только с подтверждёнными публичными возможностями;
- короткая philosophy page;
- contact page с минимальной формой и подтверждёнными direct channels;
- primary CTA system и последовательные переходы;
- conditional omission team/clients/reviews;
- responsive, keyboard, focus, reduced-motion и media-performance contracts;
- core technical SEO primitives после получения production domain и verified entity data.

## 10. Что переносится на последующие этапы

- визуальная дизайн-система, typography, palette и окончательный green;
- конкретная media curation, права, derivatives, alt и project captions;
- финальный украинский copy;
- backend формы и privacy/legal implementation;
- keyword/competitor research;
- direction/capability/case SEO pages;
- equipment specifications и capacity claims;
- location pages;
- client, review и team content до получения доказательств;
- preview, deployment, analytics и production promotion.

Stage 1 не разрешает начинать эти работы автоматически.
