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