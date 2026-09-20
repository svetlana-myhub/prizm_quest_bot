"""Загрузчик истории курса PZM с DYOR API (вся история жетона).
Запуск: python fill_rates_dyor.py [мин_дней_назад]   (по умолчанию 500)"""
import sys
import time
from datetime import datetime, timezone

import requests
import db
from market import PZM_JETTON

BASE = f"https://api.dyor.io/v1/jettons/{PZM_JETTON}"
LIMIT = 100
MIN_DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 500
stop_ts = time.time() - MIN_DAYS * 86400

db.init_trades()
db.init_alert_chats()  # чтобы таблицы уже существовали

def parse_ts(iso):
    # "2026-09-19T08:20:28Z" -> unix timestamp
    iso = iso.replace("Z", "+00:00")
    return datetime.fromisoformat(iso).timestamp()

def parse_usd(item):
    v = item.get("value", {})
    usd = v.get("usd") or {}
    price = int(usd.get("value", 0))
    dec = int(usd.get("decimals", 6))
    return price / (10 ** dec) if price else 0.0

added = 0
skipped = 0
cursor = None
page = 0

while True:
    page += 1
    params = {"limit": LIMIT}
    if cursor:
        params["cursor"] = cursor
    try:
        r = requests.get(BASE + "/price/ticks", params=params, timeout=20)
        if r.status_code == 429:
            print("⚠️ 429 — пауза 5 сек")
            time.sleep(5)
            continue
        if r.status_code != 200:
            print(f"⚠️ HTTP {r.status_code}: {r.text[:150]}")
            break
        d = r.json()
    except Exception as e:
        print(f"⚠️ Ошибка запроса: {e} — пауза 5 сек")
        time.sleep(5)
        continue
    items = d.get("items", [])
    if not items:
        break
    too_old = False
    for it in items:
        ts = parse_ts(it["time"])
        if ts < stop_ts:
            too_old = True
            break
        price = parse_usd(it)
        if price > 0:
            db.rate_snapshot_put(int(ts), price, 0.0)
            added += 1
        else:
            skipped += 1
    print(f"страница {page}: +{len(items)} тиков, всего снапшотов: {added} "
          f"(до {items[-1]['time']})")
    if too_old:
        break
    cursor = d.get("next")
    if not cursor:
        break
    time.sleep(1.2)  # 1 req/sec бесплатный лимит

print(f"✅ Готово: добавлено {added} снапшотов, пропущено {skipped}")