"""Пересчёт usd_value в журнале сделок по снапшотам DYOR.
Запуск: python repair_trades.py"""
import sqlite3
import db

con = sqlite3.connect(db.DB_PATH)
rows = con.execute("SELECT id, ts, pzm_amount FROM trades").fetchall()
updated = 0
skipped = 0

for _id, ts, pzm in rows:
    snap = db.rate_snapshot_near(ts, tol=43200)  # ±12 часов
    if snap and snap[1]:
        new_usd = pzm * snap[1]
        con.execute("UPDATE trades SET usd_value=? WHERE id=?", (new_usd, _id))
        updated += 1
    else:
        skipped += 1

con.commit()
con.close()
print(f"✅ Обновлено {updated} сделок, без снапшота: {skipped}")