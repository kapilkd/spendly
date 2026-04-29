from werkzeug.security import check_password_hash
from database.db import get_user_by_email


def test_get_register_renders_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Create your account" in response.data


def test_valid_registration_redirects_to_login(client):
    response = client.post("/register", data={
        "name": "Test User",
        "email": "test@example.com",
        "password": "password1",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_valid_registration_inserts_hashed_password(client):
    client.post("/register", data={
        "name": "Test User",
        "email": "test@example.com",
        "password": "password1",
    })
    user = get_user_by_email("test@example.com")
    assert user is not None
    assert user["password_hash"] != "password1"
    assert check_password_hash(user["password_hash"], "password1")


def test_duplicate_email_shows_error(client):
    data = {"name": "Alice", "email": "alice@example.com", "password": "password1"}
    client.post("/register", data=data)
    response = client.post("/register", data=data)
    assert response.status_code == 200
    assert b"already exists" in response.data


def test_duplicate_email_does_not_insert(client):
    data = {"name": "Alice", "email": "alice@example.com", "password": "password1"}
    client.post("/register", data=data)
    client.post("/register", data=data)
    from database.db import get_db
    count = get_db().execute(
        "SELECT COUNT(*) FROM users WHERE email = ?", ("alice@example.com",)
    ).fetchone()[0]
    assert count == 1


def test_empty_name_shows_error(client):
    response = client.post("/register", data={
        "name": "",
        "email": "bob@example.com",
        "password": "password1",
    })
    assert response.status_code == 200
    assert b"Name is required" in response.data


def test_invalid_email_shows_error(client):
    response = client.post("/register", data={
        "name": "Bob",
        "email": "notanemail",
        "password": "password1",
    })
    assert response.status_code == 200
    assert b"valid email" in response.data


def test_short_password_shows_error(client):
    response = client.post("/register", data={
        "name": "Bob",
        "email": "bob@example.com",
        "password": "short",
    })
    assert response.status_code == 200
    assert b"8 characters" in response.data


def test_name_sticky_on_validation_failure(client):
    response = client.post("/register", data={
        "name": "StickyName",
        "email": "notanemail",
        "password": "password1",
    })
    assert b"StickyName" in response.data


def test_password_not_sticky_on_validation_failure(client):
    response = client.post("/register", data={
        "name": "Bob",
        "email": "notanemail",
        "password": "secret99",
    })
    assert b"secret99" not in response.data
