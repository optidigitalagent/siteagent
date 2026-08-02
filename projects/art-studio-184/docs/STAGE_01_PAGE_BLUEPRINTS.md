# Art Studio 184 — Stage 01 page blueprints

Дата: 2026-08-02
Назначение: зафиксировать смысл, порядок и dependency каждой секции пяти core pages до начала дизайна и программирования.

## Общие правила blueprints

- Public language: украинский.
- Primary CTA: `Обговорити проєкт`.
- Первые четыре страницы имеют отдельный `NextPageLink`.
- Одна секция не может существовать только ради ритма или повторения CTA.
- Status применяется к секции и отдельным claims независимо.
- `CONDITIONAL`-секция полностью исчезает, если evidence не получен.
- Финальные тексты, изображения и visual layout не утверждаются этим документом.

## 1. Головна — `/`

- **Цель:** за первый viewport объяснить предложение, показать реальную работу, затем дать достаточный обзор направлений, качества, возможностей и процесса для перехода в галерею или к контакту.
- **Аудитория:** бренд-менеджеры, агентства, event-команды, бизнесы и частные заказчики, которым нужен физический декоративный/брендовый объект. Конкретные сегменты требуют дальнейшего business confirmation.
- **Основной intent:** понять, что создаёт Art Studio 184, и быстро оценить визуальный уровень.
- **H1:** `Створюємо об’ємні фігури, декорації та брендовані об’єкти`.
- **Primary CTA:** `Обговорити проєкт`.
- **Next-page transition:** `Переглянути галерею` → `/gallery/`.

### Последовательность секций

| № | Секция / status | Функция | Тип контента и media requirements | CTA / dependency |
| ---: | --- | --- | --- | --- |
| 1 | `Hero` — `CONFIRMED`; media `BLOCKED FOR PUBLICATION` | ответить, что создаёт мастерская, показать реальную работу и действие | один H1, короткое объяснение без final advertising copy; реальный authorised object image или композиция 2–3 images; нужен crop на 1440/390, предпочтительно новый ≥2000 px wide original либо split composition | primary `Обговорити проєкт`; secondary `Переглянути роботи`; dependency: rights, high-res, CTA destination |
| 2 | `Коротко про майстерню` — смысл `CONFIRMED`, точные claims `TBD` | объяснить сочетание художественной и производственной части, не повторяя H1 | 1 короткий paragraph/statement; один supporting detail image допустим, но не обязателен | без отдельного CTA; подтвердить формулировку `майстерня повного циклу` и in-house границы |
| 3 | `Основні напрями` — `CONFIRMED` как IA | помочь быстро распознать свой тип задачи | три direction records: `Об’ємні фігури та скульптури`, `Фотозони, декорації та інсталяції`, `Вивіски та брендовані об’єкти`; по одному representative project cover после rights review | каждая карточка ведёт к одному якорю на `/gallery/`; не создавать direction pages в V1 |
| 4 | `Вибрані проєкти` — `CONFIRMED`; конкретный набор `TBD` | доказать диапазон масштаба, материалов и назначения | **8 проектов**: достаточно для широты без превращения home в полный архив; ориентир 3/3/2 по трём направлениям с возможной корректировкой по quality; один проект может иметь один cover на home, но не несколько cards | `Усі роботи` → `/gallery/`; dependency: project grouping, rights, high-res, safe captions |
| 5 | `Якість і довговічність` — architecture `CONFIRMED`, claims `BLOCKED FOR PUBLICATION` | объяснить, за что отвечает более тщательный производственный подход | смысловые точки: material choice, конструкция, подготовка поверхности, покрытие, реальные условия; 1 detail/process image только при наличии прав | без нового primary CTA; owner подтверждает каждое durability/condition claim |
| 6 | `Не про найшвидше й найдешевше` — `CONDITIONAL` / `BLOCKED FOR PUBLICATION` | честно объяснить positioning без superiority claim | короткая decision section: trade-off в пользу качества и пригодности, без сравнительных цифр/гарантий | включать только после owner-approved wording; не дублировать секцию 5 |
| 7 | `Виробничі можливості — preview` — architecture `CONFIRMED`, факты granular | показать breadth, не пересказывать полную страницу | 6 кратких групп: `Проєктування та 3D`; `CNC і 3D-друк`; `Ручна форма, пінополістирол і склопластик`; `Метал і дерево`; `Поверхня та фарбування`; `Збірка, доставка та монтаж`; media только для подтверждённых процессов | `Дізнатися про можливості` → `/capabilities/`; неподтверждённая группа не заявляется как факт |
| 8 | `Як ми працюємо — коротко` — `CONDITIONAL` | снизить неопределённость первого обращения | 5 укрупнённых шагов: `Ідея або референс` → `Уточнення завдання` → `Концепція й конструкція` → `Виготовлення та оздоблення` → `Передача / монтаж`; точное содержание требует approval | CTA не повторяется внутри шагов; payment, timing, revisions, delivery conditions заблокированы |
| 9 | `Команда` — `CONDITIONAL` | показать людей и роли, если это реальное доказательство | имена, роли, factual bios, authorised portraits/work image | при отсутствии материалов секция удаляется; готовые объекты не подменяют team photos |
| 10 | `Клієнти` — `CONDITIONAL` | показать релевантный trust и связать клиентов с проектами | approved list/logo assets + project relation + permission | при отсутствии — удалить; **не заменять** generic brand strip; сами проекты остаются proof |
| 11 | `Відгуки` — `CONDITIONAL` | дать проверяемый голос клиента | original text, name, company/role, source, permission | при отсутствии — удалить; placeholder reviews запрещены |
| 12 | `Фінальний контакт і наступний крок` — `CONFIRMED`; destination `BLOCKED FOR PUBLICATION` | предложить простой диалог и продолжение portfolio journey | compact action panel без повторной формы; короткое contextual предложение | primary `Обговорити проєкт` → Contacts; secondary `Переглянути галерею` |

### Запрещено дублировать

- H1 другими словами в секции «Коротко»;
- все gallery categories второй раз как отдельный визуальный каталог;
- полную production story и 7-step process со страницы capabilities;
- Philosophy как большой manifesto;
- несколько кадров одного проекта как разные selected projects;
- team/clients/reviews без evidence.

## 2. Галерея — `/gallery/`

- **Цель:** показать единый архив реальных проектов, сгруппированный по направлениям, без раздутого количества кейсов.
- **Аудитория:** посетитель, который сравнивает визуальный уровень, похожие задачи, масштаб и применимость мастерской.
- **Основной intent:** увидеть реальные проекты Art Studio 184 по типу результата.
- **H1:** `Реальні роботи Art Studio 184`.
- **Primary CTA:** `Обговорити проєкт`.
- **Next-page transition:** `Дізнатися про виробничі можливості` → `/capabilities/`.

### Последовательность секций

| № | Секция / status | Функция | Контент и media | CTA / dependency |
| ---: | --- | --- | --- | --- |
| 1 | `Intro` — `CONFIRMED`, public proof claim rights-bound | объяснить, что архив состоит из проектов, а проект может иметь несколько кадров | H1, 2–3 предложения, одна contextual image опционально | primary CTA доступен; `реальні роботи` публикуется только для assets с подтверждённой связью |
| 2 | `Навігація за напрямами` — `CONFIRMED` | быстрый доступ к трём неповторяющимся category sections | anchors: `Фігури та скульптури`, `Фотозони та інсталяції`, `Вивіски та брендовані об’єкти` | sticky ниже header; desktop inline, mobile horizontal scroll; active state + focus-visible |
| 3 | `Об’ємні фігури та скульптури` — IA `CONFIRMED`, projects `TBD` | показать объекты, где форма/персонаж является главным результатом | V1 ориентир: **6 подтверждённых проектов**, по 1 cover + до 3 дополнительных frames; grid сохраняет project grouping | открытие project lightbox; future SEO status определяется отдельно |
| 4 | `Фотозони, декорації та інсталяції` — IA `CONFIRMED`, projects `TBD` | показать spatial/event/scene work без дробления похожих кадров | V1 ориентир: **6 подтверждённых проектов**, 1–4 frames/project; обязательны различия назначения и масштаба | project lightbox; captions только из confirmed facts |
| 5 | `Вивіски та брендовані об’єкти` — IA `CONFIRMED`, projects `TBD` | показать signage/display/branded-object результат без неподтверждённого client claim | V1 ориентир: **6 подтверждённых проектов**, 1–4 frames/project; бренд в кадре не означает подтверждённого клиента | project lightbox; trademark/permission review обязателен |
| 6 | `Compact inquiry` — `CONFIRMED`, destination blocked | дать действие после proof | compact action panel без повторной формы | `Обговорити проєкт` → `/contacts/` |
| 7 | `Next page` — `CONFIRMED` | объяснить следующий вопрос: как это производится | короткий transition, не новый production section | `Дізнатися про виробничі можливості` |

Если после правовой/семантической группировки в категории нет шести сильных проектов, публикуется меньше. Число `6` — editorial target, не разрешение создавать ложные записи.

### Project grouping contract

- content unit: `Project` с устойчивым `project_id`;
- обязательные поля V1: category, cover, authorised frames, safe alt, frame order, provenance status;
- title/caption/material/date/location/client выводятся только при подтверждении;
- один object cluster (например несколько ракурсов одного объекта) = один project;
- exact duplicates исключаются;
- `name.jpg` и `name (2).jpg` не объединяются/удаляются автоматически без visual/project review;
- похожие кадры не повышают project count;
- home selected work ссылается на ту же project entity/anchor, а не копирует отдельную запись.

### Lightbox functional contract

- открывается из project card/cover и показывает frames только этого project;
- modal dialog с accessible name из project title или нейтрального verified label;
- close button, Escape, backdrop click как дополнительный способ;
- previous/next buttons, Arrow Left/Right; controls имеют accessible names;
- mobile swipe дополняет, но не заменяет buttons;
- показывает frame counter `n / total`;
- caption только для подтверждённых project facts; при отсутствии — нейтральный frame counter без выдумки;
- focus переходит в dialog, удерживается внутри и возвращается к trigger;
- background scroll заблокирован;
- reduced motion отключает сложные transitions;
- current/next frame могут preload, остальные lazy-load;
- image error не закрывает dialog молча: frame получает error state и доступен переход к следующему;
- browser back не должен уводить пользователя непредсказуемо; URL/state contract определяется в реализации.

### Запрещено дублировать

- отдельный ряд category cards перед теми же category sections;
- один проект в нескольких категориях без обоснованного primary category;
- разные кадры одного объекта как разные кейсы;
- производственные возможности как длинные explanations;
- неподтверждённые client names, materials, dates, sizes или results.

## 3. Виробничі можливості — `/capabilities/`

- **Цель:** объяснить путь от идеи к объекту и границы подтверждённых процессов.
- **Аудитория:** посетитель, которому важно понять техническую применимость, материалы, production chain и формат взаимодействия.
- **Основной intent:** проверить, может ли Art Studio 184 реализовать конкретный физический объект.
- **H1:** `Виробничі можливості Art Studio 184`.
- **Primary CTA:** `Обговорити проєкт`.
- **Next-page transition:** `Дізнатися про наш підхід` → `/philosophy/`.

### Последовательность секций

| № | Секция / status | Функция | Content/media requirements | Dependency |
| ---: | --- | --- | --- | --- |
| 1 | `Intro` — architecture `CONFIRMED`, full-cycle claim `TBD` | связать художественную и техническую задачи | H1 + short scope; 1 object/process visual | подтвердить public wording о полном цикле и partner processes |
| 2 | `Проєктування та 3D` — `CONDITIONAL` | объяснить анализ задачи, model/construction planning | verified list: анализ, 3D modelling/model prep/construction design; model/render/process media | подтвердить, что делается, кем и в каких случаях |
| 3 | `CNC і 3D-друк` — `CONDITIONAL` | показать digital fabrication как средство, не product category | milling, 3D print, part prep, scaling only if verified; process photo | models, working sizes, tolerances, materials — `BLOCKED FOR PUBLICATION` |
| 4 | `Ручна форма, пінополістирол і склопластик` — `CONDITIONAL` | показать ручную и material production chain | manual sculpting, foam processing, reinforcement, fiberglass, moulding only if confirmed; process/details | определить in-house/partner; safety-sensitive specifics не нужны без пользы |
| 5 | `Метал і дерево` — `CONDITIONAL` | объяснить construction/support work | frames, welding, metal structures, wood elements; process/structure image | in-house status и доступные виды работ подтвердить |
| 6 | `Поверхня та фарбування` — `CONDITIONAL` | показать качество finish как отдельный этап | preparation, putty, sanding, primer, paint, protection only if confirmed; close detail/process series | claims о погодостойкости/сроке службы требуют evidence |
| 7 | `Збірка, доставка та монтаж` — `CONDITIONAL` | закрыть путь до готового результата | assembly, transport, installation/on-site work only where verified; installation image with rights | geography, terms, responsibility — `BLOCKED FOR PUBLICATION` |
| 8 | `Як ми працюємо` — structure `CONFIRMED`, operations `TBD` | дать полный понятный процесс без финансовой выдумки | 7 шагов ниже; 2–4 process images при наличии | owner approves sequence, responsibilities and terminology |
| 9 | `Compact inquiry` — `CONFIRMED`, destination blocked | перевести техническое понимание в короткий запрос | compact action panel без полей; form остаётся на Contacts | реальный destination/fallback |
| 10 | `Next page` — `CONFIRMED` | перейти от capability к принципам качества | короткая contextual link | `/philosophy/` |

### Full process: 7-step architecture

1. `Ідея або референс` — заказчик может прийти без готового технического задания.
2. `Уточнення завдання` — назначение, условия, масштаб и ожидаемый результат; точный список полей не превращается в обязательную форму.
3. `Концепція, модель і конструкція` — только применимые и подтверждённые действия.
4. `Матеріали та план виготовлення` — без неподтверждённых обещаний цены/срока.
5. `Виготовлення` — factual process groups из подтверждённой capability matrix.
6. `Оздоблення та погодження` — поверхность/paint/approval points после owner confirmation.
7. `Передача, доставка або монтаж` — только подтверждённый вариант для конкретной географии/ответственности.

Не публикуются без подтверждения: 50% предоплаты, финальный платёж, typical timing, количество правок, гарантии, capacity, exact delivery/mounting terms.

### Запрещено дублировать

- gallery categories как capabilities;
- одну и ту же производственную группу под разными названиями;
- полный process на home;
- Philosophy через абстрактные value cards;
- неподтверждённые equipment models/specs и in-house claims.

## 4. Філософія — `/philosophy/`

- **Цель:** коротко объяснить происхождение и принципы работы мастерской, связанные с качеством, материалами, конструкцией и долговечностью.
- **Аудитория:** посетитель, который уже видел работы/возможности и хочет понять отношение к результату.
- **Основной intent:** оценить подход Art Studio 184 к качеству и выбору решений.
- **H1:** `Підхід Art Studio 184 до роботи`.
- **Primary CTA:** `Обговорити проєкт`.
- **Next-page transition:** `Перейти до контактів` → `/contacts/`.
- **Объём:** 3 основные content sections, 2–4 изображения, CTA и next link.

### Последовательность секций

| № | Секция / status | Функция | Content/media requirements | Dependency |
| ---: | --- | --- | --- | --- |
| 1 | `Intro` — `CONFIRMED` как функция, copy `TBD` | обозначить, что страница о подходе, а не повторе услуг | H1 + one short thesis; real object/detail image | финальная формулировка не утверждает превосходство |
| 2 | `Як з’явилася майстерня` — `CONDITIONAL` / `BLOCKED FOR PUBLICATION` | дать человеческое происхождение мастерской | factual short story, 1 archival/workshop image if authorised | owner подтверждает hobby-origin, dates/events не придумываются |
| 3 | `Ставлення, матеріали й деталі` — `CONDITIONAL` / `BLOCKED FOR PUBLICATION` | объяснить personal responsibility и связать качество с конкретными решениями | 2–3 evidence-backed principles; work/process/detail media | owner approves wording; claims совпадают с capability matrix; fake quote запрещён |
| 4 | `Довговічність замість поспіху` — `CONDITIONAL` / `BLOCKED FOR PUBLICATION` | объяснить anti-cheap/anti-fast positioning как trade-off | краткий decision-focused текст; no numeric guarantee | owner-approved wording и evidence о реальных условиях |
| 5 | `Compact inquiry + next page` — `CONFIRMED`, destination blocked | перевести доверие в действие и закончить путь | compact action panel без формы + contact transition | primary `Обговорити проєкт`; secondary `Перейти до контактів` |

Если история или positioning не подтверждены, страница не раздувается: остаётся краткое factual объяснение подхода из подтверждённых материалов либо Stage 2 блокируется как недостаточно содержательная Philosophy.

### Запрещено дублировать

- полный список направлений и capabilities;
- home selected projects как второй gallery;
- абстрактные cards `цінності / турбота / інновації` без доказательств;
- invented founder story, dates, quotes, awards, team size;
- повтор одного anti-cheap тезиса в нескольких секциях.

## 5. Контакти — `/contacts/`

- **Цель:** дать минимальный, честный и доступный способ начать разговор без большого технического брифа.
- **Аудитория:** любой посетитель с идеей, reference или коротким описанием, включая тех, кто ещё не знает material/size/process.
- **Основной intent:** связаться с Art Studio 184 по поводу проекта.
- **H1:** `Обговорімо ваш проєкт`.
- **Primary CTA:** `Обговорити проєкт` как submit/verified direct action.
- **Следующий переход:** отсутствует; secondary action `Повернутися до галереї`, verified Instagram может быть дополнительным каналом.

### Последовательность секций

| № | Секция / status | Функция | Content/media requirements | Dependency |
| ---: | --- | --- | --- | --- |
| 1 | `Intro` — `CONFIRMED` | снизить порог: достаточно идеи/reference/описания | H1 + short explanation; no promise of estimate/response time | wording не обещает неподтверждённый результат |
| 2 | `Мінімальна форма` — structure `CONFIRMED`, delivery blocked | принять ровно необходимую информацию | required: `Ім’я`, `Контакт`; optional: `Зручний спосіб зв’язку`, `Коротко про проєкт`; preferred channel required только если выбран contact value неоднозначен | backend/fallback, consent и privacy contract |
| 3 | `Прямі контакти` — `CONDITIONAL` / `BLOCKED FOR PUBLICATION` | дать альтернативу форме | phone, Instagram, Telegram, Viber, WhatsApp, email, location, hours — выводится только реально подтверждённое | не показывать пустые icons/labels; определить primary channel |
| 4 | `Контекст майстерні` — `CONDITIONAL` | сохранить visual trust на финальной странице | 1 strong contextual photo + 2–3 supporting workshop/process/object images | rights + truthful context; готовая работа не выдаётся за workshop photo |
| 5 | `Result / fallback state` — `CONFIRMED` как contract | честно завершить действие | success/error/fallback states; secondary `Повернутися до галереї`; verified Instagram only if confirmed | success только после реальной отправки/выполнения fallback |

### Form contract

Не спрашиваются как обязательные при первом контакте: project type, indoor/outdoor, temporary/permanent, size, deadline, обязательные одновременно email и phone, budget, material, сложный technical questionnaire, file upload.

Возможные delivery modes следующего этапа:

- `backend_delivery` — только после endpoint, privacy и real success verification;
- `mailto` или verified messenger redirect — честный fallback;
- `copy_to_clipboard` — допустим, если объясняет следующий шаг;
- `visual_demo` — только internal preview, не production contact route.

Error state сохраняет введённые данные, называет проблему и предлагает подтверждённый direct channel. Фраза `Повідомлення надіслано` запрещена, если network delivery не доказан.

### Запрещено дублировать

- отдельную большую technical estimate form;
- capabilities checklist;
- полный About/Philosophy narrative;
- пустые messenger icons;
- неподтверждённый address/map/hours/response time;
- artificial next page после финального conversion step.
