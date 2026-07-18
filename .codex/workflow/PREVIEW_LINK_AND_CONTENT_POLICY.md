# SiteAgent — final product polish, preview-link delivery, and future revision-agent handoff

Действуй как `$siteagent-project-director`.

Это новое продуктовое решение после человеческого аудита Eliz de Fleur.

## Human decision

Eliz de Fleur Concept C принят как качественный полноценный коммерческий сайт.

Зафиксировать:

```text
human_product_audit=accepted_with_revisions
product_quality_calibration=true
strict_blind_benchmark=deferred
production_approved=false
```

Не проводить новый strict-blind run сейчас. Он может быть выполнен позже на другом бизнесе.

## Что оставить без изменений

Не менять текущую основную CTA-систему Eliz.

Не делать обязательными следующие замечания:

- не сокращать мобильное Portfolio только потому, что страница длинная;
- не подключать backend-отправку формы как обязательное условие для beta/preview;
- не требовать ручной проверки английской версии пользователем;
- не превращать About в сухую энциклопедическую страницу;
- не переписывать весь дизайн Concept C.

## Обязательная правка

Увеличить визуальную читаемость навигации в header/footer:

- текст не должен выглядеть как микроскопическая техническая подпись;
- active state должен быть заметен;
- footer links должны легко читаться на desktop/tablet/mobile;
- сохранить текущий editorial visual language;
- не увеличивать элементы грубо;
- clickable targets не меньше 44×44;
- проверить контраст, focus и mobile wrapping.

## Creative draft content policy

Пользователь разрешает AI самостоятельно дописывать творческий и демонстрационный контент, когда открытых данных бизнеса недостаточно.

Добавить provenance для каждого content field:

```text
verified_fact
inferred_brand_copy
generated_demo_content
missing_required_fact
```

AI разрешено создавать:

- слоганы;
- философию бренда;
- описания услуг;
- эмоциональный copywriting;
- объяснение процесса в общем виде;
- структуру страницы цен;
- названия пакетов;
- демонстрационные подписи;
- FAQ общего характера;
- CTA;
- placeholder-layout для будущего контента.

AI запрещено выдавать за подтверждённый факт:

- реальные цены;
- имена сотрудников;
- медицинские лицензии;
- годы работы;
- количество клиентов;
- рейтинги;
- реальные отзывы;
- гарантии;
- адреса;
- телефоны;
- сертификаты;
- результаты лечения;
- юридические условия.

### Цена / price page

Если для категории бизнеса страница цен ожидаема, но реальный прайс не найден:

Разрешено создать полноценный дизайн страницы или секции Price.

Безопасные варианты:

- `Wycena indywidualna`;
- `Cena zależy od zakresu projektu`;
- `Pakiet podstawowy — do uzupełnienia`;
- `Przykładowa struktura oferty`;
- `Zapytaj o aktualny cennik`.

Не вставлять выдуманные числовые цены как реальные цены компании.

Для internal preview можно показывать demo placeholder, но он должен иметь:

```text
content_status=generated_demo_content
production_publish_blocked=true
```

Перед production publish все factual demo placeholders должны быть подтверждены, заменены или безопасно переформулированы.

### About / philosophy

Разрешено творчески сформулировать brand philosophy на основании:

- визуального стиля;
- реальных услуг;
- публичного позиционирования;
- аудитории;
- реальных работ.

Не выдумывать биографию основателя, даты, цифры или события.

### Services

Разрешено расширять описания услуг category-aware copywriting, если направление услуги подтверждено.

Не добавлять неподтверждённую услугу как реально предоставляемую.

## Form contract

Для beta/preview-сайта форма может быть визуально и интерактивно полноценной без реального backend delivery.

Допустимые режимы:

```text
visual_demo
copy_to_clipboard
mailto
instagram_redirect
telegram_redirect
backend_delivery
```

Если backend не подключён:

- форма должна честно использовать один из fallback-режимов;
- не показывать ложное сообщение «заявка отправлена»;
- production report должен указать form mode.

## Preview-link delivery — обязательное новое поведение

Каждый успешно собранный сайт должен приходить пользователю со ссылкой.

Добавить отдельный безопасный Preview Publishing Contract.

### Preview — не production

Preview deployment:

- отдельный от customer production;
- уникальный URL для run/project;
- без custom domain клиента;
- `noindex, nofollow`;
- только authorised media;
- без секретов;
- без Telegram production delivery;
- без изменения customer production;
- может быть заменён новым preview после фиксов.

Предпочтительный transport:

```text
Cloudflare Pages preview/direct-upload preview project
```

Если Cloudflare preview недоступен, разрешён fallback:

```text
GitHub Pages preview repository
```

### Обязательный output успешного job

Финальный ответ должен содержать:

```text
preview_url
project_id
run_id
repository_or_artifact_path
desktop_screenshot_path
mobile_screenshot_path
form_mode
content_placeholders_count
production_blockers
next_action
```

Пользователь не должен открывать локальные папки, чтобы впервые увидеть сайт.

### Human audit flow

```text
site generated
→ tests passed
→ preview published
→ preview URL returned
→ human reviews URL
→ user sends fixes or approves
→ only then optional production publish
```

## Текущий Eliz task

1. Исправить только читаемость header/footer navigation.
2. CTA не менять.
3. Не перестраивать Concept C.
4. Перезапустить focused visual/browser QA.
5. Создать preview deployment Eliz.
6. Добавить `noindex,nofollow`.
7. Вернуть preview URL.
8. Не запускать customer production deployment.
9. Обновить human-audit report и `NEXT_ACTION.md`.
10. Commit и push changes.

## Acceptance for this task

Завершить, когда:

- footer/header navigation читаема;
- CTA сохранена;
- current Eliz design не ухудшен;
- desktop/tablet/mobile QA прошли;
- preview URL реально открывается HTTP 200;
- preview содержит все пять страниц;
- PL/EN, navigation, filters и form fallback работают;
- noindex/nofollow подтверждены;
- production не запускался;
- final response содержит прямую ссылку.

Финальный checkpoint:

```text
ELIZ_PREVIEW_READY_FOR_USER_REVIEW
```

## Future phase — Site Revision Agent

Сейчас не реализовывать полностью, но зафиксировать в Project Brain и roadmap будущий отдельный агент:

```text
SiteRevisionAgent
```

Назначение:

- пользователь выбирает существующий project;
- пишет ТЗ обычным сообщением;
- агент читает project context;
- изменяет текущий сайт;
- не создаёт новый сайт с нуля;
- сохраняет дизайн-систему и бизнес-контекст;
- запускает tests и visual QA;
- создаёт новую preview-ссылку;
- после одобрения обновляет production.

Каждый site project должен позже хранить:

```text
project_id
business_id
repository
current_production_url
current_preview_url
design_system
business_research
media_manifest
content_provenance
deployment_provider
change_history
human_decisions
```

Будущий workflow:

```text
open project
→ user gives change request
→ impact analysis
→ implementation
→ tests
→ preview URL
→ user approval
→ production update
```

Не смешивать SiteRevisionAgent с текущим new-site generation pipeline.

## External actions

Разрешён только preview deployment.

Не запускать:

- customer production deployment;
- production `go`;
- Telegram customer delivery;
- изменение custom domain.

Не выключать компьютер до commit/push и проверки preview URL.
