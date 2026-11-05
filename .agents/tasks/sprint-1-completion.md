# Sprint 1 — Security Implementation Completion Report

**Date:** 2025-07-19  
**Sprint:** Sprint 1 — Security Fixes  
**Status:** COMPLETE

---

## Tasks Completed

### Task 1 — Secure contracts.py write endpoints

**File modified:** `backend/routes/contracts.py`

Added `@require_role('OFFICER')` decorator to four endpoint functions:

| Line | Function | Route |
|------|----------|-------|
| 146 | `create_inspection` | POST /api/inspections |
| 179 | `update_inspection` | PUT /api/inspections/<id> |
| 217 | `create_corrective_action` | POST /api/corrective-actions |
| 249 | `resolve_corrective_action` | POST /api/corrective-actions/<id>/resolve |

Pattern used (matching existing `create_contract`):
```python
@contracts_bp.route('/api/inspections', methods=['POST'])
@require_role('OFFICER')
def create_inspection():
```

Also added `@require_role('OFFICER', 'BIDDER')` to `GET /api/contracts` (Task 5).

---

### Task 2 — Secure chat.py (require auth)

**File modified:** `backend/routes/chat.py`

Added authentication check as the FIRST check inside `chat()`, before the API key guard:

```python
session = get_session(request)
if not session:
    return jsonify({'error': 'Authentication required'}), 401
```

Any authenticated user (OFFICER, BIDDER, STAKEHOLDER) may use the chat endpoint. `@require_role` was not used because it only admits named roles.

Removed the duplicate `get_session(request)` call in the role-context enrichment block (the session returned by the auth check is reused directly).

---

### Task 3 — Fix GROQ_API_KEY env var

**Files modified:** `backend/routes/chat.py`, `backend/.env.example`

`chat.py` changes:
- Module docstring: `<GROK_API_KEY>` → `<GROQ_API_KEY>`
- Top-of-file assignment changed to support both canonical and legacy names:
  ```python
  GROQ_API_KEY = os.environ.get('GROQ_API_KEY') or os.environ.get('GROK_API_KEY', '')
  ```
- All remaining `GROK_API_KEY` references renamed to `GROQ_API_KEY` (503 guard + Authorization header).

`.env.example` addition after `GROQ_API_KEY=`:
```
# GROK_API_KEY= is a deprecated alias for GROQ_API_KEY — prefer GROQ_API_KEY above
```

---

### Task 4 — Login rate limiting

**Files created:** `backend/limiter.py`  
**Files modified:** `backend/requirements.txt`, `backend/app.py`, `backend/routes/auth.py`, `backend/.env.example`

- `requirements.txt`: added `flask-limiter>=3.5.0`
- `limiter.py`: singleton `Limiter` instance with `get_remote_address` key function, `fixed-window` strategy, no default limits (per-route only), `RATELIMIT_STORAGE_URI` env var for Redis/Memcache in multi-worker deployments.
- `app.py`: added `from limiter import limiter` import; added `limiter.init_app(app)` after SECRET_KEY block.
- `auth.py`: added `from limiter import limiter`; added `@limiter.limit('10 per minute')` between route decorator and `def login()`.
- `.env.example`: added `RATELIMIT_STORAGE_URI=` block with production guidance at end of file.

---

### Task 5 — Protect sensitive GET endpoints

**Files modified:** `backend/routes/dashboard.py`, `backend/routes/reports.py`, `backend/routes/bidders.py`, `backend/routes/contracts.py`

#### Role-Access Matrix

| Endpoint | Previous auth | Intended access | Verdict | Change made |
|---|---|---|---|---|
| GET /api/dashboard | None | Officers only — aggregates compliance scores, bidder names, audit activity | ADD AUTH | `@require_role('OFFICER')` |
| GET /api/audit | None | Officers only — full decision audit trail | ADD AUTH | `@require_role('OFFICER')` |
| GET /api/bidders/<id> | None | Officers + Bidders (bidder can view own profile) | ADD AUTH | `@require_role('OFFICER', 'BIDDER')` |
| GET /api/bidders/<id>/compliance | None | Officers + Bidders (bidder can view own compliance) | ADD AUTH | `@require_role('OFFICER', 'BIDDER')` |
| GET /api/contracts | None | Officers + Bidders (filter by bidder_id already supported) | ADD AUTH | `@require_role('OFFICER', 'BIDDER')` |

**Justifications:**
- `/api/dashboard` reveals aggregate compliance scores, bidder names, risk levels, and audit activity — sensitive procurement intelligence. OFFICER only.
- `/api/audit` is the officer decision trail — confidential procurement records. OFFICER only.
- `/api/bidders/<id>` and `/api/bidders/<id>/compliance` need BIDDER access so vendors can view their own profile/compliance; OFFICER needs access to review all bidders.
- `/api/contracts` needs BIDDER access so vendors can track contracts awarded to them (bidder_id filter); OFFICER needs full access.
- Public stakeholder routes (`/api/public/*`) were not touched — they remain fully unauthenticated.
- `GET /api/bidders/<bidder_id>/report` was NOT changed in this sprint (not in the Task 5 scope list).

---

### Task 6 — Fix mass assignment in update_inspection

**File modified:** `backend/routes/contracts.py`

Replaced unbounded `i.update({k: v for k, v in data.items() if k != 'id'})` with an explicit allowlist:

```python
ALLOWED_INSPECTION_FIELDS = {
    'inspection_type', 'inspector', 'inspector_id', 'inspected_at',
    'status', 'items', 'overall_result', 'corrective_action_required',
    'corrective_action_id', 'report_notes', 'attachments',
    'milestone_id',
}
for i in inspections:
    if i['id'] == inspection_id:
        i.update({k: v for k, v in data.items() if k in ALLOWED_INSPECTION_FIELDS})
```

Protected fields (blocked from update): `id`, `contract_id`, `bidder_id`, `tender_id`, and any field starting with `_`.

---

### Task 7 — Production SECRET_KEY enforcement

**File modified:** `backend/app.py`

- Added `import sys as _sys` to stdlib imports at top of file.
- Replaced the permissive fallback with a strict production guard:
  - Detects production via `FLASK_ENV=production`, `RENDER`, or `RAILWAY_ENVIRONMENT` env vars.
  - If production and `SECRET_KEY` is missing: prints FATAL message to stderr and calls `sys.exit(1)`.
  - If production and `SECRET_KEY` equals the known dev fallback hash: prints FATAL message and exits.
  - Local dev without `SECRET_KEY`: uses the deterministic dev fallback with a WARNING print (no exit).
- `.env.example` already had `SECRET_KEY=` with the generation command — no change needed.

---

## Security Improvements Summary

| # | Improvement | Severity Fixed |
|---|---|---|
| 1 | 4 unauthenticated write endpoints now require OFFICER role | HIGH |
| 2 | `/api/chat` now requires authentication (any role) | HIGH |
| 3 | GROQ_API_KEY typo fixed — chatbot now activates when key is set correctly | HIGH |
| 4 | Login endpoint now rate-limited to 10 req/min per IP | HIGH |
| 5 | `/api/dashboard` now requires OFFICER auth | HIGH |
| 6 | `/api/audit` now requires OFFICER auth | HIGH |
| 7 | `/api/bidders/<id>` now requires OFFICER or BIDDER auth | MEDIUM |
| 8 | `/api/bidders/<id>/compliance` now requires OFFICER or BIDDER auth | MEDIUM |
| 9 | `/api/contracts` now requires OFFICER or BIDDER auth | MEDIUM |
| 10 | Mass assignment in `update_inspection` replaced with explicit allowlist | MEDIUM |
| 11 | Production server refuses to start with missing or known-weak SECRET_KEY | HIGH |

---

## Verification Command Outputs (verbatim)

```
contracts.py OK
chat.py OK
auth.py OK
app.py OK
limiter.py OK
flask-limiter importable
```

**contracts.py require_role/endpoint grep:**
```
LineNumber Line
---------- ----
        12 from routes.auth import require_role
        39 @require_role('OFFICER', 'BIDDER')
        64 @require_role('OFFICER')
       146 @require_role('OFFICER')
       147 def create_inspection():
       179 @require_role('OFFICER')
       180 def update_inspection(inspection_id):
       217 @require_role('OFFICER')
       218 def create_corrective_action():
       249 @require_role('OFFICER')
       250 def resolve_corrective_action(ca_id):
```

**chat.py GROQ_API_KEY grep:**
```
LineNumber Line
---------- ----
        10   Auth     : Authorization: Bearer <GROQ_API_KEY>
        23 # Support both GROQ_API_KEY (canonical) and GROK_API_KEY (legacy alias)
        24 GROQ_API_KEY = os.environ.get('GROQ_API_KEY') or os.environ.get('GROK_API_KEY', '')
       121     if not GROQ_API_KEY:
       123             'error': 'Groq API key not configured. Set GROQ_API_KEY in backend/.env.',
       126                 'Please set GROQ_API_KEY in the server environment.'
       155                 'Authorization': f'Bearer {GROQ_API_KEY}',
```

**auth.py limiter grep:**
```
LineNumber Line
---------- ----
        18 from limiter import limiter  # noqa: E402
        95 @limiter.limit('10 per minute')
```

**app.py SECRET_KEY/sys.exit/limiter grep:**
```
LineNumber Line
---------- ----
        19 from limiter import limiter  # noqa: E402
        74 # Set SECRET_KEY in the environment for production.
        75 _secret = os.environ.get('SECRET_KEY')
        77 _is_production = (
        78     os.environ.get('FLASK_ENV') == 'production'
        84     if _is_production:
        86             '[boot] FATAL: SECRET_KEY is not set in a production environment. '
        87             'Set SECRET_KEY to a securely generated random value. '
        91         _sys.exit(1)
        93     print('[boot] WARNING: Using development SECRET_KEY — NOT safe for production.')
        94 elif _secret == _DEV_FALLBACK and _is_production:
        96         '[boot] FATAL: SECRET_KEY is set to the known development fallback value. '
       100     _sys.exit(1)
       102 app.config['SECRET_KEY'] = _secret
       105 # ── Rate limiter ─────────────────────────────────────────────
       106 limiter.init_app(app)
```

**Additional compile checks (dashboard, reports, bidders):**
```
dashboard.py OK
reports.py OK
bidders.py OK
```

---

## Regressions Discovered

None. No existing business logic was altered — only authentication guards were added and one mass-assignment was replaced with an allowlist over the same underlying data structure.

---

## Remaining Risks Not Addressed in This Sprint

| Risk | Severity | Sprint |
|---|---|---|
| SHA-256 password hashing (bcrypt not used) | HIGH | Sprint 2 |
| Token revocation is in-memory only (revoked tokens re-valid after restart) | HIGH | Sprint 2 |
| `_revoked` set capped at 5000 entries — cleared on overflow (DoS vector) | MEDIUM | Sprint 2 |
| All structured data (tenders, bidders, bids, contracts) persists in JSON flat files — cloud restart destroys all data | CRITICAL | Sprint 2 |
| Plaintext password fallback still accepted for demo users | HIGH | Sprint 2 |
| `str(e)` error detail leaked to client in admin.py and documents.py without DEBUG_ERRORS guard | MEDIUM | Sprint 3 |
| Audit trail entries for a bidder are deleted on bidder deletion (M-006) | MEDIUM | Sprint 3 |
| `GET /api/bidders/<id>/report` still unauthenticated (not in Task 5 scope) | MEDIUM | Sprint 2 |
| localhost CORS origins always present in production | LOW | Sprint 3 |
| Rate limiter uses in-memory storage by default — not shared across Render workers | LOW | Deployment |
| `POST /api/grievances` accepts anonymous submissions — intentional, but should consider CAPTCHA | LOW | Sprint 3 |

---

## Deployment Configuration Still Required

The following environment variables must be set on Render/Vercel before going to production:

| Variable | Purpose | Required |
|---|---|---|
| `SECRET_KEY` | Signs auth tokens — server will refuse to start without this in production | **CRITICAL** |
| `DATABASE_URL` | PostgreSQL connection string — required for persistent storage | **CRITICAL** |
| `GROQ_API_KEY` | Groq API key for AI chat (starts with `gsk_`) | HIGH |
| `CORS_ORIGINS` | Comma-separated list of Vercel frontend origins | HIGH |
| `RATELIMIT_STORAGE_URI` | Redis/Memcache URI for shared rate-limit state across workers | MEDIUM |
| `SUPABASE_URL` | Supabase project URL for document storage | MEDIUM |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key | MEDIUM |
| `FLASK_ENV` | Set to `production` on Render (triggers SECRET_KEY enforcement) | HIGH |

Generate `SECRET_KEY` with:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
