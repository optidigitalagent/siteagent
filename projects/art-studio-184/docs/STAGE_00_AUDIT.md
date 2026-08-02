# Art Studio 184 — Stage 00 source audit

Дата аудита: 2026-08-02
Статус: аналитический документ; сайт, исходный код, дизайн-система и deploy не создавались.

## 1. Executive summary

Удалось изучить текущий репозиторий SiteAgent, публичный черновик Art Studio 184, структурный референс Unique Rabbit Studios и публичное портфолио с фотографиями работ. Все три сайта отвечали без авторизации; ограничения `401` не было.

Черновик Art Studio 184 доступен и имеет восемь связанных маршрутов, но является placeholder-прототипом, а не основой для доработки. На страницах нет ни одной реальной фотографии: все визуальные места заняты текстом `Image placeholder`; hero до оффера занимает первый экран; главная теряет header при прокрутке; галерея дважды повторяет одни и те же категории; форма не отправляет данные; весь контент английский; часть производственных и платёжных утверждений не подтверждена. Исходного репозитория черновика нет, поэтому редактировать его как проект невозможно.

Сильнейший доступный актив — портфолио: 190 уникальных опубликованных файлов работ в трёх сериях. Оно доказывает визуальную широту работ, но требует отбора, правовой проверки, дедупликации, подписей и технической подготовки. Большинство кадров портретные; текущего материала недостаточно для бескомпромиссного широкого desktop hero.

Unique Rabbit полезен только как сценарный ориентир: сначала показать работы, затем объяснить производство и привести к заявке. Его бренд, тексты, изображения, показатели, страницы и визуальную систему копировать нельзя.

Вывод: нужен новый, отдельно изолированный проект с собственной пятистраничной архитектурой, украинским контентом, реальными материалами Art Studio 184 и новой проверкой desktop/mobile. Главные риски до разработки — отсутствие подтверждённых контактов и CTA-маршрута, отсутствие оформленных прав/провенанса на медиа и недостаток документальных материалов о команде, мастерской, оборудовании и процессах.

## 2. Audit limitations

- Проверка выполнена по публичным HTTP-ответам, HTML, CSS/JS, sitemap/robots, публичному Git tree портфолио и выборочному визуальному просмотру изображений.
- Встроенный браузер в сессии был недоступен: список доступных browser bindings пуст. Поэтому не выполнялись реальные viewport screenshots, scroll/hover/focus проверки, клики по меню, lightbox и форме.
- Desktop/mobile выводы по черновику основаны на статических breakpoints и поведении в CSS/JS, а не на screenshot-led QA.
- Формы не отправлялись. Авторизация не обходилась. Сайты не клонировались и не скачивались целиком.
- У публичного черновика нет исходного репозитория; невозможно проверить его build-конфигурацию, историю решений и backend.
- Портфолио проверено полностью по DOM и файловым метаданным, но визуальная художественная оценка является выборочной. Для всех 190 файлов получены размеры, ориентация, размер и Git blob SHA; полная ручная покадровая арт-дирекция остаётся задачей media curation.
- Публичные фотографии не содержат оформленного asset-level provenance/licence manifest. Факт публикации не равен подтверждённому разрешению на новый коммерческий сайт.
- Не подтверждены владельцем контакты, команда, оборудование, характеристики, клиенты, отзывы, география, схема оплаты и юридические данные.
- Черновик, Rabbit и портфолио не возвращали `401`. Корневые страницы всех трёх источников возвращали `200`.
- До начала аудита Git worktree уже содержал семь изменений существующих файлов агента. Они не относятся к этому этапу и не изменялись в ходе аудита.

## 3. Website-agent repository assessment

### Назначение и архитектура

Текущий репозиторий — Python-система `site-agent / website-agent`, а не исходный код Art Studio 184. Его основной производственный путь:

`Telegram intake → очередь → research/evidence → media/brand → reference selection → Design Director → Codex Studio → critics/fixer → acceptance → isolated preview или production promotion → live verification → Telegram`.

Основные контуры:

- `site_agent/cli.py`, `telegram_bot.py`, `job_queue.py` — CLI, Telegram и durable queue;
- `orchestrator.py`, `workflow.py`, `models.py`, `config.py` — orchestration, контракты, модели, env-конфигурация;
- `research.py`, `instagram.py`, `media.py`, `generated_media.py`, `brand.py` — evidence, intake, provenance, brand identity;
- `reference_import.py`, `reference_discovery.py`, `references/site_designs/` — библиотека референсов;
- `agents.py`, `prompts.py`, `studio.py`, `builder.py`, `templates/` — strategy/design/build; `codex_studio` является default, Jinja — только explicit compatibility mode;
- `critic.py`, `commercial_usefulness.py`, `product_director.py`, `acceptance.py` — независимые продуктовые и quality gates;
- `preview.py`, `publisher.py`, `telegram_notify.py` — preview/production publication и delivery;
- `refinement.py` — отдельный, непубликующий workflow для существующего сайта;
- `tests/`, `scripts/smoke_build.py` — regression и smoke verification;
- `.agents/skills/`, `.codex/skills/` — creative/research/implementation/review skills;
- `.codex/project_brain/`, `.codex/workflow/` — долговременная продуктовая память и operational state;
- `runs/<job-id>/` — игнорируемые Git recoverable artifacts одного запуска, а не место для долговременного клиентского исходника.

### Как агент создаёт сайты

Нормальная команда `python -m site_agent.cli go` забирает URL из `.codex/inbox/telegram_jobs.json`; повторно спрашивать URL не требуется. Для новых работ default — `SITE_BUILDER=codex_studio`, без silent fallback на шаблон. Система сохраняет research, manifest медиа, brand package, selected references, design brief, implementation package, concept/source, screenshots, critic reports, acceptance и deployment metadata внутри отдельного run.

Возможности, полезные Art Studio 184:

- evidence research и запрет неподтверждённых claims;
- media provenance, deduplication, quality/orientation analysis и media planning;
- trait-based reference analysis без копирования категории;
- UX architecture, storytelling, украинский conversion copy;
- отдельный Design Director и Codex implementation package;
- responsive/accessibility/SEO/anti-template review;
- browser QA, screenshot-led criticism, fixer и acceptance audit;
- isolated noindex preview и отдельная production promotion lane;
- recoverable checkpoints.

### Команды репозитория

- `python -m site_agent.cli go` — claim/resume следующего Telegram preview job;
- `python -m site_agent.cli <URL>` — прямой запуск по URL;
- `python -m site_agent.reference_import` — импорт референсов;
- `python -m site_agent.reference_import --refresh-discovery` — обновление discovery;
- `python -m site_agent.cli refinement-start|refinement-continue|refinement-status|refinement-accept` — отдельный existing-site workflow;
- `python -m site_agent.cli production-promote ... --authorize-production` — отдельно авторизуемое production promotion;
- `python -m unittest discover -s tests -v`, `python -m compileall site_agent scripts tests`, `python scripts/smoke_build.py` — проверки;
- `python -m site_agent.telegram_bot` — bot-only runtime.

На этапе 0 эти команды генерации, build, publish и delivery не запускались.

### Размещение и изоляция Art Studio 184

Стандартной tracked-папки `projects/` до этапа 0 не существовало. `runs/` предназначена для эфемерных/recoverable run artifacts и игнорируется Git, поэтому не подходит как единственный долговременный клиентский проект.

Рекомендуемая граница:

- сейчас: только `projects/art-studio-184/docs/STAGE_00_AUDIT.md`;
- после отдельного утверждения этапа 1: долговременные документы и будущий исходник держать только под `projects/art-studio-184/`, не смешивая их с `site_agent/`, `tests/`, `.agents/`, `.codex/` или `references/`;
- если будущая реализация пойдёт через production orchestrator, каждый run дополнительно получает собственный `runs/<job-id>/`, но не становится заменой клиентскому source-of-truth.

Ядро агента, которое нельзя менять в рамках работы над Art Studio 184 без отдельной задачи: `site_agent/`, `tests/`, `scripts/`, `requirements*.txt`, deploy-конфигурация, `.agents/skills/`, `.codex/skills/`, `.codex/project_brain/`, `.codex/workflow/`, `.codex/inbox/`, `plugins/`, `references/` и root-конфигурация.

Ограничения: normal `go` ориентирован на Telegram/one-link pipeline, а текущий этап — ручной multi-source audit. Нельзя превращать этот audit в queue job, молча генерировать сайт, публиковать preview или изменять workflow. Также browser QA в этой сессии недоступна.

## 4. Source inventory

| Источник | Назначение | Доступность | Что удалось получить | Ограничения |
| -------- | ---------- | ----------- | -------------------- | ----------- |
| Задание владельца | Product/brand/IA требования | доступно полностью | язык, стиль, page order, желаемые секции, запреты, вопросы к подтверждению | не содержит подтверждённых контактов, прав на медиа и operational facts |
| Текущий репозиторий SiteAgent | рабочая система и будущий инструмент | локально доступен | архитектура, skills, workflows, commands, storage и safety boundaries | это не репозиторий сайта Art Studio 184; worktree был грязным до аудита |
| `https://art-studio-184.funckj.chatgpt.site` | аудит текущего черновика | `200`, без 401 | восемь маршрутов, HTML/CSS/JS, тексты, IA, form state, metadata, robots/sitemap | нет source repo; browser/screenshots недоступны; нет реальных изображений |
| `https://uniquerabbitstudios.com` | структурный/UX-референс | `200`; sitemap доступен | 11 sitemap routes, core pages, тексты, формы, проверяемые переходы | interactions/scroll/mobile визуально не проверены; нельзя копировать бренд и материалы |
| `https://optidigitalagent.github.io/porfolio/` | реальные работы Art Studio 184 | `200` | 190 displayed assets, 3 категории, размеры/orientation, duplicates, lightbox structure | права и подписи не документированы; browser QA недоступна; страница смешана с брендом Rabbit |
| `https://github.com/optidigitalagent/porfolio` | файловые метаданные портфолио | публичный Git tree доступен | blob SHA/size, 205 photo blobs, 15 unused, exact duplicates | репозиторий — не новый сайт и не должен hotlink-использоваться как production media store |

## 5. Current draft audit

| Страница или раздел | Что есть сейчас | Что работает | Что не соответствует задаче | Рекомендация |
| ------------------- | --------------- | ------------ | --------------------------- | ------------ |
| Global shell | semantic header/nav/main/footer, skip link, active `aria-current` | понятная базовая IA; desktop active underline; мобильный toggle 46×46 по статическому коду | нет header CTA; на home header переопределён с `sticky` на `absolute`; mobile active underline скрыт; footer повторяет большой слоган и не содержит подтверждённые контакты/Instagram/город | спроектировать новый persistent header и компактный footer; проверить на 1440/1024/768/390/360 |
| `/` | placeholder slider → offer/CTA → 3 направления → 4 преимущества → CTA | после первого экрана оффер понятен; есть Gallery и Estimate CTA | первый экран занят placeholder slider; H1/оффер/CTA ниже; нет реальных работ, процесса, команды, клиентов, отзывов, полноценного production блока, позиции «не быстро/дёшево» | сохранить только принцип ясного оффера и 3 направлений; полностью перестроить portfolio-led home |
| `/gallery` | зелёный hero → 3 category cards → те же 3 категории как carousel | общая taxonomy читаема | категории продублированы; 12 placeholder records; проекты не открываются; нет compact request и перехода к capabilities; крупный зелёный фон против brief | единый архив: каждая категория один раз, реальные фото, lightbox, CTA, next-page link |
| `/services` | 6 service rows + 8-step `How We Work` | связывает производство и монтаж; путь проекта в целом понятен | нет отдельного coverage ряда требуемых capabilities; шесть одинаковых CTA; нет перехода к philosophy; claims `50%/50%`, «own team» и часть capability wording не подтверждены | переименовать в «Виробничі можливості», подтвердить оборудование/процесс/оплату, добавить недостающие capabilities и next step |
| `/our-mission` | короткий hero, narrative и `We Create / We Care / We Deliver` | компактность и связь ремесла с технологией подходят | нет истории «началось как увлечение», долговечности и аргумента против «самое быстрое/дешёвое»; нет реальных фото, заявки и перехода к Contact | создать короткую собственную «Філософія» на подтверждённой истории, без цитат и повтора home |
| `/contact` | большая technical estimate form и explanatory aside | labels/required fields видимы; форма честно сообщает, что endpoint не подключён | форма чрезмерна; обязательны phone+email, project type и description; нет preferred channel, реального contact fallback, Instagram, city, фото; submit не отправляет | низкопороговая форма: имя, один контакт, способ связи, необязательное описание; рядом прямые подтверждённые каналы |
| `/3d-characters-sculptures` | 4 offer sections + 6 selected-work placeholders | возможный taxonomy seed | английский, нет proof, claims требуют evidence, нет следующего page transition | рассматривать только как будущую SEO/IA гипотезу после demand/content/media проверки |
| `/photo-zones-installations` | 4 offer sections + 6 placeholders | возможный taxonomy seed | те же проблемы; смешивает несколько поисковых намерений | не утверждать страницу до taxonomy и keyword research |
| `/signage-brand-displays` | 4 offer sections + 6 placeholders | показывает branded object range | те же проблемы; часть services может требовать отдельного intent | использовать как исследовательский список, не переносить страницу напрямую |
| SEO/metadata | unique title/description/OG text, один H1, semantic links, robots allow | базовые title/description лучше полного отсутствия | `lang=en`, нет canonical, OG image, JSON-LD, breadcrumbs; sitemap пуст; favicon metadata содержит `localhost`; Gallery повторяет H2 | построить украинскую SEO-систему в новом проекте после архитектуры и factual confirmation |

Дополнительные факты:

- Все восемь внутренних маршрутов возвращают `200`; несуществующий маршрут возвращает `404`.
- В DOM страниц нет реальных `<img>`; все visual slots — placeholders.
- Палитра черновика: `#000`, `#080808`, `#0e0e0e`, `#161616`, белый/серый и акцент `#00c8c0`.
- Цвет `#00c8c0` не подтверждён как брендовый цвет Art Studio 184. Стиль portfolio page использует тот же цвет, но сама страница подписана Unique Rabbit, поэтому её CSS не является доказательством бренда Art.
- На Gallery зелёный используется как фон крупного hero, что противоречит прямому требованию владельца.
- Home slider меняется автоматически примерно раз в 7 секунд; статический код не показывает pause control, а `prefers-reduced-motion` не отключает JS interval.

## 6. Requirements compliance matrix

| Требование владельца | Статус | Что найдено | Что отсутствует |
| -------------------- | ------ | ----------- | --------------- |
| Основной язык — украинский | не выполнено | весь черновик английский | украинская IA, copy и metadata |
| Чёрный/очень тёмный фон, белый и серый текст | выполнено | тёмная palette реализована | проверка реального rendering/contrast |
| Зелёный только как акцент | выполнено частично | акцент используется в controls/text | Gallery hero залит зелёным целиком |
| Зелёный основан на портфолио | невозможно проверить | CSS использует `#00c8c0` | нет доказательства, что это брендовый цвет; требуется brand/media color study |
| Реальные фото создают главную ценность | не выполнено | нет ни одного реального изображения | curated media plan и production delivery assets |
| Не шаблонный/не пустой вид | не выполнено | базовая тёмная система согласована | placeholders, повторяемые cards и generic copy доминируют |
| Header остаётся сверху | выполнено частично | sticky на внутренних страницах по CSS | home переопределён на `absolute`; runtime scroll test отсутствует |
| Header не исчезает на главной | не выполнено | — | persistent home header |
| Удобное mobile menu | невозможно проверить | 46×46 toggle и responsive menu присутствуют в коде | live keyboard/touch/focus/scroll/overflow evidence |
| Compact CTA в header | не выполнено | — | реальный CTA |
| Активная страница понятна | выполнено частично | `aria-current` и desktop underline | мобильный visual active state не найден |
| Порядок 5 страниц владельца | не выполнено | Home, Gallery, Services, Contact, Mission | Ukrainian naming; Contact/Mission order; capabilities label |
| Compact CTA + next page после содержания | не выполнено | отдельные CTA встречаются | системный последовательный переход на каждой странице |
| Сильный home hero | не выполнено | full-screen slider | реальный image, точный offer и CTA в viewport |
| Краткое объяснение бизнеса | выполнено частично | есть ниже slider | вынести в первый meaningful viewport и подтвердить copy |
| Основные направления | выполнено | 3 направления есть | подтвердить taxonomy и заменить placeholders |
| Выбранные проекты | не выполнено | placeholders | curated real projects |
| Краткая философия | выполнено частично | passion/detail copy | подтверждённая собственная история |
| Качество и долговечность | выполнено частично | quality/detail упомянуты | material/durability evidence и конкретика |
| Почему не «самое быстрое и дешёвое» | не выполнено | — | подтверждённая позиция и объяснение пользы |
| Производственные возможности на home | выполнено частично | сжаты в один абзац | понятный overview и link на capabilities |
| Процесс на home | не выполнено | — | краткий подтверждённый process |
| Команда, клиенты, отзывы | не выполнено | данных нет | подтверждённые материалы или честное исключение секций |
| Compact request на home | не выполнено | только ссылки | низкопороговый conversion block |
| Галерея — единый архив, категории один раз | не выполнено | категории есть | убрать двойное card+carousel повторение |
| Фото удобно открываются | не выполнено | project articles не интерактивны | lightbox/detail interaction |
| Gallery → capabilities | не выполнено | — | compact request + next link |
| Полный список capabilities | выполнено частично | milling, printing, welding, woodworking, install | 3D model, manual sculpture, foam, fiberglass, metal, surface prep, putty, primer, paint, coatings, assembly, delivery и доказательства |
| `Як ми працюємо` | выполнено частично | 8 шагов есть | owner approval; безопасная формулировка оплаты; этапы поверхности/монтажа |
| Короткая Philosophy | выполнено частично | страница короткая | hobby origin, durability, anti-cheap positioning, photos, CTA, next link |
| Compact Contact | не выполнено | technical form есть | low-friction fields и direct contact routes |
| Полезный compact footer | выполнено частично | navigation/portfolio/services links | verified contacts, Instagram, city, CTA; убрать повторяющийся большой slogan |
| SEO-ready architecture | выполнено частично | unique titles/descriptions, H1 | UA semantics, canonical, non-empty sitemap, OG media, schema, breadcrumbs, alt, scalable URLs |

## 7. Unique Rabbit structural analysis

Публичный sitemap показывает 11 routes: главная, Gallery, Services, Our Mission, Contact, 3D Characters & Mascots, Custom Themes & Photo Ops, Giant Letters & Signage, Sports, Privacy Policy, Terms and Conditions. Category routes доступны при корректно percent-encoded URL. Sitemap публикует `http` loc, которые следует нормализовать до HTTPS при анализе.

### Карта страниц

Rabbit строит модель `Home → Gallery/categories → Services → Contact`, с Mission как отдельной философской страницей. Подходит принцип постепенного движения от результата к возможностям и заявке. Art Studio 184 нужен собственный порядок `Головна → Галерея → Виробничі можливості → Філософія → Контакти`; routes Rabbit нельзя переносить буквально.

### Хедер

В HTML подтверждена единая primary navigation Home/Gallery/Services/Contact/Our Mission и мобильный вариант `More`. Sticky behavior, scroll transformation, active state и interaction не проверены без браузера. Для Art переносим только требование постоянной доступности навигации, не shell/design.

### Главная

H1: `Your imagination is our blueprint.®`; далее About Us, направления, Why Unique Rabbit, Customers, Testimonials и mailing list. Полезна последовательность «обещание → направления → отличие → proof». Не подходят абстрактный hero без точного оффера, подписка как главный conversion, неподтверждённые clients/testimonials и зарегистрированный чужой slogan.

### Галерея

Gallery показывает Characters/Mascots, Themes/Photo Ops и Signage с коротким обещанием и `Show More`; верхний `Find out more` ведёт на Services. Подходит ориентация на реальные результаты перед технологиями. Для Art категории должны появляться один раз как полноценные подборки; ранний переход не должен уводить до просмотра archive.

### Services

Rabbit объясняет Concept/3D Modeling, CAD, Sculpting, Welding, Installation, затем перечисляет возможности `20,000 square foot` facility. Подходит единая цепочка от идеи до установки. Нельзя копировать показатели, equipment list, copy или американскую B2B-конкретику. Art использует только подтверждённые capabilities.

### Mission

Страница компактна и связывает традиционное ремесло с технологиями. Это переносимый принцип. Философия Art должна опираться на собственную историю, качество, материалы, долговечность и честный отказ от «самое быстрое и дешёвое».

### Contacts

Rabbit использует большую estimate form: company, name, phone, email, plans/model, indoor/outdoor, permanent/temporary, deadline и attachments; рядом address/phone/email/hours. Сочетание формы и прямых каналов полезно, но сама форма прямо противоречит brief Art. Нужен первый контакт с низким порогом.

### CTA

`Need an Estimate?`, `Need a quote?`, `Drop us a line!` и mailing signup показывают несколько конкурирующих CTA. Для Art нужен один основной украинский CTA-язык и один вторичный переход, без копирования фраз.

### Переходы

Проверен Gallery → Services; Services содержит contact block. Полная линейная последовательность Rabbit не доказана. Адаптация для Art: на каждой странице после content — компактная заявка и явный переход к следующей странице.

### Футер

Публичный текстовый слой подтверждает Gallery/Services/Contact/Privacy/Terms и GoDaddy copyright. Визуальная compactness и mobile behavior не проверены. Переносится только принцип полезной навигации и юридических ссылок.

### Desktop и mobile

Без браузерных captures нельзя утверждать responsive quality, sticky header, mobile menu, hover/focus и animation behavior. Эти свойства не являются доказанным референсом и должны проектироваться/тестироваться независимо.

Итог адаптации: использовать только преобразованный сценарий `реальные проекты → производственные возможности → философия качества → простой контакт`. Не копировать название, logo, slogan, тексты, images, customers, reviews, metrics, form, composition, routes, styling или animations.

## 8. Portfolio audit

Источник: `https://optidigitalagent.github.io/porfolio/`; публичный Git tree: `https://github.com/optidigitalagent/porfolio`.

### Количество и категории

| Категория | Уникальные grid assets | Ориентир для новой IA |
| --- | ---: | --- |
| 3D Characters & Sculptures | 81 | сильная самостоятельная категория после украинского naming audit |
| Photo Zones & Installations | 56 | вероятно требует разделения по intent только после content/SEO исследования |
| Signage & Brand Displays | 53 | может покрывать вывески, branded objects и большие product replicas |
| **Всего** | **190** | достаточно для отбора, но не для публикации всех файлов без curation |

В DOM 194 `<img>`: 190 уникальных grid images, три повторных intro image и один пустой lightbox image. В репозитории 205 photo blobs; 15 не используются страницей.

### Размер, ориентация и техническое качество

- 150 portrait, 38 landscape, 2 square.
- 134 файла имеют 960×1280, 30 — 1280×960; минимальный размер — 556×660.
- 11 файлов ниже практического порога `max side 1200 / min side 700`.
- 190 displayed originals занимают 25,485,585 bytes, около 24.3 MiB.
- Страница загружает все изображения eager: нет `loading=lazy`, `srcset`, `width` и `height`.
- В выборке заметны phone/Telegram compression, различия white balance, workshop clutter и WIP. Сильнее всего работают законченные объекты в контексте.

### Дубли и похожие кадры

Два точных content duplicate доказаны одинаковым Git blob SHA:

1. `photo_2026-05-26_17-22-37.jpg` = `photo_2026-05-26_17-22-40.jpg`;
2. `photo_2026-05-27_10-02-26.jpg` = `photo_2026-05-27_10-02-25.jpg`.

Также есть 46 пар `name.jpg` / `name (2).jpg` — 92 файла. Их SHA/perceptual comparison не подтверждает точное дублирование, а совпадение основы имени само по себе не доказывает связь кадров. Семантическую принадлежность к одному объекту нужно установить ручной проектной группировкой, а не автоматическим удалением.

Подтверждённые визуальные кластеры одного объекта включают KitKat car, Garnier bottles, orange mascot, Mark lips installation, mushroom project и gingerbread figures/installed scene. Для новой галереи один объект не должен создавать ложное ощущение множества кейсов.

### Предварительно сильные изображения

Кандидаты provisional; окончательное использование требует подтверждения прав, high-resolution original и crop test.

- Hero/home landscape: `photo_2026-05-26_17-22-42.jpg` — dramatic neon wall; `photo_2026-05-26_17-23-06 (2).jpg` — чистый contextual Oberig display; `photo_2026-05-26_17-22-52.jpg` — wide pale foliage relief.
- 3D/sculpture: `photo_2026-05-27_10-02-19.jpg`, `photo_2026-05-26_17-23-23.jpg`, `photo_2026-05-26_17-24-34 (2).jpg`, `photo_2026-05-26_17-24-32.jpg`.
- Photo zones/installations: `photo_2026-05-27_10-02-21 (2).jpg`, `photo_2026-05-26_17-24-42.jpg`, `photo_2026-05-26_17-23-06 (2).jpg`, `photo_2026-05-26_17-23-24.jpg`.
- Signage/displays: `photo_2026-05-26_17-22-42.jpg`, `photo_2026-05-26_17-22-47.jpg`, `photo_2026-05-27_10-01-17.jpg`.

Ни один файл не является идеальным full-width retina desktop hero: лучших landscape кадров мало, их ширина около 1280 px. На текущих материалах безопаснее split/composed hero или новая широкая съёмка.

### Слабые/secondary-only изображения

- `photo_2026-05-26_17-22-35.jpg` и точный duplicate cluster mushroom — грязный стол/провода;
- `photo_2026-05-27_10-02-12.jpg` — wrapped/in-progress объект;
- `photo_2026-05-26_17-23-03.jpg` — форма в перегруженной мастерской;
- `photo_2026-05-26_17-23-00.jpg` — тёмный незавершённый bird;
- `photo_2026-05-26_17-22-48.jpg` — clutter/event setup;
- `photo_2026-05-27_10-01-01.jpg` — busy и category-misaligned modified car.

WIP-кадры можно использовать только в честном process context, не как polished portfolio hero.

### Недостающие типы медиа

- 16:9/21:9 hero не меньше 2000 px;
- последовательные professional series одного проекта;
- команда, имена/роли и портреты;
- чистые wide shots мастерской, входа, интерьера и оборудования;
- CNC/3D print/welding/sculpting/surface prep/painting/assembly в работе;
- delivery/installation и человек для масштаба;
- before/after и project process sequence;
- нейтральные product/object shots;
- видео;
- подписи: project name, client permission, date, location, material, scale, brief/result;
- asset-level rights/provenance.

### Риски прямого использования GitHub Pages

- mutable third-party URLs и зависимость от владельца repository;
- eager 24.3 MiB transfer, отсутствие responsive derivatives и dimension attributes;
- контент страницы смешан с брендом Unique Rabbit (`title`, labels, CTA `#MAIN-SITE-URL`);
- третьесторонние марки (например KitKat, Garnier, Matrix, Victoria’s Secret, Oberig, Mark/Avon) требуют подтверждения портфолио/клиентских/trademark прав;
- нет licence/provenance metadata;
- источник не должен быть production CDN. После правовой проверки выбранные originals нужно перенести в управляемый media pipeline с checksum, derivatives, alt и ownership record.

Кроме того, GitHub прямо описывает Pages как сервис, не предназначенный для free hosting online business, и применяет limits: `https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits`.

## 9. Preliminary page map

### Головна

1. Portfolio-led hero: точный offer + primary CTA + real visual.
2. Коротко: чем занимается Art Studio 184 и для кого.
3. Три подтверждённых направления.
4. Selected projects с различными типами задач.
5. Качество, материалы и долговечность.
6. Почему мастерская не оптимизирует работу под «быстрее и дешевле».
7. Краткий overview production capabilities.
8. Короткий `Як ми працюємо`.
9. Команда/клиенты/отзывы только при наличии подтверждённых материалов; иначе не создавать filler.
10. Compact request.
11. Переход в Галерею.

### Галерея

1. Короткий intro и proof statement.
2. Категория 1: описание + curated set + lightbox.
3. Категория 2: описание + curated set + lightbox.
4. Категория 3: описание + curated set + lightbox.
5. При необходимости дополнительные категории только после taxonomy review.
6. Compact request.
7. Переход в `Виробничі можливості`.

Предварительное ядро: `Об’ємні фігури та скульптури`, `Фотозони, декорації та інсталяції`, `Вивіски та брендовані об’єкти`. `Арт-об’єкти`, `оформлення заходів`, `вітрини`, `рекламні конструкції`, `неонові вивіски`, `великі копії продуктів`, fiberglass и foam не утверждать как отдельные категории до проверки intent, overlap и media depth.

### Виробничі можливості

1. Intro: от идеи до монтажа.
2. Design/3D modelling.
3. CNC и 3D printing.
4. Manual sculpture, foam и fiberglass.
5. Metal/welding/wood.
6. Surface prep, putty, primer, paint и protective coatings.
7. Assembly, delivery и installation.
8. `Як ми працюємо` — только подтверждённые шаги.
9. Compact request.
10. Переход в `Філософія`.

### Філософія

1. Короткая история появления мастерской.
2. Отношение к объекту как к собственной работе.
3. Качество, материалы, детали и долговечность.
4. Объяснение отказа от «самое быстрое/дешёвое».
5. 2–4 сильных реальных фотографии.
6. Compact request.
7. Переход в `Контакти`.

### Контакти

1. Сильная contextual фотография.
2. Короткое invitation.
3. Имя.
4. Один контакт.
5. Предпочтительный способ связи.
6. Необязательное описание.
7. Verified Instagram/phone/email/messengers/location/hours.
8. Несколько дополнительных фото.
9. Финальный CTA.

### Потенциальные SEO-страницы для проверки, не для немедленного создания

- направления: sculptures/figures, photo zones/installations, signage/branded objects;
- capabilities: CNC foam milling, 3D printing, fiberglass, large promotional replicas;
- project/case pages с уникальным brief/process/result/media;
- location/service-area page только при подтверждённой географии.

Каждая требует отдельного intent, реальной услуги, unique copy, достаточных photos и пользы. Пустые programmatic страницы запрещены.

## 10. User journey

`Головна → Галерея → Виробничі можливості → Філософія → Контакти`

1. **Головна:** посетитель за первый viewport понимает, что мастерская создаёт физические арт-/бренд-объекты, видит real work и CTA. Он получает overview направлений и доверие к качеству.
2. **Галерея:** посетитель проверяет визуальный диапазон и находит похожий тип задачи. После каждой крупной подборки может открыть изображения; в конце видит compact request и следующий шаг.
3. **Виробничі можливості:** посетитель понимает, как идея становится объектом, какие процессы доступны и способен ли studio реализовать масштаб/материал/монтаж. После content — запрос расчёта и переход к подходу.
4. **Філософія:** посетитель проверяет отношение к качеству, материалам и долговечности. Эта страница объясняет ценовую/временную позицию без выдуманных superiority claims.
5. **Контакти:** минимальная форма и прямые verified channels позволяют начать разговор без заполнения технического брифа.

Решение связаться может возникнуть уже в hero, после подходящего project или после confirmation capabilities. Поэтому compact CTA присутствует на каждой странице, но не заменяет next-page link и не повторяется бессодержательно.

## 11. Content audit

### Подтверждено

- название проекта и требование основного украинского языка;
- желаемая пятистраничная последовательность;
- dark visual direction и зелёный только как accent;
- владелец указывает три предварительных направления и перечень желаемых capabilities;
- публичное портфолио показывает реальные finished objects в трёх текущих series;
- черновик и Rabbit доступны как reference evidence, не как source code.

### Требует подтверждения

- официальный spelling/wordmark/logo и брендовый green;
- все capability claims и in-house status;
- process sequence, timing, estimate, prepayment/final payment;
- история «началось как увлечение» и допустимая формулировка;
- quality/durability/anti-cheap positioning;
- contacts, city/address, service geography, hours;
- team, names/roles;
- clients, logos, testimonials/cases;
- право использовать каждый portfolio asset и third-party brand;
- финальные categories и CTA wording.

### Отсутствует

- подтверждённый phone/email/Telegram/Viber/WhatsApp/Instagram target;
- location, hours, legal entity/policy;
- equipment models, work sizes и capacity;
- team/workshop/equipment/process/install media;
- project names, materials, sizes, dates, locations и results;
- review originals и client permissions;
- профессиональный wide hero;
- SEO keyword/demand/competitor research.

### Нельзя придумывать

- contacts, address, geography, hours;
- names, roles, team size, years in business;
- clients, logos, reviews, ratings, awards;
- equipment characteristics, capacity, guarantees и сроки;
- price, 50/50 payment, delivery/installation conditions;
- project facts, materials, dimensions и results;
- права на photos/brands;
- quote от лица мастерской.

## 12. Missing materials

### Контакты

- phone, email, Instagram;
- Telegram/Viber/WhatsApp и приоритетный канал;
- city, exact address или допустимая public location;
- service geography и возможность выезда/доставки;
- hours и response-time promise, если его хотят публиковать.

### Команда

- имена, роли, короткие factual bios;
- права на публикацию;
- портреты и совместная фотография;
- кто отвечает за design/modeling/fabrication/painting/installation.

### Клиенты

- approved client list;
- разрешения на logos и branded objects;
- связь photo → client/project;
- что можно показывать публично и что confidential.

### Отзывы

- оригинальный текст, имя/роль/company, источник/date;
- согласие на публикацию;
- проверяемые links/screenshots при необходимости.

### Производство

- перечень in-house и partner processes;
- реальные материалы;
- ограничения по масштабу/весу/наружному использованию;
- delivery/installation geography и responsibility.

### Оборудование

- модели CNC/3D printers и working dimensions;
- supported materials/tolerances, если их можно публиковать;
- фото оборудования в работе;
- подтверждение safety/confidentiality того, что попадает в кадр.

### Процессы

- owner-approved journey от brief до handover;
- estimate/contract/prepayment/final payment;
- revision/approval points;
- typical timing только если можно подтвердить;
- кто организует delivery и installation.

### SEO

- подтверждённая география и языковая форма названия услуг;
- priority services и margins/business priorities;
- реальные customer questions;
- сезонность и target segments;
- competitors только для research, не копирования.

### Юридические данные

- legal/business name и реквизиты, если нужны;
- privacy controller/contact;
- consent wording, retention и form processor;
- cookie/analytics policy;
- terms/warranty/returns только при реальной применимости.

### Изображения

- high-resolution originals для curated subset, выбранного из 190 assets;
- rights/provenance manifest;
- wide hero shoot;
- team, workshop, equipment, process, installation, scale и detail photos;
- project metadata и alt source facts;
- video и poster frames.

## 13. SEO readiness recommendations

1. Исследовать украинскую семантику по трём продуктовым направлениям и production capabilities; отделить product intent от technology intent.
2. Подтвердить local intent только после города/географии. Не создавать location pages без реального обслуживания и unique value.
3. На этапе архитектуры утвердить пять core pages и только затем решить, какие direction/capability pages имеют самостоятельный intent.
4. Case pages создавать для реальных проектов с unique brief, photos, materials/process и result; не плодить thin galleries.
5. Для каждой утверждённой страницы подготовить unique Ukrainian `title`, `description`, один H1, логичную H2–H3 структуру, descriptive URL и internal links.
6. В реализации потребуются canonical, XML sitemap, robots, OG/Twitter image, descriptive alt, responsive image derivatives, breadcrumbs и performance budget.
7. `Organization`/`LocalBusiness` добавлять только с подтверждёнными name/address/contact/geography; `BreadcrumbList` — после финальной IA.
8. Не переносить английские draft titles и не индексировать placeholder/preview. Preview должен быть noindex; production indexability — отдельный gate.
9. Не публиковать все 190 files на одной eager page. Нужны curation, lazy loading, `srcset/sizes`, dimensions, modern formats и CDN/managed storage.

Пока нельзя создавать: team/client/review pages, price/payment pages, location pages, equipment-spec pages и десятки category/service pages без подтверждённых facts, intent и media.

## 14. Risks

### Critical

- Нет подтверждённого contact/CTA destination: сайт не сможет честно конвертировать.
- Нет оформленного media rights/provenance manifest: production использование портфолио и third-party brands нельзя считать разрешённым.
- Исходного кода черновика нет: попытка «редактировать» live draft создаст ложный recovery/source contract; нужен новый проект.

### High

- Черновик показывает placeholders вместо работ и проваливает первый meaningful viewport.
- Unsupported 50/50 payment и другие production claims могут стать ложными customer-facing facts.
- Нет team/workshop/equipment/process proof при большом объёме production narrative.
- 190 eager GitHub Pages assets создают около 24.3 MiB transfer и не имеют responsive delivery.
- Portfolio page смешана с брендом Unique Rabbit; автоматический перенос принесёт чужую identity/copy.
- Украинская IA/copy/semantics отсутствуют.

### Medium

- 46 filename-collision pairs требуют ручной группировки; два exact duplicates и подтверждённые визуальные кластеры могут раздуть perceived case count.
- Большинство кадров portrait; wide hero требует composition compromise или нового shoot.
- Некоторые фото WIP/clutter/compressed и снижают perceived quality.
- Browser screenshots/interactions/mobile не проверены в этой сессии.
- Финальная taxonomy может пересекать objects, events, materials и technologies.
- SEO demand, local geography и case depth ещё не исследованы.
- Worktree был грязным до аудита, поэтому безопасный single-file commit по условию задания невозможен без вмешательства в чужие изменения.

### Low

- Draft sitemap пуст, favicon metadata содержит localhost, OG images отсутствуют.
- Portfolio CTA содержит placeholder `#MAIN-SITE-URL` и page title Unique Rabbit.
- Rabbit Privacy Policy — placeholder и не является юридическим образцом.

## 15. Preserve / reject / redesign matrix

| Элемент чернового сайта | Решение | Причина |
| ----------------------- | ------- | ------- |
| Три широких направления | Preserve as reference | совпадают с текущим портфолио и дают понятный верхний уровень; taxonomy ещё требует подтверждения |
| Dark palette direction | Preserve as reference | соответствует brief, но конкретный green не подтверждён |
| Clear Gallery/Estimate CTA labels | Preserve as reference | намерение понятно; wording и destination нужно локализовать/подтвердить |
| Короткая mission tone | Preserve as reference | компактность полезна; факты и формулировки должны быть собственными |
| Semantic header/nav/main/footer/skip link | Preserve as reference | полезные accessibility primitives, не visual template |
| Placeholder hero и все placeholder media | Reject | не показывают бизнес и проваливают first viewport |
| Повтор категорий card → carousel | Reject | прямо запрещено brief и создаёт semantic duplication |
| English copy/metadata | Reject | основной язык — украинский |
| Крупный зелёный Gallery hero | Reject | нарушает правило accent-only |
| Claims `50%/50%`, own team и неподтверждённые capabilities | Reject | нет owner confirmation |
| Большая technical contact form | Reject | высокий порог и противоречие direct brief |
| Repeated oversized footer slogan | Reject | перегружает все страницы и не помогает conversion |
| Header и page journey | Redesign | home header исчезает; нет compact CTA и последовательных transitions |
| Home architecture | Redesign | нужен real portfolio-led journey с offer/CTA в первом viewport |
| Gallery | Redesign | единый curated archive, lightbox, project grouping, CTA и next link |
| Capabilities | Redesign | evidence-backed production story вместо неполного service list |
| Philosophy | Redesign | собственная короткая история, quality/material/durability logic |
| Contacts/footer | Redesign | verified low-friction routes, city/Instagram/legal links |
| SEO architecture | Redesign | UA semantics, scalable factual pages, canonical/sitemap/schema/media performance |

## 16. Questions for Stage 1

1. Каково официальное украинское написание названия, есть ли logo/wordmark и brand files?
2. Какой green владелец считает брендово правильным, или его нужно определить после анализа logo/authorised media?
3. Какие phone/email/Instagram/messengers подтверждены, и какой канал является primary CTA?
4. Какой город, адрес и реальная география работы/доставки/монтажа?
5. Какие перечисленные capabilities выполняются in-house, какие через партнёров, и что можно утверждать публично?
6. Подтверждён ли предложенный `Як ми працюємо`; какова реальная схема estimate/prepayment/final payment?
7. Какие три top-level категории окончательно приняты; какие потенциальные категории являются отдельными услугами, а какие материалами/технологиями?
8. Какие 8–15 проектов являются приоритетными, как они называются и что о них можно раскрывать?
9. Есть ли права на все выбранные фотографии и third-party brand objects; доступны ли high-resolution originals?
10. Можно ли публиковать team, clients и reviews; какие материалы подтверждены?
11. Какая формулировка истории «началось как увлечение» и позиции против «быстро/дёшево» одобрена владельцем?
12. Каким должен быть честный form mode на первом release: backend delivery, messenger, email или другой verified fallback?

## 17. Recommended scope for Stage 1

Следующий этап должен оставаться архитектурным, без преждевременного production build:

1. Утвердить неизменяемую карту пяти core pages.
2. Утвердить секции и функцию каждой секции, исключив filler и semantic repetition.
3. Утвердить последовательные transitions и primary/secondary CTA system.
4. Утвердить taxonomy галереи и правила группировки same-project frames.
5. Утвердить factual boundary: confirmed / missing / prohibited claims.
6. Утвердить media shortlist, rights checklist и список обязательной досъёмки.
7. Утвердить compact form fields и настоящий contact destination.
8. Подготовить карту потенциальных SEO pages с intent/content/media criteria, но не создавать их автоматически.
9. Зафиксировать desktop/tablet/mobile behavior contract для header, gallery, CTA, footer и lightbox.

Stage 1 не должен копировать Rabbit, кодировать страницы, публиковать preview или начинать deploy без отдельного задания.

## 18. Final conclusion

- **Можно ли редактировать существующий черновик?** Нет. Исходного кода нет; live draft — внешний placeholder prototype. Его можно использовать только как audit/reference evidence.
- **Нужно ли создавать новый проект?** Да, в отдельной границе `projects/art-studio-184/` после утверждения архитектуры.
- **Что взять из черновика?** Только широкую трёхчастную taxonomy, dark-direction, отдельные ясные CTA intentions, compact mission tone и semantic accessibility primitives.
- **Что взять из Rabbit?** Только преобразованный пользовательский сценарий: works → capabilities → philosophy/trust → contact. Не брать brand, copy, media, metrics, layout, routes, form и visual system.
- **Что взять из портфолио?** Curated real project media, после rights confirmation, deduplication, project grouping, high-res retrieval, captions и performance preparation.
- **Какие материалы нужны до разработки?** Verified contacts/CTA, brand/logo/green, rights, high-res hero, project metadata, team/workshop/equipment/process media, approved capabilities/process/payment, clients/reviews и legal/SEO inputs.
- **Готов ли проект переходить к архитектуре?** Условно да: источников достаточно для Stage 1 IA, но не для production implementation. Critical business-contact и media-rights blockers должны остаться видимыми и быть закрыты до публикации.

Scope Stage 0 соблюдён: создан только этот аналитический документ. Код агента, конфигурация, зависимости, сайт, deploy и Stage 1 не изменялись и не запускались.
