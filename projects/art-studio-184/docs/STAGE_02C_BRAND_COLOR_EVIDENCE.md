# Art Studio 184 — доказательство accent green

Дата: 2026-08-02
Статус: evidence fixation Stage 2C; design tokens и дизайн-система не создавались.

## Решение

Основной accent green:

`#00c8c0` — `CONFIRMED BY OWNER + VERIFIED IN PORTFOLIO SOURCE`.

Основание состоит из двух независимых частей:

1. владелец прямо указал взять точный зелёный с сайта портфолио (`STAGE_02B_OWNER_RESPONSES_AND_CODEX_TASK.md`, Q06);
2. commit-pinned source портфолио объявляет `--accent: #00c8c0`.

Это решение фиксирует цвет, но не разрешает создавать palette tokens, заливать им большие поверхности или начинать дизайн-систему.

## Source evidence

| Поле | Значение |
| --- | --- |
| Public URL | `https://optidigitalagent.github.io/porfolio/` |
| Repository | `https://github.com/optidigitalagent/porfolio` |
| Commit | `cfaf29892ed11abd5d30346bd3e2b8a02b5b2db5` |
| Commit-pinned source | `https://raw.githubusercontent.com/optidigitalagent/porfolio/cfaf29892ed11abd5d30346bd3e2b8a02b5b2db5/index.html` |
| `index.html` blob SHA | `4f58d0d2c1cf0ecf646f0f76f82843ba286b103e` |
| Declaration | `:root { --accent: #00c8c0; --accent2: #009e97; }` |
| Primary value | `#00c8c0` |
| Darker declared value | `#009e97` |

Live `index.html` и commit-pinned source были byte-identical: `79,300` bytes, SHA-256 `1d0a6c269ef78269eba2436b4067ff416df90eab460840ce6889caface12f9bf`.

## Consistency in portfolio CSS

`#00c8c0` объявлен один раз как `--accent` и используется через `var(--accent)` шесть раз в пяти правилах:

- `.page-header-label` — text color;
- `.category-number` — text color;
- `.category-number::after` — marker background;
- `.btn-main-site` — border и text color;
- `.btn-main-site:hover` — background.

Прямых конфликтующих primary-green literals в embedded CSS не найдено. Тёмный `#009e97` объявлен как `--accent2`, но `var(--accent2)` не используется ни разу. Поэтому он фиксируется только как существующий secondary/darker value и не утверждается основным.

## Comparison with current draft

Черновик `https://art-studio-184.funckj.chatgpt.site` загружает stylesheet `/assets/index-p7sVox8h.css`, где объявлено `--brand-green:#00c8c0`. Значение совпадает с портфолио.

Применение не совпадает с owner direction: draft использует green широко, включая `.page-hero` background и многочисленные headings. Portfolio source использует его существенно сдержаннее. Для следующего этапа действует правило владельца: зелёный — accent, не доминирующая заливка.

## Boundary

- `#00c8c0` можно считать закрытым brand input.
- `#009e97` можно анализировать как darker supporting value, но нельзя автоматически повышать до brand token.
- Официальный logo asset всё ещё отсутствует.
- Финальная palette, contrast pairs, states и color tokens относятся к отдельному design stage.
