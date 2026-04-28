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
