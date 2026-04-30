# Spec: Login and Logout

## Overview

This step wires up the login form and logout route using Flask's built-in
`session` (signed cookie). A returning user submits their email and password;
the server verifies the credentials with `check_password_hash`, stores the
`user_id` in the session, and redirects to the dashboard (or `/` for now).
Logout clears the session and redirects to `/login`. The nav in `base.html`
is updated to conditionally show either "Sign in / Get started" (logged-out)
or "Hi, [Name] / Logout" (logged-in). No `flask-login` is used — only Flask's
built-in `session` object.

## Depends on

- Step 1 — Database setup (`users` table must exist)
- Step 2 — Registration (users must be able to create accounts to log into)

## Routes

- `POST /login` — validates credentials, sets session, redirects — public
- `GET /logout` — clears session, redirects to `/login` — public (no auth guard yet)

## Database changes

No database changes. One new helper is needed in `database/db.py`:
- `get_user_by_id(user_id)` — used to restore user context from session.
The `users` table already has the required columns from Step 1.

## Templates

- **Modify:** `templates/login.html`
  - Fix hardcoded `action="/login"` → `action="{{ url_for('login') }}"`
  - Add sticky `value="{{ request.form.get('email', '') }}"` on the email field
  - Password field must NOT be sticky

- **Modify:** `templates/base.html`
  - Nav currently always shows "Sign in" and "Get started"
  - Add a Jinja2 conditional: if `session.get('user_id')` is set, show
    "Hi, {{ session['user_name'] }}" text and a "Logout" link;
    otherwise show the existing "Sign in" and "Get started" links

## Files to change

- `app.py` — add `session` to Flask imports; add `check_password_hash` to
  werkzeug import; set `app.secret_key`; update `/login` to handle POST;
  implement `/logout`; import `get_user_by_id` from db
- `database/db.py` — add `get_user_by_id(user_id)` helper
- `templates/login.html` — fix action URL, add sticky email value
- `templates/base.html` — conditional nav based on session

## Files to create

None.

## New dependencies

No new dependencies. Flask's `session` is built-in. `check_password_hash` is
already available via `werkzeug==3.1.6` in `requirements.txt`.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders — never f-strings in SQL)
- Passwords verified with `werkzeug.security.check_password_hash` — never compare plain text
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` must be set before any session use — use a hard-coded
  dev string (e.g. `"spendly-dev-secret"`) with a comment that it must be
  replaced by an env var in production; do NOT load from a `.env` file
  (no new packages)
- Session stores only `user_id` (int) and `user_name` (str) — never the
  password hash or full user row
- On bad credentials: re-render `login.html` with `error="Invalid email or
  password."` — same message for both wrong email and wrong password (no
  enumeration)
- On success: `redirect(url_for('landing'))` as a placeholder until a
  dashboard route exists
- `GET /logout` must call `session.clear()` then redirect to `url_for('login')`
- No `@login_required` decorator yet — that comes in a later step

## Definition of done

- [ ] `GET /login` still renders the empty form with no error
- [ ] `POST /login` with valid credentials sets `session['user_id']` and
      redirects (verify via browser or test that response is 302)
- [ ] `POST /login` with wrong password re-renders form with
      `"Invalid email or password."` and does NOT set a session
- [ ] `POST /login` with unknown email re-renders form with the same error
      message (no enumeration leak)
- [ ] The email field retains the submitted value on login failure;
      the password field is empty
- [ ] `GET /logout` clears the session and redirects to `/login`
- [ ] After logout, `session.get('user_id')` is `None`
- [ ] Logged-in nav shows "Hi, [user name]" and a "Logout" link
- [ ] Logged-out nav shows "Sign in" and "Get started" (unchanged)
- [ ] No raw SQL appears in `app.py`
- [ ] The login form `action` uses `url_for('login')`, not a hardcoded string
