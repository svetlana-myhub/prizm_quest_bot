"""График курса PZM картинкой: тёмно-фиолетовый стиль Prizm (matplotlib). v5"""
import io
import os
import threading
import time

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcache")

from telebot import types

_plt = None


def _plt_mod():
    """Ленивый импорт matplotlib: не тормозим старт веб-воркера."""
    global _plt
    if _plt is None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        _plt = plt
    return _plt

import db
from market import get_rates, get_rub_rate, get_liquidity, PZM_JETTON

COIN_PATH = os.path.join("assets", "prizm_coin.png")
SYMBOL_PATH = os.path.join("assets", "prizm_symbol.png")
BUY_URL = f"https://dedust.io/ru/swap/GRAM/{PZM_JETTON}"
WATERMARK_ALPHA = 0.15          # водяной знак
HEADER_FS = 25                  # строка пары+курса в шапке
BOX_FS = 22                     # бокс расчёта PZM
GRID_N = 6                      # линий сетки

CURS = {"usd": ("💲 USDT", "USDT"), "gram": ("💎 GRAM", "GRAM"), "rub": ("💸 RUB", "RUB")}
PERIODS = {"24h": ("24 часа", 86400), "7d": ("7 дней", 7 * 86400),
           "30d": ("1 месяц", 30 * 86400), "180d": ("6 месяцев", 180 * 86400),
           "365d": ("1 год", 365 * 86400), "all": ("всё время", None)}

BG, LINE, FILL = "#160726", "#c26bff", "#8b2fd6"
GRID = "#2a1745"
GREEN, RED, TEXT, MUTED = "#3ddc84", "#ff5c7a", "#f3eaff", "#9d8bc0"

_cache = {}
_sym_cache = {"img": None, "tried": False}
_prewarm_started = False


def _load_symbol():
    """Символ Prizm без белого фона; геометрия символа не изменяется."""
    if _sym_cache["tried"]:
        return _sym_cache["img"]
    _sym_cache["tried"] = True
    try:
        from PIL import Image, ImageDraw
        im = Image.open(SYMBOL_PATH).convert("RGBA")
        ImageDraw.floodfill(im, (0, 0), (255, 0, 255, 255), thresh=60)
        px = im.load()
        w, h = im.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if (r, g, b) == (255, 0, 255):
                    px[x, y] = (0, 0, 0, 0)
        _sym_cache["img"] = im
    except Exception:
        _sym_cache["img"] = None
    return _sym_cache["img"]


def trim(s):
    """Убирает лишние нули в конце после запятой: 8177.081000 -> 8177.081"""
    return s.rstrip("0").rstrip(".") if "." in s else s


def fm(v):
    if v >= 1e6:
        return trim(f"{v / 1e6:.2f}") + "M"
    if v >= 1e3:
        return trim(f"{v / 1e3:.1f}") + "K"
    return f"{v:.0f}"


def fmt_val(v, cur):
    return trim(f"{v:.4f}") if cur == "rub" else trim(f"{v:.6f}")


def fmt_amount(a):
    """Призм целиком с пробелами; сокращаем только круглые нули.
    88888888 -> '88 888 888', 8800 -> '8.8K', 8880 -> '8.88K', 1500000 -> '1.5M'"""
    if a == int(a):
        n = int(a)
        if n >= 1000 and n % 100 == 0:
            if n >= 1e6:
                return trim(f"{n / 1e6:.2f}") + "M"
            return trim(f"{n / 1000:.2f}") + "K"
        return f"{n:,}".replace(",", " ")
    return trim(f"{a:.4f}")


def fmt_money(v):
    """Результат в валюте: от 1 — два знака с пробелами в тысячах,
    меньше 1 — шесть знаков (курс же крошечный)."""
    if v >= 1:
        return trim(f"{v:,.2f}".replace(",", " "))
    return trim(f"{v:.6f}")


def get_series(cur, sec):
    now = int(time.time())
    ts0 = now - sec if sec else 0
    if cur == "gram":
        _, ton_now, _ = get_rates()
        if not ton_now:
            return []
        out = []
        for ts, p, t in db.snapshots_full_since(ts0):
            out.append((ts, p / (t if t and t > 0 else ton_now)))
        return out
    usd = db.snapshots_since(ts0)
    if cur == "rub":
        rub = get_rub_rate()
        if not rub:
            return []
        return [(ts, v * rub) for ts, v in usd]
    return usd


def chart_markup(cur, period, amount=100):
    a = str(int(amount)) if amount == int(amount) else repr(amount)
    mark = types.InlineKeyboardMarkup()
    mark.row(*[types.InlineKeyboardButton(("✅ " if c == cur else "") + lb,
                                          callback_data=f"chart:{c}:{period}:{a}")
               for c, lb in (("usd", "💲 USDT"), ("gram", "💎 GRAM"), ("rub", "💸 RUB"))])
    p6 = [("24h", "24 часа"), ("7d", "7 дней"), ("30d", "1 месяц"),
          ("180d", "6 мес"), ("365d", "1 год"), ("all", "Всё время")]
    mark.row(*[types.InlineKeyboardButton(("✅ " if p == period else "") + lb,
                                          callback_data=f"chart:{cur}:{p}:{a}")
               for p, lb in p6[:3]])
    mark.row(*[types.InlineKeyboardButton(("✅ " if p == period else "") + lb,
                                          callback_data=f"chart:{cur}:{p}:{a}")
               for p, lb in p6[3:]])
    mark.row(types.InlineKeyboardButton("🔢 Калькулятор",
                                        callback_data=f"chartcalc:{cur}:{period}"),
             types.InlineKeyboardButton("🟣 Купить PRIZM", url=BUY_URL))
    return mark


def _prewarm():
    """Фоновый прогрев кэша: все валюты x периоды, чтобы кнопки меняли
    картинку мгновенно."""
    for c in CURS:
        for p in PERIODS:
            try:
                render(c, p)
            except Exception:
                pass


def render(cur, period, amount=100):
    plt = _plt_mod()    
    key = (cur, period, amount)
    now = int(time.time())
    hit = _cache.get(key)
    if hit and now - hit[0] < 900:
        return hit[1], hit[2]
    label, sec = PERIODS[period]
    series = get_series(cur, sec)
    if len(series) < 2:
        return None, None
    ts = [p[0] for p in series]
    vals = [p[1] for p in series]
    first, last = vals[0], vals[-1]
    pct = (last - first) / first * 100 if first else 0.0
    vmin, vmax = min(vals), max(vals)
    sym = CURS[cur][1]
    full = get_series(cur, None)          # вся доступная история валюты
    days = (full[-1][0] - full[0][0]) // 86400 if len(full) >= 2 else 0

    fig = plt.figure(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(BG)

    ax = fig.add_axes([0.04, 0.2, 0.92, 0.62])
    ax.set_facecolor("none")
    wm = _load_symbol()
    if wm is not None and WATERMARK_ALPHA > 0:
        ins = ax.inset_axes([0.36, 0.15, 0.28, 0.70])
        ins.imshow(wm, alpha=WATERMARK_ALPHA)
        ins.axis("off")
        ins.set_zorder(0.5)
    ax.set_zorder(1)

    ax.plot(ts, vals, color=LINE, lw=1.7, zorder=3)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.margins(x=0.01, y=0.12)
    lo, hi = ax.get_ylim()

    # заливка до нижней границы зоны
    ax.fill_between(ts, vals, lo, color=FILL, alpha=0.22, zorder=2)
    # сетка ровно по зоне: нижняя линия по низу, верхняя по верху
    ys = [lo + (hi - lo) * i / GRID_N for i in range(GRID_N + 1)]
    ax.hlines(ys, ts[0], ts[-1], colors=GRID, lw=0.6, zorder=1)
    ax.hlines(vmax, ts[0], ts[-1], colors=GREEN, lw=0.8,
              ls=(0, (4, 4)), alpha=0.55, zorder=2)
    ax.hlines(vmin, ts[0], ts[-1], colors=RED, lw=0.8,
              ls=(0, (4, 4)), alpha=0.55, zorder=2)

    # мин/макс: у краёв выравнивание к краю, чтобы не вылезало за кадр
    span = (ts[-1] - ts[0]) or 1

    def ha_for(t):
        if (t - ts[0]) / span < 0.12:
            return "left"
        if (ts[-1] - t) / span < 0.12:
            return "right"
        return "center"

    imin, imax = vals.index(vmin), vals.index(vmax)
    ax.plot(ts[imax], vmax, "o", color=GREEN, ms=5, zorder=4)
    ax.plot(ts[imin], vmin, "o", color=RED, ms=5, zorder=4)
    ax.annotate(f"макс {fmt_val(vmax, cur)}", (ts[imax], vmax),
                textcoords="offset points", xytext=(0, 10),
                color=GREEN, fontsize=8, ha=ha_for(ts[imax]))
    ax.annotate(f"мин {fmt_val(vmin, cur)}", (ts[imin], vmin),
                textcoords="offset points", xytext=(0, -14),
                color=RED, fontsize=8, ha=ha_for(ts[imin]))

    # шапка: монета крупнее, надпись ближе к ней, бейдж справа по центру
    has_coin = os.path.exists(COIN_PATH)
    if has_coin:
        ico = fig.add_axes([0.04, 0.79, 0.145, 0.145])
        ico.imshow(plt.imread(COIN_PATH))
        ico.axis("off")
    hx = 0.18 if has_coin else 0.05
    fig.text(hx, 0.865, f"PZM/{sym} {fmt_val(last, cur)}", color=LINE,
             fontsize=HEADER_FS, weight="bold", va="center")
    col = GREEN if pct >= 0 else RED
    fig.text(0.96, 0.865, f"{pct:+.2f}% за {label}", color=col, fontsize=12,
             ha="right", va="center",
             bbox=dict(boxstyle="round,pad=0.3", fc=col, alpha=0.15, ec=col, lw=0.8))

    # подвал
    d0 = time.strftime("%d.%m.%Y", time.gmtime(ts[0]))
    d1 = time.strftime("%d.%m.%Y", time.gmtime(ts[-1]))
    fig.text(0.04, 0.21, d0, color=MUTED, fontsize=8)
    fig.text(0.96, 0.21, d1, color=MUTED, fontsize=8, ha="right")
    pzm_liq, gram_liq = get_liquidity()
    amt_s = fmt_amount(amount)
    fig.text(0.053, 0.117, f"{amt_s} PZM = {fmt_money(last * amount)} {sym}",
             color=TEXT, fontsize=BOX_FS, weight="bold",
             bbox=dict(boxstyle="round,pad=0.35", fc="#2a1245", ec="#4b2a75", lw=0.8))
    if pzm_liq:
        fig.text(0.96, 0.117,
                 f"ликвидность: {fm(pzm_liq)} PZM / {fm(gram_liq)} GRAM",
                 color=MUTED, fontsize=8, ha="right")
    fig.text(0.04, 0.045, "Источник: DYOR.io + ЦБ РФ · " +
             time.strftime("%d.%m.%Y %H:%M UTC", time.gmtime(now)),
             color=MUTED, fontsize=7)
    fig.text(0.96, 0.045, f"история: {days} дн. · {label}",
             color=MUTED, fontsize=8, ha="right")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=BG)
    plt.close(fig)
    png = buf.getvalue()
    cur_em = {"USDT": "💲", "GRAM": "💎", "RUB": "💸"}.get(sym, "💲")
    cap_lines = [f"📊 <b>PZM/{sym}</b> · {label}",
                 f"{cur_em} Курс: {fmt_val(last, cur)} {sym}",
                 f"{'🟢' if pct >= 0 else '🔴'} {pct:+.2f}% за период",
                 f"⬆️ макс {fmt_val(vmax, cur)}",
                 f"⬇️ мин {fmt_val(vmin, cur)}"]
    try:
        pzm_liq, gram_liq = get_liquidity()
    except Exception:
        pzm_liq = gram_liq = 0
    if pzm_liq:
        cap_lines.append(f"💰 Ликвидность: {fm(pzm_liq)} PZM / {fm(gram_liq)} GRAM")
    caption = "\n".join(cap_lines)
    if amount != 100:
        caption = (f"🟣 <b>{fmt_amount(amount)} PZM = "
                   f"{fmt_money(last * amount)} {sym}</b>\n\n" + caption)
    _cache[key] = (now, png, caption)
    return png, caption


def show_chart(bot, chat_id, cur, period, edit_msg_id=None, call=None,
               thread=None, amount=100):
    global _prewarm_started
    png, caption = render(cur, period, amount)
    mark = chart_markup(cur, period, amount)
    if png is None:
        if call:
            try:
                bot.answer_callback_query(call.id, "Мало данных за период",
                                          show_alert=True)
            except Exception:
                pass
            return
        msg = bot.send_message(chat_id, "📉 Мало данных для графика за этот период — "
                                    "попробуйте другой.", message_thread_id=thread)
        return msg
    if call:
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
    if not _prewarm_started and amount == 100:
        _prewarm_started = True
        threading.Thread(target=_prewarm, daemon=True).start()
    if edit_msg_id:
        try:
            media = types.InputMediaPhoto(
                media=types.InputFile(io.BytesIO(png), file_name="chart.png"),
                caption=caption, parse_mode="HTML")
            bot.edit_message_media(media=media, chat_id=chat_id,
                                   message_id=edit_msg_id, reply_markup=mark)
            return
        except Exception as e:
            if "not modified" in str(e):
                return                      # нажали уже активную кнопку — нечего делать
            print(f"⚠️ edit_message_media: {e}")
            try:
                bot.delete_message(chat_id, edit_msg_id)
            except Exception:
                pass
    msg = bot.send_photo(chat_id, png, caption=caption, parse_mode="HTML",
                         reply_markup=mark, message_thread_id=thread)
    return msg
