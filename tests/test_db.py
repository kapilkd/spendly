import sqlite3
import pytest
from database.db import get_db, seed_db


def test_tables_exist(app):
    db = get_db()
    tables = {
        row['name']
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert 'users' in tables
    assert 'expenses' in tables


def test_seed_inserts_data(app):
    seed_db()
    db = get_db()
    user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    expense_count = db.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    assert user_count == 1
    assert expense_count == 8


def test_seed_is_idempotent(app):
    seed_db()
    seed_db()  # second call must not add duplicates
    db = get_db()
    assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM expenses").fetchone()[0] == 8


def test_seed_user_fields(app):
    from werkzeug.security import check_password_hash
    seed_db()
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email = ?", ("demo@spendly.dev",)
    ).fetchone()
    assert user is not None
    assert user['name'] == "Demo User"
    assert check_password_hash(user['password_hash'], "password123")


def test_fk_enforcement(app):
    db = get_db()
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO expenses (user_id, title, amount, category, date) "
            "VALUES (?, ?, ?, ?, ?)",
            (9999, "Ghost expense", 100.0, "Food", "2026-04-01")
        )
        db.commit()


def test_get_db_same_connection(app):
    db1 = get_db()
    db2 = get_db()
    assert db1 is db2


def test_close_db_on_teardown(app):
    conn_ref = None
    with app.app_context():
        conn_ref = get_db()
    with pytest.raises(Exception):
        conn_ref.execute("SELECT 1")
