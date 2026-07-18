# SiteAgent — Eliz material rebuild recovery handoff

Действуй как `$siteagent-project-director`.

Это новый Codex-чат. Не восстанавливай старую переписку и не начинай проект заново.

## Источники истины

Сначала прочитай:

- `AGENTS.md`
- весь `.codex/project_brain/`
- весь `.codex/workflow/`
- `.codex/workflow/FULL_SITE_PRODUCT_CORRECTION.md`
- `.codex/workflow/NEXT_ACTION.md`
- `.codex/handoffs/FULL_SITE_PRODUCT_CORRECTION_REPORT.md`
- локальный Git/worktree
- существующие `runs/`

Локальные `NEXT_ACTION.md` и `FULL_SITE_PRODUCT_CORRECTION_REPORT.md` имеют приоритет над старым remote checkpoint, если они новее и согласованы с artifacts/checksums.

## Текущий фактический статус

Финальный checkpoint `AUTONOMOUS_FULL_SITE_AGENT_READY_FOR_HUMAN_AUDIT` ещё не достигнут.

Уже сделано:

- Orange Beauty Studio и Bella Dent Clinic помечены:
  - `technical_status=accepted`
  - `product_status=rejected_by_human_audit`
  - `rejection_reason=incomplete_commercial_website`
- введён immutable `requested_product_type`;
- обычный business job по умолчанию больше не сжимается в `micro_site`;
- добавлен full-site completeness gate;
- добавлен независимый `ProductDirectorAuditor`;
- для Eliz de Fleur восстановлены blind inputs: 24 authorised photos и 2 authorised videos;
- создан rich research/design/implementation package;
- созданы три design concepts;
- выбран `Concept C`;
- созданы screenshots;
- первый full-site build был отклонён;
- recovery loop уже частично исправлен.

Текущий recoverable blocker Eliz:

1. четыре недоступных Cloudinary-изображения;
2. навигационные targets меньше 44 px;
3. material rebuild после этих findings ещё не завершён;
4. полный unittest suite, smoke build и final browser QA ещё не завершены;
5. финальные correction reports/commit/push ещё не завершены.

Последняя focused verification:

```text
53 focused tests passed
git diff --check passed
```

Production, Telegram и Cloudflare не запускались.

## Первая задача: crash-recovery audit

Сначала проверь:

- `git status --short`;
- staged / unstaged / untracked;
- `git log --oneline --decorate -20`;
- `git reflog -20`;
- local commits после remote HEAD;
- remote HEAD;
- merge/rebase/cherry-pick/lock state;
- `.codex/workflow/NEXT_ACTION.md`;
- `.codex/handoffs/FULL_SITE_PRODUCT_CORRECTION_REPORT.md`;
- Eliz run checkpoints;
- rich package checksums;
- Concept C artifacts;
- current selected source;
- current build output;
- screenshots;
- critic/ProductDirector reports;
- Cloudinary/media manifests;
- browser QA reports.

Не делать `git reset --hard`.
Не делать `git clean`.
Не удалять существующий Eliz run.
Не начинать research, media analysis, reference selection, design brief или concept generation заново, если artifacts/checksums валидны.

Если локальные изменения ещё не закоммичены, сначала создай безопасный recovery checkpoint commit после targeted validation. Не включай `.env`, секреты, browser profiles, caches или временные lock-файлы.

## Eliz recovery: исправить material blockers

Продолжить с выбранного `Concept C`.

### Недоступные Cloudinary assets

Для каждого из четырёх недоступных изображений:

- определить exact asset/public_id/URL;
- подтвердить, что asset принадлежит Eliz и authorised;
- проверить исходный local processed file;
- проверить Cloudinary credentials только как boolean presence, не печатая секреты;
- проверить существование asset через Cloudinary API или delivery request;
- если URL сформирован неверно — исправить генерацию URL;
- если asset отсутствует, но local authorised source существует — загрузить его повторно в правильную папку/public_id;
- если Cloudinary временно недоступен — использовать локальный authorised asset для calibration build, но не оставлять broken production reference;
- обновить media manifest, checksum и provenance;
- не использовать stock/reference/fixture media;
- не уменьшать full-site scope из-за broken URLs.

После исправления:

- broken images = 0;
- failed media requests = 0;
- каждый использованный asset присутствует в manifest;
- desktop/tablet/mobile renders используют доступные media.

### Tap/navigation targets

Исправить все interactive targets меньше 44×44 CSS px:

- desktop navigation;
- tablet navigation;
- mobile menu;
- language switch;
- filters;
- project controls;
- gallery controls;
- form controls;
- video controls;
- close/back buttons.

Допустимо увеличить clickable wrapper/padding при сохранении композиции.

Проверить keyboard focus, visible focus, no overlap, no overflow и no clipped controls.

## Material rebuild, а не косметический patch

После blockers выполнить полноценный material rebuild выбранного Concept C.

Сверить финальный сайт с rich product contract:

- `requested_product_type=full_commercial_site`;
- полноценная navigation;
- польский язык по умолчанию;
- английская версия;
- Home;
- Services;
- Portfolio;
- Contact;
- working form;
- meaningful About/Studio content;
- proof/media depth;
- полный conversion journey;
- no placeholders;
- no fake facts/reviews/clients;
- no silent scope shrink;
- все пригодные authorised photos/videos используются осмысленно;
- desktop/tablet/mobile имеют полноценную структуру.

Не засчитывать повторный CTA, декоративную панель или одну фотографию как отдельную meaningful section.

## Blind benchmark

Research Strategist, Design Director и Builder не должны использовать готовый manual Eliz baseline как design/layout/copy input.

После final autonomous build только независимый `ProductDirectorAuditor` сравнивает его с manual baseline:

```text
https://optidigitalagent.github.io/eliz-de-fleur-site-20260711095843/
```

Сравнение:

- product completeness;
- information architecture;
- services clarity;
- portfolio depth;
- media use;
- visual quality;
- mobile;
- PL/EN;
- navigation;
- contact/form;
- commercial journey;
- originality.

Новый autonomous result должен быть не слабее manual baseline.

Если слабее — выполнить material redesign/fixer cycle, а не принимать технически чистый, но продуктово слабый результат.

## Independent acceptance

`ProductDirectorAuditor` не должен видеть внутренние critic scores до своего решения.

Он обязан отклонить результат, если:

- это concept page вместо полноценного сайта;
- нет services coverage;
- нет proof/portfolio depth;
- нет conversion journey;
- нет работающей navigation;
- есть broken media;
- сайт заметно слабее manual benchmark;
- техническая чистота маскирует продуктовую неполноту.

Human gate остаётся включённым:

```text
CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true
```

## Required verification

После принятого material rebuild запусти:

1. focused recovery tests;
2. `python -m unittest discover -s tests -v`;
3. `python -m compileall -q site_agent scripts tests`;
4. `python -m pip check`;
5. `python scripts/smoke_build.py`;
6. final browser QA на desktop/tablet/mobile;
7. accessibility QA;
8. broken-link/media-request audit;
9. console error audit;
10. `git diff --check`;
11. secret scan.

## Required reports

Обнови/создай:

```text
.codex/handoffs/FULL_SITE_PRODUCT_CORRECTION_REPORT.md
.codex/handoffs/FULL_SITE_PRODUCT_CORRECTION_REPORT.json
```

Отчёты должны содержать:

- root cause;
- invalidated Orange/Bella acceptance;
- implemented product contracts;
- Eliz selected Concept C;
- четыре broken media assets и исправление каждого;
- tap-target fixes;
- final information architecture;
- media usage map;
- ProductDirector result;
- comparison with manual baseline;
- screenshots paths;
- all test results;
- unresolved blockers;
- external actions;
- final commits and HEAD SHA;
- next action;
- secret-safety confirmation.

Обнови `.codex/workflow/NEXT_ACTION.md`.

## Git safety and completion

После успешных проверок:

- commit валидные changes;
- push в `origin/main`;
- убедиться, что local HEAD = remote HEAD;
- не коммитить secrets;
- не запускать production publishing.

Не запускать:

- production `go`;
- Telegram delivery;
- Cloudflare publishing;
- customer production deployment.

Финальный checkpoint:

```text
AUTONOMOUS_FULL_SITE_AGENT_READY_FOR_HUMAN_AUDIT
```

Не останавливайся после исправления четырёх URLs или tap targets. Остановка допустима только на финальном checkpoint либо на доказанном внешнем blocker.

Не выключай компьютер до создания reports, commit и push.
