from telebot import types


def level_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🌱 Новичок", callback_data="level:newbie"),
        types.InlineKeyboardButton("🚀 Уже знаком", callback_data="level:known"),
    )
    return markup


def main_menu_kb():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎯 Квест", callback_data="menu:quest"),
        types.InlineKeyboardButton("🔷 Факты", callback_data="menu:facts"),
    )
    markup.add(
        types.InlineKeyboardButton(" Игры", callback_data="menu:games"),
        types.InlineKeyboardButton("🏅 Бейджи", callback_data="menu:badges"),
    )
    markup.add(
        types.InlineKeyboardButton("🎓 Финальный тест", callback_data="test:start"),
    )
    markup.add(
        types.InlineKeyboardButton("️ Помощь", callback_data="menu:help"),
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


def back_menu_kb():
    markup = types.InlineKeyboardMarkup()
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
        types.InlineKeyboardButton(" Главное меню", callback_data="menu:home")
    )
    return markup


def final_test_retry_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔄 Попробовать снова", callback_data="test:start")
    )
    markup.add(
        types.InlineKeyboardButton(" Главное меню", callback_data="menu:home")
    )
    return markup


def captcha_kb(correct_answer, options):
    """
    Клавиатура капчи.
    correct_answer — правильный ответ (int), нужен для проверки в callback.
    options — список из 3 вариантов ответа (int), уже перемешанный.
    """
    markup = types.InlineKeyboardMarkup()
    
    # Собираем все 3 кнопки в один список
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
    
    # Добавляем все три кнопки ОДНИМ вызовом — они встанут в один ряд
    markup.add(*buttons)
    
    return markup


def claim_bonus_kb():
    """Кнопка для получения приветственного бонуса."""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🎁 Получить награду", callback_data="bonus:claim")
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


def start_quest_kb():
    """Кнопка после получения Daily Bonus — начать квест."""
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(" Начать Квест", callback_data="menu:quest")
    )
    return markup