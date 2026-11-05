"""
Create demo users in PostgreSQL with bcrypt-hashed passwords.

Usage:
    DATABASE_URL=postgresql://... python backend/scripts/create_demo_users.py

Environment variables:
    DATABASE_URL         Required. PostgreSQL connection string.
    DEMO_OFFICER_PASS    Password for officer@demo.gov  (default: 'password' in non-production)
    DEMO_BIDDER_PASS     Password for bidder@demo.com   (default: 'password' in non-production)
    DEMO_BIDDER2_PASS    Password for bidder2@demo.com  (default: 'password' in non-production)
    DEMO_CITIZEN_PASS    Password for citizen@demo.com  (default: 'password' in non-production)
    FLASK_ENV            Set to 'production' to disable default password fallback.

Behaviour:
    - Uses ON CONFLICT (email) DO NOTHING — fully idempotent (safe to run multiple times).
    - Never prints passwords or password hashes.
    - Refuses to run if DATABASE_URL is not set.
    - Refuses to run in production mode without explicit env-var passwords.
    - Prints 'Created N demo user(s). Skipped M (already exist).'
    - Exits with code 0 on success, 1 on error.
"""
import os
import sys
import uuid

# ── Environment checks ───────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if not DATABASE_URL:
    print('ERROR: DATABASE_URL environment variable is not set. Refusing to run.', file=sys.stderr)
    sys.exit(1)

FLASK_ENV = os.environ.get('FLASK_ENV', 'development').strip().lower()
IS_PRODUCTION = FLASK_ENV == 'production'

_BCRYPT_ROUNDS = 12

# ── Resolve demo passwords ────────────────────────────────────
_DEFAULT_PASSWORD = 'password'

def _get_password(env_var: str) -> str:
    """Return password from env var, or default if in non-production mode."""
    val = os.environ.get(env_var, '').strip()
    if val:
        return val
    if IS_PRODUCTION:
        print(
            f'ERROR: {env_var} is not set and FLASK_ENV=production. '
            'Explicit demo passwords are required in production.',
            file=sys.stderr,
        )
        sys.exit(1)
    return _DEFAULT_PASSWORD


officer_pass = _get_password('DEMO_OFFICER_PASS')
bidder_pass = _get_password('DEMO_BIDDER_PASS')
bidder2_pass = _get_password('DEMO_BIDDER2_PASS')
citizen_pass = _get_password('DEMO_CITIZEN_PASS')

# ── Demo user definitions ─────────────────────────────────────
DEMO_USERS = [
    {
        'email': 'officer@demo.gov',
        'password': officer_pass,
        'name': 'Demo Officer',
        'role': 'OFFICER',
        'department': 'Procurement Department',
        'employee_id': 'EMP-DEMO-001',
        'organization_id': None,
        'organization_name': 'CPCL - Chennai Petroleum Corporation Limited',
    },
    {
        'email': 'bidder@demo.com',
        'password': bidder_pass,
        'name': 'Demo Bidder',
        'role': 'BIDDER',
        'department': None,
        'employee_id': None,
        'organization_id': 'BID-001',
        'organization_name': 'ABC Construction Ltd',
    },
    {
        'email': 'bidder2@demo.com',
        'password': bidder2_pass,
        'name': 'Demo Bidder 2',
        'role': 'BIDDER',
        'department': None,
        'employee_id': None,
        'organization_id': 'BID-002',
        'organization_name': 'XYZ Infra Pvt Ltd',
    },
    {
        'email': 'citizen@demo.com',
        'password': citizen_pass,
        'name': 'Demo Citizen',
        'role': 'STAKEHOLDER',
        'department': None,
        'employee_id': None,
        'organization_id': None,
        'organization_name': 'Public',
    },
]

# ── Hash passwords with bcrypt ────────────────────────────────
try:
    import bcrypt as _bcrypt
except ImportError:
    print('ERROR: bcrypt is not installed. Run: pip install bcrypt>=4.0.1', file=sys.stderr)
    sys.exit(1)


def _hash_password(password: str) -> str:
    """Return bcrypt hash string (never logged)."""
    return _bcrypt.hashpw(password.encode('utf-8'), _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode('utf-8')


# ── Database insertion ────────────────────────────────────────
try:
    import psycopg2
except ImportError:
    print('ERROR: psycopg2 is not installed. Run: pip install psycopg2-binary', file=sys.stderr)
    sys.exit(1)

INSERT_SQL = """
    INSERT INTO users (
        id, email, password_hash, name, role,
        department, employee_id, organization_id, organization_name, active
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true)
    ON CONFLICT (email) DO NOTHING
"""

created = 0
skipped = 0

try:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    for user in DEMO_USERS:
        user_id = str(uuid.uuid4())
        password_hash = _hash_password(user['password'])

        cur.execute(INSERT_SQL, (
            user_id,
            user['email'].lower(),
            password_hash,
            user['name'],
            user['role'],
            user.get('department'),
            user.get('employee_id'),
            user.get('organization_id'),
            user['organization_name'],
        ))
        rows_affected = cur.rowcount
        if rows_affected == 1:
            created += 1
        else:
            skipped += 1

    conn.commit()
    cur.close()
    conn.close()

except Exception as exc:
    print(f'ERROR: Database operation failed: {exc}', file=sys.stderr)
    sys.exit(1)

print(f'Created {created} demo user(s). Skipped {skipped} (already exist).')
sys.exit(0)
