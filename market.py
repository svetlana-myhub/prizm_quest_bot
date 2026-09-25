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
    """Живые резервы пула DeDust напрямую из смарт-контракта: (PZM, TON)"""
    cached_pzm = _liq_cache.get("pzm")
    cached_ton = _liq_cache.get("ton", _liq_cache.get("gram"))
    
    # Кэш на 5 минут, чтобы не спамить TON Center API
    if cached_pzm is not None and time.time() - _liq_cache["ts"] < 300:
        return cached_pzm, cached_ton
        
    try:
        url = "https://toncenter.com/api/v2/runGetMethod"
        payload = {
            "address": PZM_POOL,
            "method": "get_reserves",
            "stack": []
        }
        r = requests.post(url, json=payload, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            if data.get("ok") and "result" in data:
                stack = data["result"].get("stack", [])
                if len(stack) >= 2:
                    # stack[0] - reserve0 (TON), stack[1] - reserve1 (PZM)
                    # Значения приходят в hex формате: ["num", "0x..."]
                    reserve0_hex = stack[0][1]
                    reserve1_hex = stack[1][1]
                    
                    # Конвертируем из hex в десятичные и применяем decimals
                    ton_raw = int(reserve0_hex, 16)
                    pzm_raw = int(reserve1_hex, 16)
                    
                    ton = ton_raw / 1e9
                    pzm = pzm_raw / 100  # У PZM ровно 2 знака после запятой
                    
                    _liq_cache.update(ts=time.time(), pzm=pzm, ton=ton, gram=ton)
                    return pzm, ton
    except Exception as e:
        print(f"⚠️ Ошибка получения ликвидности из блокчейна: {e}")
        
    # В случае ошибки возвращаем последние закэшированные значения
    return _liq_cache.get("pzm"), _liq_cache.get("ton", _liq_cache.get("gram"))


PERIODS = [("7 дней", 7 * 86400), ("1 месяц", 30 * 86400), ("1 год", 365 * 86400)]


def rate_change_lines(pzm_usd_now):
    """Изменения курса за периоды по снапшотам: [(метка, % или None)]"""
    out = []
    now = int(time.time())
    for label, sec in PERIODS:
        tol = max(43200, sec // 12)          # 7д: ±14ч, 1мес: ±2.5д, 1год: ±30д
        row = db.rate_snapshot_near(now - sec, tol=tol)
        if not row and sec >= 365 * 86400:
            old = db.rate_snapshot_oldest()
            if old and old[1] and (now - old[0]) >= 300 * 86400:
                days = (now - old[0]) // 86400
                out.append((f"с начала торгов ({days} дн)",
                            (pzm_usd_now - old[1]) / old[1] * 100))
                continue
        if row and row[1]:
            out.append((label, (pzm_usd_now - row[1]) / row[1] * 100))
        else:
            out.append((label, None))
    return out