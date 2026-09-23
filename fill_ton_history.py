"""Дозаполнение истории ton_usd в rate_snapshots из TonAPI (безопасно повторять)."""
import sqlite3
import time
import bisect

import requests

con = sqlite3.connect("botdata/prizmquest.db")
t_min = con.execute("SELECT MIN(ts) FROM rate_snapshots").fetchone()[0]
t_max = int(time.time())
print("диапазон:", t_min, "->", t_max)

points = []
seg = t_min
while seg < t_max:
    seg_end = min(seg + 90 * 86400, t_max)
    r = requests.get("https://tonapi.io/v2/rates/chart",
                     params={"token": "TON", "currency": "usd",
                             "start_date": seg, "end_date": seg_end}, timeout=20)
    d = r.json()
    pts = d.get("points")
    if pts is None:
        print("⚠️ ответ без points:", str(d)[:200])
        break
    points += [(int(p[0]), float(p[1])) for p in pts]
    print(f"  сегмент {seg}..{seg_end}: +{len(pts)} точек")
    seg = seg_end

points.sort()
ts_list = [p[0] for p in points]
price = dict(points)
print("всего точек TON:", len(points))

rows = con.execute(
    "SELECT ts FROM rate_snapshots WHERE ton_usd IS NULL OR ton_usd=0").fetchall()
for (ts,) in rows:
    i = bisect.bisect_left(ts_list, ts)
    cand = [c for c in (ts_list[i - 1] if i > 0 else None,
                        ts_list[i] if i < len(ts_list) else None) if c is not None]
    if not cand:
        continue
    near = min(cand, key=lambda c: abs(c - ts))
    con.execute("UPDATE rate_snapshots SET ton_usd=? WHERE ts=?", (price[near], ts))
con.commit()
print("✅ обновлено строк:", len(rows))
print("теперь с ton_usd:", con.execute(
    "SELECT COUNT(*) FROM rate_snapshots WHERE ton_usd IS NOT NULL AND ton_usd>0"
).fetchone()[0])