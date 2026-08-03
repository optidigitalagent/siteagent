# Art Studio 184 — ключевые решения владельца, Stage 2E

Дата: 2026-08-03

Статус: `OWNER DECISIONS LOCKED`; разрешён переход к Stage 3A, но не к коду или публикации.

Этот документ фиксирует решения для начала visual direction и design system planning. Он не меняет подтверждённые факты Stages 0–2D и не является разрешением на создание сайта, production-код или публикацию.

## 1. Hero

- Provisional choice: `H2`.
- Состав: `White Flower + Bird Flock + Multicolour Neon`.
- Статус: `APPROVED FOR DESIGN EXPLORATION, NOT FINAL FOR PUBLICATION`.
- В Stage 3A можно исследовать desktop/tablet/mobile композицию H2 с отдельной text safe zone и одним eager dominant image.
- Финальное media assignment, crop, focal points, mark visibility и responsive QA остаются открытыми до Stage 3B и публикации.

## 2. Featured projects

- Для первой версии дизайна использовать shortlist из 12 проектов Stage 2C: `4 + 4 + 4` по трём утверждённым категориям.
- Нерешённые группы за пределами shortlist не блокируют первую дизайн-итерацию.
- Internal English labels не становятся публичными названиями автоматически.
- Public UA names, project boundaries, frame order, factual captions и индивидуальные решения по видимым сторонним брендам остаются ограничениями для production-кода и публикации.
- Нельзя выводить из изображений client relationship, material, size, date, location или result.

## 3. Logo

- Владелец предоставил исходное изображение логотипа:
  `projects/art-studio-184/references/brand/ART184_OWNER_LOGO_SOURCE.png`.
- Это raster PNG source (`1920×1080`), а не финальный production-ready logo package.
- Позже допустимы только crop, удаление окружающего пустого поля, centering cleanup и визуальная калибровка без изменения самого знака.
- Логотип не редизайнить, не перерисовывать и не перекрашивать без отдельного решения владельца.
- Не создавать alternate marks. Текстовый знак `Art Studio 184` больше не считать основной временной заменой при наличии owner logo source.
- Master source должен оставаться неизменным; производные создаются отдельно на следующем разрешённом этапе.

## 4. Team section

- Использовать графические карточки Максима и Люды без вымышленных или сгенерированных лиц.
- Подтверждённый background секции сохраняется.
- Реальные фото команды не обязательны для Stage 3A.
- Графические карточки не должны имитировать реальные портреты или documentary proof.

## 5. Страница «Виробничі можливості»

- Страница входит в первую версию сайта.
- Первая версия должна быть честной и high-level.
- Модели станков и точные технические характеристики не требуются.
- Допустимы только подтверждённые Stage 2B общие смыслы: у мастерской есть сильные производственные возможности, профессиональное оборудование и приоритет качественного результата.
- Запрещены неподтверждённые цифры, размеры, capacity, допуски, скорость, производительность, бренды оборудования, гарантии, material properties и обещания `усе робимо самі`.
- Готовые проекты нельзя выдавать за документальное фото конкретного оборудования или процесса.

## 6. Форма

- Design и code contract должны предусматривать реальную отправку заявки в Telegram.
- До готовности backend дизайн обязан включать честные loading, success, error и fallback states.
- Production не может показывать успешную отправку без доказанного приёма заявки backend-ом.
- Рабочий Telegram backend, privacy/controller details, реальная policy и end-to-end success/error evidence обязательны до publication.
- Прямая ссылка `@liu_ryb` остаётся подтверждённым error fallback, но не заменяет backend, если на production показывается форма отправки.

## 7. Intentionally deferred

- модели и точные характеристики станков;
- точный legal/privacy copy;
- client permissions matrix вне выбранных для публикации assets;
- полный project-by-project fact sheet;
- полная equipment gallery;
- полный production media pack.

Отложенные данные не становятся темой страницы и не заменяются placeholder-фактами, fake proof или расширенными неподтверждёнными claims.

## Decision matrix

| Decision | Status | Blocks Design? | Blocks Code? | Blocks Publication? |
| --- | --- | --- | --- | --- |
| Hero H2 | `APPROVED FOR DESIGN EXPLORATION, NOT FINAL FOR PUBLICATION` | Нет | Да, до final assignment/crop contract | Да |
| Stage 2C shortlist из 12 проектов | `APPROVED FOR FIRST DESIGN ITERATION` | Нет | Да, пока не закрыты first-release metadata и выбранные brand decisions | Да для unresolved rendered assets |
| Owner logo raster source | `AVAILABLE WITH LIMITATIONS` | Нет для Stage 3A | Да, до final cropped/centred package | Да |
| Графические team cards | `APPROVED FOR STAGE 3A` | Нет | Нет в утверждённой non-anthropomorphic форме | Нет сами по себе |
| High-level capabilities page | `APPROVED WITH CLAIM LIMITS` | Нет | Нет в подтверждённой high-level форме | Нет, если все claims остаются source-bound |
| Telegram form UX | `APPROVED AS REAL-DELIVERY CONTRACT` | Нет | Да, до backend/privacy contract | Да |
| Deferred production detail | `DEFERRED` | Нет | Только если соответствующая функция включена | Да, если неподтверждённые детали попадают в public output |
