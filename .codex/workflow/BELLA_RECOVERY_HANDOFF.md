# SiteAgent — Bella recovery handoff for a new Codex chat

Действуй как `$siteagent-project-director`.

Это новый чат. Не восстанавливай старую переписку и не трать контекст на её пересказ.

Источники истины:

- `AGENTS.md`
- `.codex/project_brain/`
- `.codex/workflow/`
- `.codex/workflow/MANUAL_WORKFLOW_REBUILD.md`
- `.codex/workflow/ORANGE_RECOVERY_ROADMAP.md`
- локальный Git/worktree
- существующие `runs/`

## Текущий фактический статус

### Orange Beauty Studio

Orange recovery завершена и принята как no-publish Level B micro-site calibration.

Подтверждённые результаты:

- scope-aware reviews различают:
  - full site;
  - micro-site;
  - blocked evidence;
- fresh desktop/tablet/mobile QA passed;
- commercial gate: `100`;
- independent review: `91`;
- acceptance audit passed;
- mobile proof-media capture issue исправлен в inspector;
- production publishing не запускался;
- Telegram delivery не запускался;
- Cloudflare publishing не запускался.

Orange не переделывать и не запускать заново.

Использовать её artifacts только как завершённую calibration evidence.

### Bella Dent Clinic

Существующий run:

```text
runs/bella-dent-clinic-calibration
```

Уже созданы и должны быть повторно использованы при валидных checksums:

- business research;
- authorised-media manifest;
- selected references;
- reference rationale;
- design implementation brief;
- immutable implementation package.

Bella остановлена до Studio concept generation.

Причина остановки:

- strategist определил `micro_site`;
- generic media counter попытался повысить scope до `full_site`;
- это недопустимое downstream scope escalation;
- resolver и next-action checkpoint уже должны сохранять более ограничительный scope.

Текущий checkpoint:

```text
BELLA_CALIBRATION_SCOPE_RESOLUTION_RECOVERABLE
```

## Первая задача нового чата

Проведи crash-recovery audit:

- `git status`;
- staged / unstaged / untracked;
- `git log`;
- `git reflog`;
- local commits;
- remote HEAD;
- merge/rebase/cherry-pick/lock state;
- `.codex/workflow/NEXT_ACTION.md`;
- Orange completion artifacts;
- Bella checkpoints и package checksums.

Не удаляй runs.
Не начинай Orange или Bella заново.
Не повторяй успешные expensive stages без доказанной необходимости.

## Сначала сохранить уже сделанную работу

Если локальные изменения после последнего remote commit ещё не закоммичены:

1. Проверь targeted tests для:
   - scope-aware critic;
   - scope-aware commercial review;
   - scope resolver;
   - inspector mobile proof-media capture;
   - Orange acceptance.

2. Удали из commit только:
   - секреты;
   - `.env`;
   - временные browser profiles;
   - lock-файлы процессов;
   - непреднамеренные cache artifacts.

3. Создай checkpoint commit, включающий:
   - scope-aware review;
   - scope resolver;
   - Orange completion evidence;
   - обновлённый `NEXT_ACTION.md`.

4. Push в `origin/main`.

5. Убедись, что local HEAD совпадает с remote HEAD.

Если checkpoint commit уже существует локально или удалённо, не создавай дубликат.

## Неизменяемое правило scope

Утверждённый scope не может быть повышен обычным downstream heuristics.

Допустимые переходы:

- сохранить текущий scope;
- понизить до `blocked`, если evidence недостаточно;
- повысить только при:
  - новом подтверждённом evidence;
  - явном повторном strategist resolution;
  - записанном rationale.

Количество media само по себе не повышает `micro_site` до `full_site`.

## Возобновление Bella

После recovery:

1. Возобнови:

```text
runs/bella-dent-clinic-calibration
```

2. Продолжи строго с:

```text
Studio concept generation
```

3. Используй:

```text
one concept
Level B micro-site
```

4. Не регенерируй research/media/references/design/package, если они валидны.

5. Не используй существующий сайт Bella как:
   - design input;
   - layout input;
   - copy input;
   - structure input.

Существующий Bella site разрешён только для:

- подтверждения business facts;
- media provenance;
- blind comparison после новой генерации.

6. Используй только:

- `source_kind=business`;
- `user_authorized=true`;
- `allowed_for_public_site=true`;
- подтверждённые реальные media.

Не использовать:

- stock;
- fixture media;
- reference media;
- чужое portfolio media;
- неподтверждённые assets.

## Bella Level B quality contract

Bella micro-site обязан быть полноценным компактным коммерческим продуктом.

Обязательно:

- ясный business identity;
- подтверждённый dental offer;
- понятный CTA в первом desktop/mobile viewport;
- реальные клинические/командные/интерьерные media только при наличии прав;
- компактный conversion path;
- trust без выдуманных proof;
- завершённая композиция;
- полноценный mobile;
- accessibility;
- отсутствие fake facts.

Нельзя автоматически требовать:

- большую команду;
- отзывы;
- сертификаты;
- полный прайс;
- FAQ;
- длинный процесс;
- лишние секции;
- неподтверждённые clinical claims.

Но нельзя и автоматически принимать слабый micro-site.

Critics должны проверять:

- clarity;
- trust;
- commercial logic;
- CTA;
- real-media use;
- visual quality;
- responsive quality;
- accessibility;
- business fit;
- anti-copy;
- absence of unsupported claims.

## Полный Bella cycle

Выполни:

1. one-concept generation;
2. concept validation;
3. implementation;
4. desktop/tablet/mobile screenshots;
5. scope-aware commercial review;
6. independent critics;
7. material fixer;
8. повторные screenshots;
9. accessibility QA;
10. browser QA;
11. media provenance audit;
12. anti-copy audit;
13. no-old-site-copy audit;
14. no-Orange-copy audit;
15. final acceptance evidence.

## Автономность

Пользователя не подключать к routine решениям.

Самостоятельно:

- исправляй код;
- возобновляй checkpoints;
- выполняй retries;
- запускай tests;
- делай material revisions;
- создавай commits;
- push валидных изменений.

Можно остановиться только при доказанном внешнем blocker:

- отсутствуют права на конкретные media;
- отсутствуют credentials/account access;
- подтверждённые факты противоречат друг другу и меняют offer;
- требуется необратимое внешнее действие.

При blocker показать:

- точную причину;
- что уже сделано;
- что испробовано;
- минимальное действие пользователя.

Не показывай и не записывай секреты или содержимое `.env`.

## Запрещённые внешние действия

Во время Bella calibration не запускать:

- `go`;
- Telegram delivery;
- Cloudflare publishing;
- production publishing.

`CREATIVE_STUDIO_HUMAN_CALIBRATION_REQUIRED=true` оставить включённым.

Human gate применяется только к финальному product-level audit, а не к routine internal stages.

## Финальное завершение всего SiteAgent

После принятия Bella:

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

- финальную архитектуру;
- checkpoint;
- commits;
- final HEAD SHA;
- active/excluded reference counts;
- Orange result;
- Bella result;
- media manifests;
- research;
- design briefs;
- implementation packages;
- screenshots;
- critic/fixer history;
- acceptance reports;
- tests;
- unresolved blockers;
- external actions;
- точные artifact paths;
- next action;
- secret-safety confirmation.

4. Обнови:

```text
.codex/workflow/NEXT_ACTION.md
```

5. Commit и push валидные изменения в `origin/main`.

6. Проверь совпадение local и remote HEAD.

Финальный checkpoint:

```text
AUTONOMOUS_SITEAGENT_READY_FOR_FINAL_PRODUCT_AUDIT
```

В самом последнем ответе выведи:

- checkpoint;
- final commit SHA;
- путь к Markdown report;
- путь к JSON report;
- итоги tests;
- итоги Orange;
- итоги Bella;
- точное следующее действие.

Не выключай компьютер до создания, проверки, commit и push финальных отчётов.
