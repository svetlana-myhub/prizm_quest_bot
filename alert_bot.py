import os
import time
import base64
import requests
import threading
from datetime import datetime, timezone

import telebot
from telebot import types

import db
import chart

import sys
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

import logging                                  # ← НОВОЕ
logging.basicConfig(level=logging.INFO,         # ← НОВОЕ
                    stream=sys.stderr,
                    format="%(asctime)s %(message)s")
log = logging.info                              # ← НОВОЕ

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

import socket
from config import ADMIN_TG_IDS

from market import (TONAPI, PZM_JETTON, PZM_POOL, get_rates,
                    get_rub_rate, get_liquidity, rate_change_lines)


# === КОНФИГУРАЦИЯ ===
BUY_URL = "https://dedust.io/ru/swap/GRAM/EQDROsytSxLtDp_2pRIEainUGqZPRBbXkwayVn7VAT7bHHWL"

TONCENTER = "https://toncenter.com/api/v2"

DEFAULT_IMAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "alert_default.jpg")

ALERT_TOKEN = os.getenv("ALERT_BOT_TOKEN")
if not ALERT_TOKEN:
    raise RuntimeError("Не найден ALERT_BOT_TOKEN в .env")

bot = telebot.TeleBot(ALERT_TOKEN)

last_seen_ts = 0
waiting_photo = {}
domain_cache = {}  # {wallet_raw: (domain_or_None, timestamp)}
thread_prompt = {}
pending_thread = {}
pending_image_target = {}
holders_cache = {"counts": None, "ts": 0}
monitor_beat = {"ts": 0.0}


# ========== ДАННЫЕ ==========


def get_holders_counts():
    """Количество холдеров по категориям (кэш 10 минут)"""
    if holders_cache["counts"] is not None and time.time() - holders_cache["ts"] < 600:
        return holders_cache["counts"]
    try:
        r = requests.get(f"{TONAPI}/jettons/{PZM_JETTON}/holders?limit=1000", timeout=10).json()
        c = {"1-49": 0, "50": 0, "100": 0}
        for h in r.get("addresses", []):
            bal = int(h.get("balance", 0)) / 100
            if 1 <= bal <= 49:
                c["1-49"] += 1
            if bal >= 50:
                c["50"] += 1
            if bal >= 100:
                c["100"] += 1
        holders_cache["counts"] = c
        holders_cache["ts"] = time.time()
        return c
    except Exception as e:
        print(f"⚠️ Ошибка получения холдеров: {e}")
        return holders_cache["counts"]


def fill_holders(plain, html, counts, mode):
    """Подставить число холдеров нужной категории (или убрать строку)"""
    if counts:
        return (plain.replace("{HOLDERS}", str(counts.get(mode, "?"))),
                html.replace("{HOLDERS}", str(counts.get(mode, "?"))))
    drop = "👥 Holders: {HOLDERS}\n"
    return (plain.replace(drop, "").replace("👥 Holders: {HOLDERS}", ""),
            html.replace(drop, "").replace("👥 Holders: {HOLDERS}", ""))


def get_pool_reserves():
    try:
        payload = {"address": PZM_POOL, "method": "get_reserves", "stack": []}
        r = requests.post(f"{TONCENTER}/runGetMethod", json=payload, timeout=10).json()
        if r.get("ok"):
            stack = r["result"]["stack"]
            return int(stack[0][1], 16) / 1e9, int(stack[1][1], 16) / 100
    except Exception as e:
        log(f"⚠️ Ошибка резервов: {e}")
    return None, None


# ========== АДРЕСА ==========

def _crc16(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


def raw_to_friendly(raw: str) -> str:
    wc, hexpart = raw.split(":")
    body = bytes([0x51, int(wc) & 0xFF]) + bytes.fromhex(hexpart)
    crc = _crc16(body).to_bytes(2, "big")
    return base64.urlsafe_b64encode(body + crc).decode()


def short_addr(raw: str) -> str:
    try:
        f = raw_to_friendly(raw)
        return f[:6] + "..." + f[-4:]
    except Exception:
        return raw[:6] + "..." + raw[-4:]


def get_ton_domain(wallet_raw: str):
    """Получить TON-домен кошелька (кэш 1 час)"""
    if wallet_raw in domain_cache:
        domain, ts = domain_cache[wallet_raw]
        if time.time() - ts < 3600:
            return domain

    domain = None
    try:
        friendly = raw_to_friendly(wallet_raw)
        urls = [
            f"{TONAPI}/accounts/{friendly}/dns/backresolve",
            f"{TONAPI}/dns/backresolve/{friendly}",
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=5).json()
                domains = [d for d in (r.get("domains") or []) if isinstance(d, str)]
                if domains:
                    domain = domains[0]
                    break
            except Exception:
                continue
    except Exception:
        pass

    domain_cache[wallet_raw] = (domain, time.time())
    return domain


def display_wallet(wallet_raw: str) -> tuple:
    """Возвращает (отображаемый текст, HTML-ссылка)"""
    try:
        friendly = raw_to_friendly(wallet_raw)
        short = friendly[:6] + "..." + friendly[-4:]
        
        domain = get_ton_domain(wallet_raw)
        if domain:
            return domain, f'<a href="https://tonviewer.com/{friendly}">{domain}</a>'
        else:
            return short, f'<a href="https://tonviewer.com/{friendly}">{short}</a>'
    except Exception:
        return wallet_raw[:10] + "...", wallet_raw[:10] + "..."

def get_topic_name(chat_id, thread_id):
    """Название темы по служебному сообщению о её создании"""
    try:
        for m in bot.get_chat_history(chat_id, limit=200):
            if getattr(m, "message_thread_id", None) == thread_id and \
                    getattr(m, "message_forum_topic_created", None) is not None:
                return m.message_forum_topic_created.name
    except Exception as e:
        print(f"⚠️ Не удалось прочитать название темы: {e}")
    return None

# ========== ПОМОЩНИКИ ==========

def is_admin(chat_id, user_id):
    try:
        m = bot.get_chat_member(chat_id, user_id)
        return m.status in ("creator", "administrator")
    except Exception:
        return False


def fmt_num(x):
    return f"{x:,.2f}".replace(",", " ")

def fmt_token(x):
    s = f"{x:,.4f}".replace(",", " ")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s

def mthread(message):
    """ID темы, из которой пришло сообщение (None = главная)"""
    return getattr(message, "message_thread_id", None)


def settings_markup(row, target=None):
    suf = f":{target}" if target is not None else ""
    mark = types.InlineKeyboardMarkup()
    mark.add(types.InlineKeyboardButton(
        "✅ Сделки: вкл" if row["trades_on"] else "❌ Сделки: выкл",
        callback_data=f"alert_toggle{suf}"))
    f = row.get("trade_filter", "all")
    filter_labels = {"all": "Все", "buys": "Только покупки", "sells": "Только продажи"}
    mark.add(types.InlineKeyboardButton(
        f"🔍 Показывать: {filter_labels.get(f, 'Все')}", callback_data=f"alert_filter{suf}"))
    mark.add(types.InlineKeyboardButton(
        f"💰 Мин. объём: {fmt_num(row['min_volume_pzm'])} PZM", callback_data=f"alert_min{suf}"))
    mode = row.get("holders_mode") or "50"
    labels = {"1-49": "1-49 PZM", "50": "50+ PZM", "100": "100+ PZM"}
    mark.add(types.InlineKeyboardButton(
        f"👥 Холдеры: {labels.get(mode, '50+ PZM')}", callback_data=f"alert_holders{suf}"))
    thread = row.get("thread_id")
    if thread:
        tname = row.get("thread_title") or f"тема #{thread}"
        mark.add(types.InlineKeyboardButton(f"📌 Куда: {tname}", callback_data=f"alert_thread{suf}"))
    else:
        mark.add(types.InlineKeyboardButton("📌 Куда: главная тема", callback_data=f"alert_thread{suf}"))
    mark.add(types.InlineKeyboardButton("🖼 Картинка: сменить", callback_data=f"alert_img{suf}"))
    mark.add(types.InlineKeyboardButton("🖼 Картинка: сбросить", callback_data=f"alert_img_reset{suf}"))
    mark.add(types.InlineKeyboardButton("👀 Предпросмотр", callback_data=f"alert_preview{suf}"))
    mark.add(types.InlineKeyboardButton("📣 Тест оповещения в чате", callback_data=f"alert_test{suf}"))
    mark.add(types.InlineKeyboardButton(
        "🧹 Автоочистка: вкл" if row.get("autoclean") else "🧹 Автоочистка: выкл",
        callback_data=f"alert_clean{suf}"))
    mark.add(types.InlineKeyboardButton("🔕 Отключить оповещения", callback_data=f"alert_off{suf}"))
    return mark


def settings_text(row):
    img = "своя" if row.get("image_file_id") else "стандартная"
    return (f"⚙️ Настройки оповещений о сделках PZM\n\nЧат: {row['title']}\nКартинка: {img}\n"
            "Управляйте кнопками ниже.")


# ========== ОБРАБОТЧИКИ ==========

@bot.message_handler(commands=["start"], func=lambda m: m.chat.type == "private")
def start_private(message):
    bot.send_message(message.chat.id, (
        "👋 Привет! Я публикую сделки с Prizm (PZM) на DeDust в чаты и каналы.\n\n"
        "Как подключить:\n"
        "1️⃣ Добавьте меня в ваш чат или канал\n"
        "   (с правом «Публиковать сообщения» и «Удалять сообщения»)\n\n"
        "либо используйте команду /add — добавить бота в группу "
        "(нужные права выбираются автоматически)\n\n"
        "2️⃣ Отправьте в чате /alert — я открою настройки\n"
        "   (настраивают только администраторы чата)\n\n"
        "либо отправьте в боте /chats — я настрою ваши чаты и каналы, "
        "к которым подключен бот как администратор\n\n"
        "Мои команды:\n"
        "/rate — текущий курс PZM\n"
        "/chart — график курса картинкой: 3 валюты × 6 периодов\n"
        "/calc — калькулятор PRIZM: пересчёт любой суммы в USDT, GRAM и RUB\n"        
        "/stats — статистика сделок по периодам\n"
        "/alert — настройки оповещений\n"
        "/add — добавить бота в группу\n"
        "/chats — мои чаты и каналы: настройки\n"
        "/testalert — тестовое сообщение с картинкой"))


@bot.message_handler(commands=["add"])
def add_cmd(message):
    bot_name = "swap_pzm_bot"
    link = (f"https://t.me/{bot_name}?startgroup=true"
            "&admin=change_info+delete_messages+pin_messages")
    text = (
        f"➕ <b>Добавить меня в группу</b>\n\n"
        f"Нажмите ссылку ниже — откроется список ваших групп. "
        f"Выберите нужную, и я подключусь с нужными правами автоматически.\n\n"
        f"<a href=\"{link}\">👉 Добавить бота в группу</a>"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML",
                     message_thread_id=mthread(message))
    

@bot.message_handler(commands=["rate"])
def rate_cmd(message):
    pzm_usd, ton_usd, diff24 = get_rates()
    rub = get_rub_rate()
    pzm_gram = pzm_usd / ton_usd if ton_usd else None
    lines = ["📈 <b>Текущий курс PZM:</b>\n"]
    lines.append(f"💲 $ {pzm_usd:.6f} USDT")
    if pzm_gram:
        lines.append(f"💎 {pzm_gram:.6f} GRAM")
    if rub:
        lines.append(f"💸 ₽ {pzm_usd * rub:.4f} RUB")
    lines.append("\n📊 <b>Изменение курса в 💲:</b>")
    lines.append(f"24 часа: {diff24}")
    for label, pct in rate_change_lines(pzm_usd):
        if pct is None:
            lines.append(f"{label}: — (история копится)")
        else:
            lines.append(f"{label}: {pct:+.2f}%")
    pzm_liq, gram_liq = get_liquidity()
    if pzm_liq:
        lines.append(f"\n💰 <b>Ликвидность пула:</b>\n"
                     f"{fmt_num(pzm_liq)} PZM / {fmt_num(gram_liq)} GRAM")
    mark = types.InlineKeyboardMarkup()
    mark.add(types.InlineKeyboardButton("📊 График курса",
                                        callback_data="chartopen:usd:7d"))
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode="HTML",
                     reply_markup=mark,
                     message_thread_id=getattr(message, "message_thread_id", None))


@bot.message_handler(commands=["chart"])
def chart_cmd(message):
    chart.show_chart(bot, message.chat.id, "usd", "7d",
                     thread=getattr(message, "message_thread_id", None))


@bot.callback_query_handler(func=lambda c: c.data.startswith("chartopen:"))
def chart_open_cb(call):
    _, cur, period = call.data.split(":")
    chart.show_chart(bot, call.message.chat.id, cur, period, call=call,
                     thread=getattr(call.message, "message_thread_id", None))


@bot.callback_query_handler(func=lambda c: c.data.startswith("chart:"))
def chart_cb(call):
    parts = call.data.split(":")
    if len(parts) == 4:                     # новые кнопки с суммой
        _, cur, period, amt = parts
        amount = float(amt)
    else:                                   # старые кнопки без суммы
        _, cur, period = parts
        amount = 100
    chart.show_chart(bot, call.message.chat.id, cur, period,
                     edit_msg_id=call.message.message_id, call=call,
                     thread=getattr(call.message, "message_thread_id", None),
                     amount=amount)


@bot.message_handler(commands=["calc"])
def calc_cmd(message):
    CALC_WAIT[message.from_user.id] = (
        message.chat.id, "usd", "7d",
        getattr(message, "message_thread_id", None))
    bot.send_message(message.chat.id,
                     "🔢 Введите количество PZM для расчёта (только число).\n"
                     "Отмена — /cancel",
                     message_thread_id=getattr(message, "message_thread_id", None))    


CALC_WAIT = {}


@bot.callback_query_handler(func=lambda c: c.data.startswith("chartcalc:"))
def chart_calc_cb(call):
    _, cur, period = call.data.split(":")
    thread = getattr(call.message, "message_thread_id", None)
    CALC_WAIT[call.from_user.id] = (call.message.chat.id, cur, period, thread)
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id,
                     "🔢 Введите количество PZM для расчёта (только число)\n"
                     "Отмена — /cancel",
                     message_thread_id=thread)


@bot.message_handler(commands=["cancel"])
def cancel_cmd(message):
    CALC_WAIT.pop(message.from_user.id, None)
    bot.send_message(message.chat.id, "↩️ Отменено.",
                     message_thread_id=getattr(message, "message_thread_id", None))


@bot.message_handler(func=lambda m: m.content_type == "text"
                     and m.from_user.id in CALC_WAIT)
def calc_input(message):
    st = CALC_WAIT.pop(message.from_user.id, None)
    if not st:
        return
    chat_id, cur, period, thread = st
    try:
        amount = float(message.text.replace(",", ".").strip())
        if amount <= 0:
            raise ValueError
    except Exception:
        CALC_WAIT[message.from_user.id] = st
        bot.send_message(message.chat.id,
                         "⚠️ Нужно число, например 1000. Ещё раз или /cancel.",
                         message_thread_id=thread)
        return
    chart.show_chart(bot, chat_id, cur, period, amount=amount, thread=thread)


@bot.message_handler(commands=["alert"])
def alert_cmd(message):
    chat = message.chat
    if chat.type in ("group", "supergroup", "channel"):
        if not is_admin(chat.id, message.from_user.id):
            bot.reply_to(message, "⚙️ Настраивать оповещения могут только администраторы чата.")
            return
    row = db.alert_get(chat.id)
    if row is None:
        db.alert_upsert(chat.id, chat.title or "Личный чат", chat.type)
        row = db.alert_get(chat.id)
    bot.send_message(chat.id, settings_text(row), reply_markup=settings_markup(row), message_thread_id=mthread(message))


def make_sample():
    pzm_usd, ton_usd, diff = get_rates()
    now = datetime.now(timezone.utc).strftime("%d.%m %H:%M UTC")
    return (
        "🟢 Покупка PZM на DeDust (превью)\n"
        f"🟣 1 000.00 PZM (~${1000 * pzm_usd:.2f})\n"
        "💎 Заплачено: 0.72 GRAM\n"
        "👛 Покупатель: alice.ton\n"
        "🔗 Txn: 4b2c7780...793494\n"
        "👥 Holders: {HOLDERS}\n"
        f"📈 Курс PZM: ${pzm_usd:.6f}\n"
        f"📊 24ч: {diff}\n"
        f"🕒 {now}"
    )

@bot.message_handler(commands=["chats"], func=lambda m: m.chat.type != "private")
def chats_cmd_group(message):
    bot.send_message(message.chat.id,
                     "ℹ️ Команда /chats работает в личной переписке с ботом.",
                     message_thread_id=mthread(message))

@bot.message_handler(commands=["chats"], func=lambda m: m.chat.type == "private")
def chats_cmd(message):
    items = []
    for r in db.alert_get_all():
        if r["chat_type"] == "private":
            continue
        try:
            m = bot.get_chat_member(r["chat_id"], message.from_user.id)
        except Exception:
            continue
        if m.status in ("creator", "administrator"):
            items.append(r)
    if not items:
        bot.send_message(message.chat.id,
                         "Не нашел чатов и каналов, где вы админ и я подключён.\n"
                         "Добавьте меня через /add или через администраторов канала.")
        return
    mark = types.InlineKeyboardMarkup()
    for r in items:
        icon = "📢" if r["chat_type"] == "channel" else "👥"
        mark.add(types.InlineKeyboardButton(f"{icon} {r['title']}",
                                            callback_data=f"chat:{r['chat_id']}"))
    bot.send_message(message.chat.id,
                     "Ваши чаты и каналы — выберите для настройки:", reply_markup=mark)


@bot.message_handler(commands=["testalert"])
def test_alert(message):
    chat = message.chat
    if chat.type in ("group", "supergroup", "channel"):
        if not is_admin(chat.id, message.from_user.id):
            return
    row = db.alert_get(chat.id)
    if row is None:
        db.alert_upsert(chat.id, chat.title or "Личный чат", chat.type)
        row = db.alert_get(chat.id)
    sample = make_sample()
    counts = get_holders_counts()
    sample, _ = fill_holders(sample, sample, counts, row.get("holders_mode") or "50")
    send_alert(row, sample, sample, is_buy=True,
               thread_override=mthread(message), trade=True)


STAT_PERIODS = {"today": "сегодня", "7d": "7 дней", "30d": "30 дней",
                "180d": "6 месяцев", "365d": "1 год", "all": "всё время"}
STAT_SIDES = {"all": "все сделки", "buys": "только покупки", "sells": "только продажи"}


def stats_markup(period, side):
    mark = types.InlineKeyboardMarkup()
    mark.row(*[types.InlineKeyboardButton(("✅ " if p == period else "") + lb,
                                          callback_data=f"stats:{p}:{side}")
               for p, lb in (("today", "Сегодня"), ("7d", "7 дней"), ("30d", "30 дней"))])
    mark.row(*[types.InlineKeyboardButton(("✅ " if p == period else "") + lb,
                                          callback_data=f"stats:{p}:{side}")
               for p, lb in (("180d", "6 мес"), ("365d", "1 год"), ("all", "Всё время"))])
    mark.row(*[types.InlineKeyboardButton(("✅ " if s == side else "") + lb,
                                          callback_data=f"stats:{period}:{s}")
               for s, lb in (("all", "Все"), ("buys", "🟢 Покупки"), ("sells", "🔴 Продажи"))])
    return mark


def show_stats(chat_id, period, side, thread=None, call=None):
    now = int(time.time())
    if period == "today":
        dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        ts0 = int(dt.timestamp())
    elif period == "all":
        ts0 = 0
    else:
        days = {"7d": 7, "30d": 30, "180d": 180, "365d": 365}[period]
        ts0 = now - days * 86400
    rows = db.trades_since(ts0, side)
    title = f"📊 <b>Статистика: {STAT_PERIODS[period]}</b> ({STAT_SIDES[side]})"
    if not rows:
        text = title + "\n\nПока нет сделок за период — журнал только начал копить историю."
    else:
        n = len(rows)
        buys = sum(r[1] for r in rows)
        sells = n - buys
        vol_pzm = sum(r[2] for r in rows)
        vol_usd = sum(r[3] for r in rows)
        maxr = max(rows, key=lambda r: r[2])
        parts = [f"Сделок: <b>{n}</b>"]
        if side == "all":
            g = round(buys / n * 10)
            parts.append(f"🟢 {buys} / 🔴 {sells}")
            parts.append("🟩" * g + "🟥" * (10 - g))
        parts.append(f"Объём: <b>{fmt_num(vol_pzm)} PZM</b> (~${vol_usd:.2f})")
        parts.append(f"Крупнейшая: {fmt_num(maxr[2])} PZM ({'🟢' if maxr[1] else '🔴'})")
        parts.append(f"Средняя: {fmt_num(vol_pzm / n)} PZM")
        text = title + "\n\n" + "\n".join(parts)
    mark = stats_markup(period, side)
    if call:
        try:
            bot.edit_message_text(text, chat_id, call.message.message_id,
                                  parse_mode="HTML", reply_markup=mark)
        except Exception:
            pass
        bot.answer_callback_query(call.id)
    else:
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=mark,
                         message_thread_id=thread)


@bot.message_handler(commands=["stats"])
def stats_cmd(message):
    show_stats(message.chat.id, "7d", "all", thread=mthread(message))


@bot.callback_query_handler(func=lambda c: c.data.startswith("stats:"))
def stats_cb(call):
    _, period, side = call.data.split(":")
    show_stats(call.message.chat.id, period, side, call=call)


@bot.callback_query_handler(func=lambda c: c.data.startswith("alert_") or c.data.startswith("chat:"))
def alert_callbacks(call):
    data = call.data

    # Выбор чата из личного списка
    if data.startswith("chat:"):
        target = int(data[5:])
        row = db.alert_get(target)
        if row is None or not is_admin(target, call.from_user.id):
            bot.answer_callback_query(call.id, "Недоступно.")
            return
        bot.send_message(call.message.chat.id, settings_text(row),
                         reply_markup=settings_markup(row, target))
        bot.answer_callback_query(call.id)
        return

    action, _, tid = data.partition(":")
    if tid:
        cid = int(tid)
        if not is_admin(cid, call.from_user.id):
            bot.answer_callback_query(call.id, "Только администраторы чата.")
            return
    else:
        cid = call.message.chat.id
        if call.message.chat.type in ("group", "supergroup", "channel"):
            if not is_admin(cid, call.from_user.id):
                bot.answer_callback_query(call.id, "Только администраторы чата.")
                return

    row = db.alert_get(cid)
    if row is None:
        bot.answer_callback_query(call.id, "Чат не подключён.")
        return

    if action == "alert_toggle":
        db.alert_toggle(cid)
    elif action == "alert_filter":
        current = row.get("trade_filter", "all")
        cycle = {"all": "buys", "buys": "sells", "sells": "all"}
        db.alert_set_filter(cid, cycle.get(current, "all"))
    elif action == "alert_min":
        steps = [0, 1000, 10000, 50000]
        cur = row["min_volume_pzm"]
        nxt = steps[(steps.index(cur) + 1) % len(steps)] if cur in steps else 0
        db.alert_set_min(cid, nxt)
    elif action == "alert_holders":
        cycle = {"1-49": "50", "50": "100", "100": "1-49"}
        db.alert_set_holders_mode(cid, cycle.get(row.get("holders_mode") or "50", "50"))
    elif action == "alert_thread":
        if tid:
            bot.answer_callback_query(call.id, "Настройка тем доступна через /alert внутри группы.")
            return
        try:
            chat_info = bot.get_chat(cid)
        except Exception:
            chat_info = None
        if chat_info is None or not getattr(chat_info, "is_forum", False):
            bot.answer_callback_query(call.id, "В этом чате нет тем — оповещения идут в главную тему.")
            return
        waiting_photo[cid] = "thread_pick"
        mark = types.InlineKeyboardMarkup()
        mark.add(types.InlineKeyboardButton("❌ Отмена", callback_data="thread_cancel"))
        sent = bot.send_message(
            cid,
            "✍️ Напишите любое сообщение в нужной теме, куда должны приходить "
            "оповещения о сделках — я запомню её 📌\n"
            "По умолчанию оповещения приходят в главную тему.",
            reply_markup=mark,
            message_thread_id=mthread(call.message))
        thread_prompt[cid] = sent.message_id
        bot.answer_callback_query(call.id)
        return
    elif action == "alert_img":
        waiting_photo[call.message.chat.id] = True
        pending_image_target[call.message.chat.id] = int(tid) if tid else None
        bot.send_message(call.message.chat.id,
                         "🖼 Пришлите фото обычным сообщением — я сохраню его для оповещений.")
        bot.answer_callback_query(call.id)
        return
    elif action == "alert_img_reset":
        db.alert_reset_image(cid)
    elif action == "alert_preview":
        sample = make_sample()
        counts = get_holders_counts()
        sample, _ = fill_holders(sample, sample, counts, row.get("holders_mode") or "50")
        try:
            send_preview(call.message.chat.id, mthread(call.message), row, sample)
            bot.answer_callback_query(call.id, "Вот как будет выглядеть оповещение.")
        except Exception as e:
            print(f"⚠️ Не удалось показать предпросмотр: {e}")
            bot.answer_callback_query(call.id, "Не удалось показать предпросмотр.")
        return        
    elif action == "alert_test":
        sample = make_sample()
        counts = get_holders_counts()
        sample, _ = fill_holders(sample, sample, counts, row.get("holders_mode") or "50")
        send_alert(row, sample, sample, True, trade=True)
        bot.answer_callback_query(call.id, "Отправлено!")
        return
    elif action == "alert_clean":
        db.alert_set_autoclean(cid, not row.get("autoclean"))
    elif action == "alert_off":
        db.alert_remove(cid)
        bot.answer_callback_query(call.id, "Оповещения отключены.")
        try:
            bot.edit_message_text("🔕 Оповещения отключены для этого чата. Вернуть: /alert или /chats",
                                  call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        return

    row = db.alert_get(cid)
    try:
        bot.edit_message_text(settings_text(row), call.message.chat.id, call.message.message_id,
                              reply_markup=settings_markup(row, int(tid) if tid else None))
    except Exception:
        pass
    bot.answer_callback_query(call.id, "Обновлено")


@bot.callback_query_handler(func=lambda c: c.data == "thread_cancel")
def thread_cancel(call):
    chat = call.message.chat
    waiting_photo.pop(chat.id, None)
    msg_id = thread_prompt.pop(chat.id, None)
    if msg_id:
        try:
            bot.delete_message(chat.id, msg_id)
        except Exception:
            pass
    bot.answer_callback_query(call.id, "Отменено.")


@bot.message_handler(content_types=["text"],
                     func=lambda m: waiting_photo.get(m.chat.id) == "thread_pick")
def pick_thread(message):
    chat = message.chat
    if chat.type in ("group", "supergroup") and not is_admin(chat.id, message.from_user.id):
        return
    msg_id = thread_prompt.pop(chat.id, None)
    if msg_id:
        try:
            bot.delete_message(chat.id, msg_id)
        except Exception:
            pass
    thread_id = mthread(message)
    if not thread_id:
        db.alert_reset_thread(chat.id)
        waiting_photo.pop(chat.id, None)
        bot.send_message(chat.id, "✅ Оповещения будут приходить в главную тему.")
        return
    title = get_topic_name(chat.id, thread_id)
    db.alert_set_thread(chat.id, thread_id, title)
    if title:
        waiting_photo.pop(chat.id, None)
        bot.send_message(chat.id, f"✅ Оповещения будут приходить в тему «{title}».",
                         message_thread_id=thread_id)
    else:
        pending_thread[chat.id] = thread_id
        waiting_photo[chat.id] = "thread_name"
        bot.send_message(chat.id,
                         "Название темы не нашлось автоматически (создана давно).\n"
                         "✍️ Пришлите одним сообщением название темы для меню:",
                         message_thread_id=thread_id)


@bot.message_handler(content_types=["text"],
                     func=lambda m: waiting_photo.get(m.chat.id) == "thread_name")
def save_thread_name(message):
    chat = message.chat
    if chat.type in ("group", "supergroup") and not is_admin(chat.id, message.from_user.id):
        return
    thread_id = pending_thread.pop(chat.id, None)
    waiting_photo.pop(chat.id, None)
    if thread_id is None:
        return
    title = message.text.strip()[:64]
    db.alert_set_thread_title(chat.id, title)
    bot.send_message(chat.id, f"✅ Сохранено: оповещения в тему «{title}».",
                     message_thread_id=thread_id)
    

@bot.message_handler(content_types=["photo"])
def save_photo(message):
    chat = message.chat
    if waiting_photo.get(chat.id) is not True:
        return
    target = pending_image_target.pop(chat.id, None) or chat.id
    waiting_photo.pop(chat.id, None)
    if target != chat.id:
        if not is_admin(target, message.from_user.id):
            return
    elif chat.type in ("group", "supergroup", "channel"):
        if not is_admin(chat.id, message.from_user.id):
            return
    fid = message.photo[-1].file_id
    db.alert_set_image(target, fid)
    bot.send_message(chat.id, "🖼 Картинка сохранена! Теперь оповещения будут приходить с ней.")


@bot.my_chat_member_handler()
def my_chat_member(update):
    chat = update.chat
    status = update.new_chat_member.status
    print(f"📥 my_chat_member: chat={chat.id} type={chat.type} status={status}")
    if status in ("member", "administrator"):
        if chat.type == "private":
            db.alert_upsert(chat.id, chat.title or "Личный чат", chat.type, trades_on=0)
        else:
            try:
                db.alert_upsert(chat.id, chat.title or "Чат", chat.type)
            except Exception as e:
                print(f"⚠️ Не удалось записать чат в базу: {e}")
            try:
                bot.send_message(chat.id, (
                    "👋 Я подключён! Буду публиковать здесь сделки с PZM на DeDust.\n\n"
                    "Администраторы: /alert — настройки, /testalert — проверка."))
            except Exception as e:
                print(f"⚠️ Не удалось поприветствовать: {e}")
    elif status in ("left", "kicked"):
        db.alert_remove(chat.id)


# ========== СДЕЛКИ И РАССЫЛКА ==========

def parse_trade(event):
    """Возвращает (простой текст, HTML-текст, количество PZM, is_buy) или (None, None, 0, False)"""
    for action in event.get("actions", []):
        if action["type"] not in ("JettonSwap", "Swap"):
            continue
        swap = action.get("JettonSwap") or action.get("Swap") or {}
        if swap.get("dex") != "dedust":
            continue
        mi = swap.get("jetton_master_in") or {}
        mo = swap.get("jetton_master_out") or {}
        sym_in = mi.get("symbol", "GRAM")
        sym_out = mo.get("symbol", "GRAM")
        if "PZM" not in (sym_in, sym_out):
            continue

        amount_in = swap.get("amount_in")
        amount_out = swap.get("amount_out")
        dec = {"PZM": 2, "GRAM": 9, "TON": 9, "USD₮": 6, "USDT": 6}
        is_buy = sym_out == "PZM"
        
        if is_buy:
            pzm_amount = int(amount_out or 0) / 10 ** dec.get(sym_out, 0)
            other_sym, other_raw = sym_in, amount_in
        else:
            pzm_amount = int(amount_in or 0) / 10 ** dec.get(sym_in, 0)
            other_sym, other_raw = sym_out, amount_out
        
        other_amount = int(other_raw) / 10 ** dec.get(other_sym, 0) if other_raw else None

        pzm_usd, ton_usd, diff = get_rates()
        usd_value = pzm_amount * pzm_usd
        if other_amount is None and other_sym in ("GRAM", "TON"):
            other_amount = usd_value / ton_usd if ton_usd else 0

        wallet = (swap.get("user_wallet") or {}).get("address", "")
        time_str = datetime.fromtimestamp(event["timestamp"], tz=timezone.utc).strftime("%d.%m %H:%M UTC")

        head = "🟢 Покупка PZM на DeDust" if is_buy else "🔴 Продажа PZM на DeDust"
        plain = [head, f"🟣 {fmt_token(pzm_amount)} PZM (~${usd_value:.2f})"]
        html = list(plain)

        # Эмодзи оплаты зависит от токена
        pay_emoji = {"GRAM": "💎", "TON": "💎", "USD₮": "💲", "USDT": "💲"}.get(other_sym, "💵")
        if other_amount is not None:
            verb = "Заплачено" if is_buy else "Получено"
            line = f"{pay_emoji} {verb}: {fmt_token(other_amount)} {other_sym}"
            plain.append(line)
            html.append(line)
        
        if wallet:
            who = "Покупатель" if is_buy else "Продавец"
            display_text, html_link = display_wallet(wallet)
            plain.append(f"👛 {who}: {display_text}")
            html.append(f"👛 {who}: {html_link}")
        
        # Ссылка на транзакцию
        event_id = event.get("event_id", "")
        if event_id:
            txn_url = f"https://tonviewer.com/transaction/{event_id}"
            plain.append(f"🔗 Txn: {event_id[:8]}...{event_id[-6:]}")
            html.append(f'🔗 Txn: <a href="{txn_url}">{event_id[:8]}...{event_id[-6:]}</a>')

        plain.append("👥 Holders: {HOLDERS}")
        html.append("👥 Holders: {HOLDERS}")

        line = f"📈 Курс PZM: ${pzm_usd:.6f}"
        plain.append(line)
        html.append(line)
        
        line = f"📊 24ч: {diff}"
        plain.append(line)
        html.append(line)
        
        line = f"🕒 {time_str}"
        plain.append(line)
        html.append(line)
        
        meta = {"ts": event.get("timestamp", int(time.time())), "is_buy": is_buy,
                "pzm": pzm_amount, "other_sym": other_sym,
                "other_amount": other_amount, "usd": pzm_amount * pzm_usd,
                "event_id": event.get("event_id", "")}
        return "\n".join(plain), "\n".join(html), pzm_amount, is_buy, meta
    
    return None, None, 0, False, {}


CHANNEL_URL = "https://t.me/prizm"


def send_alert(row, plain, html, is_buy, thread_override="default", trade=False):
    img = row.get("image_file_id")
    thread_id = row.get("thread_id") if thread_override == "default" else thread_override

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🟣 Купить PZM", url=BUY_URL))
    markup.add(types.InlineKeyboardButton("📢 Канал PRIZM", url=CHANNEL_URL))
    markup.add(types.InlineKeyboardButton("📊 График курса",
                                          callback_data="chartopen:usd:24h"))


    # Автоочистка: удаляем предыдущее оповещение перед новым
    if trade and row.get("autoclean"):
        old = row.get("last_alert_msg_id")
        if old:
            try:
                bot.delete_message(row["chat_id"], old)
            except Exception:
                pass

    def _send(thread):
        if img:
            return bot.send_photo(row["chat_id"], img, caption=html, parse_mode="HTML",
                                  reply_markup=markup, message_thread_id=thread)
        elif os.path.exists(DEFAULT_IMAGE):
            with open(DEFAULT_IMAGE, "rb") as f:
                return bot.send_photo(row["chat_id"], f, caption=html, parse_mode="HTML",
                                      reply_markup=markup, message_thread_id=thread)
        else:
            return bot.send_message(row["chat_id"], html, parse_mode="HTML",
                                    reply_markup=markup, message_thread_id=thread)

    msg = None
    try:
        msg = _send(thread_id)
    except Exception as e:
        if thread_id:
            # Тема удалена/недоступна — шлём в общую ленту и сбрасываем настройку
            log(f"⚠️ Тема {thread_id} недоступна в {row['chat_id']}: {e} — шлю в общую ленту")
            db.alert_reset_thread(row["chat_id"])
            try:
                msg = _send(None)
            except Exception as e2:
                e = e2
                msg = None
        if msg is None:
            err = str(e).lower()
            fatal = any(k in err for k in ("kicked", "not a member",
                                           "chat not found", "bot was blocked",
                                           "group chat was upgraded"))
            if fatal:
                log(f"🗑 Чат {row['chat_id']} недоступен навсегда ({e}) — убираю из базы")
                db.alert_remove(row["chat_id"])
                for aid in ADMIN_TG_IDS:
                    try:
                        bot.send_message(aid, f"🗑 Чат {row['chat_id']} "
                                         f"({row.get('title')}) удалён из настроек: {e}")
                    except Exception:
                        pass
            else:
                log(f"⚠️ Временная ошибка отправки в {row['chat_id']}: {e} — чат оставляю, пропуск")
            return

    if trade:
        db.alert_set_last_msg(row["chat_id"], msg.message_id)


def send_preview(chat_id, thread_id, row, text):
    """Показать превью там, где идёт настройка (НЕ в целевой чат)"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🟣 Купить PZM", url=BUY_URL))
    markup.add(types.InlineKeyboardButton("📢 Канал PRIZM", url=CHANNEL_URL))
    img = row.get("image_file_id")
    if img:
        bot.send_photo(chat_id, img, caption=text, parse_mode="HTML",
                       reply_markup=markup, message_thread_id=thread_id)
    elif os.path.exists(DEFAULT_IMAGE):
        with open(DEFAULT_IMAGE, "rb") as f:
            bot.send_photo(chat_id, f, caption=text, parse_mode="HTML",
                           reply_markup=markup, message_thread_id=thread_id)
    else:
        bot.send_message(chat_id, text, parse_mode="HTML",
                         reply_markup=markup, message_thread_id=thread_id)
        

def notify_admin(text):
    for uid in ADMIN_TG_IDS:
        try:
            bot.send_message(uid, text)
        except Exception as e:
            print(f"⚠️ Не удалось уведомить админа {uid}: {e}")


def safe_monitor():
    while True:
        try:
            monitor_trades()
        except Exception as e:
            notify_admin(f"🔴 Монитор сделок упал: {e}. Перезапуск через 15 сек...")
            time.sleep(15)


def broadcast(plain, html, pzm_amount, is_buy):
    counts = get_holders_counts()
    for row in db.alert_get_enabled():
        if pzm_amount < row["min_volume_pzm"]:
            continue
        f = row.get("trade_filter", "all")
        if f == "buys" and not is_buy:
            continue
        if f == "sells" and is_buy:
            continue
        p2, h2 = fill_holders(plain, html, counts, row.get("holders_mode") or "50")
        send_alert(row, p2, h2, is_buy, trade=True)


def monitor_trades():
    global last_seen_ts
    log("🚀 Монитор сделок запущен...")
    try:
        r = requests.get(f"{TONAPI}/accounts/{PZM_POOL}/events?limit=10", timeout=10).json()
        events = r.get("events", [])
        if events:
            last_seen_ts = max(e["timestamp"] for e in events)
    except Exception as e:
        log(f"⚠️ Ошибка инициализации: {e}")

    fails = 0
    while True:
        monitor_beat["ts"] = time.time()
        try:
            r = requests.get(f"{TONAPI}/accounts/{PZM_POOL}/events?limit=20", timeout=10).json()
            events = r.get("events", [])
            new_events = [e for e in events if e["timestamp"] > last_seen_ts]
            for event in sorted(new_events, key=lambda e: e["timestamp"]):
                plain, html, pzm_amount, is_buy, meta = parse_trade(event)
                if plain:
                    db.trade_log(meta["ts"], meta["is_buy"], meta["pzm"],
                                 meta["other_sym"], meta["other_amount"], meta["usd"],
                                 meta["event_id"])
                    log(plain)
                    broadcast(plain, html, pzm_amount, is_buy)
            if events:
                last_seen_ts = max(e["timestamp"] for e in events)
        except requests.exceptions.ConnectionError:
            fails += 1
            log(f"⚠️ Нет связи с tonapi.io (попытка {fails}). Жду...")
            time.sleep(15 if fails < 3 else 60)
            continue
        except Exception as e:
            fails += 1
            log(f"❌ Ошибка мониторинга: {e}")
            time.sleep(15 if fails < 3 else 60)
            continue
        fails = 0
        time.sleep(30)


def rate_snapshot_loop():
    while True:
        try:
            pzm_usd, ton_usd, _ = get_rates()
            if pzm_usd:
                db.rate_snapshot_put(int(time.time()), pzm_usd, ton_usd)
        except Exception as e:
            print(f"⚠️ Снапшот курса: {e}")
        time.sleep(3600)


def start_alert_bot():
    """Точка входа: монитор + поллинг бота (для WSGI)"""
    try:
        private_cmds = [
            types.BotCommand("start", "о боте и как подключить"),
            types.BotCommand("rate", "текущий курс PZM"),
            types.BotCommand("chart", "график курса картинкой"),
            types.BotCommand("calc", "калькулятор PRIZM"),            
            types.BotCommand("stats", "статистика сделок по периодам"),
            types.BotCommand("alert", "настройки оповещений"),
            types.BotCommand("add", "добавить бота в группу"),
            types.BotCommand("chats", "мои чаты и каналы: настройки"),
            types.BotCommand("testalert", "тестовое сообщение с картинкой"),
        ]
        group_cmds = [
            types.BotCommand("rate", "текущий курс PZM"),
            types.BotCommand("chart", "график курса картинкой"),
            types.BotCommand("calc", "калькулятор PRIZM"),            
            types.BotCommand("stats", "статистика сделок по периодам"),
            types.BotCommand("alert", "настройки оповещений"),
            types.BotCommand("add", "добавить бота в группу"),
            types.BotCommand("testalert", "тестовое сообщение с картинкой"),
        ]
        bot.set_my_commands(private_cmds, scope=types.BotCommandScopeAllPrivateChats())
        bot.set_my_commands(group_cmds, scope=types.BotCommandScopeAllGroupChats())
    except Exception as e:
        print(f"⚠️ Не удалось задать меню команд: {e}") 
    db.init_alert_chats()
    threading.Thread(target=safe_monitor, daemon=True, name="alert_monitor").start()
    db.init_trades()
    threading.Thread(target=rate_snapshot_loop, daemon=True, name="rate_snapshotter").start()
    notify_admin(f"🟢 Алерт-бот запущен (машина: {socket.gethostname()})")
    fails = 0    
    while True:
        started = time.time()
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=10,
                                 allowed_updates=["message", "callback_query", "my_chat_member"])
        except Exception as e:
            fails += 1
            if fails in (5, 20, 50):
                notify_admin(f"🔴 Алерт-бот: {fails} попыток переподключения подряд. Ошибка: {e}")
            print(f"⚠️ Поллинг упал: {e}. Перезапуск через 10 сек...")
            time.sleep(10)
            continue
        if fails >= 5:
            notify_admin("🟢 Алерт-бот: поллинг восстановлен")
        fails = 0
        if time.time() - started < 5:
            print("🛑 Поллинг остановлен оператором. Завершаем работу.")
            break
        print("⚠️ Поллинг завершился сам. Перезапуск через 10 сек...")
        time.sleep(10)


if __name__ == "__main__":
    log("🚀 Prizm Alert Bot (v4 — картинки и адреса)")
    log("=" * 55)
    start_alert_bot()