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
        types.InlineKeyboardButton("🎮 Игры", callback_data="menu:games"),
        types.InlineKeyboardButton("🏅 Бейджи", callback_data="menu:badges"),
    )
    markup.add(
        types.InlineKeyboardButton("ℹ️ Помощь", callback_data="menu:help"),
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