import sqlite3
from pathlib import Path

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    level TEXT CHECK(level IN ('newbie', 'known')),
    consent_at TEXT,
    state TEXT NOT NULL DEFAULT 'START',
    crystals INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    final_test_passed INTEGER NOT NULL DEFAULT 0,
    prizm_address TEXT
    last_active_at TEXT,
    daily_bonus_streak INTEGER NOT NULL DEFAULT 0,
    last_daily_bonus TEXT,
    ton_wallet TEXT,
    invited_by INTEGER,
    referral_code TEXT,
    referrals_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fact_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    fact_id TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, fact_id)
);

CREATE TABLE IF NOT EXISTS crystals_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quest_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    step_code TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, step_code)
);

CREATE TABLE IF NOT EXISTS badges (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    badge_code TEXT NOT NULL,
    awarded_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, badge_code)
);

CREATE TABLE IF NOT EXISTS rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    reward_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_manual',
    wallet_address TEXT,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, code)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS myth_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    myth_id TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, myth_id)
);

CREATE TABLE IF NOT EXISTS word_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    word_id TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, word_id)
);
"""

BADGES_SEED = [
    ("facts_master", "🔷 Исследователь Prizm"),
    ("security_keeper", "🔐 Хранитель безопасности"),
    ("quest_graduate", "🎓 Выпускник квеста"),
    ("myth_master", "🎭 Разоблачитель мифов"),
    ("word_master", "🧠 Эрудит Prizm"),
]


def get_connection():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        
        # Добавляем новые колонки для старых баз
        new_columns = [
            "ALTER TABLE users ADD COLUMN last_active_at TEXT",
            "ALTER TABLE users ADD COLUMN daily_bonus_streak INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN last_daily_bonus TEXT",
            "ALTER TABLE users ADD COLUMN ton_wallet TEXT",
            "ALTER TABLE users ADD COLUMN invited_by INTEGER",
            "ALTER TABLE users ADD COLUMN referral_code TEXT",
            "ALTER TABLE users ADD COLUMN referrals_count INTEGER NOT NULL DEFAULT 0",
        ]
        
        for sql in new_columns:
            try:
                conn.execute(sql)
            except Exception:
                pass  # Колонка уже есть
        
        conn.commit()
    finally:
        conn.close()


def get_or_create_user(tg_id, username=None, first_name=None):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO users (tg_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                updated_at = datetime('now')
            """,
            (tg_id, username, first_name),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user(tg_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_level(tg_id, level):
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE users
            SET level = ?,
                state = 'MENU',
                consent_at = COALESCE(consent_at, datetime('now')),
                updated_at = datetime('now')
            WHERE tg_id = ?
            """,
            (level, tg_id),
        )
        conn.commit()
    finally:
        conn.close()


def is_fact_done(tg_id, fact_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM fact_progress WHERE tg_id = ? AND fact_id = ?",
            (tg_id, fact_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_fact_done(tg_id, fact_id, is_correct):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO fact_progress (tg_id, fact_id, is_correct)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id, fact_id) DO UPDATE SET
                is_correct = excluded.is_correct,
                completed_at = datetime('now')
            """,
            (tg_id, fact_id, int(is_correct)),
        )
        conn.commit()
    finally:
        conn.close()


def count_done_facts(tg_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM fact_progress WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        return row["cnt"]
    finally:
        conn.close()


def is_step_done(tg_id, step_code):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM quest_progress WHERE tg_id = ? AND step_code = ?",
            (tg_id, step_code),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_step_done(tg_id, step_code):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO quest_progress (tg_id, step_code) VALUES (?, ?)",
            (tg_id, step_code),
        )
        conn.commit()
    finally:
        conn.close()


def award_badge_once(tg_id, badge_code):
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO user_badges (tg_id, badge_code) VALUES (?, ?)",
            (tg_id, badge_code),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_badge_title(badge_code):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT title FROM badges WHERE code = ?", (badge_code,)
        ).fetchone()
        return row["title"] if row else badge_code
    finally:
        conn.close()


def get_user_badges(tg_id):
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT b.title
            FROM user_badges ub
            JOIN badges b ON b.code = ub.badge_code
            WHERE ub.tg_id = ?
            ORDER BY ub.awarded_at
            """,
            (tg_id,),
        ).fetchall()
        return [row["title"] for row in rows]
    finally:
        conn.close()


def is_myth_done(tg_id, myth_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM myth_progress WHERE tg_id = ? AND myth_id = ?",
            (tg_id, myth_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_myth_done(tg_id, myth_id, is_correct):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO myth_progress (tg_id, myth_id, is_correct)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id, myth_id) DO UPDATE SET
                is_correct = excluded.is_correct,
                completed_at = datetime('now')
            """,
            (tg_id, myth_id, int(is_correct)),
        )
        conn.commit()
    finally:
        conn.close()


def count_done_myths(tg_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM myth_progress WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        return row["cnt"]
    finally:
        conn.close()


def is_word_done(tg_id, word_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM word_progress WHERE tg_id = ? AND word_id = ?",
            (tg_id, word_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_word_done(tg_id, word_id, is_correct):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO word_progress (tg_id, word_id, is_correct)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id, word_id) DO UPDATE SET
                is_correct = excluded.is_correct,
                completed_at = datetime('now')
            """,
            (tg_id, word_id, int(is_correct)),
        )
        conn.commit()
    finally:
        conn.close()


def count_done_words(tg_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM word_progress WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        return row["cnt"]
    finally:
        conn.close()


def add_crystals(tg_id, amount, reason):
    if amount == 0:
        return
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO crystals_ledger (tg_id, amount, reason) VALUES (?, ?, ?)",
            (tg_id, amount, reason),
        )
        conn.execute(
            """
            UPDATE users
            SET crystals = crystals + ?, updated_at = datetime('now')
            WHERE tg_id = ?
            """,
            (amount, tg_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_final_test_passed(tg_id):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET final_test_passed = 1 WHERE tg_id = ?",
            (tg_id,),
        )
        conn.commit()
    finally:
        conn.close()


def is_final_test_passed(tg_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT final_test_passed FROM users WHERE tg_id = ?", (tg_id,)
        ).fetchone()
        return row["final_test_passed"] == 1 if row else False
    finally:
        conn.close()


def set_prizm_address(tg_id, address):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET prizm_address = ? WHERE tg_id = ?",
            (address, tg_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_prizm_address(tg_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT prizm_address FROM users WHERE tg_id = ?", (tg_id,)
        ).fetchone()
        return row["prizm_address"] if row else None
    finally:
        conn.close()


def reset_user_progress(tg_id):
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE users SET 
               crystals = 0,
               final_test_passed = 0,
               prizm_address = NULL
               WHERE tg_id = ?""",
            (tg_id,),
        )
        # Удаляем все записи о пройденном контенте
        conn.execute("DELETE FROM fact_progress WHERE tg_id = ?", (tg_id,))
        conn.execute("DELETE FROM quest_progress WHERE tg_id = ?", (tg_id,))
        conn.execute("DELETE FROM myth_progress WHERE tg_id = ?", (tg_id,))
        conn.execute("DELETE FROM word_progress WHERE tg_id = ?", (tg_id,))
        conn.execute("DELETE FROM user_badges WHERE tg_id = ?", (tg_id,))
        conn.execute("DELETE FROM crystals_ledger WHERE tg_id = ?", (tg_id,))
        conn.commit()
    finally:
        conn.close()


        # === АДМИН-КОМАНДЫ И СТАТИСТИКА ===

def create_reward_claim(tg_id, code, reward_type, wallet_address, status="pending_manual"):
    """Создать заявку на награду"""
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO rewards (tg_id, code, reward_type, status, wallet_address)
               VALUES (?, ?, ?, ?, ?)""",
            (tg_id, code, reward_type, status, wallet_address),
        )
        conn.commit()
    finally:
        conn.close()


def get_pending_claims():
    """Получить все заявки со статусом pending_manual"""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """SELECT r.*, u.username, u.first_name 
               FROM rewards r
               JOIN users u ON r.tg_id = u.tg_id
               WHERE r.status = 'pending_manual'
               ORDER BY r.created_at DESC""",
        )
        return cursor.fetchall()
    finally:
        conn.close()


def mark_reward_paid(tg_id, code):
    """Отметить выплату как выполненную"""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE rewards 
               SET status = 'paid', updated_at = datetime('now')
               WHERE tg_id = ? AND code = ?""",
            (tg_id, code),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_full_info(tg_id):
    """Полная информация о пользователе"""
    conn = get_connection()
    try:
        # Основная информация
        user = conn.execute(
            "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
        ).fetchone()
        
        if not user:
            return None
        
        info = dict(user)
        
        # Прогресс по фактам
        facts = conn.execute(
            "SELECT COUNT(*) as total, SUM(is_correct) as correct FROM fact_progress WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        info["facts_total"] = facts["total"]
        info["facts_correct"] = facts["correct"] or 0
        
        # Прогресс по квесту
        quest = conn.execute(
            "SELECT COUNT(*) as completed FROM quest_progress WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        info["quest_completed"] = quest["completed"]
        
        # Прогресс по мифам
        myths = conn.execute(
            "SELECT COUNT(*) as total, SUM(is_correct) as correct FROM myth_progress WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        info["myths_total"] = myths["total"]
        info["myths_correct"] = myths["correct"] or 0
        
        # Прогресс по словам
        words = conn.execute(
            "SELECT COUNT(*) as total, SUM(is_correct) as correct FROM word_progress WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        info["words_total"] = words["total"]
        info["words_correct"] = words["correct"] or 0
        
        # Бейджи
        badges = conn.execute(
            "SELECT badge_code FROM user_badges WHERE tg_id = ?",
            (tg_id,),
        ).fetchall()
        info["badges"] = [b["badge_code"] for b in badges]
        
        # Награды
        rewards = conn.execute(
            "SELECT * FROM rewards WHERE tg_id = ? ORDER BY created_at DESC",
            (tg_id,),
        ).fetchall()
        info["rewards"] = [dict(r) for r in rewards]
        
        # Кто пригласил
        if info.get("invited_by"):
            inviter = conn.execute(
                "SELECT username, first_name FROM users WHERE tg_id = ?",
                (info["invited_by"],),
            ).fetchone()
            info["inviter_username"] = inviter["username"] if inviter else None
            info["inviter_name"] = inviter["first_name"] if inviter else None
        
        # Сколько пригласил
        referrals = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE invited_by = ?",
            (tg_id,),
        ).fetchone()
        info["referrals_count_actual"] = referrals["count"]
        
        return info
    finally:
        conn.close()


def get_stats():
    """Общая статистика бота"""
    conn = get_connection()
    try:
        stats = {}
        
        # Всего пользователей
        stats["total_users"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        
        # Активные за 7 дней
        stats["active_7d"] = conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_active_at >= datetime('now', '-7 days')"
        ).fetchone()[0]
        
        # Активные за 30 дней
        stats["active_30d"] = conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_active_at >= datetime('now', '-30 days')"
        ).fetchone()[0]
        
        # Прошли квест (хотя бы 1 шаг)
        stats["quest_started"] = conn.execute(
            "SELECT COUNT(DISTINCT tg_id) FROM quest_progress"
        ).fetchone()[0]
        
        # Прошли финальный тест
        stats["test_passed"] = conn.execute(
            "SELECT COUNT(*) FROM users WHERE final_test_passed = 1"
        ).fetchone()[0]
        
        # Запросили награду
        stats["reward_claimed"] = conn.execute(
            "SELECT COUNT(DISTINCT tg_id) FROM rewards"
        ).fetchone()[0]
        
        # Получили выплату
        stats["reward_paid"] = conn.execute(
            "SELECT COUNT(DISTINCT tg_id) FROM rewards WHERE status = 'paid'"
        ).fetchone()[0]
        
        # Ожидают выплаты
        stats["reward_pending"] = conn.execute(
            "SELECT COUNT(DISTINCT tg_id) FROM rewards WHERE status = 'pending_manual'"
        ).fetchone()[0]
        
        return stats
    finally:
        conn.close()


def get_all_users_tg_ids():
    """Получить все ID пользователей (для рассылки)"""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT tg_id FROM users")
        return [row["tg_id"] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_users_by_filter(filter_type):
    """Получить пользователей по фильтру для рассылки"""
    conn = get_connection()
    try:
        if filter_type == "active":
            # Активные за 30 дней
            cursor = conn.execute(
                "SELECT tg_id FROM users WHERE last_active_at >= datetime('now', '-30 days')"
            )
        elif filter_type == "quest_done":
            # Прошли квест (хотя бы 1 шаг)
            cursor = conn.execute(
                "SELECT DISTINCT tg_id FROM quest_progress"
            )
        elif filter_type == "quest_not_done":
            # Не прошли квест
            cursor = conn.execute(
                """SELECT tg_id FROM users 
                   WHERE tg_id NOT IN (SELECT DISTINCT tg_id FROM quest_progress)"""
            )
        elif filter_type == "inactive":
            # Не заходили 7+ дней
            cursor = conn.execute(
                """SELECT tg_id FROM users 
                   WHERE last_active_at < datetime('now', '-7 days') 
                   OR last_active_at IS NULL"""
            )
        else:
            # Все пользователи
            cursor = conn.execute("SELECT tg_id FROM users")
        
        return [row["tg_id"] for row in cursor.fetchall()]
    finally:
        conn.close()


def update_last_active(tg_id):
    """Обновить время последней активности"""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE users SET last_active_at = datetime('now') WHERE tg_id = ?",
            (tg_id,),
        )
        conn.commit()
    finally:
        conn.close()


def export_to_csv():
    """Экспорт всех данных в CSV формат"""
    conn = get_connection()
    try:
        # Пользователи
        users = conn.execute("SELECT * FROM users").fetchall()
        
        # Формируем CSV
        import csv
        import io
        
        output = io.StringIO()
        
        # Пользователи
        output.write("=== USERS ===\n")
        if users:
            writer = csv.DictWriter(output, fieldnames=users[0].keys())
            writer.writeheader()
            for user in users:
                writer.writerow(dict(user))
        
        output.write("\n=== REWARDS ===\n")
        rewards = conn.execute("SELECT * FROM rewards").fetchall()
        if rewards:
            writer = csv.DictWriter(output, fieldnames=rewards[0].keys())
            writer.writeheader()
            for reward in rewards:
                writer.writerow(dict(reward))
        
        output.write("\n=== USER_BADGES ===\n")
        badges = conn.execute("SELECT * FROM user_badges").fetchall()
        if badges:
            writer = csv.DictWriter(output, fieldnames=badges[0].keys())
            writer.writeheader()
            for badge in badges:
                writer.writerow(dict(badge))
        
        return output.getvalue()
    finally:
        conn.close()