from werkzeug.security import generate_password_hash
from database.db import create_user


def _register(email="test@example.com", password="password1"):
    create_user("Test User", email, generate_password_hash(password))


def test_get_login_renders_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Sign in" in response.data


def test_valid_login_redirects(app, client):
    _register()
    response = client.post("/login", data={
        "email": "test@example.com",
        "password": "password1",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_valid_login_sets_session(app, client):
    _register()
    with client.session_transaction() as sess:
        assert "user_id" not in sess
    client.post("/login", data={"email": "test@example.com", "password": "password1"})
    with client.session_transaction() as sess:
        assert sess["user_id"] is not None
        assert sess["user_name"] == "Test User"


def test_wrong_password_shows_error(app, client):
    _register()
    response = client.post("/login", data={
        "email": "test@example.com",
        "password": "wrongpass",
    })
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_wrong_password_does_not_set_session(app, client):
    _register()
    client.post("/login", data={"email": "test@example.com", "password": "wrongpass"})
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_unknown_email_shows_same_error(client):
    response = client.post("/login", data={
        "email": "nobody@example.com",
        "password": "password1",
    })
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_email_sticky_on_failure(app, client):
    _register()
    response = client.post("/login", data={
        "email": "test@example.com",
        "password": "wrongpass",
    })
    assert b"test@example.com" in response.data


def test_password_not_sticky_on_failure(app, client):
    _register()
    response = client.post("/login", data={
        "email": "test@example.com",
        "password": "wrongpass",
    })
    assert b"wrongpass" not in response.data


def test_logout_clears_session(app, client):
    _register()
    client.post("/login", data={"email": "test@example.com", "password": "password1"})
    with client.session_transaction() as sess:
        assert "user_id" in sess
    client.get("/logout")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_redirects_to_login(app, client):
    _register()
    client.post("/login", data={"email": "test@example.com", "password": "password1"})
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
