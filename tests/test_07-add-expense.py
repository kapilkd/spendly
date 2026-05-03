"""
Tests for Step 07: Add Expense feature.

All test logic is derived exclusively from the feature specification at:
  .claude/specs/07-add-expense.md

Routes under test:
  GET  /expenses/add   — render the add-expense form (auth required)
  POST /expenses/add   — validate and persist a new expense (auth required)

Spec-defined allowed categories:
  Food, Transport, Entertainment, Utilities, Shopping, Healthcare, Bills,
  Education, Other

On success the user is redirected to /profile (never shown the form again).
On validation failure the form is re-rendered (200) with the error message and
all previously submitted values pre-filled (sticky inputs).
"""

import pytest
from app import app as flask_app
from database.db import init_db, get_db
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Fresh in-memory Flask app for every test."""
    flask_app.config.update({
        'TESTING': True,
        'DATABASE': ':memory:',
        'SECRET_KEY': 'test-secret',
        'WTF_CSRF_ENABLED': False,
    })
    with flask_app.app_context():
        init_db()
        yield flask_app


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    return app.test_client()


@pytest.fixture
def user_client(app):
    """
    Test client with a freshly registered user already logged in.
    Returns (test_client, user_id) so tests can inspect the DB.
    """
    db = get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Expense Tester", "tester@example.com", generate_password_hash("securepass1")),
    )
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    tc = app.test_client()
    with tc.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Expense Tester"

    return tc, user_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_FORM = {
    "title":    "Coffee with friends",
    "amount":   "250.00",
    "category": "Food",
    "date":     "2026-05-01",
    "note":     "Nice espresso",
}


def _post_expense(client, **overrides):
    """POST /expenses/add with _VALID_FORM, overriding individual fields."""
    data = {**_VALID_FORM, **overrides}
    # Allow callers to explicitly remove a key by passing None
    data = {k: v for k, v in data.items() if v is not None}
    return client.post("/expenses/add", data=data, follow_redirects=False)


def _expense_rows(app, user_id):
    """Return all expense rows for *user_id* from the DB.

    The ``app`` fixture already holds the application context open for the
    entire test (``with flask_app.app_context(): … yield``), so we must NOT
    push a second context here — that would create a new ``g`` and a separate
    in-memory connection that sees an empty database.  We call ``get_db()``
    directly, which reuses the connection already stored on ``g``.
    """
    return get_db().execute(
        "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchall()


# ---------------------------------------------------------------------------
# 1. Auth guards
# ---------------------------------------------------------------------------

class TestAuthGuards:
    def test_get_unauthenticated_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "GET /expenses/add without login must return 302"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_get_unauthenticated_is_not_200(self, client):
        response = client.get("/expenses/add")
        assert response.status_code != 200, (
            "GET /expenses/add must not be accessible without authentication"
        )

    def test_post_unauthenticated_redirects_to_login(self, client):
        response = _post_expense(client)
        assert response.status_code == 302, (
            "POST /expenses/add without login must return 302"
        )
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST must redirect to /login"
        )

    def test_post_unauthenticated_does_not_insert_row(self, client, app):
        """An unauthenticated POST must not write anything to the DB."""
        _post_expense(client)
        # The app fixture holds the context open — call get_db() directly.
        count = get_db().execute(
            "SELECT COUNT(*) FROM expenses"
        ).fetchone()[0]
        assert count == 0, (
            "No expense must be inserted for an unauthenticated POST"
        )


# ---------------------------------------------------------------------------
# 2. GET /expenses/add — authenticated
# ---------------------------------------------------------------------------

class TestGetAddExpensePage:
    def test_returns_200_for_authenticated_user(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        assert response.status_code == 200, (
            "GET /expenses/add must return 200 for a logged-in user"
        )

    def test_page_contains_add_expense_heading(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        assert b"Add Expense" in response.data, (
            "Page must contain an 'Add Expense' heading or title"
        )

    def test_page_has_title_field(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="title"' in html, "Form must contain a title input field"

    def test_page_has_amount_field(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="amount"' in html, "Form must contain an amount input field"

    def test_page_has_category_dropdown(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="category"' in html, "Form must contain a category select field"

    def test_page_has_date_field(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="date"' in html, "Form must contain a date input field"

    def test_page_has_note_field(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert 'name="note"' in html, "Form must contain a note input field"

    def test_category_dropdown_lists_all_allowed_categories(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        for cat in [
            b"Food", b"Transport", b"Entertainment", b"Utilities",
            b"Shopping", b"Healthcare", b"Bills", b"Education", b"Other",
        ]:
            assert cat in response.data, (
                f"Category option '{cat}' must appear in the category dropdown"
            )

    def test_form_posts_to_add_expense_route(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        html = response.data.decode("utf-8")
        assert "/expenses/add" in html, (
            "Form action must point to /expenses/add"
        )

    def test_form_uses_post_method(self, user_client):
        tc, _ = user_client
        response = tc.get("/expenses/add")
        html = response.data.decode("utf-8").lower()
        assert 'method="post"' in html, "Form must use method='post'"

    def test_page_extends_base_template(self, user_client):
        """Base template landmark (e.g., nav or base-level wrapper) must be present."""
        tc, _ = user_client
        response = tc.get("/expenses/add")
        # base.html always renders; check for the HTML doctype or a known base landmark
        assert b"<!DOCTYPE html>" in response.data or b"<!doctype html>" in response.data, (
            "Page must render a full HTML document (extends base.html)"
        )


# ---------------------------------------------------------------------------
# 3. POST /expenses/add — happy path
# ---------------------------------------------------------------------------

class TestPostExpenseHappyPath:
    def test_valid_post_redirects_to_profile(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc)
        assert response.status_code == 302, (
            "A valid POST must redirect (302)"
        )
        assert "/profile" in response.headers["Location"], (
            "Successful POST must redirect to /profile"
        )

    def test_valid_post_inserts_one_row_in_db(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc)
        rows = _expense_rows(app, user_id)
        assert len(rows) == 1, (
            "Exactly one expense row must be inserted after a valid POST"
        )

    def test_valid_post_stores_correct_title(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc, title="Special Coffee")
        rows = _expense_rows(app, user_id)
        assert rows[0]["title"] == "Special Coffee", (
            "Stored title must match the submitted value"
        )

    def test_valid_post_stores_correct_amount(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc, amount="375.50")
        rows = _expense_rows(app, user_id)
        assert abs(rows[0]["amount"] - 375.50) < 0.001, (
            "Stored amount must match the submitted numeric value"
        )

    def test_valid_post_stores_correct_category(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc, category="Transport")
        rows = _expense_rows(app, user_id)
        assert rows[0]["category"] == "Transport", (
            "Stored category must match the submitted value"
        )

    def test_valid_post_stores_correct_date(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc, date="2026-04-15")
        rows = _expense_rows(app, user_id)
        assert rows[0]["date"] == "2026-04-15", (
            "Stored date must match the submitted YYYY-MM-DD value"
        )

    def test_valid_post_stores_correct_note(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc, note="Espresso at noon")
        rows = _expense_rows(app, user_id)
        assert rows[0]["note"] == "Espresso at noon", (
            "Stored note must match the submitted value"
        )

    def test_valid_post_stores_correct_user_id(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc)
        rows = _expense_rows(app, user_id)
        assert rows[0]["user_id"] == user_id, (
            "Expense must be associated with the logged-in user's ID"
        )

    def test_valid_post_without_note_succeeds(self, user_client, app):
        """Note is optional — omitting it must not cause an error."""
        tc, user_id = user_client
        data = {k: v for k, v in _VALID_FORM.items() if k != "note"}
        response = tc.post("/expenses/add", data=data, follow_redirects=False)
        assert response.status_code == 302, (
            "POST without a note must still succeed and redirect"
        )
        rows = _expense_rows(app, user_id)
        assert len(rows) == 1, "Expense without a note must be saved to the DB"

    def test_valid_post_with_empty_note_succeeds(self, user_client, app):
        """An empty note field must be accepted (treated as optional)."""
        tc, user_id = user_client
        _post_expense(tc, note="")
        rows = _expense_rows(app, user_id)
        assert len(rows) == 1, "Expense with empty note string must be saved to the DB"

    def test_success_does_not_re_render_the_form(self, user_client):
        """After a valid POST the response must be a redirect, never a 200 with the form."""
        tc, _ = user_client
        response = _post_expense(tc)
        assert response.status_code != 200, (
            "A successful POST must NOT re-render the add-expense form"
        )

    def test_new_expense_appears_on_profile_after_redirect(self, user_client):
        tc, _ = user_client
        _post_expense(tc, title="Unique Expense Title XYZ")
        # Follow the redirect to /profile
        profile = tc.get("/profile")
        assert b"Unique Expense Title XYZ" in profile.data, (
            "The new expense must appear in the profile transaction list immediately after redirect"
        )

    def test_profile_transaction_count_increases_after_add(self, user_client, app):
        """
        Start with no expenses for this user; after adding one, the profile must
        show a transaction count of 1.
        """
        tc, user_id = user_client
        _post_expense(tc)
        profile = tc.get("/profile")
        assert b"1" in profile.data, (
            "Profile transaction count must be 1 after adding the first expense"
        )

    def test_profile_total_reflects_new_expense(self, user_client):
        """After adding a 500-rupee expense the profile total must include it."""
        tc, _ = user_client
        _post_expense(tc, amount="500", title="Total Check Expense")
        profile = tc.get("/profile")
        assert "500".encode() in profile.data, (
            "Profile total spent must include the newly added expense amount"
        )


# ---------------------------------------------------------------------------
# 4. POST validation — empty / whitespace title
# ---------------------------------------------------------------------------

class TestTitleValidation:
    def test_empty_title_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, title="")
        assert response.status_code == 200, (
            "Empty title must re-render the form (200), not redirect"
        )

    def test_empty_title_shows_error_message(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, title="")
        assert b"Title" in response.data or b"title" in response.data, (
            "A title-related error message must appear when title is empty"
        )

    def test_whitespace_only_title_returns_200(self, user_client):
        """Server must strip whitespace before checking — spaces-only is invalid."""
        tc, _ = user_client
        response = _post_expense(tc, title="     ")
        assert response.status_code == 200, (
            "Whitespace-only title must re-render the form with an error"
        )

    def test_whitespace_only_title_shows_error(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, title="     ")
        assert b"required" in response.data.lower() or b"title" in response.data.lower(), (
            "A validation error must be shown for a whitespace-only title"
        )

    def test_empty_title_does_not_insert_row(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc, title="")
        rows = _expense_rows(app, user_id)
        assert len(rows) == 0, (
            "No expense must be inserted when the title is empty"
        )

    def test_whitespace_title_does_not_insert_row(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc, title="   ")
        rows = _expense_rows(app, user_id)
        assert len(rows) == 0, (
            "No expense must be inserted when the title is whitespace-only"
        )


# ---------------------------------------------------------------------------
# 5. POST validation — amount
# ---------------------------------------------------------------------------

class TestAmountValidation:
    def test_zero_amount_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="0")
        assert response.status_code == 200, (
            "Zero amount must re-render the form (200)"
        )

    def test_zero_amount_shows_error(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="0")
        assert b"amount" in response.data.lower() or b"positive" in response.data.lower(), (
            "An amount-related error must appear for zero amount"
        )

    def test_negative_amount_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="-100")
        assert response.status_code == 200, (
            "Negative amount must re-render the form (200)"
        )

    def test_negative_amount_shows_error(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="-100")
        assert b"amount" in response.data.lower() or b"positive" in response.data.lower(), (
            "An amount-related error must appear for negative amount"
        )

    def test_non_numeric_amount_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="abc")
        assert response.status_code == 200, (
            "Non-numeric amount must re-render the form (200)"
        )

    def test_non_numeric_amount_shows_error(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="abc")
        assert b"amount" in response.data.lower() or b"positive" in response.data.lower(), (
            "An amount-related error must appear for non-numeric input"
        )

    def test_empty_amount_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="")
        assert response.status_code == 200, (
            "Empty amount must re-render the form (200)"
        )

    def test_empty_amount_shows_error(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="")
        assert b"amount" in response.data.lower() or b"positive" in response.data.lower(), (
            "An amount-related error must appear for empty amount"
        )

    @pytest.mark.parametrize("bad_amount", ["0", "0.00", "-1", "-0.01", "abc", "", "  "])
    def test_bad_amounts_do_not_insert_row(self, user_client, app, bad_amount):
        tc, user_id = user_client
        _post_expense(tc, amount=bad_amount)
        rows = _expense_rows(app, user_id)
        assert len(rows) == 0, (
            f"No expense must be inserted for invalid amount '{bad_amount}'"
        )

    def test_valid_decimal_amount_is_accepted(self, user_client, app):
        """e.g., 99.99 is a valid positive amount."""
        tc, user_id = user_client
        response = _post_expense(tc, amount="99.99")
        assert response.status_code == 302, (
            "Decimal amount 99.99 must be accepted and result in a redirect"
        )


# ---------------------------------------------------------------------------
# 6. POST validation — date
# ---------------------------------------------------------------------------

class TestDateValidation:
    def test_wrong_date_format_dd_mm_yyyy_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, date="01-05-2026")
        assert response.status_code == 200, (
            "DD-MM-YYYY date format must fail validation and re-render the form"
        )

    def test_wrong_date_format_dd_mm_yyyy_shows_error(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, date="01-05-2026")
        assert b"date" in response.data.lower() or b"YYYY-MM-DD" in response.data, (
            "A date-format error must be shown for DD-MM-YYYY input"
        )

    def test_wrong_date_format_text_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, date="May 1 2026")
        assert response.status_code == 200, (
            "Freeform text date must fail validation and re-render the form"
        )

    def test_empty_date_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, date="")
        assert response.status_code == 200, (
            "Empty date must fail validation and re-render the form"
        )

    def test_empty_date_shows_error(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, date="")
        assert b"date" in response.data.lower(), (
            "A date-related error must appear when date is empty"
        )

    @pytest.mark.parametrize("bad_date", ["01-05-2026", "2026/05/01", "May 1 2026", ""])
    def test_bad_dates_do_not_insert_row(self, user_client, app, bad_date):
        tc, user_id = user_client
        _post_expense(tc, date=bad_date)
        rows = _expense_rows(app, user_id)
        assert len(rows) == 0, (
            f"No expense must be inserted for invalid date '{bad_date}'"
        )

    def test_valid_yyyy_mm_dd_date_is_accepted(self, user_client, app):
        tc, user_id = user_client
        response = _post_expense(tc, date="2026-12-31")
        assert response.status_code == 302, (
            "YYYY-MM-DD date must be accepted and result in a redirect"
        )


# ---------------------------------------------------------------------------
# 7. POST validation — category
# ---------------------------------------------------------------------------

class TestCategoryValidation:
    def test_unknown_category_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, category="Gambling")
        assert response.status_code == 200, (
            "An unknown category must re-render the form (200)"
        )

    def test_unknown_category_shows_error(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, category="Gambling")
        assert b"category" in response.data.lower() or b"valid" in response.data.lower(), (
            "A category-related error must appear for an unknown category"
        )

    def test_empty_category_returns_200(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, category="")
        assert response.status_code == 200, (
            "Empty category selection must re-render the form"
        )

    def test_empty_category_shows_error(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, category="")
        assert b"category" in response.data.lower() or b"valid" in response.data.lower(), (
            "A category-related error must appear when category is empty"
        )

    @pytest.mark.parametrize("bad_cat", ["Gambling", "Rent", "Miscellaneous", "FOOD", "food", ""])
    def test_invalid_categories_do_not_insert_row(self, user_client, app, bad_cat):
        tc, user_id = user_client
        _post_expense(tc, category=bad_cat)
        rows = _expense_rows(app, user_id)
        assert len(rows) == 0, (
            f"No expense must be inserted for invalid category '{bad_cat}'"
        )

    @pytest.mark.parametrize("valid_cat", [
        "Food", "Transport", "Entertainment", "Utilities",
        "Shopping", "Healthcare", "Bills", "Education", "Other",
    ])
    def test_all_allowed_categories_are_accepted(self, app, valid_cat):
        """Every category from the spec-defined allowed list must produce a successful insert."""
        db = get_db()
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (f"User {valid_cat}", f"{valid_cat.lower()}@example.com",
             generate_password_hash("pass1234")),
        )
        db.commit()
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        tc = app.test_client()
        with tc.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["user_name"] = f"User {valid_cat}"

        response = _post_expense(tc, category=valid_cat)
        assert response.status_code == 302, (
            f"Category '{valid_cat}' must be accepted and redirect to /profile"
        )
        rows = get_db().execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchall()
        assert len(rows) == 1, (
            f"One expense must be in the DB after posting with category '{valid_cat}'"
        )
        assert rows[0]["category"] == valid_cat, (
            f"Stored category must be '{valid_cat}'"
        )


# ---------------------------------------------------------------------------
# 8. Sticky form values on validation failure
# ---------------------------------------------------------------------------

class TestStickyFormValues:
    def test_title_is_pre_filled_after_bad_amount(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, title="My Lunch", amount="-5")
        assert b"My Lunch" in response.data, (
            "Title must be pre-filled after a failed POST due to bad amount"
        )

    def test_amount_is_pre_filled_after_bad_date(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="123", date="not-a-date")
        assert b"123" in response.data, (
            "Amount must be pre-filled after a failed POST due to bad date"
        )

    def test_category_is_pre_selected_after_bad_title(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, title="", category="Shopping")
        assert b"Shopping" in response.data, (
            "Category must be pre-selected (value present in HTML) after a failed POST"
        )

    def test_date_is_pre_filled_after_bad_amount(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, amount="0", date="2026-06-15")
        assert b"2026-06-15" in response.data, (
            "Date must be pre-filled after a failed POST due to bad amount"
        )

    def test_note_is_pre_filled_after_bad_title(self, user_client):
        tc, _ = user_client
        response = _post_expense(tc, title="", note="Remember this note")
        assert b"Remember this note" in response.data, (
            "Note must be pre-filled after a failed POST due to empty title"
        )

    def test_all_fields_sticky_on_invalid_category(self, user_client):
        tc, _ = user_client
        response = _post_expense(
            tc,
            title="Sticky Test",
            amount="88",
            category="UnknownCat",
            date="2026-07-04",
            note="Sticky note",
        )
        html = response.data.decode("utf-8")
        assert "Sticky Test" in html, "Title must be sticky after invalid category"
        assert "88" in html, "Amount must be sticky after invalid category"
        assert "2026-07-04" in html, "Date must be sticky after invalid category"
        assert "Sticky note" in html, "Note must be sticky after invalid category"


# ---------------------------------------------------------------------------
# 9. Error message visibility
# ---------------------------------------------------------------------------

class TestErrorMessageVisibility:
    def test_error_container_present_on_validation_failure(self, user_client):
        """The error element from the template must be rendered on any validation failure."""
        tc, _ = user_client
        response = _post_expense(tc, title="")
        html = response.data.decode("utf-8")
        # The spec says form re-renders with an error message; the template uses
        # a conditional block — any non-empty error text means the block rendered
        assert "error" in html.lower(), (
            "An error element must appear in the HTML when validation fails"
        )

    def test_no_error_shown_on_get(self, user_client):
        """A fresh GET must not display an error message."""
        tc, _ = user_client
        response = tc.get("/expenses/add")
        # Check that the error div/block is absent on a clean GET
        assert b"auth-error" not in response.data, (
            "Error block must not be rendered on a clean GET request"
        )


# ---------------------------------------------------------------------------
# 10. DB side effects and data integrity
# ---------------------------------------------------------------------------

class TestDbSideEffects:
    def test_multiple_expenses_stored_independently(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc, title="First Expense", amount="100")
        _post_expense(tc, title="Second Expense", amount="200")
        rows = _expense_rows(app, user_id)
        assert len(rows) == 2, "Two separate POSTs must result in two DB rows"
        titles = {r["title"] for r in rows}
        assert "First Expense" in titles
        assert "Second Expense" in titles

    def test_expense_row_has_all_required_columns(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc, title="Column Check", amount="50", category="Bills",
                      date="2026-03-10", note="Test note")
        rows = _expense_rows(app, user_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["title"] == "Column Check"
        assert abs(row["amount"] - 50.0) < 0.001
        assert row["category"] == "Bills"
        assert row["date"] == "2026-03-10"
        assert row["note"] == "Test note"
        assert row["user_id"] == user_id
        assert row["id"] is not None, "Row must have an auto-assigned ID"

    def test_expense_created_at_is_set(self, user_client, app):
        tc, user_id = user_client
        _post_expense(tc)
        rows = _expense_rows(app, user_id)
        assert rows[0]["created_at"] is not None, (
            "created_at must be set automatically on insert"
        )

    def test_second_user_does_not_see_first_users_expense(self, app):
        """Expenses must be isolated per user_id."""
        db = get_db()

        # Create user 1
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("User One", "one@isolation.com", generate_password_hash("pass1234")),
        )
        db.commit()
        user1_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Create user 2
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("User Two", "two@isolation.com", generate_password_hash("pass1234")),
        )
        db.commit()
        user2_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # User 1 adds an expense
        tc1 = app.test_client()
        with tc1.session_transaction() as sess:
            sess["user_id"] = user1_id
            sess["user_name"] = "User One"
        _post_expense(tc1, title="User One Secret Expense")

        # User 2 views their own profile
        tc2 = app.test_client()
        with tc2.session_transaction() as sess:
            sess["user_id"] = user2_id
            sess["user_name"] = "User Two"

        profile = tc2.get("/profile")
        assert b"User One Secret Expense" not in profile.data, (
            "User 2 must NOT see User 1's expenses on their profile page"
        )

    def test_failed_validation_leaves_db_empty(self, user_client, app):
        """Any failed validation must leave the expenses table empty for this user."""
        tc, user_id = user_client
        # Fire several invalid posts
        _post_expense(tc, title="")
        _post_expense(tc, amount="0")
        _post_expense(tc, date="bad")
        _post_expense(tc, category="NotACategory")
        rows = _expense_rows(app, user_id)
        assert len(rows) == 0, (
            "No expense must be inserted after multiple failed validation attempts"
        )
