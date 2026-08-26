import logging
import re

import telebot

from config import BOT_TOKEN, ADMIN_TG_IDS
import db
from keyboards import (
    level_kb,
    main_menu_kb,
    fact_read_kb,
    quiz_kb,
    next_fact_kb,
    back_menu_kb,
)
from texts import (
    DISCLAIMER,
    MAIN_MENU_TEXT,
    SEED_WARNING,
    HELP_TEXT,
    QUEST_SOON,
    GAMES_SOON,
    BADGES_SOON,
    FACTS_ALL_DONE,
    UNKNOWN_TEXT,
)
from content.facts import FACTS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

db.init_db()

bot = telebot.TeleBot(BOT_TOKEN)


def is_admin(tg_id):
    return tg_id in ADMIN_TG_IDS


def looks_like_seed(text):
    if not text:
        return False
    words = re.findall(r"[A-Za-zА-Яа-яЁё]+", text)
    return len(words) in (12, 24)


def get_fact_by_id(fact_id):
    for fact in FACTS:
        if fact["id"] == fact_id:
            return fact
    return None


def find_next_fact(tg_id):
    for fact in FACTS:
        if not db.is_fact_done(tg_id, fact["id"]):
            return fact
    return None


def format_fact(fact):
    return (
        f"🔷 {fact['title']}\n\n"
        f"{fact['text']}\n\n"
        f"💡 Пример из жизни: {fact['life_example']}\n\n"
        f"❗️ Важно: {fact['important']}"
    )


def edit_or_send(call, text, markup):
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
        )
    except Exception as exc:
        if "message is not modified" in str(exc):
            return
        bot.send_message(call.message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=["start"])
def start(message):
    user = message.from_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    bot.send_message(message.chat.id, DISCLAIMER, reply_markup=level_kb())


@bot.message_handler(commands=["help"])
def help_command(message):
    user = message.from_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    bot.send_message(message.chat.id, HELP_TEXT, reply_markup=main_menu_kb())


@bot.message_handler(commands=["profile"])
def profile(message):
    user = message.from_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    stored = db.get_user(user.id)
    done = db.count_done_facts(user.id)
    level_text = {
        "newbie": "новичок 🌱",
        "known": "уже знаком 🚀",
    }.get(stored["level"], "ещё не выбран")
    text = (
        "👤 Профиль\n\n"
        f"Уровень: {level_text}\n"
        f"Кристаллы: {stored['crystals']} 🔷\n"
        f"Факты пройдены: {done}/10\n"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu_kb())


@bot.callback_query_handler(func=lambda call: call.data.startswith("level:"))
def choose_level(call):
    level = call.data.split(":", 1)[1]
    if level not in ("newbie", "known"):
        bot.answer_callback_query(call.id, "Неизвестный уровень")
        return
    db.set_level(call.from_user.id, level)
    bot.answer_callback_query(call.id, "Уровень сохранён")
    edit_or_send(call, MAIN_MENU_TEXT, main_menu_kb())


@bot.callback_query_handler(func=lambda call: call.data.startswith("menu:"))
def main_menu(call):
    section = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)

    if section == "home":
        edit_or_send(call, MAIN_MENU_TEXT, main_menu_kb())
        return

    if section == "facts":
        fact = find_next_fact(call.from_user.id)
        if fact is None:
            edit_or_send(call, FACTS_ALL_DONE, back_menu_kb())
        else:
            edit_or_send(call, format_fact(fact), fact_read_kb(fact["id"]))
        return

    texts = {
        "quest": QUEST_SOON,
        "games": GAMES_SOON,
        "badges": BADGES_SOON,
        "help": HELP_TEXT,
    }
    edit_or_send(call, texts.get(section, "Раздел в разработке"), main_menu_kb())


@bot.callback_query_handler(func=lambda call: call.data.startswith("fact:"))
def fact_flow(call):
    parts = call.data.split(":")
    action = parts[1]

    if action == "next":
        bot.answer_callback_query(call.id)
        fact = find_next_fact(call.from_user.id)
        if fact is None:
            edit_or_send(call, FACTS_ALL_DONE, back_menu_kb())
        else:
            edit_or_send(call, format_fact(fact), fact_read_kb(fact["id"]))
        return

    if action == "quiz":
        bot.answer_callback_query(call.id)
        fact = get_fact_by_id(parts[2])
        if fact is None:
            return
        quiz = fact["quiz"]
        edit_or_send(
            call,
            f"❓ {quiz['question']}",
            quiz_kb(fact["id"], quiz["options"]),
        )
        return

    if action == "ans":
        fact = get_fact_by_id(parts[2])
        if fact is None:
            return
        answer_index = int(parts[3])
        quiz = fact["quiz"]

        if answer_index == quiz["correct_index"]:
            bot.answer_callback_query(call.id)
            if not db.is_fact_done(call.from_user.id, fact["id"]):
                db.mark_fact_done(call.from_user.id, fact["id"], True)
                db.add_crystals(
                    call.from_user.id,
                    fact["reward_crystals"],
                    f"fact:{fact['id']}",
                )
            result_text = (
                f"✅ Верно! +{fact['reward_crystals']} 🔷\n\n"
                f"{quiz['explanation']}"
            )
            edit_or_send(call, result_text, next_fact_kb())
        else:
            bot.answer_callback_query(call.id, "Неверно, попробуй ещё раз 😉")


@bot.message_handler(
    func=lambda message: looks_like_seed(message.text),
    content_types=["text"],
)
def seed_guard(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    bot.send_message(message.chat.id, SEED_WARNING)


@bot.message_handler(func=lambda message: True, content_types=["text"])
def unknown_text(message):
    bot.send_message(message.chat.id, UNKNOWN_TEXT, reply_markup=main_menu_kb())


if __name__ == "__main__":
    logging.info("Бот запускается...")
    bot.infinity_polling()