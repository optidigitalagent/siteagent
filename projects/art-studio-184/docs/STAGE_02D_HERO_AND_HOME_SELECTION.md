# Art Studio 184 — выбор hero и медиа главной, Stage 2D

Статус: owner decision sheet. Ни один вариант не утверждён автоматически. Все ссылки ведут только на существующие Stage 2C assets.

## Общая граница качества

- В текущем shortlist нет файла шире `1280 px`.
- Ни один вариант не поддерживает честный retina full-bleed desktop hero без нового high-resolution original.
- В первом meaningful viewport должны оставаться понятный H1, краткое объяснение, CTA `Обговорити проєкт` и путь к работам.
- На mobile смысл и CTA идут раньше высокого portrait media.
- Crop и responsive derivatives на Stage 2D не создаются.

## H1 — split hero с Illuminated Mushrooms

### Файлы

- [primary `photo_2026-05-26_17-22-35.jpg`, 956×1280](../media/stage-02c-shortlist/photo_2026-05-26_17-22-35.jpg);
- [alternate `photo_2026-05-26_17-22-41.jpg`, 755×1107](../media/stage-02c-shortlist/photo_2026-05-26_17-22-41.jpg);
- [contact sheet](../review/stage-02c/contact-sheets/curated-originals-part-1.png).

### Как выглядит

Отдельная тёмная текстовая колонка и contained vertical image. Световая скульптура создаёт выразительный первый образ, но не используется как background под текст.

| Критерий | Оценка |
| --- | --- |
| Преимущества | Один ясный объект; хороший контраст; сильная световая атмосфера; самый надёжный reading order. |
| Ограничения | Видны рабочая поверхность, провода и workshop context; full bleed запрещён. |
| Desktop | Image column `40–45%`, contained `4:5`; dome и световой gradient сохраняются. |
| Mobile | Сначала copy/CTA, затем contained `4:5` image; не full viewport. |
| Риск качества | `MEDIUM`: 956 px достаточно для колонки, не для большого фона. |
| Риск скорости | `LOW`: один eager responsive image. |
| Нужен дополнительный файл | Желателен clean high-resolution vertical original, но первая версия возможна без него. |
| Пригодность для первой версии | `ДА, С ОГРАНИЧЕНИЯМИ`; надёжный fallback. |

Решение владельца по H1: ВЫБРАТЬ / ОСТАВИТЬ РЕЗЕРВОМ / ОТКЛОНИТЬ
Комментарий: _________________________________________________________

## H2 — composed hero: White Flower + Bird Flock + Multicolour Neon

### Файлы

- dominant: [White Flower `17-22-57`, 1280×960](../media/stage-02c-shortlist/photo_2026-05-26_17-22-57.jpg);
- secondary: [Bird Flock `17-23-00`, 1280×960](../media/stage-02c-shortlist/photo_2026-05-26_17-23-00.jpg);
- secondary: [Multicolour Neon `17-22-42`, 1280×960](../media/stage-02c-shortlist/photo_2026-05-26_17-22-42.jpg);
- [contact sheet](../review/stage-02c/contact-sheets/curated-originals-part-1.png).

### Как выглядит

Три изображения показывают диапазон студии: светлая крупная форма, пространственная инсталляция и световая вывеска. Copy находится в отдельной тёмной области, а не поверх collage.

| Критерий | Оценка |
| --- | --- |
| Преимущества | Сразу показывает три направления; не растягивает один слабый source; сильный диапазон форм/света. |
| Ограничения | Сложнее композиция; neon wording требует individual mark decision; bird JPEG сильно сжат. |
| Desktop | Flower dominant `4:3`; bird/neon — меньшие tiles; copy отдельно. |
| Mobile | В первом viewport только White Flower; bird/neon после CTA. |
| Риск качества | `LOW–MEDIUM`: три 1280×960 файла, но разное сжатие. |
| Риск скорости | `MEDIUM`: только dominant image eager; остальные должны быть lazy. |
| Нужен дополнительный файл | Не обязателен для composed первой версии; желателен новый wide hero для будущего упрощения. |
| Пригодность для первой версии | `ДА, С ОГРАНИЧЕНИЯМИ`; Stage 2C preferred provisional direction. |

Решение владельца по H2: ВЫБРАТЬ / ОСТАВИТЬ РЕЗЕРВОМ / ОТКЛОНИТЬ
Можно ли использовать neon frame с видимым текстом: ДА / НЕТ / НУЖЕН ДРУГОЙ КАДР
Комментарий: _________________________________________________________

## H3 — contained wide hero с Illuminated Foliage

### Файлы

- desktop: [wide `17-22-52`, 1280×656](../media/stage-02c-shortlist/photo_2026-05-26_17-22-52.jpg);
- tablet alternate: [`17-22-53`, 1280×960](../media/stage-02c-shortlist/photo_2026-05-26_17-22-53.jpg);
- mobile/detail alternate: [`17-22-55`, 1280×960](../media/stage-02c-shortlist/photo_2026-05-26_17-22-55.jpg);
- [contact sheet](../review/stage-02c/contact-sheets/curated-originals-part-1.png).

### Как выглядит

Широкая световая композиция показывается внутри max-width container. Copy размещается выше или рядом; белый текст поверх светлого изображения запрещён.

| Критерий | Оценка |
| --- | --- |
| Преимущества | Самый чистый wide frame; спокойная композиция; низкая brand risk; хорошая скорость. |
| Ограничения | 1280×656 и 87 KB; нельзя растягивать на полный экран/retina; pale scene требует отдельной text zone. |
| Desktop | Сохранить исходный ratio около `1.95:1` внутри container без upscale. |
| Mobile | Copy/CTA сначала, затем central `4:3` alternate; не вырезать узкий `4:5`. |
| Риск качества | `MEDIUM–HIGH` для большого desktop. |
| Риск скорости | `LOW`; самый лёгкий hero direction. |
| Нужен дополнительный файл | Да, если направление должно стать full-bleed или retina. |
| Пригодность для первой версии | `ДА` только как contained hero. |

Решение владельца по H3: ВЫБРАТЬ / ОСТАВИТЬ РЕЗЕРВОМ / ОТКЛОНИТЬ
Комментарий: _________________________________________________________

## Итоговый выбор hero

- [ ] выбрать H1;
- [ ] выбрать H2;
- [ ] выбрать H3;
- [ ] временно использовать: ______________________, затем заменить;
- [ ] не утверждать hero до новой фотосъёмки.

Ответ владельца:

______________________________________________________________________

## Предложение: 8 проектов на главной

Это рабочая последовательность, не утверждённый layout. Один cover представляет один project; дополнительные кадры не считаются отдельными работами.

| Порядок | Project | Cover | Зачем в последовательности | Ограничение |
| ---: | --- | --- | --- | --- |
| 1 | `SCL-01-WHITE-FLOWER` | [`17-22-57`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-57.jpg) | Чистая крупная форма, светлый вход | Нет очевидного mark |
| 2 | `INS-02-BIRD-FLOCK` | [`17-23-00`](../media/stage-02c-shortlist/photo_2026-05-26_17-23-00.jpg) | Переход к пространственной инсталляции | Сжатый JPEG |
| 3 | `SIG-02-MARQUEE-LETTERS` | [`17-22-47`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-47.jpg) | Вывески без доминирующего известного бренда | Подтвердить series boundary |
| 4 | `SCL-03-RED-TREE` | [`17-23-23`](../media/stage-02c-shortlist/photo_2026-05-26_17-23-23.jpg) | Сильный красный графический контрапункт | Seasonal character |
| 5 | `INS-01-ILLUMINATED-FOLIAGE` | [`17-22-52`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-52.jpg) | Wide световая работа | Contained only |
| 6 | `SCL-04-YELLOW-PATTERNED-FIGURE` | [`10-01-56`](../media/stage-02c-shortlist/photo_2026-05-27_10-01-56.jpg) | Яркий самостоятельный объект | Workshop background; boundary decision |
| 7 | `INS-04-SEASONAL-STOREFRONT` | [`17-24-42`](../media/stage-02c-shortlist/photo_2026-05-26_17-24-42.jpg) | Контекст, масштаб, exterior | Только после Milk Bar decision |
| 8 | `SIG-01-MULTICOLOUR-NEON` | [`17-22-42`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-42.jpg) | Тёмный световой финал | Только после wording/mark decision |

Если branded frames 7–8 не утверждены, безопасный первый набор — первые 6 проектов. `INS-03`, `SIG-03` и `SIG-04` остаются gallery-first.

Ответ владельца — оставить 6 / 7 / 8 проектов: _______________________
Удалить/заменить: ____________________________________________________
Утверждённый порядок: ________________________________________________

## Covers трёх категорий

| Категория | Основное предложение | Резерв | Ответ владельца |
| --- | --- | --- | --- |
| `Об’ємні фігури та скульптури` | [White Flower `17-22-57`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-57.jpg) | [Red Tree `17-23-23`](../media/stage-02c-shortlist/photo_2026-05-26_17-23-23.jpg) | |
| `Фотозони, декорації та інсталяції` | [Bird Flock `17-23-00`](../media/stage-02c-shortlist/photo_2026-05-26_17-23-00.jpg) | [Illuminated Foliage `17-22-52`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-52.jpg) | |
| `Вивіски та брендовані об’єкти` | [Marquee Letters `17-22-47`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-47.jpg) | [Multicolour Neon `17-22-42`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-42.jpg), только после mark decision | |

## Изображения для страницы `Філософія`

Предлагаемый набор 2–4 изображений:

1. [White Flower `17-22-58`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-58.jpg) — finished form/detail;
2. [Illuminated Foliage `17-22-55`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-55.jpg) — light/detail;
3. [Bird Flock `17-23-01 (2)`](<../media/stage-02c-shortlist/photo_2026-05-26_17-23-01 (2).jpg>) — spatial construction;
4. [Red Tree `17-23-22`](../media/stage-02c-shortlist/photo_2026-05-26_17-23-22.jpg) — distinctive finished object.

Эти изображения не доказывают материал, гарантию, срок службы или production process.

Ответ владельца — номера изображений: ________________________________

## Изображение для `Контакти`

Основное предложение: [Bird Flock `17-23-00`](../media/stage-02c-shortlist/photo_2026-05-26_17-23-00.jpg) как спокойное contextual media.
Резерв: [White Flower `17-22-57`](../media/stage-02c-shortlist/photo_2026-05-26_17-22-57.jpg).
Workshop/location image сейчас отсутствует и запрошен отдельно.

Ответ владельца: BIRD FLOCK / WHITE FLOWER / НУЖНО ДРУГОЕ ИЗОБРАЖЕНИЕ

Комментарий:

______________________________________________________________________
