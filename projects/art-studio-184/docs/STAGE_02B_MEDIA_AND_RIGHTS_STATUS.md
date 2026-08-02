# Art Studio 184 — статус медиа и прав этапа 2B

Дата: 2026-08-02
Статус: утверждённый media/rights contract для curation и последующей подготовки. Файлы портфолио не скачивались и не изменялись на этапе 2B.

## 1. Актуальное решение владельца

| Тема | Значение | Статус | Источник | Последствие |
| --- | --- | --- | --- | --- |
| Связь с бизнесом | Все переданные фотографии относятся к Art Studio 184 и являются их материалами | `CONFIRMED / EVIDENCE PENDING` | 2B Q71 | Разрешает начать curation; formal asset-level record ещё нужен. |
| Разрешение на новый сайт | Владелец разрешает использовать фотографии из портфолио на новом коммерческом сайте | `CONFIRMED BY OWNER / FORMAL EVIDENCE PENDING` | 2B Q72 | Owner authorization зафиксирована; selected-asset register и publication risk review сохраняются. |
| Author/rights register | Автор и формальный rights holder для каждого файла не зафиксированы | `NEEDS EVIDENCE` | 2B Q71 | Создать asset-level register для фактически выбранных кадров. |
| High-resolution originals | Отдельных originals сейчас нет | `CONFIRMED` | 2B Q70 | До появления лучших originals использовать текущие опубликованные файлы с учётом их реальных размеров/качества. |
| Project metadata | Names, materials, sizes, dates, locations и results не собраны | `DEFERRED / NEEDS OWNER INPUT` | 2B Q73 | Нельзя создавать factual captions/cases; допустимы нейтральные visual alt facts. |
| Сторонние бренды | Владелец разрешает показывать выполненные работы и бренды в кадре | `CONFIRMED BY OWNER / EVIDENCE PENDING` | 2B Q74 | Formal client/brand permission не приложена; brand presence не доказывает client relation. |

Решение владельца заменяет раннюю гипотезу о полном отсутствии разрешения, но не создаёт отсутствующие сведения об авторе, chain of title, client relation или individual brand permission.

## 2. Правило Project, не File

1. Единица галереи — один реальный объект/заказ `Project`.
2. Несколько ракурсов, этапов и контекстов одного объекта связываются с одним `project_id`.
3. Один project получает одну primary category; вторичные связи не создают копию.
4. Exact duplicates исключаются из selection и не увеличивают perceived case count.
5. Stage 00 доказал две exact duplicate pairs:
   - `photo_2026-05-26_17-22-37.jpg` = `photo_2026-05-26_17-22-40.jpg`;
   - `photo_2026-05-27_10-02-26.jpg` = `photo_2026-05-27_10-02-25.jpg`.
6. `name.jpg` / `name (2).jpg` не удаляются и не объединяются автоматически; 46 таких filename pairs требуют visual/project review.
7. Похожие кадры одного объекта не становятся разными projects.
8. `190 displayed assets` — число файлов публичного источника, не `190 проектов`.
9. Project names, client, material, dimensions, date, location и result появляются только из owner-provided metadata.

## 3. Shortlist 8–15 проектов

Первый shortlist выбирает агент из портфолио. Это разрешённая media curation, а не окончательный hero или page design.

Обязательные критерии:

- визуальная сила;
- разнообразие;
- разные категории;
- разный масштаб;
- минимальное количество похожих кадров;
- project grouping вместо file counting;
- достаточное техническое качество для предполагаемой роли;
- отсутствие exact duplicates;
- безопасный статус брендов/прав для предполагаемого публичного использования.

Stage 2A provisional список из 11 файлов можно использовать как seed, но он не является утверждённым shortlist проектов. Итог curation должен сопоставить каждый выбранный cover/supporting frame с `project_id`, primary category, quality notes, actual dimensions, rights status и known brand marks.

## 4. Текущие и будущие media sources

| Media type | Текущее состояние | Статус | Разрешённое действие | Ограничение |
| --- | --- | --- | --- | --- |
| Portfolio files | 190 displayed assets доступны на публичной portfolio page/Git tree | `READY FOR CURATION WITH LIMITATIONS` | Инвентаризация, visual grouping, dedupe и shortlist 8–15 | Не скачивать все 190 без отдельной задачи; не hotlink в production. |
| High-res originals | Отсутствуют | `NEEDS EVIDENCE` | Запросить для selected subset; до этого использовать текущие файлы | Не обещать retina/full-bleed качество и не выбирать окончательный hero на 2B. |
| Hero | Нет утверждённого финального asset | `NEEDS EVIDENCE` | После shortlist провести crop/quality study | Окончательный hero не выбирать на 2B. |
| Equipment | Новые фотографии будут позже | `DEFERRED` | Подготовить shot list | Finished project не выдавать за equipment/process photo. |
| Processes | Новые фотографии будут позже | `DEFERRED` | Подготовить truthful stage/claim roles | Не использовать AI/чужие/готовые project images как документальный process proof. |
| Team portraits | Настоящих фотографий пока нет | `DEFERRED` | Использовать честные дизайнерские placeholders | Не генерировать и не использовать изображения вымышленных людей. |
| Clients/reviews | Списки и evidence будут позже | `DEFERRED` | Suppress corresponding sections | Не создавать fake logos/reviews. |

## 5. Командная секция и reference assets

### `art184_team_cards_layout_reference.png`

- Фактический формат: PNG (`RawFormat` PNG GUID), `684 × 223` px, `240,963` bytes, `Format32bppArgb`.
- SHA-256: `901395e620150e3581b4db3ecad9b0991c9e6408a82974c15b44fcafb010f37e`.
- Роль: только reference композиции/структуры двух персональных карточек.
- Canonical provenance type: `reference_only`.
- Usage status: `REFERENCE ONLY`.
- Фотографии людей из него запрещено рендерить, копировать или использовать как портреты Максима/Люды.

### `art184_team_section_background.png`

- Фактический формат: PNG (`RawFormat` PNG GUID), `1920 × 1080` px, `3,358,480` bytes, `Format32bppArgb`.
- SHA-256: `8fb5358116a940c79b9af6c8d0b989e87b287172ff4445acccbb233bf6946544`.
- Роль: утверждённый фон будущей секции команды.
- Canonical provenance type: `user_provided_business_asset`.
- Usage status: `CONFIRMED FOR TEAM BACKGROUND`; render-use boundary — только фон будущей секции команды.
- Перед implementation потребуется responsive crop, contrast/readability и performance review; исходный файл на 2B не изменяется.

### Контракт первой версии команды

- две карточки: Максим Рибалко и Люда Рибалко;
- нейтральные фирменные portrait placeholders, честно не выдаваемые за реальные портреты;
- весь публичный текст на украинском;
- Артёма Антонова в публичную командную секцию не добавлять;
- вымышленных людей генерировать нельзя.

## 6. Сторонние бренды и client claims

Stage 00 отмечал среди возможных marks KitKat, Garnier, Matrix, Victoria’s Secret, Oberig и Mark/Avon. Этот перечень — audit risk, не утверждённый список клиентов.

Для каждого selected branded frame нужно записать:

- asset/project ID;
- видимый mark;
- owner authorization;
- formal evidence status;
- разрешено ли показывать mark;
- разрешено ли называть client relationship (по умолчанию нет без отдельного evidence);
- допустимый neutral caption/alt;
- решение `use`, `crop if truthful`, `exclude` или `hold`.

Owner permission на изображение бренда не разрешает формулировки `наш клієнт`, `партнер` или использование client logo strip без отдельного подтверждения.

## 7. Production media pipeline

GitHub Pages portfolio нельзя использовать как production CDN. Для каждого rendered asset требуются:

- managed storage под контролем проекта;
- сохранённый current source/original и immutable source record;
- SHA-256 checksum;
- canonical provenance type и allowed-use boundary;
- `project_id`, frame order и primary category;
- фактические width/height;
- WebP/AVIF derivatives с сохранением исходника;
- responsive variants и `srcset`/`sizes` plan;
- crop/focal-point notes отдельно для desktop/tablet/mobile;
- lazy/eager priority по роли, без eager-load всех 190 файлов;
- truthful alt facts без предположений о клиенте, материале, размере или локации;
- mark/rights review и publication decision;
- visual quality note и fallback/error behavior.

Текущие опубликованные файлы могут быть source для selected subset до появления originals, но их нельзя выдавать за более высокое разрешение и нельзя загружать все автоматически.

## 8. Media blockers по этапам

### Для дизайна

- official logo asset/variants отсутствуют;
- точный green HEX не утверждён;
- project shortlist 8–15 ещё не создан;
- окончательный hero asset/crop не определён;
- equipment/process photos отложены;
- реальные team portraits отсутствуют, поэтому нужен честный placeholder system.

Media curation и structural team exploration начинать можно. Финальную brand/hero/equipment art direction — нельзя до закрытия соответствующего evidence.

### Для кода

- нет подготовленного selected media manifest;
- нет managed URLs, derivatives, dimensions и alt-fact records;
- нет финального hero/media assignments;
- нет equipment/process assets;
- нет project metadata для factual captions/cases.

Текущий code scaffolding `NOT READY`. После закрытия Stage 2C и отдельной авторизации можно будет начать framework-agnostic media schema/structural scaffolding; production gallery/media wiring потребует подготовленного manifest и derivatives.

### Для публикации

- managed storage и responsive derivatives не подготовлены — `BLOCKED FOR PUBLICATION`;
- selected-asset rights/author/brand register не создан — `NEEDS EVIDENCE`, а disputed/unclear asset должен быть исключён;
- formal third-party brand/client permissions отсутствуют — `BLOCKED FOR PUBLICATION` для client claims и для кадров, которые не пройдут individual risk decision;
- project-level factual captions отсутствуют — `BLOCKED FOR PUBLICATION` для names/materials/sizes/dates/locations/results;
- final hero quality/crop не проверены — `BLOCKED FOR PUBLICATION` для hero role;
- equipment/process documentary media отсутствуют — соответствующие визуальные claims подавляются;
- client/review proof отсутствует — соответствующие секции подавляются.

## 9. Что закрывает media readiness

1. Выполнить visual curation всех доступных records без массового production import.
2. Сгруппировать frames по проектам и исключить exact duplicates.
3. Выбрать 8–15 projects по утверждённым критериям.
4. Создать selected-asset register: checksum, dimensions, project, category, owner authorization, formal rights status, visible marks, intended role.
5. Получить available originals для selected subset или явно принять quality limits текущих files.
6. Провести hero/crop study, не выбирая asset по filename alone.
7. Подготовить managed storage и responsive derivatives.
8. Получить equipment/process media или подавить соответствующие documentary blocks.
9. Сохранить честный team placeholder contract до настоящих portrait assets.
