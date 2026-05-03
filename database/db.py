import sqlite3
import os
from flask import current_app, g


def get_db():
    if 'db' not in g:
        db_path = current_app.config['DATABASE']
        if db_path != ':memory:':
            db_path = os.path.join(current_app.root_path, db_path)
        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            title       TEXT    NOT NULL,
            amount      REAL    NOT NULL,
            category    TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            note        TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
    """)
    db.commit()


def seed_db():
    from werkzeug.security import generate_password_hash

    db = get_db()
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        return

    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.dev", generate_password_hash("password123"))
    )
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    db.executemany(
        "INSERT INTO expenses (user_id, title, amount, category, date, note) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (user_id, "Grocery run",          450.00, "Food",          "2026-04-01", "Weekly groceries"),
            (user_id, "Metro card recharge",   200.00, "Transport",     "2026-04-03", None),
            (user_id, "Netflix subscription",  649.00, "Entertainment", "2026-04-05", "Monthly plan"),
            (user_id, "Electricity bill",     1200.00, "Utilities",     "2026-04-10", "April bill"),
            (user_id, "Lunch with team",       380.00, "Food",          "2026-04-15", "Cafe Coffee Day"),
            (user_id, "New shoes",             2499.00, "Shopping",     "2026-04-18", None),
            (user_id, "Doctor consultation",   500.00, "Healthcare",    "2026-04-21", "General checkup"),
            (user_id, "Dinner with family",    1350.00, "Food",         "2026-04-25", "Weekend dinner"),
        ]
    )
    db.commit()


def get_user_by_email(email):
    return get_db().execute(
        "SELECT * FROM users WHERE email = ?",
        (email,)
    ).fetchone()


def _date_clause(from_date, to_date):
    if from_date and to_date:
        return " AND date BETWEEN ? AND ?", [from_date, to_date]
    if from_date:
        return " AND date >= ?", [from_date]
    if to_date:
        return " AND date <= ?", [to_date]
    return "", []


def get_summary_stats(user_id, from_date=None, to_date=None):
    db = get_db()
    clause, date_params = _date_clause(from_date, to_date)
    row = db.execute(
        """
        SELECT COALESCE(SUM(amount), 0) AS total_spent,
               COUNT(*) AS transaction_count
        FROM   expenses
        WHERE  user_id = ?
        """
        + clause,
        [user_id] + date_params,
    ).fetchone()
    top_row = db.execute(
        """
        SELECT   category, SUM(amount) AS cat_total
        FROM     expenses
        WHERE    user_id = ?
        """
        + clause
        + " GROUP BY category ORDER BY cat_total DESC LIMIT 1",
        [user_id] + date_params,
    ).fetchone()
    top_category = top_row["category"] if top_row else "—"
    return {
        "total_spent":       f"₹{row['total_spent']:,.0f}",
        "transaction_count": row["transaction_count"],
        "top_category":      top_category,
    }


def create_user(name, email, password_hash):
    db = get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash)
    )
    db.commit()


def create_expense(user_id, title, amount, category, date, note):
    db = get_db()
    db.execute(
        "INSERT INTO expenses (user_id, title, amount, category, date, note) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, title, amount, category, date, note)
    )
    db.commit()


def get_recent_transactions(user_id, limit=10, from_date=None, to_date=None):
    clause, date_params = _date_clause(from_date, to_date)
    rows = get_db().execute(
        """
        SELECT date, title, category, amount
        FROM   expenses
        WHERE  user_id = ?
        """
        + clause
        + " ORDER BY date DESC, id DESC LIMIT ?",
        [user_id] + date_params + [limit],
    ).fetchall()
    return [
        {
            "date":     r["date"],
            "title":    r["title"],
            "category": r["category"],
            "amount":   f"₹{r['amount']:,.0f}",
        }
        for r in rows
    ]


def get_user_by_id(user_id):
    from datetime import datetime
    row = get_db().execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    if row is None:
        return None
    created_at = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
    return {
        "id":           row["id"],
        "name":         row["name"],
        "email":        row["email"],
        "member_since": created_at.strftime("%B %Y"),
    }


def get_category_breakdown(user_id, from_date=None, to_date=None):
    clause, date_params = _date_clause(from_date, to_date)
    rows = get_db().execute(
        """
        SELECT   category, SUM(amount) AS amount
        FROM     expenses
        WHERE    user_id = ?
        """
        + clause
        + " GROUP BY category ORDER BY amount DESC",
        [user_id] + date_params,
    ).fetchall()
    if not rows:
        return []
    total = sum(r["amount"] for r in rows)
    cats = [
        {
            "name":       r["category"],
            "amount":     f"₹{r['amount']:,.0f}",
            "percent":    int(r["amount"] / total * 100),
            "_remainder": (r["amount"] / total * 100) % 1,
        }
        for r in rows
    ]
    deficit = 100 - sum(c["percent"] for c in cats)
    for i in sorted(range(len(cats)), key=lambda i: cats[i]["_remainder"], reverse=True)[:deficit]:
        cats[i]["percent"] += 1
    for c in cats:
        del c["_remainder"]
    return cats
