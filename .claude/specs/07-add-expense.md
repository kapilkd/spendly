# Spec: Add Expense

## Overview

This step implements the Add Expense feature, allowing logged-in users to record a new expense via a form. It converts the existing `GET /expenses/add` stub into a fully functioning page that accepts a title, amount, category, date, and optional note, persists the record to the database, and redirects the user back to their dashboard on success. This is the first write-path feature in the app.

## Depends on

- Step 01 — Database Setup (expenses table exists)
- Step 03 — Login and Logout (session-based auth)
- Step 04/05 — Profile Page (redirect target after submit)

## Routes

- `GET /expenses/add` — Render the add-expense form — logged-in only
- `POST /expenses/add` — Validate and persist the new expense, redirect to `/profile` on success — logged-in only

## Database changes

No new tables or columns. The `expenses` table already exists with the required schema:

```
id, user_id, title, amount, category, date, note, created_at
```

A new DB helper function `create_expense` must be added to `database/db.py`.

## Templates

- **Create:** `templates/add_expense.html` — full add-expense form page extending `base.html`
- **Modify:** none

## Files to change

- `app.py` — replace `add_expense` stub with GET + POST handler; add `create_expense` to the import from `database.db`
- `database/db.py` — add `create_expense(user_id, title, amount, category, date, note)` helper

## Files to create

- `templates/add_expense.html`

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords hashed with werkzeug (not relevant here, but stated for completeness)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Auth guard: check `session.get("user_id")` at the top of both GET and POST handlers; redirect to `/login` if missing
- Amount must be validated as a positive number server-side; reject if missing or ≤ 0
- Title must be non-empty; strip whitespace before checking
- Date must match `YYYY-MM-DD` format (use the existing `_DATE_RE` regex in `app.py`)
- Category must be one of the allowed values; reject unknown values with a form error
- On validation failure, re-render the form with the error message and previously entered values pre-filled
- On success, redirect to `url_for('profile')` — never render the form again after a successful POST
- The `create_expense` DB helper must call `get_db()`, execute an INSERT with `?` placeholders, and call `db.commit()`
- Allowed categories: Food, Transport, Entertainment, Utilities, Shopping, Healthcare, Bills, Education, Other
- Use `abort(400)` only for truly malformed requests; use form re-render with error message for user input errors
- The "Add Expense" link on the profile page should use `url_for('add_expense')` — check if `profile.html` already has such a link and add it if missing

## Definition of done

- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders a form with fields: Title, Amount, Category (dropdown), Date, Note (optional)
- [ ] Submitting an empty title shows a validation error and re-renders the form
- [ ] Submitting a non-positive or non-numeric amount shows a validation error
- [ ] Submitting an invalid date format shows a validation error
- [ ] Submitting a valid form saves the expense to the database and redirects to `/profile`
- [ ] The new expense appears in the recent transactions list on the profile page immediately after redirect
- [ ] Summary stats on the profile page (total spent, transaction count) update to reflect the new expense
- [ ] All form fields retain their values when a validation error occurs (sticky inputs)
- [ ] The page title and heading clearly indicate "Add Expense"
