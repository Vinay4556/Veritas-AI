"""
conftest.py — pytest fixtures for Sprint 4 test suite.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Ensure the backend directory is on sys.path so that `import app` etc. work
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Provide a minimal SECRET_KEY before importing the Flask app so the boot check passes
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-sprint4-tests')
# Ensure we never accidentally hit a production guard
os.environ.pop('FLASK_ENV', None)

# The test session dict used to satisfy require_role checks
_TEST_SESSION = {
    'id': 'USR-TEST-001',
    'user_id': 'USR-TEST-001',
    'email': 'officer@test.gov',
    'name': 'Test Officer',
    'role': 'OFFICER',
}
_TEST_TOKEN = 'test-bearer-token-sprint4'


@pytest.fixture(scope='session')
def app():
    """Create the Flask application in testing mode."""
    from app import app as flask_app
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key-for-sprint4-tests'
    return flask_app


@pytest.fixture
def client(app):
    """A test client for the Flask app, with auth bypassed via patched SESSIONS."""
    from routes.auth import SESSIONS

    # Patch SESSIONS.get so any token returns our test officer session.
    # This avoids the revoked_tokens DB table lookup failing in the test env.
    original_get = SESSIONS.get

    def _mock_get(token, default=None):
        if token:
            return _TEST_SESSION
        return default

    SESSIONS.get = _mock_get
    try:
        yield app.test_client()
    finally:
        SESSIONS.get = original_get


@pytest.fixture
def officer_token():
    """Return the test Bearer token string."""
    return _TEST_TOKEN


@pytest.fixture
def auth_headers(officer_token):
    """HTTP headers dict that includes the Bearer token."""
    return {'Authorization': f'Bearer {officer_token}'}
