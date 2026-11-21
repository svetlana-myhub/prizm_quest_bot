from telebot import types


# ==============================================================================
# СТАРЫЕ ФУНКЦИИ (СОХРАНЕНЫ БЕЗ ИЗМЕНЕНИЙ)
# ==============================================================================

def level_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🌱 Новичок", callback_data="level:newbie"),
        types.InlineKeyboardButton("🚀 Уже знаком", callback_data="level:known"),
    )
    return markup


def fact_read_kb(fact_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "✅ Я понял, давай вопрос!",
            callback_data=f"fact:quiz:{fact_id}",
        )
    )
    return markup


def quiz_kb(fact_id, options):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for index, option in enumerate(options):
        markup.add(
            types.InlineKeyboardButton(
                option,
                callback_data=f"fact:ans:{fact_id}:{index}",
            )
        )
    return markup


def next_fact_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➡️ Следующий факт", callback_data="fact:next")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def step_start_kb(step):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if step.get("kind") == "question":
        markup.add(
            types.InlineKeyboardButton(
                "❓ Ответить на вопрос",
                callback_data=f"quest:quiz:{step['id']}",
            )
        )
    else:
        markup.add(
            types.InlineKeyboardButton(
                "✅ Шаг выполнен",
                callback_data=f"quest:done:{step['id']}",
            )
        )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def quest_answer_kb(step):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for index, option in enumerate(step["options"]):
        markup.add(
            types.InlineKeyboardButton(
                option,
                callback_data=f"quest:ans:{step['id']}:{index}",
            )
        )
    return markup


def quest_next_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➡️ Следующий шаг", callback_data="quest:next")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def myths_kb(myth_id, options):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for index, option in enumerate(options):
        markup.add(
            types.InlineKeyboardButton(
                option,
                callback_data=f"myth:ans:{myth_id}:{index}",
            )
        )
    return markup


def next_myth_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➡️ Следующий миф", callback_data="myth:next")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def words_kb(word_id, options):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for index, option in enumerate(options):
        markup.add(
            types.InlineKeyboardButton(
                option,
                callback_data=f"word:ans:{word_id}:{index}",
            )
        )
    return markup


def next_word_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➡️ Следующее слово", callback_data="word:next")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def final_test_start_kb():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(
            "🎓 Начать финальный тест",
            callback_data="test:start",
        )
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def final_test_answer_kb(question_id, options):
    markup = types.InlineKeyboardMarkup(row_width=1)
    for index, option in enumerate(options):
        markup.add(
            types.InlineKeyboardButton(
                option,
                callback_data=f"test:ans:{question_id}:{index}",
            )
        )
    return markup


def final_test_next_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➡️ Следующий вопрос", callback_data="test:next")
    )
    return markup


def final_test_result_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🏆 Получить награду", callback_data="reward:claim")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def final_test_retry_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔄 Попробовать снова", callback_data="test:start")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def captcha_kb(correct_answer, options):
    """
    Клавиатура капчи.
    correct_answer — правильный ответ (int), нужен для проверки в callback.
    options — список из 3 вариантов ответа (int), уже перемешанный.
    """
    markup = types.InlineKeyboardMarkup()
    
    buttons = []
    for option in options:
        if option == correct_answer:
            buttons.append(
                types.InlineKeyboardButton(
                    str(option),
                    callback_data=f"captcha:ok:{correct_answer}",
                )
            )
        else:
            buttons.append(
                types.InlineKeyboardButton(
                    str(option),
                    callback_data=f"captcha:fail:{correct_answer}",
                )
            )
    
    markup.add(*buttons)
    
    return markup


def welcome_kb():
    """Клавиатура после приветственного сообщения."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎁 Получить награду", callback_data="bonus:claim")
    )
    markup.add(
        types.InlineKeyboardButton("ℹ️ Помощь", callback_data="menu:help")
    )
    return markup


def pin_bot_kb():
    """Кнопки после получения бонуса — закрепление бота."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✅ Готово, я закрепил(а) бота!", callback_data="pin:done"),
        types.InlineKeyboardButton("🛠 Показать инструкцию", callback_data="pin:instruction"),
    )
    return markup


def pin_done_kb():
    """Кнопка после прочтения инструкции."""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Отлично, я закрепил(а) бота!", callback_data="pin:done")
    )
    return markup


def daily_bonus_instruction_kb():
    """Кнопка после сообщения о Daily Bonus — переход в меню."""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def after_daily_bonus_kb():
    """Кнопки после получения Daily Bonus — переход к обучению или в меню."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚀 Начать обучение", callback_data="academy:facts_start")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def daily_bonus_main_kb():
    """Кнопка Daily Bonus в главном меню."""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📆 Забрать награду!", callback_data="bonus:daily")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def daily_bonus_claim_kb():
    """Кнопка для получения Daily Bonus."""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Забрать награду!", callback_data="bonus:claim_daily")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def daily_bonus_wait_kb(next_time):
    """Кнопка, когда бонус ещё недоступен (показывает время следующего)."""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(f"⏰ Следующий бонус: {next_time}", callback_data="noop")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


# ==============================================================================
# ОБНОВЛЕННЫЕ ФУНКЦИИ (ЗАМЕНЕНЫ НА НОВЫЕ ВЕРСИИ)
# ==============================================================================

def main_menu_kb():
    """Главное меню: 2 колонки, 5 рядов."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📆 Daily Bonus", callback_data="menu:daily_bonus"),
        types.InlineKeyboardButton("🚀 СТАРТ", callback_data="menu:start"),
    )
    markup.add(
        types.InlineKeyboardButton("💸 PRIZM Airdrop", callback_data="menu:airdrop"),
        types.InlineKeyboardButton("🎓 Академия PRIZM", callback_data="menu:academy"),
    )
    markup.add(
        types.InlineKeyboardButton("💳 Кошелек", callback_data="menu:wallet"),
        types.InlineKeyboardButton("👨‍🎓 Профиль", callback_data="menu:profile"),
    )
    markup.add(
        types.InlineKeyboardButton("🛒 Купить PZM", callback_data="menu:buy"),
        types.InlineKeyboardButton("⚙️ Настройки", callback_data="menu:settings"),
    )
    markup.add(
        types.InlineKeyboardButton("🎮 Игры", callback_data="menu:games"),
        types.InlineKeyboardButton("❓ Помощь", callback_data="menu:help"),
    )
    return markup


def back_menu_kb(callback="menu:home"):
    """Универсальная кнопка Назад."""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("⬅️ Назад", callback_data=callback)
    )
    return markup


# ==============================================================================
# НОВЫЕ ФУНКЦИИ (ДОБАВЛЕНЫ)
# ==============================================================================

def academy_kb():
    """Академия PRIZM: 2 колонки."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💎 10 фактов о Prizm", callback_data="academy:facts_start"),
        types.InlineKeyboardButton("🟣 Квест: 5 шагов", callback_data="academy:quest"),
    )
    markup.add(
        types.InlineKeyboardButton("📚 Крипто-азбука", callback_data="academy:crypto_alphabet"),
        types.InlineKeyboardButton("🛡 Мифы и Безопасность", callback_data="academy:myths"),
    )
    markup.add(
        types.InlineKeyboardButton("🎓 Финальный тест", callback_data="academy:final_test"),
        types.InlineKeyboardButton("⚡️ Ускорение парамайнинга", callback_data="academy:paramining"),
    )
    markup.add(
        types.InlineKeyboardButton("📖 Крипто-словарь", callback_data="academy:glossary"),
        types.InlineKeyboardButton("📚 Инструкции", callback_data="academy:instructions"),
    )
    # ДОБАВЛЯЕМ ЭТИ ДВЕ СТРОКИ:
    markup.add(
        types.InlineKeyboardButton("🎮 Демо-квест", callback_data="academy:old_quest"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def start_quest_kb():
    """Кнопки после получения Daily Bonus: СТАРТ + Главное меню."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚀 СТАРТ — начать обучение", callback_data="academy:facts_start")
    )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup


def instructions_kb():
    """Подменю Инструкций."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛒 Где купить Prizm", callback_data="inst:buy"),
        types.InlineKeyboardButton("📤 Как вывести монеты", callback_data="inst:withdraw"),
        types.InlineKeyboardButton("💰 Как продать монеты", callback_data="inst:sell"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:academy"),
    )
    return markup


def profile_kb():
    """Профиль: 2 колонки."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💎 Баланс и история", callback_data="profile:balance"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="profile:stats"),
    )
    markup.add(
        types.InlineKeyboardButton("🏆 Достижения", callback_data="profile:achievements"),
        types.InlineKeyboardButton("👥 Рефералы", callback_data="profile:referrals"),
    )
    markup.add(
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def referrals_kb():
    """Подменю Рефералов."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔗 Моя ссылка", callback_data="ref:my_link"),
        types.InlineKeyboardButton("👥 Мои рефералы", callback_data="ref:my_referrals"),
    )
    markup.add(
        types.InlineKeyboardButton("📝 Условия и награды", callback_data="ref:rules"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="ref:stats"),
    )
    markup.add(
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:profile"),
    )
    return markup


def achievements_kb():
    """Подменю Достижений (бывшие Бейджи)."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🥇 Мои бейджи", callback_data="ach:badges"),
        types.InlineKeyboardButton("📜 История наград", callback_data="ach:history"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:profile"),
    )
    return markup


def wallet_kb():
    """Кошелек: 2 колонки."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔵 TON-кошелек", callback_data="wallet:ton"),
        types.InlineKeyboardButton("🟣 PRIZM-кошелек", callback_data="wallet:prizm"),
    )
    markup.add(
        types.InlineKeyboardButton("📥 Пополнить баланс", callback_data="wallet:deposit"),
        types.InlineKeyboardButton("📤 Вывести монеты", callback_data="wallet:withdraw"),
    )
    markup.add(
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def buy_pzm_kb():
    """Купить PZM: 2 колонки."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📈 Курс PZM", callback_data="buy:rate"),
        types.InlineKeyboardButton("📊 График", callback_data="buy:chart"),
    )
    markup.add(
        types.InlineKeyboardButton("🔢 Калькулятор", callback_data="buy:calc"),
        types.InlineKeyboardButton("📚 Инструкции", callback_data="buy:instructions"),
    )
    markup.add(
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def airdrop_kb():
    """PRIZM Airdrop."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔢 Ввести промокод", callback_data="airdrop:promo"),
        types.InlineKeyboardButton("🪎 Открыть PRIZM-BOX", callback_data="airdrop:box"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def daily_bonus_menu_kb():
    """Daily Bonus: подменю."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🎁 Забрать награду", callback_data="bonus:claim_daily"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def start_kb():
    """Кнопка СТАРТ (ведет к началу или продолжению 10 фактов)."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🟢 Начать обучение", callback_data="academy:facts_start"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def help_kb():
    """Помощь."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💬 Задать вопрос", callback_data="help:ask"),
        types.InlineKeyboardButton("📜 Команды бота", callback_data="help:commands"),
        types.InlineKeyboardButton("ℹ️ О боте", callback_data="help:about"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def settings_kb():
    """Настройки."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🌐 Язык: Русский", callback_data="settings:lang_ru"),
        types.InlineKeyboardButton("🔔 Уведомления", callback_data="settings:notifications"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def games_kb():
    """Игры (заглушка)."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🕹 Мини-игры (скоро)", callback_data="games:stub"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="menu:home"),
    )
    return markup


def fact_step_kb(fact_id, step_index, total_steps, button_text="➡️ Далее"):
    """Кнопки для шага факта: Далее + Назад (шаг назад)."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if step_index < total_steps - 1:
        markup.add(
            types.InlineKeyboardButton(button_text, callback_data=f"fact10:step:{fact_id}:{step_index + 1}")
        )
    else:
        markup.add(
            types.InlineKeyboardButton("💪 Всегда готов!", callback_data=f"fact10:quiz:{fact_id}")
        )
    
    # Кнопка Назад — шаг назад по факту (если не первый шаг)
    if step_index > 0:
        markup.add(
            types.InlineKeyboardButton("⬅️ Назад", callback_data=f"fact10:step:{fact_id}:{step_index - 1}")
        )
    else:
        # На первом шаге — выход на экран прогресса
        markup.add(
            types.InlineKeyboardButton("⬅️ Выйти", callback_data="academy:facts_progress")
        )
    
    return markup


def fact_quiz_kb(fact_id, options_count=4):
    """Клавиатура с 4 вариантами ответа в один ряд."""
    markup = types.InlineKeyboardMarkup(row_width=4)
    buttons = []
    for i in range(options_count):
        buttons.append(
            types.InlineKeyboardButton(
                str(i + 1),
                callback_data=f"fact10:ans:{fact_id}:{i}"
            )
        )
    markup.add(*buttons)
    markup.add(
        types.InlineKeyboardButton("⬅️ Назад к тексту", callback_data=f"fact10:step:{fact_id}:0")
    )
    return markup


def fact_result_kb(fact_id, is_correct, next_fact_id=None):
    """Клавиатура после ответа на вопрос."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    if is_correct:
        if next_fact_id:
            markup.add(
                types.InlineKeyboardButton(
                    "➡️ Следующий факт",
                    callback_data=f"fact10:start:{next_fact_id}"
                )
            )
        else:
            markup.add(
                types.InlineKeyboardButton(
                    "🎓 Завершить обучение",
                    callback_data="fact10:all_done"
                )
            )
    else:
        markup.add(
            types.InlineKeyboardButton(
                "🔄 Попробовать ещё раз",
                callback_data=f"fact10:quiz:{fact_id}"
            )
        )
    markup.add(
        types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home")
    )
    return markup