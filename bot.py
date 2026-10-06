import logging
import re

import random 

import telebot
from telebot import types

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
    myths_kb,
    next_myth_kb,
    words_kb,
    next_word_kb,
    captcha_kb,
    claim_bonus_kb,
    pin_bot_kb,       # ← добавили
    pin_done_kb,      # ← добавили
    daily_bonus_instruction_kb,   # ← добавили
    daily_bonus_main_kb,       # ← если используешь
    daily_bonus_claim_kb,      # ← добавили
    daily_bonus_wait_kb,       # ← добавили
    start_quest_kb,               # ← добавили
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
    MYTHS_ALL_DONE,
    WORDS_ALL_DONE,
    CAPTCHA_TEXT,       # ← добавили
    CAPTCHA_SUCCESS_TEXT,  # ← добавили
    CAPTCHA_FAIL_TEXT,     # ← добавили
    WELCOME_TEXT,       # ← добавили
    PIN_BOT_TEXT,           # ← добавили
    PIN_INSTRUCTION_TEXT,   # ← добавили
    DAILY_BONUS_INTRO_TEXT,       # ← добавили
    DAILY_BONUS_RECEIVED_TEXT,    # ← добавили
    DAILY_BONUS_MENU_TEXT,
    REWARD_ALREADY_CLAIMED,
)    
from content.final_test import FINAL_TEST_QUESTIONS, PASSING_SCORE
from keyboards import (
    final_test_start_kb,
    final_test_answer_kb,
    final_test_next_kb,
    final_test_result_kb,
    final_test_retry_kb,
)
from texts import (
    FINAL_TEST_INTRO,
    FINAL_TEST_PASS,
    REWARD_CLAIM_TEXT,
    REWARD_INVALID_ADDRESS,
)
from content.facts import FACTS
from content.quest import QUEST_STEPS
from content.myths import MYTHS
from content.words import WORDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

db.init_db()

bot = telebot.TeleBot(BOT_TOKEN)


# Хранит прогресс теста для каждого пользователя: {tg_id: {'q_index': 0, 'score': 0}}
test_sessions = {}

# Хранит ID пользователей, которые сейчас должны отправить адрес кошелька
awaiting_prizm = set()


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


def get_myth_by_id(myth_id):
    for m in MYTHS:
        if m["id"] == myth_id:
            return m
    return None

def find_next_myth(tg_id):
    for m in MYTHS:
        if not db.is_myth_done(tg_id, m["id"]):
            return m
    return None

def get_word_by_id(word_id):
    for w in WORDS:
        if w["id"] == word_id:
            return w
    return None

def find_next_word(tg_id):
    for w in WORDS:
        if not db.is_word_done(tg_id, w["id"]):
            return w
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
            parse_mode="HTML",  # ← добавили
        )
    except Exception as exc:
        if "message is not modified" in str(exc):
            return
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")  # ← добавили


@bot.message_handler(commands=["start"])
def start(message):
    user = message.from_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    
    # Проверяем, пройдена ли капча
    user_data = db.get_user(user.id)
    if user_data and user_data.get("captcha_passed"):
        # Капча уже пройдена — показываем приветственное сообщение
        bot.send_message(
            message.chat.id,
            WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=claim_bonus_kb(),
        )
    else:
        # Нужно пройти капчу
        send_captcha(message.chat.id)


@bot.message_handler(commands=["help"])
def help_command(message):
    user = message.from_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    bot.send_message(message.chat.id, HELP_TEXT, reply_markup=main_menu_kb())


@bot.message_handler(commands=["menu"])
def menu_command(message):
    """Показать главное меню."""
    db.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    bot.send_message(message.chat.id, MAIN_MENU_TEXT, reply_markup=main_menu_kb())


@bot.message_handler(commands=["test"])
def test_command(message):
    user = message.from_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    
    # Создаём фейковый call для совместимости с callback
    class FakeCall:
        def __init__(self, user_id, chat_id):
            self.from_user = type('obj', (object,), {'id': user_id})()
            self.message = type('obj', (object,), {
                'chat': type('obj', (object,), {'id': chat_id})()
            })()
            self.id = None
        
        def answer_callback_query(self, id):
            pass
    
    fake_call = FakeCall(message.from_user.id, message.chat.id)
    start_final_test(fake_call)
    bot.send_message(message.chat.id, "🎓 Финальный тест запущен!")


def get_level_text(level):
    """Преобразует уровень в красивый текст"""
    level_map = {
        "newbie": "новичок 🌱",
        "known": "уже знаком 🚀",
    }
    return level_map.get(level, "ещё не выбран")


@bot.message_handler(commands=["profile"])
def profile(message):
    user = message.from_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    db.update_last_active(user.id)  # Обновляем время последней активности
    
    user_info = db.get_user_full_info(user.id)
    
    if not user_info:
        bot.send_message(message.chat.id, "❌ Ошибка получения данных.")
        return
    
    username = f"@{user.username}" if user.username else "не указан"
    
    # Дней в боте
    from datetime import datetime
    created = user_info.get('created_at')
    days_in_bot = "неизвестно"
    if created:
        try:
            created_dt = datetime.fromisoformat(created)
            days_in_bot = (datetime.now() - created_dt).days
        except:
            pass
    
    # Последний вход
    last_active = user_info.get('last_active_at') or "никогда"
    
    # Прогресс
    facts = f"{user_info.get('facts_correct', 0)}/{user_info.get('facts_total', 0)}"
    quest = user_info.get('quest_completed', 0)
    myths = f"{user_info.get('myths_correct', 0)}/{user_info.get('myths_total', 0)}"
    words = f"{user_info.get('words_correct', 0)}/{user_info.get('words_total', 0)}"
    test_passed = "✅" if user_info.get('final_test_passed') else "❌"
    
    # Бейджи
    badges = user_info.get('badges', [])
    badges_text = ", ".join(badges) if badges else "пока нет"
    
    # Награды
    rewards = user_info.get('rewards', [])
    if rewards:
        rewards_list = []
        for r in rewards:
            rewards_list.append(f"• {r['code']}: {r['status']}")
        rewards_text = "\n".join(rewards_list)
    else:
        rewards_text = "нет"
    
    # Рефералы
    inviter = user_info.get('inviter_username')
    inviter_text = f"@{inviter}" if inviter else "никто"
    referrals = user_info.get('referrals_count_actual', 0)
    
    text = (
        f"👤 **Ваш профиль**\n\n"
        f"📅 **Активность:**\n"
        f"• ID: `{user.id}`\n"
        f"• Имя: {user.first_name or 'без имени'}\n"
        f"• Username: {username}\n"
        f"• Дней в боте: {days_in_bot}\n"
        f"• Последний вход: {last_active}\n"
        f"• Daily Bonus серия: {user_info.get('daily_bonus_streak', 0)}\n\n"
        f" **Прогресс:**\n"
        f"• Факты: {facts}\n"
        f"• Квест шагов: {quest}\n"
        f"• Мифы: {myths}\n"
        f"• Слова: {words}\n"
        f"• Финальный тест: {test_passed}\n\n"
        f"💎 **Баланс:**\n"
        f"• Кристаллы: {user_info.get('crystals', 0)}\n\n"
        f"🏆 **Награды:**\n"
        f"• Бейджи: {badges_text}\n"
        f"• Нач. уровень: {get_level_text(user_info.get('level', 'newbie'))}\n"
        f"• Заявки на награду:\n{rewards_text}\n\n"
        f"👥 **Рефералы:**\n"
        f"• Пригласил: {inviter_text}\n"
        f"• Приглашено друзей: {referrals}\n\n"
        f"💳 **Кошельки:**\n"
        f"• PRIZM: {user_info.get('prizm_address') or 'не указан'}\n"
        f"• TON: {user_info.get('ton_wallet') or 'не указан'}"
    )
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=main_menu_kb())


@bot.message_handler(commands=["reset"])
def reset_progress(message):
    tg_id = message.from_user.id
    db.reset_user_progress(tg_id)
    bot.send_message(message.chat.id, "✅ Ваш прогресс сброшен. Начинаем заново!")    


@bot.message_handler(commands=["admin_reset"])
def admin_reset(message):
    """Админский сброс прогресса любого пользователя по его Telegram ID."""
    # Проверка прав админа
    if message.from_user.id not in ADMIN_TG_IDS:
        bot.send_message(message.chat.id, " Эта команда только для администратора.")
        return
    
    # Парсим ID пользователя из сообщения: /admin_reset 123456789
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        bot.send_message(
            message.chat.id,
            "Использование: /admin_reset <telegram_id>\n\n"
            "Пример: /admin_reset 123456789",
        )
        return
    
    target_tg_id = int(parts[1])
    
    # Проверяем, существует ли такой пользователь
    user = db.get_user(target_tg_id)
    if not user:
        bot.send_message(message.chat.id, f"❌ Пользователь с ID {target_tg_id} не найден в базе.")
        return
    
    # Сбрасываем прогресс
    db.reset_user_progress(target_tg_id)
    
    bot.send_message(
        message.chat.id,
        f"✅ Прогресс пользователя {target_tg_id} полностью сброшен.",
    )    


@bot.callback_query_handler(func=lambda call: call.data.startswith("level:"))
def choose_level(call):
    level = call.data.split(":", 1)[1]
    if level not in ("newbie", "known"):
        bot.answer_callback_query(call.id, "Неизвестный уровень")
        return
    db.set_level(call.from_user.id, level)
    bot.answer_callback_query(call.id, "Уровень сохранён")
    edit_or_send(call, MAIN_MENU_TEXT, main_menu_kb())


@bot.callback_query_handler(func=lambda call: call.data == "captcha:done")
def after_captcha(call):
    """Обработчик кнопки 'Продолжить' после капчи."""
    bot.answer_callback_query(call.id)
    # Показываем приветственное сообщение с кнопкой получения бонуса
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=WELCOME_TEXT,
    )


@bot.callback_query_handler(func=lambda call: call.data == "bonus:claim")
def claim_bonus(call):
    """Начисляем приветственный бонус 10 Prizm."""
    # Проверяем, не получал ли уже бонус
    user = db.get_user(call.from_user.id)
    if user and user.get("welcome_bonus_claimed"):
        bot.answer_callback_query(call.id, "Вы уже получили приветственный бонус!")
        return
    
    # Начисляем 10 кристаллов
    db.add_crystals(call.from_user.id, 10, "welcome_bonus")
    
    # Отмечаем, что бонус получен
    db.mark_welcome_bonus_claimed(call.from_user.id)
    
    bot.answer_callback_query(call.id, "✅ +10 Prizm!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=PIN_BOT_TEXT,
        parse_mode="HTML",
        reply_markup=pin_bot_kb(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "pin:instruction")
def show_pin_instruction(call):
    """Показывает инструкцию по закреплению бота."""
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=PIN_INSTRUCTION_TEXT,
        parse_mode="HTML",
        reply_markup=pin_done_kb(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "pin:done")
def pin_done(call):
    """Пользователь закрепил бота — показываем информацию о Daily Bonus."""
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=DAILY_BONUS_INTRO_TEXT,
        parse_mode="HTML",
        reply_markup=daily_bonus_instruction_kb(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "pin:done")
def pin_done(call):
    """Пользователь закрепил бота — показываем информацию о Daily Bonus."""
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=DAILY_BONUS_INTRO_TEXT,
        parse_mode="HTML",
        reply_markup=daily_bonus_instruction_kb(),
    )


@bot.callback_query_handler(func=lambda call: call.data == "bonus:daily")
def claim_daily_bonus(call):
    """Начисляем ежедневный бонус."""
    # Здесь будет логика проверки кулдауна 24 часа и начисления
    # Пока просто показываем сообщение о получении
    db.add_crystals(call.from_user.id, 1, "daily_bonus")
    
    bot.answer_callback_query(call.id, "✅ +1 Prizm!")
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=DAILY_BONUS_RECEIVED_TEXT,
        parse_mode="HTML",
        reply_markup=start_quest_kb(),
    )

        
@bot.callback_query_handler(func=lambda call: call.data.startswith("menu:"))
def main_menu(call):
    section = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id)
        
    if section == "daily_bonus":
        can_claim, time_left = db.can_claim_daily_bonus(call.from_user.id)
        
        if can_claim:
            edit_or_send(call, DAILY_BONUS_MENU_TEXT, daily_bonus_claim_kb())
        else:
            text = f"⏰ Вы уже получили Daily Bonus!\n\nСледующий бонус будет доступен через: {time_left}"
            edit_or_send(call, text, daily_bonus_wait_kb(time_left))
        return

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

    if section == "games":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton(" Миф или правда", callback_data="myth:start"),
            types.InlineKeyboardButton(" Отгадай слово", callback_data="word:start"),
        )
        markup.add(types.InlineKeyboardButton("🏠 Главное меню", callback_data="menu:home"))
        edit_or_send(call, "Выберите игру:", markup)
        return

    if section == "help":
        edit_or_send(call, HELP_TEXT, back_menu_kb())
        return


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


@bot.callback_query_handler(func=lambda call: call.data == "bonus:claim_daily")
def claim_daily_bonus_handler(call):
    """Начисляем Daily Bonus."""
    can_claim, next_time = db.can_claim_daily_bonus(call.from_user.id)
    
    if not can_claim:
        bot.answer_callback_query(call.id, "Бонус ещё недоступен!")
        return
    
    # Начисляем бонус
    streak = db.claim_daily_bonus(call.from_user.id)
    
    bot.answer_callback_query(call.id, f"✅ +1 Prizm! Серия: {streak} дней")
    
    # Показываем сообщение о получении
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=DAILY_BONUS_RECEIVED_TEXT,
        parse_mode="HTML",
        reply_markup=start_quest_kb(),
    )        


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


@bot.message_handler(func=lambda message: not message.text.startswith('/'), content_types=["text"])
def unknown_text(message):
    bot.send_message(message.chat.id, UNKNOWN_TEXT, reply_markup=main_menu_kb())


@bot.callback_query_handler(func=lambda call: call.data.startswith("myth:"))
def myth_flow(call):
    parts = call.data.split(":")
    action = parts[1]

    if action == "start":
        bot.answer_callback_query(call.id)
        myth = find_next_myth(call.from_user.id)
        if myth is None:
            edit_or_send(call, MYTHS_ALL_DONE, back_menu_kb())
        else:
            edit_or_send(
                call,
                f"🎭 {myth['statement']}",
                myths_kb(myth["id"], ["✅ Правда", "❌ Миф"]),
            )
        return

    if action == "next":
        bot.answer_callback_query(call.id)
        myth = find_next_myth(call.from_user.id)
        if myth is None:
            edit_or_send(call, MYTHS_ALL_DONE, back_menu_kb())
        else:
            edit_or_send(
                call,
                f"🎭 {myth['statement']}",
                myths_kb(myth["id"], ["✅ Правда", "❌ Миф"]),
            )
        return

    if action == "ans":
        myth = get_myth_by_id(parts[2])
        if myth is None:
            return
        answer_index = int(parts[3])
        # Если myth["answer"] == True (правда), то правильный ответ — индекс 0 ("✅ Правда")
        # Если myth["answer"] == False (миф), то правильный ответ — индекс 1 ("❌ Миф")
        correct_index = 0 if myth["answer"] else 1
        is_correct = answer_index == correct_index

        if not db.is_myth_done(call.from_user.id, myth["id"]):
            db.mark_myth_done(call.from_user.id, myth["id"], is_correct)
            if is_correct:
                db.add_crystals(
                    call.from_user.id,
                    myth["reward_crystals"],
                    f"myth:{myth['id']}",
                )

        if is_correct:
            extra = ""
            if db.count_done_myths(call.from_user.id) == len(MYTHS):
                if db.award_badge_once(call.from_user.id, "myth_master"):
                    extra = "\n\n Новый бейдж: 🎭 Разоблачитель мифов!"
            text = (
                f"✅ Верно! +{myth['reward_crystals']} 🔷{extra}\n\n"
                f"{myth['explanation']}"
            )
            edit_or_send(call, text, next_myth_kb())
        else:
            text = f"❌ Неверно.\n\n{myth['explanation']}"
            edit_or_send(call, text, next_myth_kb())


@bot.callback_query_handler(func=lambda call: call.data.startswith("word:"))
def word_flow(call):
    parts = call.data.split(":")
    action = parts[1]

    if action == "start":
        bot.answer_callback_query(call.id)
        word = find_next_word(call.from_user.id)
        if word is None:
            edit_or_send(call, WORDS_ALL_DONE, back_menu_kb())
        else:
            edit_or_send(
                call,
                f"🧠 Отгадай слово\n\n💡 {word['hint']}",
                words_kb(word["id"], word["options"]),
            )
        return

    if action == "next":
        bot.answer_callback_query(call.id)
        word = find_next_word(call.from_user.id)
        if word is None:
            edit_or_send(call, WORDS_ALL_DONE, back_menu_kb())
        else:
            edit_or_send(
                call,
                f"🧠 Отгадай слово\n\n💡 {word['hint']}",
                words_kb(word["id"], word["options"]),
            )
        return

    if action == "ans":
        word = get_word_by_id(parts[2])
        if word is None:
            return
        answer_index = int(parts[3])
        is_correct = answer_index == word["correct_index"]

        if not db.is_word_done(call.from_user.id, word["id"]):
            db.mark_word_done(call.from_user.id, word["id"], is_correct)
            if is_correct:
                db.add_crystals(
                    call.from_user.id,
                    word["reward_crystals"],
                    f"word:{word['id']}",
                )

        if is_correct:
            extra = ""
            if db.count_done_words(call.from_user.id) == len(WORDS):
                if db.award_badge_once(call.from_user.id, "word_master"):
                    extra = "\n\n Новый бейдж: 🧠 Эрудит Prizm!"
            text = (
                f"✅ Верно! Это «{word['term']}». +{word['reward_crystals']} 🔷{extra}\n\n"
                f"{word['explanation']}"
            )
            edit_or_send(call, text, next_word_kb())
        else:
            edit_or_send(call, "❌ Неверно, попробуй ещё раз 😉", None)


# --- ФИНАЛЬНЫЙ ТЕСТ ---

@bot.callback_query_handler(func=lambda call: call.data == "test:start")
def start_final_test(call):
    if call.id:
        bot.answer_callback_query(call.id)
    test_sessions[call.from_user.id] = {"q_index": 0, "score": 0}
    show_test_question(call)


def show_test_question(call):
    tg_id = call.from_user.id
    session = test_sessions.get(tg_id)
    if not session:
        return
    
    q_index = session["q_index"]
    if q_index >= len(FINAL_TEST_QUESTIONS):
        finish_test(call)
        return
    
    q = FINAL_TEST_QUESTIONS[q_index]
    text = f"🎓 Вопрос {q_index + 1} из {len(FINAL_TEST_QUESTIONS)}\n\n{q['question']}"
    edit_or_send(call, text, final_test_answer_kb(q["id"], q["options"]))


@bot.callback_query_handler(func=lambda call: call.data.startswith("test:ans:"))
def handle_test_answer(call):
    parts = call.data.split(":")
    q_id = parts[2]
    ans_index = int(parts[3])
    tg_id = call.from_user.id
    
    session = test_sessions.get(tg_id)
    if not session:
        return
    
    q = next((q for q in FINAL_TEST_QUESTIONS if q["id"] == q_id), None)
    if not q:
        return
    
    is_correct = (ans_index == q["correct_index"])
    if is_correct:
        session["score"] += 1
    
    result_text = f"{'✅ Верно!' if is_correct else '❌ Неверно.'}\n\n{q['explanation']}"
    edit_or_send(call, result_text, final_test_next_kb())


@bot.callback_query_handler(func=lambda call: call.data == "test:next")
def next_test_question(call):
    bot.answer_callback_query(call.id)
    tg_id = call.from_user.id
    if tg_id in test_sessions:
        test_sessions[tg_id]["q_index"] += 1
    show_test_question(call)


def finish_test(call):
    tg_id = call.from_user.id
    session = test_sessions.pop(tg_id, {"score": 0})
    score = session["score"]
    
    if score >= PASSING_SCORE:
        db.set_final_test_passed(tg_id)
        edit_or_send(call, FINAL_TEST_PASS, final_test_result_kb())
    else:
        fail_text = (
            "❌ К сожалению, вы не набрали проходной балл.\n\n"
            f"Ваш результат: {score} из {len(FINAL_TEST_QUESTIONS)}. "
            f"Нужно минимум {PASSING_SCORE}.\n\n"
            "Не расстраивайтесь! Вы можете пройти тест ещё раз."
        )
        edit_or_send(call, fail_text, final_test_retry_kb())


# --- ЗАЯВКА НА НАГРАДУ ---

@bot.callback_query_handler(func=lambda call: call.data == "reward:claim")
def claim_reward(call):
    bot.answer_callback_query(call.id)
    tg_id = call.from_user.id
    
    # Проверяем, не отправлял ли уже
    if tg_id in awaiting_prizm:
        edit_or_send(call, "Вы уже в процессе отправки адреса.", back_menu_kb())
        return
    
    # Проверяем, есть ли уже заявка
    existing = db.get_user_full_info(tg_id)
    if existing and existing.get("rewards"):
        for reward in existing["rewards"]:
            if reward["status"] == "pending_manual":
                edit_or_send(call, REWARD_ALREADY_CLAIMED, back_menu_kb())
                return
    
    awaiting_prizm.add(tg_id)
    edit_or_send(call, REWARD_CLAIM_TEXT, back_menu_kb())


@bot.message_handler(func=lambda m: m.from_user.id in awaiting_prizm, content_types=["text"])
def handle_prizm_address(message):
    address = message.text.strip().upper()
    
    if not re.match(r"^PRIZM-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{5}$", address):
        bot.send_message(message.chat.id, REWARD_INVALID_ADDRESS)
        return
    
    # Сохраняем адрес в БД
    db.set_prizm_address(message.from_user.id, address)
    
    # Создаём заявку в таблице rewards
    db.create_reward_claim(
        tg_id=message.from_user.id,
        code="prizm_quest_1100",
        reward_type="cashback_1100_pzm",
        wallet_address=address,
        status="pending_manual",
    )
    
    awaiting_prizm.discard(message.from_user.id)
    
    # ВРЕМЕННАЯ ЗАГЛУШКА для GRAM-кошелька
    gram_wallet = "БУДЕТ_УКАЗАН_В_КВЕСТЕ"
    
    # Формируем сообщение для копирования
    copy_text = (
        f"<code>Prizm Quest пройден! 🎉\n\n"
        f"Мой PRIZM-кошелёк:\n{address}\n\n"
        f"Мой GRAM-кошелёк:\n{gram_wallet}\n\n"
        f"Мной куплено 1000 PZM\n"
        f"Выведено на кошелек 1000 PZM\n\n"
        f"#подарок</code>"
    )
    
    bot.send_message(
        message.chat.id,
        f"✅ Ваша заявка сформирована!\n\n"
        f"Скопируйте целиком блок ниже и отправьте в чат:\n\n{copy_text}",
        parse_mode="HTML",
    )
    
    bot.send_message(
        message.chat.id,
        "Организатор проверит, всё ли выполнено верно, и начислит награду. "
        "Обычно это занимает до 24 часов.\n\nСпасибо, что прошли Prizm Quest! 🎉"
    )


# --- АДМИН-КОМАНДЫ ---

@bot.message_handler(commands=["stats"])
def admin_stats(message):
    if not is_admin(message.from_user.id):
        return
    
    stats = db.get_stats()
    
    text = (
        "📊 **Статистика бота:**\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f" Активных за 7 дней: {stats['active_7d']}\n"
        f"🟢 Активных за 30 дней: {stats['active_30d']}\n\n"
        f"🎯 Начали квест: {stats['quest_started']}\n"
        f"🎓 Прошли тест: {stats['test_passed']}\n\n"
        f" Запросили награду: {stats['reward_claimed']}\n"
        f" Ожидают выплаты: {stats['reward_pending']}\n"
        f"✅ Получили выплату: {stats['reward_paid']}"
    )
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(commands=["pending"])
def admin_pending(message):
    if not is_admin(message.from_user.id):
        return
    
    claims = db.get_pending_claims()
    
    if not claims:
        bot.send_message(message.chat.id, "⏳ Нет заявок, ожидающих выплаты.")
        return
    
    text = f"⏳ **Ожидают выплаты ({len(claims)}):**\n\n"
    
    for i, claim in enumerate(claims, 1):
        username = f"@{claim['username']}" if claim['username'] else "без username"
        name = claim['first_name'] or ""
        created = claim['created_at']
        wallet = claim['wallet_address']
        
        text += f"{i}. {username} ({name})\n"
        text += f"   Кошелёк: {wallet}\n"
        text += f"   Создана: {created}\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(commands=["user"])
def admin_user(message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Использование: /user <tg_id>\nПример: /user 123456789")
        return
    
    try:
        tg_id = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, "❌ tg_id должен быть числом.")
        return
    
    info = db.get_user_full_info(tg_id)
    
    if not info:
        bot.send_message(message.chat.id, f"❌ Пользователь с ID {tg_id} не найден.")
        return
    
    username = f"@{info['username']}" if info['username'] else "без username"
    name = info['first_name'] or "без имени"
    
    from datetime import datetime
    
    created = info['created_at']
    days_in_bot = "неизвестно"
    if created:
        try:
            created_dt = datetime.fromisoformat(created)
            days_in_bot = (datetime.now() - created_dt).days
        except:
            pass
    
    last_active = info.get('last_active_at') or "никогда"
    facts = f"{info.get('facts_correct', 0)}/{info.get('facts_total', 0)}"
    quest = info.get('quest_completed', 0)
    myths = f"{info.get('myths_correct', 0)}/{info.get('myths_total', 0)}"
    words = f"{info.get('words_correct', 0)}/{info.get('words_total', 0)}"
    
    badges = info.get('badges', [])
    badges_text = ", ".join(badges) if badges else "нет"
    
    rewards = info.get('rewards', [])
    if rewards:
        rewards_text = "\n".join([
            f"  - {r['code']}: {r['status']} ({r['wallet_address']})"
            for r in rewards
        ])
    else:
        rewards_text = "нет"
    
    inviter = info.get('inviter_username') or "никто"
    referrals = info.get('referrals_count_actual', 0)
    
    text = (
        f"👤 **{username}** ({name})\n"
        f"ID: `{tg_id}`\n\n"
        f"📅 **Активность:**\n"
        f"• Дней в боте: {days_in_bot}\n"
        f"• Последний вход: {last_active}\n"
        f"• Daily Bonus серия: {info.get('daily_bonus_streak', 0)}\n\n"
        f" **Прогресс:**\n"
        f"• Факты: {facts}\n"
        f"• Квест шагов: {quest}\n"
        f"• Мифы: {myths}\n"
        f"• Слова: {words}\n"
        f"• Финальный тест: {'✅' if info.get('final_test_passed') else ''}\n\n"
        f"💎 **Баланс:**\n"
        f"• Кристаллы: {info.get('crystals', 0)}\n\n"
        f"🏆 **Награды:**\n"
        f"• Бейджи: {badges_text}\n"
        f"• Статус: {info.get('level', 'newbie')}\n"
        f"• Заявки:\n{rewards_text}\n\n"
        f"👥 **Рефералы:**\n"
        f"• Пригласил: {inviter}\n"
        f"• Приглашено: {referrals}\n\n"
        f"💳 **Кошельки:**\n"
        f"• PRIZM: {info.get('prizm_address') or 'не указан'}\n"
        f"• TON: {info.get('ton_wallet') or 'не указан'}"
    )
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(commands=["paid"])
def admin_paid(message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Использование: /paid <tg_id>\nПример: /paid 123456789")
        return
    
    try:
        tg_id = int(parts[1])
    except ValueError:
        bot.send_message(message.chat.id, " tg_id должен быть числом.")
        return
    
    info = db.get_user_full_info(tg_id)
    if not info:
        bot.send_message(message.chat.id, f"❌ Пользователь с ID {tg_id} не найден.")
        return
    
    marked = 0
    for reward in info.get('rewards', []):
        if reward['status'] == 'pending_manual':
            db.mark_reward_paid(tg_id, reward['code'])
            marked += 1
    
    if marked > 0:
        bot.send_message(message.chat.id, f"✅ Отмечено {marked} выплат(ы) для пользователя {tg_id}.")
        
        try:
            bot.send_message(
                tg_id,
                " Поздравляем! Ваша заявка на награду подтверждена. "
                "Средства будут отправлены в течение 24 часов."
            )
        except:
            pass
    else:
        bot.send_message(message.chat.id, f"⚠️ У пользователя {tg_id} нет заявок, ожидающих выплаты.")


@bot.message_handler(commands=["broadcast"])
def admin_broadcast(message):
    if not is_admin(message.from_user.id):
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        bot.send_message(
            message.chat.id,
            "Использование: /broadcast <фильтр> <текст>\n\n"
            "Фильтры:\n"
            "• all — всем пользователям\n"
            "• active — активные за 30 дней\n"
            "• quest_done — прошли квест\n"
            "• quest_not_done — не прошли квест\n"
            "• inactive — не заходили 7+ дней\n\n"
            "Пример: /broadcast active Привет! Напоминаем о боте."
        )
        return
    
    filter_type = parts[1]
    text = parts[2]
    
    valid_filters = ["all", "active", "quest_done", "quest_not_done", "inactive"]
    if filter_type not in valid_filters:
        bot.send_message(message.chat.id, f"❌ Неверный фильтр. Допустимые: {', '.join(valid_filters)}")
        return
    
    tg_ids = db.get_users_by_filter(filter_type)
    
    if not tg_ids:
        bot.send_message(message.chat.id, "❌ Нет пользователей по этому фильтру.")
        return
    
    sent = 0
    failed = 0
    
    for tg_id in tg_ids:
        try:
            bot.send_message(tg_id, text)
            sent += 1
        except:
            failed += 1
    
    bot.send_message(
        message.chat.id,
        f" Рассылка завершена!\n"
        f"• Отправлено: {sent}\n"
        f"• Ошибок: {failed}\n"
        f"• Всего: {len(tg_ids)}"
    )


@bot.message_handler(commands=["export"])
def admin_export(message):
    if not is_admin(message.from_user.id):
        return
    
    csv_data = db.export_to_csv()
    
    if not csv_data:
        bot.send_message(message.chat.id, " Нет данных для экспорта.")
        return
    
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_data)
        temp_path = f.name
    
    try:
        with open(temp_path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="📊 Экспорт данных бота")
    finally:
        os.unlink(temp_path)

    
# === КОНЕЦ: АДМИН-КОМАНД ===


def generate_captcha_question():
    """Генерирует простой математический пример и варианты ответов."""
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    correct = a + b
    
    wrong_options = set()
    while len(wrong_options) < 2:
        wrong = correct + random.choice([-2, -1, 1, 2])
        if wrong > 0 and wrong != correct:
            wrong_options.add(wrong)
    
    options = [correct] + list(wrong_options)
    random.shuffle(options)
    
    return {
        "text": f"Сколько будет {a} + {b}?",
        "correct": correct,
        "options": options,
    }


def send_captcha(chat_id):
    """Показывает пользователю новую капчу."""
    q = generate_captcha_question()
    bot.send_message(
        chat_id,
        f"{CAPTCHA_TEXT}\n\n<b>{q['text']}</b>",
        parse_mode="HTML",
        reply_markup=captcha_kb(q["correct"], q["options"]),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("captcha:"))
def handle_captcha(call):
    """Обрабатывает ответ на капчу."""
    parts = call.data.split(":")
    result = parts[1]
    correct_answer = int(parts[2])
    
    if result == "ok":
        # Правильный ответ — отмечаем, что капча пройдена
        db.set_captcha_passed(call.from_user.id)
        bot.answer_callback_query(call.id, "✅ Верно!")
        # Показываем приветственное сообщение с кнопкой получения награды
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=WELCOME_TEXT,
            parse_mode="HTML",
            reply_markup=claim_bonus_kb(),
        )

    else:
        bot.answer_callback_query(call.id, "Неверно, попробуй ещё раз")
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=CAPTCHA_FAIL_TEXT.format(correct=correct_answer),
            parse_mode="HTML",
        )
        import time
        time.sleep(1.5)
        send_captcha(call.message.chat.id)


if __name__ == "__main__":
    logging.info("Бот запускается...")
    
    # Настраиваем список команд для обычных пользователей
    bot.set_my_commands([
        types.BotCommand("start", "Начать общение с ботом"),
        types.BotCommand("menu", "Главное меню"),
        types.BotCommand("reset", "Сбросить прогресс и начать заново"),
        types.BotCommand("help", "Помощь и информация"),
        types.BotCommand("profile", "Мой профиль и баланс"),
        types.BotCommand("test", "Пройти финальный тест"),
    ])
    
    bot.infinity_polling()
