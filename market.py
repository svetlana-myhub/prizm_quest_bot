"""Рыночные данные: общий модуль для обоих ботов (алерт и квест)."""
import time
import requests
import db
import logging

log = logging.info

TONAPI = "https://tonapi.io/v2"
DEDUST_API = "https://api.dedust.io/v2"
PZM_JETTON = "EQDROsytSxLtDp_2pRIEainUGqZPRBbXkwayVn7VAT7bHHWL"
PZM_POOL = "EQAa6k6QZCq87DyyrnIZQOZsP8xF7B3gOMKXvHD7r-pevSub"

# ═══ СЮДА ВЫРЕЗАТЬ ИЗ alert_bot.py: строку rates_cache = {...}
rates_cache = {"pzm_usd": 0.0013, "ton_usd": 1.36, "diff_24h": "—", "ts": 0}
# ═══ и функцию get_rates() целиком (вместе с её кэшем и комментариями)
def get_rates():
    global rates_cache
    if time.time() - rates_cache["ts"] < 60:
        return rates_cache["pzm_usd"], rates_cache["ton_usd"], rates_cache["diff_24h"]
    try:
        url = f"{TONAPI}/rates?tokens=ton,{PZM_JETTON}&currencies=usd"
        r = requests.get(url, timeout=10).json()
        rates = r.get("rates")
        if not rates:
            raise ValueError(f"tonapi ответил без rates: {str(r)[:150]}")
        pzm = rates[PZM_JETTON]["prices"]["USD"]
        ton = rates["TON"]["prices"]["USD"]
        diff = rates[PZM_JETTON].get("diff_24h", {}).get("USD", "—")
        rates_cache = {"pzm_usd": pzm, "ton_usd": ton, "diff_24h": diff, "ts": time.time()}
        return pzm, ton, diff
    except Exception as e:
        log(f"⚠️ Ошибка курсов: {e}")
        return rates_cache["pzm_usd"], rates_cache["ton_usd"], rates_cache["diff_24h"]


_dec_cache = {"dec": None}
_rub_cache = {"ts": 0, "rub": None}
_liq_cache = {"ts": 0, "pzm": None, "gram": None}


def get_pzm_decimals():
    if _dec_cache["dec"] is None:
        try:
            r = requests.get(f"{TONAPI}/jettons/{PZM_JETTON}", timeout=10).json()
            _dec_cache["dec"] = int(r.get("decimals", 9))
        except Exception:
            _dec_cache["dec"] = 9
    return _dec_cache["dec"]


def get_rub_rate():
    """Курс USD → RUB (ЦБ РФ, обновляется раз в час)"""
    if _rub_cache["rub"] and time.time() - _rub_cache["ts"] < 3600:
        return _rub_cache["rub"]
    try:
        r = requests.get("https://www.cbr-xml-daily.ru/daily_json.js", timeout=10).json()
        rub = float(r["Valute"]["USD"]["Value"])
        _rub_cache.update(ts=time.time(), rub=rub)
        return rub
    except Exception:
        return _rub_cache["rub"]


def get_liquidity():
    """Резервы пула DeDust: (PZM, GRAM)"""
    if _liq_cache["pzm"] is not None and time.time() - _liq_cache["ts"] < 300:
        return _liq_cache["pzm"], _liq_cache["gram"]
    try:
        r = requests.get(f"{DEDUST_API}/pools/{PZM_POOL}", timeout=10).json()
        lt, rt = r.get("leftToken") or {}, r.get("rightToken") or {}
        lr, rr = int(r.get("leftReserve", 0)), int(r.get("rightReserve", 0))
        if lt.get("symbol") == "PZM":
            pzm_raw, gram_raw = lr, rr
        else:
            pzm_raw, gram_raw = rr, lr
        pzm = pzm_raw / 10 ** get_pzm_decimals()
        gram = gram_raw / 1e9
        _liq_cache.update(ts=time.time(), pzm=pzm, gram=gram)
        return pzm, gram
    except Exception:
        return _liq_cache["pzm"], _liq_cache["gram"]


PERIODS = [("7 дней", 7 * 86400), ("1 месяц", 30 * 86400), ("1 год", 365 * 86400)]


def rate_change_lines(pzm_usd_now):
    """Изменения курса за периоды по снапшотам: [(метка, % или None)]"""
    out = []
    for label, sec in PERIODS:
        row = db.rate_snapshot_near(int(time.time()) - sec, tol=43200)
        if row and row[1]:
            out.append((label, (pzm_usd_now - row[1]) / row[1] * 100))
        else:
            out.append((label, None))
    return out