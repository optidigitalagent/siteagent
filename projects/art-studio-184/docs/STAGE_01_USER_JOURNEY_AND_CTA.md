# Art Studio 184 — Stage 01 user journey and CTA

Дата: 2026-08-02
Назначение: зафиксировать decision path, единый CTA-язык, форму, fallback и interaction states до реализации.

## 1. Основной пользовательский путь

`Головна → Галерея → Виробничі можливості → Філософія → Контакти`

| Этап | Вопрос пользователя | Ответ страницы | Решение / действие |
| --- | --- | --- | --- |
| Головна | Что делает мастерская и стоит ли смотреть дальше? | точный offer, реальные работы, три направления, качество, overview возможностей | открыть gallery или сразу обсудить проект |
| Галерея | Делали ли здесь визуально и по масштабу близкие задачи? | curated projects, grouped frames, три направления без повторов | открыть проект, перейти к capabilities или связаться |
| Виробничі можливості | Как идея становится объектом и применимы ли процессы к моей задаче? | подтверждённые production groups и полный нейтральный process | начать разговор или проверить подход к качеству |
| Філософія | Почему стоит выбрать этот подход, если он не обещает самый быстрый/дешёвый результат? | подтверждённая история и конкретная связь качества с материалами/конструкцией/деталями | перейти к контакту или сразу начать разговор |
| Контакти | Что нужно предоставить, чтобы начать? | имя + один контакт + необязательное описание; прямые verified channels | выполнить реальное contact action |

Путь последовательный, но не линейно обязательный. Primary CTA доступен на каждой странице, а каждая внутренняя страница самостоятельно объясняет свой context.

## 2. Альтернативные входы

### Вход на Gallery

Посетитель из search/social сразу понимает, что видит реальные проекты, использует category anchors и может перейти к capabilities. Он не должен возвращаться на home, чтобы понять навигацию или найти CTA.

### Вход на Capabilities

Посетитель получает H1, short intro, только подтверждённые process groups и primary CTA. Gallery доступна из header/footer, а следующий recommended step ведёт в Philosophy.

### Вход на Philosophy

Страница кратко идентифицирует Art Studio 184 и подход, не предполагая, что посетитель уже видел работы. Header/footer дают доступ к Gallery, а content closure — к Contacts.

### Вход на Contacts

Пользователь сразу видит, что большой technical brief не нужен. Form/direct contacts не зависят от просмотра остальных страниц; secondary link в Gallery поддерживает пользователя, который ещё не готов написать.

### Будущий вход на SEO/case page

Такая страница обязана объяснить конкретный intent, связать его с core Gallery/Capabilities, предложить `Обговорити проєкт` и не создавать отдельную competing conversion system.

## 3. Decision points

1. **Первый viewport:** посетитель узнаёт тип результата и решает `Переглянути роботи` или `Обговорити проєкт`.
2. **После направлений home:** выбирает gallery anchor, а не новую непроверенную service page.
3. **После selected projects:** убеждается в visual range и открывает полный archive.
4. **Внутри Gallery:** project card/lightbox помогает распознать релевантную задачу; CTA остаётся доступным, но не вставляется после каждого project.
5. **После Gallery:** пользователь, которому мало визуального proof, переходит к production logic.
6. **После capability groups:** проверяет, есть ли применимый процесс; ограничения не скрываются.
7. **После Philosophy:** принимает trade-off качества против минимальной цены/скорости только на основании owner-approved wording.
8. **На Contacts:** выбирает минимальную форму или подтверждённый direct channel.

## 4. Primary CTA

### Утверждённый label

`Обговорити проєкт`

### Почему выбран этот вариант

- понятно описывает следующий шаг;
- не обещает смету, цену, ответ в срок или принятие заказа;
- подходит посетителю с идеей, reference или частично сформированной задачей;
- одинаково работает в header, content CTA и form context;
- не требует подтверждённой калькуляционной процедуры.

### Destination contract

- header и обычные page CTAs ведут на `/contacts/`;
- CTA внутри compact inquiry может фокусировать реальную форму на той же странице только при наличии формы и понятного anchor;
- на `/contacts/` label относится к фактическому form submit или verified direct-channel action;
- пока нет подтверждённого destination/backend/fallback, действие имеет статус `BLOCKED FOR PUBLICATION` и не подменяется `#`/fake success.

## 5. Secondary CTA

Secondary action всегда описывает содержательный переход и не конкурирует с primary conversion.

| Контекст | Label | Destination |
| --- | --- | --- |
| Home hero / selected work | `Переглянути роботи` / `Усі роботи` | `/gallery/` |
| Home final transition | `Переглянути галерею` | `/gallery/` |
| Gallery closure | `Дізнатися про виробничі можливості` | `/capabilities/` |
| Capabilities closure | `Дізнатися про наш підхід` | `/philosophy/` |
| Philosophy closure | `Перейти до контактів` | `/contacts/` |
| Contacts after/fallback state | `Повернутися до галереї` | `/gallery/` |
| Direction card | descriptive category label | соответствующий anchor `/gallery/#...` |

Generic labels `Детальніше`, `Далі`, `Натиснути`, `Надіслати` без context не используются.

## 6. CTA placement по страницам

| Страница | First meaningful viewport | В content | Closure |
| --- | --- | --- | --- |
| Головна | primary + `Переглянути роботи` | один contextual primary после достаточного decision support; direction/project links не считаются primary | compact action panel без формы + `Переглянути галерею` |
| Галерея | primary доступен в intro/header | не повторять CTA после каждой category/project; один contextual action допустим после всей project grid | compact action panel без формы + переход в capabilities |
| Виробничі можливості | primary в intro/header | один action после capability evidence/process, не в каждой capability row | compact action panel без формы + переход в Philosophy |
| Філософія | primary в intro/header | не вставлять между короткими narrative sections | compact action panel без формы + переход в Contacts |
| Контакти | primary связан с form/direct action | прямые verified channels | honest result/fallback + возврат в Gallery |

Правило плотности: не более одного visually dominant primary CTA одновременно в одном viewport. Persistent header CTA может быть компактным и не конкурировать с page CTA по масштабу. Реальная форма V1 существует только на Contacts; `compact inquiry` на первых четырёх страницах означает action panel, а не четыре копии формы.

## 7. Минимальная форма

### Поля

| Поле | Обязательность | Правило |
| --- | --- | --- |
| `Ім’я` | required | один понятный text input; не требовать surname/company |
| `Контакт` | required | одно значение: phone, email или messenger handle; format guidance зависит от выбранного channel mode |
| `Зручний спосіб зв’язку` | optional/conditional | radio/select только если помогает интерпретировать `Контакт`; не требовать канал, которого нет в verified routes |
| `Коротко про проєкт` | optional | textarea; можно отправить идею или reference description без technical details |

File upload не является обязательным V1 field. Если позже добавляется, он получает отдельные size/type/privacy/error requirements и не блокирует простой first contact.

### Form behavior

- labels всегда видимы; placeholder не заменяет label;
- required status сообщён до submit;
- validation идёт на blur/submit без потери введённых данных;
- error summary получает focus, fields связаны с errors;
- submit control минимум 44×44 и сохраняет label целиком во всех states;
- при submit появляется ясное busy state без повторной отправки;
- success содержит фактическое описание результата, а не generic claim;
- user-entered content не попадает в URL/analytics/event logs без отдельного contract.

## 8. Direct contact fallback

Предпочтительный порядок определяется владельцем, но архитектура допускает:

1. verified primary messenger;
2. verified phone;
3. verified email;
4. verified Instagram;
5. `copy_to_clipboard` prepared message как вспомогательный action.

Правила:

- fallback виден до или после form error, а не скрыт в footer;
- label называет канал и ожидаемое действие;
- Telegram/Viber/WhatsApp не выводятся, пока не подтверждены;
- `mailto` не считается backend delivery;
- Instagram может быть secondary direct route, но только на официальный подтверждённый account;
- пустой `href`, `#`, неподтверждённый username или fake success запрещены.

## 9. Success, error и fallback states

### Success

Допустим только если соответствующий mode реально завершён:

- `backend_delivery`: server подтвердил приём, а UI сообщает, что именно принято;
- messenger/email redirect: UI говорит, что открыт канал/подготовлено сообщение, а не что заявка отправлена;
- copy-to-clipboard: UI сообщает, что текст скопирован, и даёт следующий verified channel.

### Validation error

- конкретно называет незаполненное/невалидное поле;
- переводит focus, сохраняет данные;
- не блокирует доступ к direct contacts.

### Transport error

- не показывает success;
- предлагает повторить действие и verified direct fallback;
- не отправляет автоматически повторный запрос без действия пользователя.

### Missing configuration

В production это blocker, а не видимый placeholder. Internal preview может честно иметь `visual_demo`, но такой mode не является готовым conversion route.

## 10. Naming rules

- одно действие получает один label: `Обговорити проєкт`;
- `Переглянути роботи` означает переход к portfolio, не contact;
- `Дізнатися про можливості` означает content navigation, не estimate;
- слово `Розрахувати`/`Отримати розрахунок` запрещено до подтверждения calculation workflow;
- `Замовити` не используется как primary CTA, пока не подтверждена схема принятия заказа;
- labels пишутся в одном grammatical style: инфинитивные action phrases;
- project/category links называют destination, а не используют `Детальніше`.

## 11. Anti-patterns

- конкурирующие `Замовити`, `Отримати кошторис`, `Написати`, `Залишити заявку` для одного действия;
- CTA после каждого capability/project/paragraph;
- CTA, ведущий на несуществующий anchor или placeholder URL;
- form, требующая размер, deadline, indoor/outdoor, project type и два contacts до первого разговора;
- primary action только в footer;
- mobile menu без CTA или с недоступным focus;
- success message без доказанной отправки;
- next-page link, визуально маскирующийся под primary submit;
- Instagram как единственный silent fallback без объяснения перехода;
- repeated CTA sections, не добавляющие нового context.
