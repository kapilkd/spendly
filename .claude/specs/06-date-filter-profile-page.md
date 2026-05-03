# Spec: Date Filter For Profile Page

## Overview

Step 6 adds a date-range filter to the profile page so users can narrow their
transaction history, summary stats, and category breakdown to a specific period.
The filter is submitted as GET query parameters (`from_date` and `to_date`),
keeping the URL bookmarkable and avoiding any session state. All four DB helpers
that back the profile page must be extended to accept an optional date range;
the profile route passes the active filter through to both the helpers and the
template so the form can repopulate its fields on reload.

## Depends on

- Step 1: Database setup (`expenses` table with a `date` column exists)
- Step 2: Registration (user accounts exist)
- Step 3: Login / Logout (`session["user_id"]` is set)
- Step 4: Profile page static UI (template structure is in place)
- Step 5: Backend connection (live DB helpers are wired to the profile route)

## Routes

No new routes. The existing `GET /profile` route is modified to read
`from_date` and `to_date` from `request.args` and pass them to DB helpers.

## Database changes

No database changes. The `expenses.date` column (`TEXT`, ISO-8601 `YYYY-MM-DD`)
already supports lexicographic date comparison with `BETWEEN`.

## Templates

- **Modify**: `templates/profile.html`
  - Add a filter form (GET method, action `url_for('profile')`) above the
    transaction table with two `<input type="date">` fields: `from_date` and
    `to_date`, and a Submit button.
  - Repopulate both inputs from the `filter` dict passed by the route so values
    persist after the form is submitted.
  - Add a "Clear" link (plain anchor pointing to `url_for('profile')`) beside
    the Submit button so the user can reset the filter.
  - All four data sections (user card, summary stats, transaction list, category
    breakdown) already use Jinja variables — no structural changes needed beyond
    the new filter form.

## Files to change

- `app.py`
  - In the `profile()` view, read `from_date` and `to_date` from
    `request.args.get(...)`.
  - Validate that if both dates are provided, `from_date <= to_date`; if not,
    pass an `error` string to the template and use unfiltered data.
  - Pass a `filter` dict `{"from_date": from_date, "to_date": to_date}` to the
    template.
  - Forward the date range to each of the four DB helpers.

- `database/db.py`
  - Update `get_summary_stats(user_id, from_date=None, to_date=None)` to
    filter by date when either bound is provided.
  - Update `get_recent_transactions(user_id, limit=10, from_date=None, to_date=None)`
    with the same optional bounds.
  - Update `get_category_breakdown(user_id, from_date=None, to_date=None)`
    with the same optional bounds.
  - `get_user_by_id` does not query expenses — leave it unchanged.

## Files to create

No new files.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never f-strings or `.format()` in SQL
- Date filtering must use `expenses.date BETWEEN ? AND ?`; when only one bound
  is provided, use `>= ?` or `<= ?` as appropriate
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags
- The filter form must use `method="get"` — never `method="post"`
- `from_date` and `to_date` inputs must have `type="date"` (browser date
  picker); do not use plain text inputs
- If neither date is supplied, the helpers behave exactly as they did before
  this step (no regression)
- Currency must always display as ₹

## Definition of done

- [ ] Visiting `/profile` with no query params shows all transactions (same behaviour as Step 5)
- [ ] Submitting a valid date range returns only transactions within that range in the transaction list
- [ ] Summary stats (total spent, transaction count, top category) reflect only the filtered date range
- [ ] Category breakdown reflects only the filtered date range
- [ ] After submitting the form, both date inputs are repopulated with the submitted values
- [ ] The "Clear" link resets the filter and shows all transactions again
- [ ] Submitting a range where `from_date > to_date` shows an error message and falls back to unfiltered data
- [ ] Submitting only `from_date` (no `to_date`) filters correctly — shows transactions on or after that date
- [ ] Submitting only `to_date` (no `from_date`) filters correctly — shows transactions on or before that date
- [ ] Visiting `/profile` without being logged in still redirects to `/login`
