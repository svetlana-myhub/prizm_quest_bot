import time
import requests
import threading
from datetime import datetime, timezone

# === КОНФИГУРАЦИЯ ===
PZM_POOL = "EQAa6k6QZCq87DyyrnIZQOZsP8xF7B3gOMKXvHD7r-pevSub"
PZM_JETTON = "EQDROsytSxLtDp_2pRIEainUGqZPRBbXkwayVn7VAT7bHHWL"

# Кэш
last_seen_ts = 0
rates_cache = {"pzm_usd": 0.0013, "ton_usd": 1.36, "ts": 0}

TONAPI = "https://tonapi.io/v2"
TONCENTER = "https://toncenter.com/api/v2"


def get_rates():
    """Курс PZM и TON в USD (кэш 2 минуты)"""
    global rates_cache
    if time.time() - rates_cache["ts"] < 120:
        return rates_cache["pzm_usd"], rates_cache["ton_usd"]
    
    try:
        url = f"{TONAPI}/rates?tokens=ton,{PZM_JETTON}&currencies=usd"
        r = requests.get(url, timeout=10).json()
        pzm = r["rates"][PZM_JETTON]["prices"]["USD"]
        ton = r["rates"]["TON"]["prices"]["USD"]
        rates_cache = {"pzm_usd": pzm, "ton_usd": ton, "ts": time.time()}
        print(f"💵 Курсы обновлены: TON=${ton:.4f}, PZM=${pzm:.6f}")
        return pzm, ton
    except Exception as e:
        print(f"⚠️ Ошибка курсов: {e}")
        return rates_cache["pzm_usd"], rates_cache["ton_usd"]


def get_pool_reserves():
    """Живые резервы пула через toncenter (get_reserves из смарт-контракта)"""
    try:
        payload = {
            "address": PZM_POOL,
            "method": "get_reserves",
            "stack": []
        }
        r = requests.post(f"{TONCENTER}/runGetMethod", json=payload, timeout=10).json()
        if r.get("ok"):
            stack = r["result"]["stack"]
            # stack[0] = резерв TON (nanoGRAM), stack[1] = резерв PZM (decimals=2)
            ton_reserve = int(stack[0][1], 16) / 1e9
            pzm_reserve = int(stack[1][1], 16) / 100
            return ton_reserve, pzm_reserve
    except Exception as e:
        print(f"⚠️ Ошибка резервов: {e}")
    return None, None


def format_trade(event):
    """Форматирование одной сделки"""
    pzm_usd, ton_usd = get_rates()
    
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
        
        amount_in = swap.get("amount_in")
        amount_out = swap.get("amount_out")
        
        # PZM decimals = 2, TON decimals = 9, USDT decimals = 6
        decimals = {"PZM": 2, "GRAM": 9, "TON": 9, "USD₮": 6, "USDT": 6}
        d_in = decimals.get(sym_in, 0)
        d_out = decimals.get(sym_out, 0)
        
        # Определяем направление (с точки зрения PZM)
        is_buy_pzm = sym_out == "PZM"
        direction = "🟢 Покупка PZM" if is_buy_pzm else "🔴 Продажа PZM"
        
        # Объёмы
        if is_buy_pzm:
            pzm_amount = int(amount_out or 0) / (10 ** d_out)
            other_amount = int(amount_in or 0) / (10 ** d_in) if amount_in else None
            other_sym = sym_in
        else:
            pzm_amount = int(amount_in or 0) / (10 ** d_in)
            other_amount = int(amount_out or 0) / (10 ** d_out) if amount_out else None
            other_sym = sym_out
        
        # Время
        ts = event["timestamp"]
        time_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%d.%m %H:%M:%S")
        
        # USD-эквивалент PZM
        pzm_usd_value = pzm_amount * pzm_usd
        
        # Если amount другого токена отсутствует, восстанавливаем его через курс
        if other_amount is None and other_sym == "GRAM":
            # GRAM = PZM_amount * pzm_usd / ton_usd
            other_amount = pzm_usd_value / ton_usd if ton_usd else None
        
        # Формируем сообщение
        print(f"\n{'='*55}")
        print(f"{direction}")
        print(f"💎 {pzm_amount:,.2f} PZM (${pzm_usd_value:.4f})")
        if other_amount is not None:
            print(f"{'🟢 за' if is_buy_pzm else '🔴 получено'}: {other_amount:,.4f} {other_sym}")
        print(f"💵 Курс PZM: ${pzm_usd:.6f}")
        print(f"🕒 {time_str} UTC")
        print(f"🔗 event_id: {event['event_id'][:16]}...")
        
        break  # одна сделка на событие


def monitor_trades():
    """Поток-монитор: каждые 30 сек ищет новые сделки"""
    global last_seen_ts
    
    print("🚀 Монитор запущен. Ищу свежие сделки в пуле TON–PZM...")
    
    # При старте получаем последние 10 сделок, чтобы сразу не дублировать
    try:
        r = requests.get(f"{TONAPI}/accounts/{PZM_POOL}/events?limit=10", timeout=10).json()
        events = r.get("events", [])
        if events:
            last_seen_ts = max(e["timestamp"] for e in events)
            print(f"📊 Стартовая точка: {datetime.fromtimestamp(last_seen_ts, tz=timezone.utc)}")
    except Exception as e:
        print(f"⚠️ Ошибка инициализации: {e}")
    
    # Получаем курсы и резервы один раз
    get_rates()
    ton_r, pzm_r = get_pool_reserves()
    if ton_r and pzm_r:
        print(f"📈 Живые резервы: {ton_r:,.2f} GRAM / {pzm_r:,.2f} PZM")
        print(f"💱 Курс из резервов: {ton_r/pzm_r:.6f} GRAM за PZM")
    
    fails = 0
    while True:
        try:
            # Берём последние 20 событий (запас, если пропустим)
            r = requests.get(f"{TONAPI}/accounts/{PZM_POOL}/events?limit=20", timeout=10).json()
            events = r.get("events", [])
            
            # Фильтруем: только новые (с timestamp > last_seen_ts)
            new_events = [e for e in events if e["timestamp"] > last_seen_ts]
            
            if new_events:
                print(f"\n🔔 Найдено {len(new_events)} новых событий")
                # Обрабатываем в хронологическом порядке
                for event in sorted(new_events, key=lambda e: e["timestamp"]):
                    format_trade(event)
                last_seen_ts = max(e["timestamp"] for e in events)
            
        except requests.exceptions.ConnectionError:
            fails += 1
            print(f"⚠️ Нет связи с tonapi.io (попытка {fails}). Жду...")
            time.sleep(15 if fails < 3 else 60)
            continue
        except Exception as e:
            fails += 1
            print(f"❌ Ошибка мониторинга: {e}")
            time.sleep(15 if fails < 3 else 60)
            continue

        fails = 0
        time.sleep(30)


if __name__ == "__main__":
    print("🚀 Prizm Alert Bot Monitor (v2 — tonapi)")
    print("=" * 55)
    
    monitor_thread = threading.Thread(target=monitor_trades, daemon=True)
    monitor_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Монитор остановлен")