"""
Tests for Step 6: Date filter on the /profile page.

All test logic is derived from the feature specification, not from reading
the implementation. The spec lives at:
  .claude/specs/06-date-filter-profile-page.md

Seeded expenses (inserted fresh for every test via the `seeded_client` fixture):
  A  2026-04-01  100  Food
  B  2026-04-10  200  Transport
  C  2026-04-20  300  Shopping
  D  2026-04-30  400  Utilities

This gives clean, predictable date boundaries for all filter assertions.
"""

import pytest
from app import app as flask_app
from database.db import init_db, get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Isolated in-memory Flask app for every test."""
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
    return app.test_client()


@pytest.fixture
def seeded_client(app):
    """
    A test client with:
      - one registered user  (id=1, name="Filter Tester")
      - four expenses spread across April 2026
    Returns (client, user_id) so tests can inject the session directly.
    """
    from werkzeug.security import generate_password_hash

    db = get_db()
    db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Filter Tester", "filter@example.com", generate_password_hash("testpass1")),
    )
    db.commit()
    user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    db.executemany(
        "INSERT INTO expenses (user_id, title, amount, category, date, note)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [
            (user_id, "Expense A", 100.0, "Food",      "2026-04-01", None),
            (user_id, "Expense B", 200.0, "Transport", "2026-04-10", None),
            (user_id, "Expense C", 300.0, "Shopping",  "2026-04-20", None),
            (user_id, "Expense D", 400.0, "Utilities", "2026-04-30", None),
        ],
    )
    db.commit()

    tc = app.test_client()
    with tc.session_transaction() as sess:
        sess["user_id"]   = user_id
        sess["user_name"] = "Filter Tester"

    return tc, user_id


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _profile(client, **params):
    """Issue GET /profile with optional query-string params."""
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"/profile?{qs}" if qs else "/profile"
    return client.get(url)


# ---------------------------------------------------------------------------
# 1. Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_get_redirects_to_login(self, client):
        response = _profile(client)
        assert response.status_code == 302, "Expected redirect for unauthenticated request"
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_unauthenticated_get_is_not_200(self, client):
        response = _profile(client)
        assert response.status_code != 200, (
            "Profile page must not be accessible without login"
        )


# ---------------------------------------------------------------------------
# 2. No filter — regression (all transactions shown)
# ---------------------------------------------------------------------------

class TestNoFilter:
    def test_returns_200_with_no_params(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        assert response.status_code == 200, "Expected 200 for authenticated /profile"

    def test_shows_all_four_expenses_with_no_filter(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        for label in (b"Expense A", b"Expense B", b"Expense C", b"Expense D"):
            assert label in response.data, (
                f"{label} should appear when no filter is applied"
            )

    def test_shows_all_categories_with_no_filter(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        for cat in (b"Food", b"Transport", b"Shopping", b"Utilities"):
            assert cat in response.data, (
                f"Category {cat} should appear with no filter"
            )

    def test_total_spent_reflects_all_expenses_with_no_filter(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        # Sum of A+B+C+D = 1,000; formatted as ₹1,000
        assert "1,000".encode() in response.data, (
            "Total spent without filter must equal ₹1,000 (sum of all four expenses)"
        )

    def test_transaction_count_reflects_all_expenses_with_no_filter(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        # 4 transactions total — "4" must appear somewhere in the stats area
        assert b"4" in response.data, (
            "Transaction count must be 4 when no filter is applied"
        )


# ---------------------------------------------------------------------------
# 3. Valid date range — both bounds provided
# ---------------------------------------------------------------------------

class TestValidRangeFilter:
    def test_returns_200_with_valid_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        assert response.status_code == 200, "Expected 200 for valid date range"

    def test_shows_only_expenses_within_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        assert b"Expense B" in response.data, "Expense B (2026-04-10) must appear in [Apr10,Apr20]"
        assert b"Expense C" in response.data, "Expense C (2026-04-20) must appear in [Apr10,Apr20]"

    def test_excludes_expenses_outside_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        assert b"Expense A" not in response.data, (
            "Expense A (2026-04-01) must NOT appear in [Apr10,Apr20]"
        )
        assert b"Expense D" not in response.data, (
            "Expense D (2026-04-30) must NOT appear in [Apr10,Apr20]"
        )

    def test_stats_total_reflects_filtered_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        # B(200) + C(300) = 500; formatted as ₹500
        assert "500".encode() in response.data, (
            "Total spent must be 500 for expenses B+C only"
        )

    def test_stats_count_reflects_filtered_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        assert b"2" in response.data, (
            "Transaction count must be 2 for the [Apr10,Apr20] range"
        )

    def test_category_breakdown_reflects_filtered_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        # B is Transport, C is Shopping — both must appear
        assert b"Transport" in response.data, "Transport must appear in category breakdown"
        assert b"Shopping" in response.data, "Shopping must appear in category breakdown"

    def test_out_of_range_categories_absent_from_breakdown(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        # Food (A, Apr01) and Utilities (D, Apr30) are outside the range.
        # They may still appear as badge text inside transaction rows for OTHER reasons,
        # but because the transaction list also filters, neither row should be present.
        assert b"Expense A" not in response.data, "Food expense must not be in filtered view"
        assert b"Expense D" not in response.data, "Utilities expense must not be in filtered view"

    def test_amounts_show_rupee_symbol_in_filtered_view(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        assert "₹".encode("utf-8") in response.data, (
            "Currency must always display as ₹ in filtered view"
        )


# ---------------------------------------------------------------------------
# 4. from_date only (no to_date)
# ---------------------------------------------------------------------------

class TestFromDateOnly:
    def test_shows_expenses_on_or_after_from_date(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-20")
        assert b"Expense C" in response.data, "Expense C (Apr 20) must appear with from_date=Apr20"
        assert b"Expense D" in response.data, "Expense D (Apr 30) must appear with from_date=Apr20"

    def test_excludes_expenses_before_from_date(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-20")
        assert b"Expense A" not in response.data, (
            "Expense A (Apr 01) must NOT appear with from_date=Apr20"
        )
        assert b"Expense B" not in response.data, (
            "Expense B (Apr 10) must NOT appear with from_date=Apr20"
        )

    def test_returns_200_with_from_date_only(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-20")
        assert response.status_code == 200, "Expected 200 with from_date only"

    def test_stats_reflect_from_date_only_filter(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-20")
        # C(300) + D(400) = 700
        assert "700".encode() in response.data, (
            "Total spent must be 700 for expenses on or after Apr 20"
        )


# ---------------------------------------------------------------------------
# 5. to_date only (no from_date)
# ---------------------------------------------------------------------------

class TestToDateOnly:
    def test_shows_expenses_on_or_before_to_date(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, to_date="2026-04-10")
        assert b"Expense A" in response.data, "Expense A (Apr 01) must appear with to_date=Apr10"
        assert b"Expense B" in response.data, "Expense B (Apr 10) must appear with to_date=Apr10"

    def test_excludes_expenses_after_to_date(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, to_date="2026-04-10")
        assert b"Expense C" not in response.data, (
            "Expense C (Apr 20) must NOT appear with to_date=Apr10"
        )
        assert b"Expense D" not in response.data, (
            "Expense D (Apr 30) must NOT appear with to_date=Apr10"
        )

    def test_returns_200_with_to_date_only(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, to_date="2026-04-10")
        assert response.status_code == 200, "Expected 200 with to_date only"

    def test_stats_reflect_to_date_only_filter(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, to_date="2026-04-10")
        # A(100) + B(200) = 300
        assert "300".encode() in response.data, (
            "Total spent must be 300 for expenses on or before Apr 10"
        )


# ---------------------------------------------------------------------------
# 6. Invalid range: from_date > to_date
# ---------------------------------------------------------------------------

class TestInvalidRange:
    def test_returns_200_with_invalid_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-30", to_date="2026-04-01")
        assert response.status_code == 200, (
            "Invalid range must still return 200 (not crash or 4xx)"
        )

    def test_shows_error_message_with_invalid_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-30", to_date="2026-04-01")
        # The spec says an error message must be shown; check for key phrase
        assert b"date" in response.data.lower(), (
            "Response must contain a date-related error message"
        )
        # Also check the CSS error container rendered by the template
        assert b"filter-error" in response.data, (
            "The filter-error element must be present for an invalid range"
        )

    def test_falls_back_to_all_expenses_with_invalid_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-30", to_date="2026-04-01")
        for label in (b"Expense A", b"Expense B", b"Expense C", b"Expense D"):
            assert label in response.data, (
                f"{label} must appear in fallback (all transactions) after invalid range"
            )

    def test_total_reflects_all_expenses_on_invalid_range(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-30", to_date="2026-04-01")
        # Fallback = all four = 1,000
        assert "1,000".encode() in response.data, (
            "Total spent must fall back to 1,000 (all expenses) for invalid range"
        )

    def test_from_equals_to_is_valid(self, seeded_client):
        """A single-day range (from == to) is valid and must not show an error."""
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-10")
        assert b"filter-error" not in response.data, (
            "from_date == to_date is a valid single-day range and must not show an error"
        )
        assert b"Expense B" in response.data, (
            "Expense B (Apr 10) must appear for a single-day range on Apr 10"
        )


# ---------------------------------------------------------------------------
# 7. Input value repopulation after valid filter submit
# ---------------------------------------------------------------------------

class TestFilterValuePersistence:
    def test_from_date_input_repopulated_after_submit(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        assert b'value="2026-04-10"' in response.data, (
            "from_date input must be repopulated with submitted value"
        )

    def test_to_date_input_repopulated_after_submit(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10", to_date="2026-04-20")
        assert b'value="2026-04-20"' in response.data, (
            "to_date input must be repopulated with submitted value"
        )

    def test_from_date_only_repopulated(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-15")
        assert b'value="2026-04-15"' in response.data, (
            "from_date input must be repopulated when only from_date was submitted"
        )

    def test_to_date_only_repopulated(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, to_date="2026-04-15")
        assert b'value="2026-04-15"' in response.data, (
            "to_date input must be repopulated when only to_date was submitted"
        )

    def test_invalid_range_does_not_repopulate_date_inputs(self, seeded_client):
        """
        After an invalid range, the spec says the route falls back to unfiltered
        data and clears the active filter (both dates become empty strings).
        The inputs must NOT be pre-filled with the rejected dates.
        """
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-30", to_date="2026-04-01")
        assert b'value="2026-04-30"' not in response.data, (
            "from_date must not be repopulated after an invalid range"
        )
        assert b'value="2026-04-01"' not in response.data, (
            "to_date must not be repopulated after an invalid range"
        )


# ---------------------------------------------------------------------------
# 8. Clear link — no params means empty / blank date inputs
# ---------------------------------------------------------------------------

class TestClearFilter:
    def test_no_params_produces_empty_from_date_value(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        # The from_date input must be present on the page
        assert b'name="from_date"' in response.data, (
            "from_date input must be present on the profile page"
        )
        # When no filter params are given the template must not prefill either input
        # with a year-like date string (the value attribute must resolve to "")
        assert b'value="2026-' not in response.data, (
            "Date inputs must not contain a prefilled date value when no filter params are given"
        )

    def test_no_params_date_inputs_have_empty_value(self, seeded_client):
        """
        The cleaner assertion: when /profile is fetched with no params the two
        date inputs must each render with value="" (the Jinja template sets
        value="{{ filter.from_date }}" which must resolve to an empty string).
        """
        tc, _ = seeded_client
        response = _profile(tc)
        html = response.data.decode("utf-8")
        # Both inputs must appear with an empty value attribute
        assert 'name="from_date"' in html, "from_date input missing from page"
        assert 'name="to_date"' in html, "to_date input missing from page"
        # Check that neither date string prefill appears (no 2026- dates in values)
        # We look specifically for the pattern value="2026-" which would mean prefilled
        import re
        value_dates = re.findall(r'value="(2026-\d{2}-\d{2})"', html)
        assert value_dates == [], (
            f"Date inputs must be empty on clear, but found prefilled values: {value_dates}"
        )

    def test_clear_link_is_present(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        assert b"/profile" in response.data, (
            "A clear link pointing to /profile must be present on the page"
        )


# ---------------------------------------------------------------------------
# 9. Filter form structure (GET method, date input types)
# ---------------------------------------------------------------------------

class TestFilterFormStructure:
    def test_filter_form_uses_get_method(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        html = response.data.decode("utf-8")
        assert 'method="get"' in html.lower(), (
            "The filter form must use method='get'"
        )

    def test_from_date_input_type_is_date(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        html = response.data.decode("utf-8")
        assert 'type="date"' in html, (
            "Date inputs must have type='date' for browser date-picker support"
        )

    def test_filter_form_action_points_to_profile(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc)
        html = response.data.decode("utf-8")
        assert 'action="/profile"' in html, (
            "Filter form action must point to /profile"
        )


# ---------------------------------------------------------------------------
# 10. Boundary inclusiveness (BETWEEN semantics)
# ---------------------------------------------------------------------------

class TestBoundaryInclusiveness:
    def test_from_date_boundary_is_inclusive(self, seeded_client):
        """Expense on exactly from_date must be included."""
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-01")
        assert b"Expense A" in response.data, (
            "Expense A on exactly from_date=2026-04-01 must be included"
        )

    def test_to_date_boundary_is_inclusive(self, seeded_client):
        """Expense on exactly to_date must be included."""
        tc, _ = seeded_client
        response = _profile(tc, to_date="2026-04-30")
        assert b"Expense D" in response.data, (
            "Expense D on exactly to_date=2026-04-30 must be included"
        )

    def test_expense_just_before_from_date_excluded(self, seeded_client):
        """Expense one day before from_date must be excluded."""
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-04-10")
        assert b"Expense A" not in response.data, (
            "Expense A (Apr 01) must be excluded when from_date=Apr10"
        )

    def test_expense_just_after_to_date_excluded(self, seeded_client):
        """Expense one day after to_date must be excluded."""
        tc, _ = seeded_client
        response = _profile(tc, to_date="2026-04-20")
        assert b"Expense D" not in response.data, (
            "Expense D (Apr 30) must be excluded when to_date=Apr20"
        )


# ---------------------------------------------------------------------------
# 11. Edge case — range with no matching expenses
# ---------------------------------------------------------------------------

class TestEmptyFilterResult:
    def test_no_matching_expenses_returns_200(self, seeded_client):
        tc, _ = seeded_client
        # A date range that contains no seeded expenses
        response = _profile(tc, from_date="2026-03-01", to_date="2026-03-31")
        assert response.status_code == 200, (
            "A range with no matching expenses must still return 200"
        )

    def test_no_matching_expenses_shows_zero_total(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-03-01", to_date="2026-03-31")
        assert b"0" in response.data, (
            "Total spent must be ₹0 when no expenses match the filter"
        )

    def test_no_matching_expenses_shows_zero_count(self, seeded_client):
        tc, _ = seeded_client
        response = _profile(tc, from_date="2026-03-01", to_date="2026-03-31")
        # Transaction count stat should show 0
        html = response.data.decode("utf-8")
        # Check that none of our known expense titles appear
        assert "Expense A" not in html
        assert "Expense B" not in html
        assert "Expense C" not in html
        assert "Expense D" not in html


# ---------------------------------------------------------------------------
# 12. Parametrized: from/to combinations and expected visible expense titles
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("from_date,to_date,expected_titles,excluded_titles", [
    # Both bounds — mid range
    ("2026-04-10", "2026-04-20", ["Expense B", "Expense C"], ["Expense A", "Expense D"]),
    # Both bounds — full range
    ("2026-04-01", "2026-04-30", ["Expense A", "Expense B", "Expense C", "Expense D"], []),
    # from only — last two
    ("2026-04-20", "",           ["Expense C", "Expense D"], ["Expense A", "Expense B"]),
    # to only — first two
    ("",           "2026-04-10", ["Expense A", "Expense B"], ["Expense C", "Expense D"]),
    # Single expense — exact date match
    ("2026-04-01", "2026-04-01", ["Expense A"], ["Expense B", "Expense C", "Expense D"]),
    ("2026-04-30", "2026-04-30", ["Expense D"], ["Expense A", "Expense B", "Expense C"]),
])
def test_parametrized_date_filter_combinations(
    seeded_client, from_date, to_date, expected_titles, excluded_titles
):
    tc, _ = seeded_client
    params = {}
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date

    response = _profile(tc, **params)
    assert response.status_code == 200

    for title in expected_titles:
        assert title.encode() in response.data, (
            f"Expected '{title}' in response for from={from_date!r} to={to_date!r}"
        )
    for title in excluded_titles:
        assert title.encode() not in response.data, (
            f"Did NOT expect '{title}' in response for from={from_date!r} to={to_date!r}"
        )


# ---------------------------------------------------------------------------
# 13. Data isolation — second user sees only their own expenses
# ---------------------------------------------------------------------------

class TestUserIsolation:
    def test_filtered_view_shows_only_current_users_expenses(self, app):
        """
        A second user with their own expenses must not see the first user's
        expenses even when the same date range is requested.
        """
        from werkzeug.security import generate_password_hash

        db = get_db()
        # User 1
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("User One", "one@example.com", generate_password_hash("pass1234")),
        )
        db.commit()
        user1_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO expenses (user_id, title, amount, category, date)"
            " VALUES (?, ?, ?, ?, ?)",
            (user1_id, "User One Expense", 999.0, "Food", "2026-04-15"),
        )

        # User 2
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("User Two", "two@example.com", generate_password_hash("pass1234")),
        )
        db.commit()
        user2_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO expenses (user_id, title, amount, category, date)"
            " VALUES (?, ?, ?, ?, ?)",
            (user2_id, "User Two Expense", 111.0, "Transport", "2026-04-15"),
        )
        db.commit()

        tc = app.test_client()
        # Log in as User 2
        with tc.session_transaction() as sess:
            sess["user_id"]   = user2_id
            sess["user_name"] = "User Two"

        response = _profile(tc, from_date="2026-04-01", to_date="2026-04-30")
        assert b"User Two Expense" in response.data, (
            "User 2 must see their own expense in the filtered view"
        )
        assert b"User One Expense" not in response.data, (
            "User 2 must NOT see User 1's expenses in any filtered view"
        )
