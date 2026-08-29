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
    step_start_kb,
    quest_answer_kb,
    quest_next_kb,
)
from texts import (
    DISCLAIMER,
    MAIN_MENU_TEXT,
    SEED_WARNING,
    HELP_TEXT,
    GAMES_SOON,
    NO_BADGES_TEXT,
    FACTS_ALL_DONE,
    QUEST_ALL_DONE_TEXT,
    QUEST_FINISHED_TEXT,
    UNKNOWN_TEXT,
)
from content.facts import FACTS
from content.quest import QUEST_STEPS

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


def get_step_by_id(step_id):
    for step in QUEST_STEPS:
        if step["id"] == step_id:
            return step
    return None


def find_next_step(tg_id):
    for step in QUEST_STEPS:
        if not db.is_step_done(tg_id, step["id"]):
            return step
    return None


def format_step(step):
    return f"🎯 {step['title']}\n\n{step['text']}"


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
    done_facts = db.count_done_facts(user.id)
    badges = db.get_user_badges(user.id)
    level_text = {
        "newbie": "новичок 🌱",
        "known": "уже знаком 🚀",
    }.get(stored["level"], "ещё не выбран")
    badges_line = ", ".join(badges) if badges else "пока нет"
    text = (
        "👤 Профиль\n\n"
        f"Уровень: {level_text}\n"
        f"Кристаллы: {stored['crystals']} 🔷\n"
        f"Факты пройдены: {done_facts}/10\n"
        f"Бейджи: {badges_line}\n"
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

    if section == "quest":
        step = find_next_step(call.from_user.id)
        if step is None:
            edit_or_send(call, QUEST_ALL_DONE_TEXT, back_menu_kb())
        else:
            edit_or_send(call, format_step(step), step_start_kb(step))
        return

    if section == "badges":
        badges = db.get_user_badges(call.from_user.id)
        if badges:
            text = "🏅 Ваши бейджи:\n\n" + "\n".join(f"— {b}" for b in badges)
        else:
            text = NO_BADGES_TEXT
        edit_or_send(call, text, back_menu_kb())
        return

    texts = {
        "games": GAMES_SOON,
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
            extra = ""
            if not db.is_fact_done(call.from_user.id, fact["id"]):
                db.mark_fact_done(call.from_user.id, fact["id"], True)
                db.add_crystals(
                    call.from_user.id,
                    fact["reward_crystals"],
                    f"fact:{fact['id']}",
                )
                if db.count_done_facts(call.from_user.id) == len(FACTS):
                    if db.award_badge_once(call.from_user.id, "facts_master"):
                        title = db.get_badge_title("facts_master")
                        extra = f"\n\n🏅 Новый бейдж: {title}!"
            result_text = (
                f"✅ Верно! +{fact['reward_crystals']} 🔷{extra}\n\n"
                f"{quiz['explanation']}"
            )
            edit_or_send(call, result_text, next_fact_kb())
        else:
            bot.answer_callback_query(call.id, "Неверно, попробуй ещё раз 😉")


@bot.callback_query_handler(func=lambda call: call.data.startswith("quest:"))
def quest_flow(call):
    parts = call.data.split(":")
    action = parts[1]

    if action == "next":
        bot.answer_callback_query(call.id)
        step = find_next_step(call.from_user.id)
        if step is None:
            edit_or_send(call, QUEST_ALL_DONE_TEXT, back_menu_kb())
        else:
            edit_or_send(call, format_step(step), step_start_kb(step))
        return

    if action == "quiz":
        bot.answer_callback_query(call.id)
        step = get_step_by_id(parts[2])
        if step is None:
            return
        edit_or_send(call, f"❓ {step['question']}", quest_answer_kb(step))
        return

    if action == "ans":
        step = get_step_by_id(parts[2])
        if step is None:
            return
        answer_index = int(parts[3])
        if answer_index == step["correct_index"]:
            bot.answer_callback_query(call.id)
            complete_step(call, step)
        else:
            bot.answer_callback_query(call.id, "Неверно, подумай ещё 😉")
        return

    if action == "done":
        bot.answer_callback_query(call.id)
        step = get_step_by_id(parts[2])
        if step is None:
            return
        complete_step(call, step)


def complete_step(call, step):
    tg_id = call.from_user.id
    if not db.is_step_done(tg_id, step["id"]):
        db.mark_step_done(tg_id, step["id"])
        db.add_crystals(tg_id, step["reward_crystals"], f"quest:{step['id']}")

    extra = ""
    if step.get("badge"):
        if db.award_badge_once(tg_id, step["badge"]):
            title = db.get_badge_title(step["badge"])
            extra = f"\n\n🏅 Новый бейдж: {title}!"

    text = f"✅ Шаг выполнен! +{step['reward_crystals']} 🔷{extra}"

    if find_next_step(tg_id) is None:
        text += "\n\n" + QUEST_FINISHED_TEXT
        edit_or_send(call, text, back_menu_kb())
    else:
        edit_or_send(call, text, quest_next_kb())


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