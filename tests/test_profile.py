def _login(client, name="Test User"):
    with client.session_transaction() as sess:
        sess["user_id"]   = 1
        sess["user_name"] = name


def test_profile_redirects_when_not_logged_in(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_returns_200_when_logged_in(client):
    _login(client)
    response = client.get("/profile")
    assert response.status_code == 200


def test_profile_shows_user_name(client):
    _login(client)
    response = client.get("/profile")
    assert b"Demo User" in response.data


def test_profile_shows_stat_labels(client):
    _login(client)
    response = client.get("/profile")
    assert b"Total Spent" in response.data
    assert b"Transactions" in response.data
    assert b"Top Category" in response.data


def test_profile_shows_transaction_rows(client):
    _login(client)
    response = client.get("/profile")
    assert b"Dinner with family" in response.data
    assert b"New shoes" in response.data
    assert b"Electricity bill" in response.data


def test_profile_shows_category_breakdown(client):
    _login(client)
    response = client.get("/profile")
    assert b"Shopping" in response.data
    assert b"Food" in response.data
    assert b"Utilities" in response.data


def test_profile_shows_avatar_initials(client):
    _login(client)
    response = client.get("/profile")
    assert b"DU" in response.data
