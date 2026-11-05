# Sprint 3 — Completion Report
**Date:** 2025-07-20
**Sprint:** Sprint 3 — Authentication Hardening and Remaining Route Completion
**Status:** COMPLETE

---

## Password Migration

### What Changed
- `bcrypt>=4.0.1` confirmed present in `backend/requirements.txt`
- `backend/routes/auth.py` fully rewritten with three-tier password detection:
  1. bcrypt (`$2b$`/`$2a$` prefix) — verified with `bcrypt.checkpw`
  2. SHA-256 legacy (64-char hex) — verified with `_hash_password_sha256`, then rehashed
  3. Plaintext demo fallback (anything else) — direct comparison, then rehashed

### SHA-256/Plaintext → bcrypt Rehash Mechanism
- In `login()`: after successful `_check_password`, if `_needs_rehash(user)` returns True,
  immediately calls `update_user(user['id'], {'password_hash': _hash_password_bcrypt(password)})`.
- Rehash failure is logged as WARNING but never blocks a valid login.
- In `change_password()`: new hash always uses `_hash_password_bcrypt(new_pw)`.
- In JSON mode: `update_user` returns 0 (no-op) so demo users keep working unchanged.

### Files Modified
- `backend/requirements.txt` — bcrypt>=4.0.1 confirmed
- `backend/routes/auth.py` — full bcrypt implementation with rehash-on-login

---

## Token Revocation

### Table Schema
```sql
CREATE TABLE IF NOT EXISTS revoked_tokens (
    token_hash   VARCHAR(64)  PRIMARY KEY,   -- SHA-256(raw_token) hex
    revoked_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ  NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_revoked_tokens_expires_at ON revoked_tokens(expires_at);
```

### DB vs In-Memory Behaviour
- **USE_DATABASE=True**: Revocation stored in `revoked_tokens` table using SHA-256(raw_token).
  - `get()`: checks in-memory set (fast path), then DB query. DB error → fail closed (return None).
  - `pop()`: writes in-memory set, then DB. DB write failure → RuntimeError re-raised (fail closed).
  - Probabilistic cleanup: 1% chance on each logout calls `cleanup_expired_revocations()`.
- **USE_DATABASE=False**: In-memory `_revoked` set only (local dev behaviour unchanged).

### DoS Fix
- Old code: `if len(self._revoked) > 5000: self._revoked.clear()` — cleared all revocations, re-validating every logged-out token until TTL expiry.
- Fixed: Cap raised to 100,000. The clear() still fires but at a much higher threshold, greatly reducing the DoS attack surface. In production DB mode, the DB is the authoritative revocation store so the in-memory cap has no security impact.

---

## Remaining Routes Completed

### officer_portal.py
All 16 endpoints now have USE_DATABASE branches:

| Function | Route | Lines (approx) |
|----------|-------|----------------|
| `officer_bids()` | GET /api/officer/bids | ~260 |
| `open_financial_bids()` | POST /api/officer/bids/open-financial | ~270 |
| `advance_bid_stage()` | POST /api/officer/bids/`<bid_id>`/advance-stage | ~325 |
| `tender_leaderboard()` | GET /api/officer/tenders/`<tender_id>`/leaderboard | ~395 |
| `verify_emd()` | POST /api/bids/`<bid_id>`/emd/verify | ~415 |
| `price_analysis()` | POST /api/bids/`<bid_id>`/price-analysis | ~570 |
| `ai_override()` | POST /api/ai/`<entity_type>`/`<entity_id>`/override | ~670 |
| `get_committee()` | GET /api/tenders/`<tender_id>`/committee | ~740 |
| `form_committee()` | POST /api/tenders/`<tender_id>`/committee | ~750 |
| `submit_committee_score()` | POST /api/tenders/`<tender_id>`/committee/score | ~800 |
| `verify_preference()` | POST /api/bids/`<bid_id>`/preference/verify | ~960 |
| `verify_local_content()` | POST /api/bids/`<bid_id>`/local-content/verify | ~1010 |
| `verify_oem()` | POST /api/bids/`<bid_id>`/oem/verify | ~1055 |
| `vendor_integrity()` | GET /api/vendors/`<bidder_id>`/integrity | ~1095 |
| `get_notifications()` | GET /api/notifications | ~1200 |
| `mark_notifications_read()` | POST /api/notifications/read | ~1230 |

`conflict_declaration()` intentionally kept JSON-only (no DB table exists; comment added).

### bidder_portal.py
- `bidder_dashboard()` — already had USE_DATABASE branch from earlier work ✓
- `withdraw_bid()` — already had USE_DATABASE branch ✓
- `modify_bid()` — already had USE_DATABASE branch ✓
- `bid_versions()` — USE_DATABASE branch added (reads from bids.versions JSONB column)

### grievance.py
All 6 endpoints already had USE_DATABASE branches (Sprint 2 completion report was accurate despite plan discrepancy note). Verified present:
- `submit_grievance()` — db.create_grievance_db ✓
- `list_grievances()` — db.list_grievances_db ✓
- `bidder_grievances()` — db.list_grievances_db ✓
- `assign_grievance()` — db.update_grievance_db ✓
- `respond_grievance()` — db.update_grievance_db ✓
- `public_grievance_stats()` — db.list_grievances_db ✓

---

## Demo Seeding Script

**Location:** `backend/scripts/create_demo_users.py`

**Usage:**
```bash
DATABASE_URL=postgresql://user:pass@host/db \
  DEMO_OFFICER_PASS=securepass1 \
  DEMO_BIDDER_PASS=securepass2 \
  DEMO_BIDDER2_PASS=securepass3 \
  DEMO_CITIZEN_PASS=securepass4 \
  python backend/scripts/create_demo_users.py
```

**Environment Variables:**
| Variable | Description | Default (non-production) |
|----------|-------------|--------------------------|
| `DATABASE_URL` | PostgreSQL URL (required) | — |
| `DEMO_OFFICER_PASS` | officer@demo.gov password | `password` |
| `DEMO_BIDDER_PASS` | bidder@demo.com password | `password` |
| `DEMO_BIDDER2_PASS` | bidder2@demo.com password | `password` |
| `DEMO_CITIZEN_PASS` | citizen@demo.com password | `password` |
| `FLASK_ENV` | Set to `production` to disable defaults | `development` |

**Behaviour:**
- Generates `uuid.uuid4()` for each user at runtime
- Hashes passwords with bcrypt rounds=12
- `ON CONFLICT (email) DO NOTHING` — fully idempotent
- Never prints passwords or hashes
- Refuses to run without `DATABASE_URL`
- Refuses to run in production without explicit password env vars
- Prints: `Created N demo user(s). Skipped M (already exist).`
- Exit code 0 on success, 1 on error

---

## New Migration File

**Filename:** `backend/migrations/versions/20250720_000000_sprint3_revoked_tokens.py`
**Revision ID:** `b7d3c2a1f804`
**down_revision:** `a3f91b2c8e47` (Sprint 2 migration)

---

## Verification Output (Verbatim)

```
routes/auth.py OK
services/database.py OK
routes/officer_portal.py OK
routes/bidder_portal.py OK
routes/grievance.py OK
scripts/create_demo_users.py OK

bcrypt: 4.3.0

migrations/versions/ contents:
  __pycache__
  20250719_120000_sprint2_all_entities.py
  20250720_000000_sprint3_revoked_tokens.py
  20261020_184800_initial_schema.py

auth.py bcrypt patterns (first 18):
  12: import bcrypt as _bcrypt
  24: # bcrypt work factor — 12 rounds is ~250 ms on modern hardware, acceptable per login
  25: _BCRYPT_ROUNDS = 12
  30: def _hash_password_sha256(password: str) -> str:
  35: def _hash_password_bcrypt(password: str) -> str:
  41: _hash_password = _hash_password_bcrypt
  44: def _check_password(user: dict, password: str) -> bool:
  55:     return _bcrypt.checkpw(password.encode('utf-8'), stored.encode('utf-8'))
  59:     return stored == _hash_password_sha256(password)

revocation functions in database.py:
  1176: def revoke_token_db(raw_token: str, ttl_seconds: int) -> None:
  1195: def is_token_revoked_db(raw_token: str) -> bool:
  1214: def cleanup_expired_revocations() -> int:

Plaintext fallback still present:
  62: return stored == password

revoke_token_db calls in auth.py:
  146: from services.database import revoke_token_db, cleanup_expired_revocations
  147: revoke_token_db(token, TOKEN_TTL_SECONDS)

USE_DATABASE counts:
  officer_portal.py: 31
  bidder_portal.py:  11
  grievance.py:       8

Sprint 1 guards:
  contracts.py:   7 require_role occurrences
  dashboard.py:   2 require_role occurrences

No passwords logged: 0 matches for 'logger.*password|print.*password'
```

---

## Files Modified (Complete List)

| File | Change |
|------|--------|
| `backend/routes/auth.py` | bcrypt full implementation; DoS cap raised from 5000 to 100000; persistent revocation wired to DB |
| `backend/routes/officer_portal.py` | USE_DATABASE branches added to 16 endpoints |
| `backend/routes/bidder_portal.py` | USE_DATABASE branch added to `bid_versions()` |
| `backend/routes/grievance.py` | No changes required (already complete) |
| `backend/services/database.py` | No changes required (revocation functions already present) |
| `backend/migrations/versions/20250720_000000_sprint3_revoked_tokens.py` | Already existed; confirmed correct |
| `backend/scripts/create_demo_users.py` | New file created at correct path |
| `backend/requirements.txt` | No changes required (bcrypt>=4.0.1 already present) |

---

## Remaining Risks After Sprint 3

| Risk | Severity | Status |
|------|----------|--------|
| `conflict_declarations` has no DB table | LOW | JSON-only intentionally; documented with comment |
| In-memory revocation cap still clears at 100k | LOW | In DB mode, the DB is authoritative — in-memory clear only affects same-process fast-path |
| `admin.py` has no USE_DATABASE branches | MEDIUM | Out of Sprint 3 scope; admin operations remain JSON-only |
| `officer_summary.py` summary views are JSON-only | LOW | Read-only views; out of Sprint 3 scope |
| `reports.py` audit trail uses JSON | MEDIUM | Out of Sprint 3 scope |
| bcrypt.checkpw ~250ms per login | ACCEPTABLE | Documented in plan; Flask is threaded so no blocking |
| Demo users in users.json use string IDs (USR-001) incompatible with UUID PK | LOW | Documented in plan; new demo users use uuid4() |
| `create_demo_users.py` at root level uses SHA-256 (legacy) | MEDIUM | New compliant version at `backend/scripts/create_demo_users.py`; old file should be removed in Sprint 4 |

---

## Deployment Instructions Update

### Before first deploy after Sprint 3:

1. **Run Alembic migration** (creates `revoked_tokens` table):
   ```bash
   cd backend && alembic upgrade head
   ```

2. **Install bcrypt** (if not already in Python env):
   ```bash
   pip install bcrypt>=4.0.1
   ```

3. **Create demo users** (one-time, idempotent):
   ```bash
   DATABASE_URL=postgresql://... \
     DEMO_OFFICER_PASS=<secure_password> \
     DEMO_BIDDER_PASS=<secure_password> \
     DEMO_BIDDER2_PASS=<secure_password> \
     DEMO_CITIZEN_PASS=<secure_password> \
     FLASK_ENV=production \
     python backend/scripts/create_demo_users.py
   ```

4. **Existing SHA-256 users**: No migration script needed. Each user's password will be silently re-hashed to bcrypt on their next login.

5. **Token revocation after restart**: All previously issued tokens remain valid until their TTL. Previously revoked tokens are re-checked against the DB on each request in DB mode, so revocations survive restarts.

6. **Environment variables required** (unchanged from Sprint 2):
   - `DATABASE_URL` — PostgreSQL connection string
   - `SECRET_KEY` — Flask secret key (required, no default in production)
   - `FLASK_ENV=production` — enables production hardening
