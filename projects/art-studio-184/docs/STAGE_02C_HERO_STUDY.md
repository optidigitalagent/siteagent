# Art Studio 184 — hero study Stage 2C

Дата: 2026-08-02
Статус: три provisional направления. Hero-код и финальный выбор не создавались.

## Общие ограничения

- В текущем наборе нет файла шире 1280 px; full-bleed retina desktop hero не поддержан.
- Первый meaningful viewport обязан содержать H1, краткое объяснение, `Обговорити проєкт` и переход к работам.
- Текст остаётся в отдельной safe zone; image overlay не должен быть единственным способом обеспечить контраст.
- Mobile показывает offer/CTA до того, как высокий portrait media вытеснит смысл из viewport.

## H1 — split hero с вертикальной световой формой

Используемые файлы:

- primary: `photo_2026-05-26_17-22-35.jpg` (`956×1280`);
- alternate/support: `photo_2026-05-26_17-22-41.jpg` (`755×1107`).

| Viewport | Crop/placement |
| --- | --- |
| Desktop | Image column 40–45%; contained `4:5`; сначала убрать нижний стол/провода, не обрезать dome и световой gradient. |
| Tablet | `3:4` contained image beside/after copy; не forcing square crop. |
| Mobile | Text, explanation и CTA first; image below in `4:5`; не использовать как full-viewport background. |

- Text safe zone: отдельная тёмная колонка, без overlay.
- Quality risk: `MEDIUM`; 956 px достаточно для contained column, недостаточно для full bleed.
- Performance: `GOOD`; один eager image, responsive derivatives позже.
- Accessibility: лучший reading order и самый надёжный contrast; visible wires не маскировать retouching-ом, только честно crop.
- Third-party risk: low; очевидный mark не найден.
- Recommendation: `VIABLE`, но не приоритет №1 из-за workshop clutter.

## H2 — composed three-image range

Используемые файлы:

- dominant: `photo_2026-05-26_17-22-57.jpg`;
- secondary: `photo_2026-05-26_17-23-00.jpg`;
- secondary: `photo_2026-05-26_17-22-42.jpg`.

| Viewport | Crop/placement |
| --- | --- |
| Desktop | Dominant flower `4:3`, bird/neon как меньшие `1:1`/`4:3` tiles; copy занимает отдельный dark region. |
| Tablet | Две media treatments; third tile уходит ниже first viewport. |
| Mobile | В первом viewport только dominant flower; secondary images после CTA. |

- Text safe zone: полностью отделена от collage.
- Quality risk: `LOW–MEDIUM`; все три files `1280×960`, но bird source сильно compressed.
- Performance: `MEDIUM`; только dominant mobile asset eager, остальные lazy; collage не должен грузить три LCP candidates.
- Accessibility: если adjacent copy уже объясняет диапазон, collage может быть decorative group; иначе alt описывает только видимые объекты.
- Third-party risk: neon wording требует individual mark review.
- Recommendation: `PREFERRED PROVISIONAL DIRECTION` — показывает диапазон без растягивания одного слабого изображения.

## H3 — contained wide contextual relief

Используемые файлы:

- desktop: `photo_2026-05-26_17-22-52.jpg` (`1280×656`);
- tablet alternate: `photo_2026-05-26_17-22-53.jpg` (`1280×960`);
- mobile/detail alternate: `photo_2026-05-26_17-22-55.jpg` (`1280×960`).

| Viewport | Crop/placement |
| --- | --- |
| Desktop | Сохранить исходный ~`1.95:1` frame внутри max-width container; не upscale выше source width. |
| Tablet | Использовать `4:3` alternate, а не вырезать центральную узкую полосу. |
| Mobile | Central `4:3` image ниже concise copy/CTA; `4:5` скрывает слишком много работы. |

- Text safe zone: над или рядом с image; white overlay на pale surface запрещён.
- Quality risk: `MEDIUM–HIGH` для большого desktop, так как 1280×656 и 87 KB.
- Performance: лучший из трёх вариантов.
- Accessibility: чистая композиция при separated text; detail alt не должен предполагать material.
- Third-party risk: очевидный mark не найден.
- Recommendation: `VIABLE AS CONTAINED HERO`, не full bleed; larger original нужен, если направление станет финальным.

## Decision

1. `H2` — preferred provisional direction.
2. `H1` — viable low-brand-risk fallback.
3. `H3` — viable only as contained contextual media.

Финальный hero не утверждён. Перед дизайном нужны owner grouping confirmation и asset-level rights/mark decisions; перед production — managed derivatives и crop QA на 1440/1024/768/390/360.
