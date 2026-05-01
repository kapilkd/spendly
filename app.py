from flask import Flask, render_template, request, redirect, url_for, session
import re
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['DATABASE'] = 'expense_tracker.db'
app.secret_key = "spendly-dev-secret"  # replace with env var in production

from database.db import close_db, init_db, seed_db, create_user, get_user_by_email, get_user_by_id

app.teardown_appcontext(close_db)


@app.cli.command('init-db')
def init_db_command():
    """Create all database tables."""
    init_db()
    seed_db()
    print("Database initialised.")


with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name     = request.form.get("name", "").strip()
    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not name:
        return render_template("register.html", error="Name is required.")

    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return render_template("register.html", error="Please enter a valid email address.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    if get_user_by_email(email):
        return render_template("register.html", error="An account with that email already exists.")

    try:
        create_user(name, email, generate_password_hash(password))
    except sqlite3.IntegrityError:
        return render_template("register.html", error="An account with that email already exists.")

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email    = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    user = get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session.clear()
    session["user_id"]   = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": session["user_name"],
        "email": "demo@spendly.dev",
        "member_since": "April 2026",
        "initials": "".join(w[0].upper() for w in session["user_name"].split()[:2]),
    }
    stats = {
        "total_spent": "₹7,228",
        "transaction_count": 8,
        "top_category": "Food",
    }
    transactions = [
        {"date": "25 Apr", "title": "Dinner with family",   "category": "Food",          "amount": "₹1,350"},
        {"date": "18 Apr", "title": "New shoes",            "category": "Shopping",      "amount": "₹2,499"},
        {"date": "15 Apr", "title": "Lunch with team",      "category": "Food",          "amount": "₹380"},
        {"date": "10 Apr", "title": "Electricity bill",     "category": "Utilities",     "amount": "₹1,200"},
        {"date": "05 Apr", "title": "Netflix subscription", "category": "Entertainment", "amount": "₹649"},
        {"date": "03 Apr", "title": "Metro card recharge",  "category": "Transport",     "amount": "₹200"},
    ]
    categories = [
        {"name": "Shopping",      "amount": "₹2,499", "percent": 35},
        {"name": "Food",          "amount": "₹1,730", "percent": 24},
        {"name": "Utilities",     "amount": "₹1,200", "percent": 17},
        {"name": "Entertainment", "amount": "₹649",   "percent": 9},
        {"name": "Healthcare",    "amount": "₹500",   "percent": 7},
        {"name": "Transport",     "amount": "₹200",   "percent": 3},
    ]
    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
