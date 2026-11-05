"""
Auth routes - Veritas AI
Token-based auth with SIGNED, STATELESS tokens.
Users stored in PostgreSQL database.
"""
import hashlib
import os
import threading
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from services.database import get_user_by_email, get_user_by_id, update_user

auth_bp = Blueprint('auth', __name__)

from limiter import limiter  # noqa: E402

TOKEN_TTL_SECONDS = int(float(os.environ.get('TOKEN_TTL_HOURS', '12')) * 3600)


# ── Signed-token session store ──────────────────────────────────────────────

def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='veritas-auth-v1')


def issue_token(session: dict) -> str:
    return _serializer().dumps(session)


class _SessionStore:
    """Dict-like facade so existing ``SESSIONS.get(token)`` call sites keep working.
    Tokens are verified cryptographically instead of looked up in memory."""

    def __init__(self):
        self._revoked = set()          # best-effort logout list (per process)
        self._lock = threading.Lock()

    def get(self, token, default=None):
        if not token or token in self._revoked:
            return default
        try:
            return _serializer().loads(token, max_age=TOKEN_TTL_SECONDS)
        except (BadSignature, SignatureExpired):
            return default

    def pop(self, token, default=None):
        session = self.get(token)
        if token:
            with self._lock:
                if len(self._revoked) > 5000:
                    self._revoked.clear()
                self._revoked.add(token)
        return session if session is not None else default

    def __contains__(self, token):
        return self.get(token) is not None

    def __getitem__(self, token):
        session = self.get(token)
        if session is None:
            raise KeyError(token)
        return session


SESSIONS = _SessionStore()


def _token_from_request(req=None) -> str:
    req = req or request
    header = req.headers.get('Authorization', '')
    if header.lower().startswith('bearer '):
        header = header[7:]
    return header.strip()


def _hash_password(password: str) -> str:
    """SHA-256 hash for demo. Use bcrypt/argon2 in production."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _check_password(user: dict, password: str) -> bool:
    """Check password — supports both plaintext demo passwords and hashed ones."""
    stored = user.get('password_hash') or user.get('password') or ''
    # If stored is a 64-char hex string it's already hashed
    if len(stored) == 64 and all(c in '0123456789abcdef' for c in stored):
        return stored == _hash_password(password)
    # Plaintext fallback for existing demo data
    return stored == password


@auth_bp.route('/api/auth/login', methods=['POST'])
@limiter.limit('10 per minute')
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = get_user_by_email(email)

    if not user or not _check_password(user, password):
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.get('active', True):
        return jsonify({'error': 'Account is inactive. Contact administrator.'}), 403

    # Update last login
    try:
        update_user(user['id'], {'last_login': datetime.now()})
    except Exception:
        pass  # a failed last_login write must never block a valid login

    session = {
        'id': user['id'],
        'user_id': user['id'],
        'email': user['email'],
        'name': user.get('name'),
        'role': user.get('role'),
        'organization_id': user.get('organization_id'),
        'organization_name': user.get('organization_name'),
        'department': user.get('department'),
        'employee_id': user.get('employee_id'),
        'logged_in_at': datetime.now().isoformat(),
    }
    token = issue_token(session)

    return jsonify({
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'name': user['name'],
            'role': user['role'],
            'organization_id': user.get('organization_id'),
            'organization_name': user.get('organization_name'),
            'department': user.get('department'),
            'employee_id': user.get('employee_id'),
        }
    })


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    SESSIONS.pop(_token_from_request(), None)
    return jsonify({'status': 'logged_out'})


@auth_bp.route('/api/auth/me', methods=['GET'])
def me():
    session = SESSIONS.get(_token_from_request())
    if not session:
        return jsonify({'error': 'Not authenticated'}), 401

    # Re-check the account so a deactivated user is locked out immediately.
    user = get_user_by_id(session.get('user_id'))
    if not user or not user.get('active', True):
        return jsonify({'error': 'Account not found or inactive'}), 401

    return jsonify(session)


@auth_bp.route('/api/auth/change-password', methods=['POST'])
def change_password():
    """Allow users to update their password."""
    session = SESSIONS.get(_token_from_request())
    if not session:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json(silent=True) or {}
    current = data.get('current_password', '')
    new_pw = data.get('new_password', '')

    if not new_pw or len(new_pw) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    user = get_user_by_id(session['user_id'])
    if not user or not _check_password(user, current):
        return jsonify({'error': 'Current password is incorrect'}), 401

    if not update_user(user['id'], {'password_hash': _hash_password(new_pw)}):
        return jsonify({'error': 'Password could not be changed in this mode (demo users are read-only).'}), 409
    return jsonify({'status': 'password_changed'})


def get_session(request):
    """Helper to get current session from request."""
    return SESSIONS.get(_token_from_request(request))


def require_role(*roles):
    """Decorator factory for role-based access control."""
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapped(*args, **kwargs):
            session = SESSIONS.get(_token_from_request())
            if not session:
                return jsonify({'error': 'Authentication required'}), 401
            if roles and session.get('role') not in roles:
                return jsonify({'error': 'Insufficient permissions', 'required': list(roles), 'current': session.get('role')}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator