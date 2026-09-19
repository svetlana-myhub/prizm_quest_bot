"""Одноразовая загрузка истории курса PZM в rate_snapshots.
Запуск: python fill_rates.py [дней]   (по умолчанию 400)"""
import sys
import time
import requests

import db
from market import TONAPI, PZM_JETTON

DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 400
to_ts = int(time.time())
from_ts = to_ts - DAYS * 86400


def normalize(points):
    """Превращает любой формат точек графика в [(ts, price)]"""
    out = []
    if isinstance(points, dict):
        items = points.items()
    else:
        items = [(None, p) for p in points]
    for key, val in items:
        ts, price = None, None
        if isinstance(val, dict):
            price = val.get("price_usd") or val.get("price") or val.get("value") or val.get("close")
            ts = val.get("ts") or val.get("timestamp") or val.get("time")
        elif isinstance(val, (int, float)):
            price = val
        elif isinstance(val, (list, tuple)) and len(val) >= 2:
            ts, price = val[0], val[1]
        if ts is None and key is not None:
            try:
                ts = int(key)
            except Exception:
                ts = None
        if ts is None or price is None:
            continue
        if ts > 10 ** 11:
            ts //= 1000
        out.append((int(ts), float(price)))
    return out


r = requests.get(f"{TONAPI}/rates/chart",
                 params={"token": PZM_JETTON, "currency": "usd",
                         "from": from_ts, "to": to_ts}, timeout=20)
print("HTTP", r.status_code)
data = r.json()
if isinstance(data, dict):
    print("keys:", list(data.keys())[:10])
points = normalize(data.get("points", data))
print("points:", len(points))
if not points:
    print("RAW SAMPLE:", str(data)[:600])
    sys.exit(1)
for ts, price in points:
    db.rate_snapshot_put(ts, price, 0.0)
print(f"✅ Снапшотов сохранено: {len(points)} "
      f"({time.ctime(points[0][0])} → {time.ctime(points[-1][0])})")