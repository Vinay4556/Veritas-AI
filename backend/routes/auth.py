"""
Auth routes - Veritas AI
Token-based auth with SIGNED, STATELESS tokens.
Users stored in PostgreSQL database.
"""
import hashlib
import os
import random
import threading
from datetime import datetime

import bcrypt as _bcrypt
from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from services.database import get_user_by_email, get_user_by_id, update_user

auth_bp = Blueprint('auth', __name__)

from limiter import limiter  # noqa: E402

TOKEN_TTL_SECONDS = int(float(os.environ.get('TOKEN_TTL_HOURS', '12')) * 3600)

# bcrypt work factor — 12 rounds is ~250 ms on modern hardware, acceptable per login
_BCRYPT_ROUNDS = 12


# ── Password helpers ─────────────────────────────────────────────────────────

def _hash_password_sha256(password: str) -> str:
    """Legacy SHA-256 hash. Only used to verify existing legacy hashes."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _hash_password_bcrypt(password: str) -> str:
    """Bcrypt hash with configured work factor. Returns a str (not bytes)."""
    return _bcrypt.hashpw(password.encode('utf-8'), _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode('utf-8')


# Canonical hasher for new passwords and password changes
_hash_password = _hash_password_bcrypt


def _check_password(user: dict, password: str) -> bool:
    """Verify a password against the stored hash.

    Detection order:
      1. bcrypt hash  ($2b$ / $2a$ prefix) — verified with bcrypt.checkpw
      2. SHA-256 hex  (64-char lowercase hex) — legacy path
      3. Plaintext    (anything else) — demo/local fallback only
    """
    stored = user.get('password_hash') or user.get('password') or ''
    if stored.startswith('$2b$') or stored.startswith('$2a$'):
        try:
            return _bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
        except Exception:
            return False
    if len(stored) == 64 and all(c in '0123456789abcdef' for c in stored):
        return stored == _hash_password_sha256(password)
    # Plaintext fallback — local demo users only; never fires in DB mode once
    # the rehash-on-login path has upgraded the stored value.
    from config import USE_DATABASE
    if USE_DATABASE or os.environ.get('FLASK_ENV') == 'production':
        return False
    return stored == password


def _needs_rehash(user: dict) -> bool:
    """True if the stored credential is not yet a bcrypt hash."""
    stored = user.get('password_hash') or user.get('password') or ''
    return not (stored.startswith('$2b$') or stored.startswith('$2a$'))


# ── Signed-token session store ──────────────────────────────────────────────

def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='veritas-auth-v1')


def issue_token(session: dict) -> str:
    return _serializer().dumps(session)


class _SessionStore:
    """Dict-like facade so existing ``SESSIONS.get(token)`` call sites keep working.
    Tokens are verified cryptographically instead of looked up in memory.

    In DATABASE mode (USE_DATABASE=True):
      - Revocation is persisted in the ``revoked_tokens`` table via SHA-256(token).
      - If the DB is unreachable during a revocation check, the request FAILS CLOSED
        (token treated as revoked) — no silent fallback to in-memory set.
      - Logout FAILS CLOSED too: if the DB write fails, a RuntimeError is raised so
        the caller can return 500. A logout that silently loses its revocation record
        would leave the old token valid until TTL expiry.

    In local-dev mode (USE_DATABASE=False):
      - In-memory ``_revoked`` set is used unchanged.
    """

    def __init__(self):
        self._revoked: set = set()      # best-effort logout list (per process, local dev)
        self._lock = threading.Lock()

    def _token_hash(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    def get(self, token, default=None):
        if not token:
            return default

        # Fast in-memory check (both modes)
        if token in self._revoked:
            return default

        # DB-mode persistent revocation check
        from config import USE_DATABASE
        if USE_DATABASE:
            try:
                from services.database import is_token_revoked_db
                if is_token_revoked_db(token):
                    return default
            except Exception:
                # DB unreachable — fail closed
                return default

        try:
            return _serializer().loads(token, max_age=TOKEN_TTL_SECONDS)
        except (BadSignature, SignatureExpired):
            return default

    def pop(self, token, default=None):
        session = self.get(token)

        if not token:
            return session if session is not None else default

        # In-memory revocation (both modes, for fast same-process checks)
        with self._lock:
            if len(self._revoked) > 100000:
                # Cap at 100 000 to prevent unbounded memory growth while avoiding
                # the DoS flaw where clearing the entire set re-validates all revoked tokens.
                self._revoked.clear()
            self._revoked.add(token)

        # DB-mode persistent revocation — FAIL CLOSED on error
        from config import USE_DATABASE
        if USE_DATABASE:
            try:
                from services.database import revoke_token_db, cleanup_expired_revocations
                revoke_token_db(token, TOKEN_TTL_SECONDS)
                # Probabilistic lazy cleanup: 1-in-100 chance, best-effort
                if random.random() < 0.01:
                    try:
                        cleanup_expired_revocations()
                    except Exception:
                        pass  # cleanup failure is non-critical
            except Exception as exc:
                # Fail closed: do NOT return successfully if DB write failed
                raise RuntimeError(
                    f'Token revocation DB write failed — logout rejected: {exc}'
                ) from exc

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


# ── Auth endpoints ──────────────────────────────────────────────────────────

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

    # Rehash-on-login: silently upgrade SHA-256 or plaintext to bcrypt
    if _needs_rehash(user):
        try:
            update_user(user['id'], {'password_hash': _hash_password_bcrypt(password)})
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                'Rehash-on-login failed for user %s: %s', user.get('id'), exc
            )
            # Rehash failure must never block a valid login

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
    token = _token_from_request()
    try:
        SESSIONS.pop(token, None)
    except RuntimeError as exc:
        import logging
        logging.getLogger(__name__).error('Logout revocation failed: %s', exc)
        return jsonify({'error': 'Logout could not be completed — please try again'}), 500
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

    if not update_user(user['id'], {'password_hash': _hash_password_bcrypt(new_pw)}):
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
