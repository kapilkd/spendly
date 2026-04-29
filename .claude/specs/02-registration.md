# Spec: Registration

## Overview

This step wires up the registration form that already exists in `register.html`
to a real `POST /register` route. A visitor fills in their name, email, and
password; the server validates the input, checks for duplicate emails, hashes the
password, inserts the new user into the `users` table, and redirects to the login
page. This is the first point at which real user records are created and is a
prerequisite for every authenticated feature that follows.

## Depends on

- Step 1 — Database setup (`users` table must exist via `init_db()`)

## Routes

- `POST /register` — validates and processes the registration form — public

## Database changes

No database changes. The `users` table (`id`, `name`, `email`, `password_hash`,
`created_at`) is already created by `init_db()` in `database/db.py`.

## Templates

- **Modify:** `templates/register.html`
  - Replace hardcoded `action="/register"` with `action="{{ url_for('register') }}"`
  - Re-render the form with sticky `name` and `email` values on validation failure
    so the user does not have to retype them

## Files to change

- `app.py` — add `POST` to the existing `register` route; import `redirect`,
  `url_for`, `request`; call the new DB helper; handle errors
- `database/db.py` — add `create_user(name, email, password_hash)` and
  `get_user_by_email(email)` helpers
- `templates/register.html` — fix hardcoded URL; add sticky field values

## Files to create

None.

## New dependencies

No new dependencies. `werkzeug.security` is already available via Flask.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders — never f-strings in SQL)
- Passwords hashed with `werkzeug.security.generate_password_hash` before insert
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB helpers belong in `database/db.py` — no inline SQL in `app.py`
- Route function must only: parse request, call helpers, render or redirect
- On duplicate email: re-render `register.html` with `error="An account with
  that email already exists."` — do NOT leak whether the account is active
- On success: `redirect(url_for('login'))` — no auto-login at this step
- Validate server-side: name non-empty, valid email format, password ≥ 8 chars;
  return a clear `error` string for each failure
- Use `abort(400)` only for structurally malformed requests, not user errors

## Definition of done

- [ ] `GET /register` still renders the empty form with no errors
- [ ] Submitting the form with valid data inserts a row into `users` and
      redirects to `/login`
- [ ] The inserted `password_hash` is never the plain-text password
      (verify with `sqlite3 expense_tracker.db "SELECT password_hash FROM users LIMIT 1"`)
- [ ] Submitting with a duplicate email re-renders the form with an error message
      and does NOT insert a duplicate row
- [ ] Submitting with a missing name, invalid email, or password shorter than
      8 characters re-renders the form with a descriptive error
- [ ] On validation failure, the `name` and `email` fields are pre-filled with
      the submitted values
- [ ] No raw SQL appears in `app.py`
- [ ] The form `action` uses `url_for('register')`, not a hardcoded string
