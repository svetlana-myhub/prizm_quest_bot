import os
import time
import base64
import requests
import threading
from datetime import datetime, timezone

import telebot
from telebot import types

import db

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

# === КОНФИГУРАЦИЯ ===
PZM_POOL = "EQAa6k6QZCq87DyyrnIZQOZsP8xF7B3gOMKXvHD7r-pevSub"
BUY_URL = "https://dedust.io/ru/swap/GRAM/EQDROsytSxLtDp_2pRIEainUGqZPRBbXkwayVn7VAT7bHHWL"
PZM_JETTON = "EQDROsytSxLtDp_2pRIEainUGqZPRBbXkwayVn7VAT7bHHWL"

TONAPI = "https://tonapi.io/v2"
TONCENTER = "https://toncenter.com/api/v2"

DEFAULT_IMAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "alert_default.jpg")

ALERT_TOKEN = os.getenv("ALERT_BOT_TOKEN")
if not ALERT_TOKEN:
    raise RuntimeError("Не найден ALERT_BOT_TOKEN в .env")

bot = telebot.TeleBot(ALERT_TOKEN)

last_seen_ts = 0
rates_cache = {"pzm_usd": 0.0013, "ton_usd": 1.36, "diff_24h": "—", "ts": 0}
waiting_photo = {}
domain_cache = {}  # {wallet_raw: (domain_or_None, timestamp)}

# ========== ДАННЫЕ ==========

def get_rates():
    global rates_cache
    if time.time() - rates_cache["ts"] < 60:
        return rates_cache["pzm_usd"], rates_cache["ton_usd"], rates_cache["diff_24h"]
    try:
        url = f"{TONAPI}/rates?tokens=ton,{PZM_JETTON}&currencies=usd"
        r = requests.get(url, timeout=10).json()
        pzm = r["rates"][PZM_JETTON]["prices"]["USD"]
        ton = r["rates"]["TON"]["prices"]["USD"]
        diff = r["rates"][PZM_JETTON].get("diff_24h", {}).get("USD", "—")
        rates_cache = {"pzm_usd": pzm, "ton_usd": ton, "diff_24h": diff, "ts": time.time()}
        return pzm, ton, diff
    except Exception as e:
        log(f"⚠️ Ошибка курсов: {e}")
        return rates_cache["pzm_usd"], rates_cache["ton_usd"], rates_cache["diff_24h"]


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


def settings_markup(row):
    mark = types.InlineKeyboardMarkup()
    
    # Вкл/выкл
    mark.add(types.InlineKeyboardButton(
        "✅ Сделки: вкл" if row["trades_on"] else "❌ Сделки: выкл",
        callback_data="alert_toggle"))
    
    # Фильтр: все / только покупки / только продажи
    f = row.get("trade_filter", "all")
    filter_labels = {"all": "Все", "buys": "Только покупки", "sells": "Только продажи"}
    mark.add(types.InlineKeyboardButton(
        f"🔍 Показывать: {filter_labels.get(f, 'Все')}",
        callback_data="alert_filter"))

    thread = row.get("thread_id")
    thread_txt = f"📌 Куда: тема #{thread}" if thread else "📌 Куда: общая лента"
    mark.add(types.InlineKeyboardButton(thread_txt, callback_data="alert_thread"))
    
    mark.add(types.InlineKeyboardButton(
        f"💰 Мин. объём: {fmt_num(row['min_volume_pzm'])} PZM",
        callback_data="alert_min"))
    mark.add(types.InlineKeyboardButton("🖼 Картинка: сменить", callback_data="alert_img"))
    mark.add(types.InlineKeyboardButton("🖼 Картинка: сбросить", callback_data="alert_img_reset"))
    mark.add(types.InlineKeyboardButton("🔕 Отключить оповещения", callback_data="alert_off"))
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
        "1️⃣ Добавьте меня в ваш канал или чат\n"
        "   (в канал — с правом «Публиковать сообщения»)\n"
        "2️⃣ Отправьте /alert — я открою настройки\n"
        "   (настраивают только администраторы чата)\n\n"
        "Команды:\n"
        "/rate — текущий курс PZM\n"
        "/alert — настройки оповещений\n"
        "/testalert — тестовое сообщение с картинкой"))


@bot.message_handler(commands=["rate"])
def rate_cmd(message):
    pzm_usd, ton_usd, diff = get_rates()
    ton_r, pzm_r = get_pool_reserves()
    text = f"💵 Текущий курс PZM: ${pzm_usd:.6f}\n📊 Изменение за 24ч: {diff}"
    if ton_r and pzm_r:
        text += f"\n💱 В GRAM: {ton_r / pzm_r:.6f} GRAM за PZM"
        text += f"\n📊 Ликвидность пула: {fmt_num(pzm_r)} PZM / {fmt_num(ton_r)} GRAM"
    bot.send_message(message.chat.id, text)


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
    bot.send_message(chat.id, settings_text(row), reply_markup=settings_markup(row))


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
    pzm_usd, ton_usd, diff = get_rates()
    now = datetime.now(timezone.utc).strftime("%d.%m %H:%M UTC")
    sample = (
        "🟢 Покупка PZM на DeDust (превью)\n"
        f"🟣 1 000.00 PZM (~${1000 * pzm_usd:.2f})\n"
        "💎 Заплачено: 0.72 GRAM\n"
        "👛 Покупатель: alice.ton\n"
        "🔗 Txn: 4b2c7780...793494\n"
        f"📈 Курс PZM: ${pzm_usd:.6f}\n"
        f"📊 24ч: {diff}\n"
        f"🕒 {now}"
    )
    send_alert(row, sample, sample, is_buy=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("alert_"))
def alert_callbacks(call):
    chat = call.message.chat
    if chat.type in ("group", "supergroup", "channel"):
        if not is_admin(chat.id, call.from_user.id):
            bot.answer_callback_query(call.id, "Только администраторы чата.")
            return
    row = db.alert_get(chat.id)
    if row is None:
        bot.answer_callback_query(call.id, "Чат не подключён.")
        return

    if call.data == "alert_toggle":
        db.alert_toggle(chat.id)
    elif call.data == "alert_filter":
        # Переключаем: all → buys → sells → all
        current = row.get("trade_filter", "all")
        cycle = {"all": "buys", "buys": "sells", "sells": "all"}
        db.alert_set_filter(chat.id, cycle.get(current, "all"))
    elif call.data == "alert_min":
        steps = [0, 1000, 10000, 50000]
        cur = row["min_volume_pzm"]
        nxt = steps[(steps.index(cur) + 1) % len(steps)] if cur in steps else 0
        db.alert_set_min(chat.id, nxt)
    elif call.data == "alert_thread":
        try:
            chat_info = bot.get_chat(chat.id)
        except Exception:
            chat_info = None
        if chat_info is None or not getattr(chat_info, "is_forum", False):
            bot.answer_callback_query(call.id, "В этом чате нет тем — сообщения идут в общую ленту.")
            return
        waiting_photo[chat.id] = "thread_pick"
        mark = types.InlineKeyboardMarkup()
        mark.add(types.InlineKeyboardButton("❌ Отмена", callback_data="thread_cancel"))
        bot.send_message(chat.id,
                         "📌 Пришлите любое сообщение ИЗ нужной темы — я запомню её.\n"
                         "(Сообщение из общей ленты = публиковать в общую ленту.)",
                         reply_markup=mark)
        bot.answer_callback_query(call.id)
        return        
    elif call.data == "alert_img":
        waiting_photo[chat.id] = True
        bot.answer_callback_query(call.id)
        bot.send_message(chat.id, "🖼 Пришлите фото в этот чат обычным сообщением — я сохраню его для оповещений.")
        return
    elif call.data == "alert_img_reset":
        db.alert_reset_image(chat.id)
    elif call.data == "alert_off":
        db.alert_remove(chat.id)
        bot.answer_callback_query(call.id, "Оповещения отключены.")
        try:
            bot.edit_message_text("🔕 Оповещения отключены для этого чата. Вернуть: /alert",
                                  chat.id, call.message.message_id)
        except Exception:
            pass
        return

    row = db.alert_get(chat.id)
    try:
        bot.edit_message_text(settings_text(row), chat.id, call.message.message_id,
                              reply_markup=settings_markup(row))
    except Exception:
        pass
    bot.answer_callback_query(call.id, "Обновлено")


@bot.callback_query_handler(func=lambda c: c.data == "thread_cancel")
def thread_cancel(call):
    waiting_photo.pop(call.message.chat.id, None)
    bot.answer_callback_query(call.id, "Отменено.")
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass


@bot.message_handler(content_types=["text"],
                     func=lambda m: waiting_photo.get(m.chat.id) == "thread_pick")
def pick_thread(message):
    chat = message.chat
    if chat.type in ("group", "supergroup") and not is_admin(chat.id, message.from_user.id):
        return
    thread_id = getattr(message, "message_thread_id", None)
    if thread_id:
        db.alert_set_thread(chat.id, thread_id)
        bot.send_message(chat.id, f"✅ Оповещения будут публиковаться в тему #{thread_id}.",
                         message_thread_id=thread_id)
    else:
        db.alert_reset_thread(chat.id)
        bot.send_message(chat.id, "✅ Оповещения будут публиковаться в общую ленту.")
    waiting_photo.pop(chat.id, None)


@bot.message_handler(content_types=["photo"])
def save_photo(message):
    chat = message.chat
    if waiting_photo.get(chat.id) is not True:
        return
    if chat.type in ("group", "supergroup", "channel"):
        if not is_admin(chat.id, message.from_user.id):
            return
    fid = message.photo[-1].file_id
    db.alert_set_image(chat.id, fid)
    waiting_photo.pop(chat.id, None)
    bot.send_message(chat.id, "🖼 Картинка сохранена! Теперь оповещения будут приходить с ней.")


@bot.my_chat_member_handler()
def my_chat_member(update):
    chat = update.chat
    status = update.new_chat_member.status
    if status in ("member", "administrator"):
        if chat.type == "private":
            db.alert_upsert(chat.id, chat.title or "Личный чат", chat.type, trades_on=0)
        else:
            db.alert_upsert(chat.id, chat.title or "Чат", chat.type)
            try:
                bot.send_message(chat.id, (
                    "👋 Я подключён! Буду публиковать здесь сделки с PZM на DeDust.\n\n"
                    "Администраторы: /alert — настройки, /testalert — проверка."))
            except Exception:
                pass
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
        
        line = f"📈 Курс PZM: ${pzm_usd:.6f}"
        plain.append(line)
        html.append(line)
        
        line = f"📊 24ч: {diff}"
        plain.append(line)
        html.append(line)
        
        line = f"🕒 {time_str}"
        plain.append(line)
        html.append(line)
        
        return "\n".join(plain), "\n".join(html), pzm_amount, is_buy
    
    return None, None, 0, False


CHANNEL_URL = "https://t.me/prizm"


def send_alert(row, plain, html, is_buy):
    img = row.get("image_file_id")
    thread_id = row.get("thread_id")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🟣 Купить PZM", url=BUY_URL))
    markup.add(types.InlineKeyboardButton("📢 Канал PRIZM", url=CHANNEL_URL))

    def _send(thread):
        if img:
            bot.send_photo(row["chat_id"], img, caption=html, parse_mode="HTML",
                           reply_markup=markup, message_thread_id=thread)
        elif os.path.exists(DEFAULT_IMAGE):
            with open(DEFAULT_IMAGE, "rb") as f:
                bot.send_photo(row["chat_id"], f, caption=html, parse_mode="HTML",
                               reply_markup=markup, message_thread_id=thread)
        else:
            bot.send_message(row["chat_id"], html, parse_mode="HTML",
                             reply_markup=markup, message_thread_id=thread)

    try:
        _send(thread_id)
    except Exception as e:
        if thread_id:
            # Тема удалена/недоступна — шлём в общую ленту и сбрасываем настройку
            log(f"⚠️ Тема {thread_id} недоступна в {row['chat_id']}: {e} — шлю в общую ленту")
            db.alert_reset_thread(row["chat_id"])
            try:
                _send(None)
                return
            except Exception as e2:
                e = e2
        log(f"⚠️ Не удалось отправить в {row['chat_id']}: {e} — убираю чат")
        db.alert_remove(row["chat_id"])


def broadcast(plain, html, pzm_amount, is_buy):
    for row in db.alert_get_enabled():
        if pzm_amount < row["min_volume_pzm"]:
            continue
        # Фильтр по типу сделки
        f = row.get("trade_filter", "all")
        if f == "buys" and not is_buy:
            continue
        if f == "sells" and is_buy:
            continue
        send_alert(row, plain, html, is_buy)


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
        try:
            r = requests.get(f"{TONAPI}/accounts/{PZM_POOL}/events?limit=20", timeout=10).json()
            events = r.get("events", [])
            new_events = [e for e in events if e["timestamp"] > last_seen_ts]
            for event in sorted(new_events, key=lambda e: e["timestamp"]):
                plain, html, pzm_amount, is_buy = parse_trade(event)
                if plain:
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


def start_alert_bot():
    """Точка входа: монитор + поллинг бота (для WSGI)"""
    db.init_alert_chats()
    threading.Thread(target=monitor_trades, daemon=True).start()
    while True:
        started = time.time()
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=10)
        except Exception as e:
            log(f"⚠️ Поллинг упал: {e}. Перезапуск через 10 сек...")
            time.sleep(10)
            continue
        # Поллинг вернулся сам без исключения
        if time.time() - started < 5:
            log("🛑 Поллинг остановлен оператором. Завершаем работу.")
            break
        log("⚠️ Поллинг завершился сам. Перезапуск через 10 сек...")
        time.sleep(10)


if __name__ == "__main__":
    log("🚀 Prizm Alert Bot (v4 — картинки и адреса)")
    log("=" * 55)
    start_alert_bot()