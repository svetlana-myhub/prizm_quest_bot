"""Одноразовая загрузка истории сделок пула в журнал.
Запуск: python fill_history.py [дней]   (по умолчанию 400)"""
import sys
import time
import requests

import db
import alert_bot  # импортируем только parse_trade; бот при импорте не стартует

TONAPI = "https://tonapi.io/v2"
POOL = alert_bot.PZM_POOL
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 400

db.init_trades()
stop_ts = time.time() - DAYS * 86400
before_lt = None
added = 0

while True:
    params = {"limit": 100}
    if before_lt:
        params["before_lt"] = before_lt
    try:
        r = requests.get(f"{TONAPI}/accounts/{POOL}/events", params=params, timeout=15).json()
    except Exception as e:
        print(f"⚠️ Ошибка запроса: {e} — пауза 10 сек и повтор")
        time.sleep(10)
        continue
    events = r.get("events", [])
    if not events:
        break
    too_old = False
    for e in events:
        if e.get("timestamp", 0) < stop_ts:
            too_old = True
            continue
        plain, html, pzm, is_buy, meta = alert_bot.parse_trade(e)
        if plain:
            row = db.rate_snapshot_near(meta["ts"], tol=21600)
            usd = meta["pzm"] * row[1] if row and row[1] else meta["usd"]
            db.trade_log(meta["ts"], meta["is_buy"], meta["pzm"], meta["other_sym"],
                         meta["other_amount"], usd, meta["event_id"])
            added += 1
    print(f"страница обработана, всего записей: {added}")
    if too_old:
        break
    before_lt = events[-1].get("lt")
    time.sleep(1.1)

print(f"✅ Готово: загружено сделок за {DAYS} дн.: {added}")