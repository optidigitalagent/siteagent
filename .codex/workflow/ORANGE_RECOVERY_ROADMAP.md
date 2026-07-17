# SiteAgent — new chat recovery roadmap

Действуй как `$siteagent-project-director`.

Это новый чат. Не пытайся восстановить старую переписку. Источники истины:

- `AGENTS.md`
- `.codex/project_brain/`
- `.codex/workflow/`
- `.codex/workflow/MANUAL_WORKFLOW_REBUILD.md`
- локальный Git/worktree
- существующие `runs/`

## Текущая сохранённая база

Последний подтверждённый remote commit:

```text
01d0f99ddb3e169d958bf37791f4ebbe9d5295c2
Add autonomous reference discovery and curation
```

До этого реализовано:

1. Новый manual-equivalent workflow:

```text
Instagram URL
→ Research Strategist
→ authorized real-media preparation / Cloudinary
→ Reference selection
→ Design Director
→ immutable implementation package
→ Codex Web Studio
→ screenshot-led critics
→ material fixer
→ acceptance / recovery / optional publishing
```

2. Роли разделены:

- Research Strategist — OpenAI
- Reference Analyst — OpenAI
- Design Director — OpenAI
- Site Builder / Fixer — Codex

3. Реализованы:

- readable `business_research.md/json`;
- readable `design_implementation_brief.md/json`;
- prompt/provider/model/checksum provenance;
- non-destructive Instagram crop;
- crop confidence и manual-review state;
- dedupe и contact sheets;
- reuse подтверждённых Cloudinary assets;
- обязательные `user_authorized=true`;
- обязательные `allowed_for_public_site=true`;
- запрет stock/fixture/reference media как business portfolio;
- immutable implementation package;
- recovery/checkpoints;
- browser QA;
- accessibility;
- Cloudflare/Telegram contracts без их запуска в calibrations.

4. Reference system:

- screenshot-led analysis;
- autonomous discovery;
- Reference Curator;
- independent Reference Auditor;
- 32 active references;
- 8 excluded references;
- решения отделены от raw captures;
- случайный `human_review_decisions.json` признан недействительным historical input;
- reference selection идёт по transferable traits, не по категории бизнеса.

5. Последняя подтверждённая проверка на commit `01d0f99`:

```text
114 tests passed
1 opt-in Cloudflare smoke skipped
```

## Текущее локальное состояние, которое нужно восстановить

Работа после `01d0f99` не завершена и, вероятно, находится только локально.

Orange Beauty Studio:

```text
runs/orange-beauty-studio-calibration
```

Фактический статус:

- Orange calibration начата;
- research/media/reference/design/build artifacts могли уже быть созданы;
- процесс остановился на recoverable конфликте `scope/critic`;
- scope определил Orange как `Level B micro-site`;
- critic/commercial review оценили его как full-site и потребовали лишние full-site элементы;
- Orange не завершена;
- Bella Dent Clinic не запускалась;
- commit/push изменений после этой работы не выполнены;
- финальные handoff-отчёты не созданы.

## Первая задача: crash-recovery audit

Сначала проверь:

- `git status`;
- staged / unstaged / untracked;
- `git log`;
- `git reflog`;
- local commits после `01d0f99`;
- merge/rebase/cherry-pick/lock state;
- `.codex/workflow/*`;
- все checkpoints Orange;
- `runs/orange-beauty-studio-calibration/`;
- research;
- authorized media manifest;
- selected references и rationale;
- design brief;
- implementation package и checksum;
- source/staging/promoted HTML;
- screenshots;
- critic/commercial reports;
- fixer history;
- technical reports.

Не удаляй run и не начинай Orange заново.

Повторно используй все checksum-valid artifacts.

## Исправление scope-aware reviews

Исправь critic/commercial contracts так, чтобы они оценивали сайт относительно утверждённого scope.

### Level B micro-site — это завершённый компактный продукт

Он обязан иметь:

- ясное название бизнеса и точный подтверждённый оффер;
- конкретный CTA в первом desktop/mobile viewport;
- реальные authorized business media;
- компактный путь: offer → работы/media → подтверждённый процесс/преимущество → запись;
- намеренную композицию;
- полноценный mobile;
- отсутствие fake facts, fake reviews, fake staff, fake prices и неподтверждённых услуг.

Он не должен автоматически получать штраф за отсутствие:

- большой команды;
- отзывов;
- сертификатов;
- полного прайса;
- FAQ;
- длинного процесса;
- множества trust-секций;
- пяти и более секций;
- любых данных, которых нет в research.

Critic должен блокировать слабый или незавершённый micro-site, но не требовать превращения Level B в искусственно растянутый full-site.

### Scope levels

Зафиксируй отдельные критерии минимум для:

- `Level A / full_site`;
- `Level B / micro_site`;
- `blocked / insufficient evidence`.

Нельзя понижать общий quality bar. Нужно исправить несоответствие критериев scope, а не автоматически одобрить Orange.

Добавь tests для:

- хороший Level B проходит;
- обрезанный/слабый Level B не проходит;
- Level B не требует full-site-only секции;
- Level A продолжает требовать полный коммерческий путь;
- unsupported proof остаётся blocker;
- scope нельзя самовольно повысить ради прохождения critic.

## Затем возобновить Orange

После исправления contracts:

1. Возобнови существующий Orange run с первого незавершённого checkpoint.
2. Не повторяй успешные expensive stages без необходимости.
3. Проведи scope-aware critic/commercial review.
4. Выполни material fixer по реальным findings.
5. Повтори desktop/tablet/mobile screenshots.
6. Проверь:
   - offer clarity;
   - real-media usage;
   - CTA;
   - business fit;
   - visual quality;
   - mobile;
   - accessibility;
   - no reference copying;
   - no old-site copying;
   - no category-template behavior.
7. Заверши Orange calibration evidence.

## Затем Bella Dent Clinic

Только после завершённой Orange:

1. Запусти Bella Dent Clinic по новому workflow.
2. Используй только authorized real business media.
3. Не используй старый Bella site как design/layout/copy input.
4. Старый сайт разрешён только для:
   - media provenance;
   - подтверждения business facts;
   - blind comparison после новой генерации.
5. Визуальный язык Bella должен быть независимо создан и не повторять Orange.
6. Проведи полный critic/fixer cycle и calibration evidence.

## Автономность

Пользователя не подключать к routine решениям.

Самостоятельно:

- исправляй код;
- возобновляй checkpoints;
- перезапускай failed stages;
- запускай tests;
- выполняй material revisions;
- commit/push после успешных проверок.

Спрашивать пользователя только при реальном внешнем blocker:

- нет прав на конкретные media;
- отсутствуют credentials/account access;
- подтверждённые бизнес-факты противоречат друг другу и меняют оффер;
- требуется необратимое внешнее действие.

Не показывай и не записывай `.env` или секреты.

## Запрещённые внешние действия

Во время Orange/Bella calibrations не запускать:

- `go`;
- Telegram delivery;
- Cloudflare publishing;
- production publishing.

`CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true` оставить включённым.

Human gate не должна останавливать routine internal stages. Она применяется только к финальному product-level audit.

## Финальное завершение

После Orange и Bella:

1. Запусти:
   - полный unittest suite;
   - compileall;
   - pip check;
   - smoke build;
   - browser QA;
   - `git diff --check`.

2. Создай:

```text
.codex/handoffs/AUTONOMOUS_SITEAGENT_FINAL_REPORT.md
.codex/handoffs/AUTONOMOUS_SITEAGENT_FINAL_REPORT.json
```

3. Отчёты должны содержать:

- итоговую архитектуру;
- final checkpoint;
- commits и HEAD SHA;
- active/excluded references;
- Orange results;
- Bella results;
- media manifests;
- research/design briefs;
- implementation packages;
- screenshots;
- critic/fixer history;
- tests;
- unresolved blockers;
- external actions;
- точные artifact paths;
- точное следующее действие;
- подтверждение отсутствия секретов.

4. Обнови `.codex/workflow/NEXT_ACTION.md`.

5. Commit и push валидные изменения в `origin/main`.

6. Проверь, что remote HEAD совпадает с local HEAD.

Финальный checkpoint:

```text
AUTONOMOUS_SITEAGENT_READY_FOR_FINAL_PRODUCT_AUDIT
```

Не выключай компьютер до создания, проверки, commit и push финальных отчётов.
