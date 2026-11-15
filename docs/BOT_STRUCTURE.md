# 🗺 Структура бота Prizm Quest

## 📁 Файлы проекта

| Файл | Назначение |
|------|-----------|
| `bot.py` | Основная логика бота, обработчики команд и кнопок |
| `db.py` | Работа с базой данных (SQLite) |
| `keyboards.py` | Все клавиатуры (кнопки) |
| `texts.py` | Все текстовые сообщения |
| `config.py` | Конфигурация (токен, пути) |
| `.env` | Секретные ключи (не коммитится!) |

---

##  Пользовательский флоу (пошагово)

### Шаг 1: Пользователь пишет `/start`

**Что видит:** Капча (математический пример с 3 кнопками)

**Код:**
- `bot.py` → функция `start()` (строка ~183)
- Проверяет `captcha_passed` в БД
- Если `0` → вызывает `send_captcha()`
- Если `1` → показывает `WELCOME_TEXT`

**База данных:**
- Таблица `users`, поле `captcha_passed` (0 или 1)

---

### Шаг 2: Пользователь решает капчу

**Что видит:** 
- Правильный ответ → приветственное сообщение `WELCOME_TEXT` с кнопками
- Неправильный → "Неверно, попробуй ещё раз" + новый пример

**Код:**
- `bot.py` → функция `handle_captcha()` (строка ~1262)
- `db.py` → функция `set_captcha_passed()` (строка ~208)
- `keyboards.py` → функция `captcha_kb()` (кнопки с вариантами)
- `texts.py` → `CAPTCHA_TEXT`, `CAPTCHA_FAIL_TEXT`

**Логика:**
- Callback data: `captcha:ok:{ответ}` или `captcha:fail:{ответ}`
- При правильном ответе: `captcha_passed = 1` в БД

---

### Шаг 3: Пользователь видит приветствие

**Что видит:** 
- Текст `WELCOME_TEXT` (о боте, кристаллах, квесте)
- Кнопки: "🎁 Получить награду" и "ℹ️ Помощь"

**Код:**
- `bot.py` → функция `start()` показывает `WELCOME_TEXT`
- `keyboards.py` → функция `welcome_kb()` (кнопки)
- `texts.py` → `WELCOME_TEXT`

**Важно:** Кнопка "Получить награду" всегда видна, даже если бонус уже получен.

---

### Шаг 4: Пользователь нажимает "Получить награду"

**Что видит:**
- Если бонус не получен → "Поздравляем! +10 Prizm" → сообщение про закрепление бота `PIN_BOT_TEXT`
- Если уже получил → "Вы уже получили приветственный бонус!"

**Код:**
- `bot.py` → функция `claim_bonus()` (строка ~427)
- `db.py` → функции `add_crystals()` и `mark_welcome_bonus_claimed()`
- `keyboards.py` → функция `pin_bot_kb()` (кнопки "Готово" и "Инструкция")
- `texts.py` → `PIN_BOT_TEXT`

**База данных:**
- Таблица `users`, поле `welcome_bonus_claimed` (0 или 1)
- Таблица `crystals_ledger` (история начислений)

---

### Шаг 5: Пользователь закрепляет бота

**Что видит:**
- Сообщение `PIN_BOT_TEXT` с двумя кнопками: "✅ Готово" и "🛠 Инструкция"
- При нажатии "Инструкция" → текст `PIN_INSTRUCTION_TEXT` с одной кнопкой "✅ Отлично"

**Код:**
- `bot.py` → функции `show_pin_instruction()` и `pin_done()`
- `keyboards.py` → функции `pin_bot_kb()` и `pin_done_kb()`
- `texts.py` → `PIN_BOT_TEXT`, `PIN_INSTRUCTION_TEXT`

---

### Шаг 6: После закрепления → информация о Daily Bonus

**Что видит:**
- Текст `DAILY_BONUS_INTRO_TEXT` (о ежедневных наградах)
- Кнопка "🏠 Главное меню"

**Код:**
- `bot.py` → функция `pin_done()` показывает `DAILY_BONUS_INTRO_TEXT`
- `keyboards.py` → функция `daily_bonus_instruction_kb()`
- `texts.py` → `DAILY_BONUS_INTRO_TEXT`

---

### Шаг 7: Пользователь в главном меню

**Что видит:**
- Текст `MAIN_MENU_TEXT`
- Кнопки: Квест, Факты, Игры, Бейджи, Daily Bonus, Финальный тест, Помощь

**Код:**
- `bot.py` → функция `main_menu()` (обработчик `menu:*`)
- `keyboards.py` → функция `main_menu_kb()`
- `texts.py` → `MAIN_MENU_TEXT`

---

### Шаг 8: Daily Bonus

**Что видит:**
- Если можно получить → текст `DAILY_BONUS_MENU_TEXT` + кнопка "✅ Забрать награду!"
- Если уже получил → "⏰ Вы уже получили Daily Bonus! Следующий через: Xч Yмин"

**Код:**
- `bot.py` → обработчик `menu:daily_bonus` и функция `claim_daily_bonus_handler()`
- `db.py` → функции `can_claim_daily_bonus()` и `claim_daily_bonus()`
- `keyboards.py` → функции `daily_bonus_claim_kb()` и `daily_bonus_wait_kb()`
- `texts.py` → `DAILY_BONUS_MENU_TEXT`, `DAILY_BONUS_RECEIVED_TEXT`

**Логика:**
- Бонус доступен раз в сутки (сброс в 00:00)
- Streak увеличивается, если не пропускать дни
- Начисляется 1 кристалл

---

##  Команды бота

| Команда | Описание | Функция в bot.py |
|---------|----------|------------------|
| `/start` | Начать заново | `start()` |
| `/menu` | Главное меню | `menu_command()` |
| `/help` | Справка | `help_command()` |
| `/profile` | Профиль и баланс | `profile()` |
| `/test` | Финальный тест | `test_command()` |
| `/reset` | Сброс прогресса | `reset_progress()` |
| `/admin_reset <tg_id>` | Админский сброс | `admin_reset()` |

---

## 🗃 База данных (таблица `users`)

| Поле | Тип | Описание |
|------|-----|----------|
| `tg_id` | INTEGER | Telegram ID пользователя (уникальный) |
| `username` | TEXT | Username в Telegram |
| `first_name` | TEXT | Имя пользователя |
| `level` | TEXT | Уровень: 'newbie' или 'known' |
| `state` | TEXT | Текущее состояние бота |
| `crystals` | INTEGER | Баланс кристаллов |
| `captcha_passed` | INTEGER | 0 = не пройдена, 1 = пройдена |
| `welcome_bonus_claimed` | INTEGER | 0 = не получен, 1 = получен |
| `daily_bonus_streak` | INTEGER | Серия ежедневных бонусов (дни подряд) |
| `last_daily_bonus` | TEXT | Дата последнего получения Daily Bonus |
| `final_test_passed` | INTEGER | 0 = не пройден, 1 = пройден |
| `prizm_address` | TEXT | Адрес кошелька PRIZM |
| `invited_by` | INTEGER | TG ID пригласившего (реферал) |
| `referral_code` | TEXT | Реферальный код пользователя |
| `referrals_count` | INTEGER | Количество приглашённых |

---

## 🔄 Callback Data (кнопки)

| Callback | Действие | Обработчик в bot.py |
|----------|----------|---------------------|
| `captcha:ok:{число}` | Правильный ответ на капчу | `handle_captcha()` |
| `captcha:fail:{число}` | Неправильный ответ | `handle_captcha()` |
| `bonus:claim` | Получить приветственный бонус | `claim_bonus()` |
| `pin:done` | Закрепил бота | `pin_done()` |
| `pin:instruction` | Показать инструкцию | `show_pin_instruction()` |
| `menu:home` | Главное меню | `main_menu()` |
| `menu:daily_bonus` | Раздел Daily Bonus | `main_menu()` |
| `menu:help` | Справка | `main_menu()` |
| `bonus:claim_daily` | Забрать Daily Bonus | `claim_daily_bonus_handler()` |

---

## 📝 Тексты (файл texts.py)

| Константа | Где используется |
|-----------|------------------|
| `DISCLAIMER` | Старое приветствие (больше не используется) |
| `WELCOME_TEXT` | Приветствие после капчи |
| `CAPTCHA_TEXT` | Текст капчи |
| `CAPTCHA_FAIL_TEXT` | Ошибка в капче |
| `PIN_BOT_TEXT` | Сообщение про закрепление бота |
| `PIN_INSTRUCTION_TEXT` | Инструкция по закреплению |
| `DAILY_BONUS_INTRO_TEXT` | Введение в Daily Bonus (после закрепления) |
| `DAILY_BONUS_MENU_TEXT` | Текст в разделе Daily Bonus |
| `DAILY_BONUS_RECEIVED_TEXT` | После получения Daily Bonus |
| `MAIN_MENU_TEXT` | Текст главного меню |
| `HELP_TEXT` | Текст справки |

---

##  Важные правила

1. **Всегда проверяй дубликаты функций** — если функция встречается дважды, Python использует последнюю.
2. **HTML-теги** — все тексты используют `<b>...</b>` для жирного шрифта, не `**...**`.
3. **`parse_mode="HTML"`** — должен быть во всех `bot.send_message()` и `bot.edit_message_text()`.
4. **Миграции БД** — новые колонки добавляются в `SCHEMA` и в список `new_columns` в `db.py`.
5. **`edit_or_send()`** — универсальная функция, автоматически добавляет `parse_mode="HTML"`.
6. **`add_crystals()`** — всегда требует 3 аргумента: `(tg_id, amount, reason)`.

---

## 🚀 Деплой

### Локально (macOS):
```bash
cd ~/projects/prizm_quest_bot
source .venv/bin/activate
python bot.py

### Локально (Windows):
cd "E:\БОТЫ\projects\prizm_quest_bot"
.\.venv\Scripts\Activate.ps1
python bot.py

### На сервере (PythonAnywhere):
cd ~/prizm_quest_bot
git pull
# Затем: Web → Reload

### Коммит и пуш:
git add .
git commit -m "описание изменений"
git push

---

## 📊 Админские команды

См. файл ADMIN_COMMANDS.md

---

Последнее обновление: 2026-10-07

---

## Что дальше?

Сохрани этот файл, закоммить его:

```bash
git add docs/BOT_STRUCTURE.md
git commit -m "docs: добавлена полная структура бота"
git push

Теперь у тебя есть полная карта бота! В следующий раз, когда запутаешься, просто открой этот файл и найди нужный шаг. 

-----------------------------

Гибридный вариант, в нем могут быть неточности:

# 🗺 Структура и архитектура Prizm Quest Bot

> Этот документ — живая карта всего бота. Он объединяет пользовательскую логику и технические детали. Если запуталась или забыла, как что-то работает — открой его и сверься.
> Последнее обновление: 2026-11-14

---

## 📁 Файловая структура проекта

```text
prizm_quest_bot/
├── bot.py                  # Точка входа, основная логика роутинга и поллинг
├── db.py                   # Работа с БД (SQLite), миграции (SCHEMA, new_columns), CRUD
├── keyboards.py            # Все Inline и Reply клавиатуры
├── config.py               # Глобальные настройки (токен, ID админа, константы)
├── .env                    # Секретные ключи (НИКОГДА не коммитить в Git!)
├── botdata/                # Локальная папка с файлом базы данных (prizmquest.db)
├── content/                # Текстовый контент (легко редактировать без лазания в код)
│   ├── facts.py            # Тексты 10 фактов о Prizm
│   ├── quest.py            # Тексты и логика 5 шагов Квеста
│   ├── myths.py            # Блок "Мифы и Безопасность"
│   └── messages.py         # Системные сообщения (Daily Bonus, приветствия и т.д.)
├── docs/                   # Документация
│   ├── BOT_STRUCTURE.md    # ← ЭТОТ ФАЙЛ
│   └── PROGRESS.txt        # Дневник разработки
└── images/                 # Медиафайлы


---

## 🎯 Пользовательский флоу (пошагово + код)

### Шаг 1: Пользователь пишет /start
- Что видит: Капча (математический пример с 3 кнопками).
- Код: bot.py → start() → проверяет captcha_passed в БД. Если 0 → send_captcha().
- БД: Таблица users, поле captcha_passed (0 или 1).

### Шаг 2: Пользователь решает капчу
- Что видит: При верном ответе → WELCOME_TEXT. При неверном → CAPTCHA_FAIL_TEXT + новый пример.
- Код: bot.py → handle_captcha(). db.py → set_captcha_passed().
- Callback: captcha:ok:{число} или captcha:fail:{число}.

### Шаг 3: Приветствие и первый бонус
- Что видит: WELCOME_TEXT (с балансом и реф. ссылкой) + кнопка "Забрать Daily Bonus".
- Код: bot.py → start() показывает welcome_kb().

### Шаг 4: Получение Daily Bonus (новый флоу)
- Что видит: DAILY_BONUS_MESSAGE (текст про демо-режим и Квест) + кнопка "🚀 Старт".
- Код: bot.py → claim_daily_bonus(). db.py → add_crystals(tg_id, 1, "daily").
- БД: Проверка can_claim_daily_bonus().

### Шаг 5: Главное меню (после нажатия "🚀 Старт" или /menu)
- Что видит: MAIN_MENU_TEXT и кнопки в 2 колонки:
  [📆 Daily Bonus] [🚀 СТАРТ]
  [💸 PRIZM Airdrop] [🎓 Академия]
  [💳 Кошелек] [👨‍🎓 Профиль]
  [🛒 Купить PZM] [⚙️ Настройки]
  [🎮 Игры] [❓ Помощь]
- Код: bot.py → cmd_menu(). keyboards.py → main_menu_kb().

### Шаг 6: Академия (Обучение)
- 10 фактов: Последовательный показ. За каждый дается 💎 Кристалл. (content/facts.py)
- Квест (5 шагов): Практика (создать кошелек → купить → вывести → запустить парамайнинг → получить 1100 PZM). (content/quest.py)
- Мифы и Безопасность: Отдельный блок с предупреждениями о мошенниках и правилах сид-фразы. (content/myths.py)

---

## 🗃 База данных (таблица users)

| Поле | Тип | Описание |
|------|-----|----------|
| tg_id | INTEGER | Telegram ID (PRIMARY KEY) |
| username | TEXT | Username в Telegram |
| first_name | TEXT | Имя пользователя |
| crystals | INTEGER | Баланс кристаллов/монет |
| captcha_passed | INTEGER | 0 = не пройдена, 1 = пройдена |
| daily_bonus_streak | INTEGER | Серия ежедневных бонусов (дни подряд) |
| last_daily_bonus | TEXT | Дата последнего получения Daily Bonus |
| quest_step | INTEGER | Текущий шаг Квеста (0-5) |
| facts_completed | INTEGER | Количество изученных фактов (0-10) |
| prizm_address | TEXT | Адрес кошелька PRIZM |
| invited_by | INTEGER | TG ID пригласившего (реферал) |
| referral_code | TEXT | Реферальный код пользователя |

*(Примечание: при добавлении новых полей обновлять SCHEMA, new_columns и reset_user_progress в db.py)*

---

## 🔄 Справочник Callback Data (кнопки)

| Callback | Действие | Обработчик в bot.py |
|----------|----------|-----------------------|
| captcha:ok:{число} | Правильный ответ на капчу | handle_captcha() |
| bonus:claim_daily | Забрать Daily Bonus | claim_daily_bonus() |
| menu:home | Главное меню | cmd_menu() |
| academy:fact:{n} | Показать факт №N | show_fact() |
| academy:quest | Начать/продолжить Квест | quest_handler() |
| academy:myths | Показать Мифы и Безопасность| show_myths() |
| profile:referrals | Открыть раздел рефералов | show_referrals() |

---

## 🔑 Золотые правила разработки (Выученные на ошибках)

1. Никогда не дублируй функции. Если функция уже есть — редактируй её. Python использует последнюю версию в файле, дубликаты ломают логику. *(Проверка: Ctrl+F → 1 вхождение).*
2. Всегда проверяй `parse_mode="HTML"`. Если текст содержит <b>, <i>, <code> — в send_message или edit_message_text должен быть parse_mode='HTML'.
3. Хелпер `edit_or_send`. Если используешь эту функцию, parse_mode='HTML' в ней уже прописан по умолчанию.
4. Точное совпадение `callback_data`. Если кнопка имеет callback_data="bonus:claim", обработчик должен искать именно эту строку.
5. Функция `add_crystals` требует 3 аргумента: db.add_crystals(tg_id, amount, reason). reason — метка для истории ("welcome", "daily", "quest").
6. Функции БД — только в `db.py`. Никогда не пиши cursor.execute напрямую в bot.py.
7. `if __name__ == "__main__":` — в самом конце. Весь код до него, после только bot.infinity_polling().

---

## 🚀 Деплой и запуск

Локально (Windows):
cd "E:\БОТы\projects\prizm_quest_bot"
.\.venv\Scripts\Activate.ps1  # или .\venv\Scripts\activate.bat
python bot.py

Локально (macOS):
cd ~/projects/prizm_quest_bot
source .venv/bin/activate
python bot.py

На сервере (PythonAnywhere):
cd ~/prizm_quest_bot
git pull origin main
# Затем в веб-интерфейсе: Web → Reload

Коммит и пуш (чек-лист):
1. Проверь отсутствие дубликатов функций.
2. Проверь parse_mode='HTML' в измененных текстах.
3. git add .
4. git commit -m "feat: краткое описание изменений"
5. git push origin main

---

## 📝 История изменений

| Дата | Что сделано |
|------|-------------|
| 2026-10-02 | Капча + приветственный бонус + закрепление бота |
| 2026-10-04 | Daily Bonus (по календарным дням) |
| 2026-10-07 | Перевод всех текстов в HTML, команда /menu |
| 2026-11-14 | Полный редизайн: 2-колоночное меню, 10 фактов, Квест, Мифы, разделение контента на папку content/ |

---

### 🛠 Как сохранить и синхронизировать этот файл:

**На Windows:**
1. Создай папку `docs` в корне проекта, если её нет.
2. Создай внутри файл `BOT_STRUCTURE.md` и вставь туда этот текст.
3. В терминале выполни:
   ```bash
   git add docs/BOT_STRUCTURE.md
   git commit -m "docs: объединена и актуализирована полная структура бота"
   git push origin main
   ```

**На Mac:**
```bash
git pull origin main

---