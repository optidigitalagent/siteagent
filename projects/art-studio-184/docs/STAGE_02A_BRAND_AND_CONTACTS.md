# Art Studio 184 — бренд, контакты и CTA

Дата подготовки: 2026-08-02
Основание: утверждённые документы этапов 0–1 и пакет этапа 2A. Этот документ не содержит финального копирайтинга.

## Brand identity

| Поле | Текущее значение | Статус | Источник | Требуемое действие |
| --- | --- | --- | --- | --- |
| Рабочее название проекта | `Art Studio 184` | `CONFIRMED` | Stage 00, разделы 1 и 11; Stage 01 Architecture | Не считать это подтверждением юридического или официального публичного написания |
| Официальное публичное написание | Не установлено | `NEEDS OWNER ANSWER` | Stage 01 Decisions, D1 | Владелец подтверждает регистр, порядок слов и допустимые языковые варианты |
| Основной публичный язык | Украинский | `CONFIRMED` | Stage 00, раздел 11; Stage 01 Architecture, принципы 9 | Сохранять во всех будущих публичных labels, H1 и CTA |
| Официальный логотип | Файл не предоставлен | `NEEDS EVIDENCE` | Stage 00, разделы 11–12; Stage 01 Decisions, D1 | Получить authorised original и подтверждение права использования |
| Варианты логотипа | Не установлены | `NEEDS OWNER ANSWER` | Stage 01 Decisions, D1 | Подтвердить основной, компактный, светлый, тёмный и монохромный варианты, если существуют |
| Текстовый знак `184 Art Studio` | Допустимость не установлена | `NEEDS OWNER ANSWER` | Пакет 2A, раздел 5A | Получить явное разрешение или запрет |
| Фирменный зелёный | Не установлен; `#00c8c0` из черновика не является доказательством | `BLOCKED FOR PUBLICATION` | Stage 00, строки 127–139; Stage 01 Decisions | Получить brand files/color study и подтверждение владельца |
| Тёмное визуальное направление | Очень тёмный фон, белый/серый текст, зелёный только как акцент | `CONFIRMED` | Stage 00, requirements matrix; Stage 01 переносит конкретную palette на следующий этап | Не превращать направление в готовую дизайн-систему |
| Запрещённые цвета | Не установлены | `NEEDS OWNER ANSWER` | Пакет 2A, раздел 5A | Владелец перечисляет ограничения |
| Слоган | Не установлен | `NEEDS OWNER ANSWER` | Stage 00, content audit | Подтвердить существующий слоган или отсутствие слогана; не создавать новый на 2A |
| Запрещённые формулировки | Частично зафиксированы в Stage 01; брендовые ограничения владельца неизвестны | `NEEDS OWNER ANSWER` | Stage 01 Decisions, раздел 7; анкета Q09 | Объединить ответ владельца с уже запрещёнными unsupported claims |

## Contact channels

| Канал | Значение | Публичный | Primary / Secondary | Статус |
| --- | --- | --- | --- | --- |
| Телефон | Не предоставлен | Нет | Не определено | `NEEDS OWNER ANSWER` |
| Email | Не предоставлен | Нет | Не определено | `NEEDS OWNER ANSWER` |
| Instagram | Не подтверждён официальный account | Нет | Не определено | `NEEDS OWNER ANSWER` |
| Telegram | Не предоставлен | Нет | Не определено | `NEEDS OWNER ANSWER` |
| Viber | Не предоставлен | Нет | Не определено | `NEEDS OWNER ANSWER` |
| WhatsApp | Не предоставлен | Нет | Не определено | `NEEDS OWNER ANSWER` |
| Город | Не установлен | Нет | Supporting information | `NEEDS OWNER ANSWER` |
| Точный адрес | Не установлен | Нет | Supporting information | `NEEDS OWNER ANSWER` |
| География заказов | Не установлена | Нет | Supporting information | `NEEDS OWNER ANSWER` |
| Доставка | Условия и география не установлены | Нет | Supporting information | `NEEDS OWNER ANSWER` |
| Монтаж | Исполнитель, условия и география не установлены | Нет | Supporting information | `NEEDS OWNER ANSWER` |
| График | Не установлен | Нет | Supporting information | `NEEDS OWNER ANSWER` |
| Получатель заявок | Не установлен | Внутреннее operational field | Primary owner | `NEEDS OWNER ANSWER` |

Ни один contact destination пока не может появиться как рабочая публичная ссылка. Пустые icons, `#`, придуманные handles и неподтверждённые адреса имеют статус `REJECTED`.

## CTA contract

### Рабочая формулировка

`Обговорити проєкт`

Статус: `PROVISIONAL`. Формулировка утверждена как архитектурный CTA на этапе 1, но пакет 2A требует оставить её предварительной до явного подтверждения владельца.

### Destination

| Элемент | Текущее состояние | Статус | Что закрывает статус |
| --- | --- | --- | --- |
| CTA на первых четырёх страницах | Архитектурно ведёт к `/contacts/` | `CONFIRMED` | Stage 01 Architecture и User Journey |
| Реальное действие на `/contacts/` | Канал не выбран | `BLOCKED FOR PUBLICATION` | Точный verified destination и owner confirmation |
| Primary contact channel | Не выбран | `NEEDS OWNER ANSWER` | Ответ на Q16/Q25 |

### Form

Архитектурно подтверждена одна минимальная форма только на `/contacts/`:

- `Ім’я` — required;
- `Контакт` — required;
- `Зручний спосіб зв’язку` — optional/conditional;
- `Коротко про проєкт` — optional.

| Form contract | Текущее состояние | Статус | Требуемое действие |
| --- | --- | --- | --- |
| Delivery mode | Не выбран: backend, Telegram-бот, email, CRM или verified redirect | `BLOCKED FOR PUBLICATION` | Выбрать режим и доказать его работу |
| Direct fallback | Не выбран | `BLOCKED FOR PUBLICATION` | Подтвердить телефон/email/messenger/Instagram |
| Error fallback | Не выбран | `BLOCKED FOR PUBLICATION` | Назначить verified direct channel; не терять введённые данные |
| Success state | Текст и доказанный результат не определены | `NEEDS OWNER ANSWER` | Утвердить сообщение, соответствующее реальному delivery mode |
| Personal-data consent | Не определено | `NEEDS OWNER ANSWER` | Решить необходимость и предоставить wording/source |
| Privacy controller/contact | Не установлены | `NEEDS EVIDENCE` | Предоставить business/legal data |
| Retention/processor | Не установлены | `NEEDS EVIDENCE` | Зафиксировать срок хранения и получателей данных |

Нельзя показывать `Повідомлення надіслано`, пока transport не подтвердил приём. Для redirect/copy fallback интерфейс сообщает только фактически выполненное действие.

## Сейчас заблокированы

- любой production CTA destination;
- отправка формы и success message;
- публичные contact links, location, hours и service geography;
- footer contact block;
- privacy policy и consent text;
- `Organization`/`LocalBusiness` contact/location fields;
- обещание срока ответа, расчёта стоимости или принятия заказа.

Эти блокировки не меняют утверждённую архитектуру пяти страниц; они запрещают выдумывать реализацию до получения ответов и доказательств.
