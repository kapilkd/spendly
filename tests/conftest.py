import pytest
from app import app as flask_app
from database.db import init_db


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    flask_app.config['DATABASE'] = ':memory:'
    with flask_app.app_context():
        init_db()
        yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()
