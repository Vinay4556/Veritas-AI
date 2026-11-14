# Veritas AI

**Procurement compliance intelligence — evidence-driven bid review in one clear workspace.**

Veritas AI helps procurement teams bring tender requirements, bidder documents and
verification evidence together, review compliance consistently, and record
decisions with a complete audit trail. It is a decision-support system: AI
extracts, matches and explains, while compliance rules stay deterministic and the
final decision remains with the authorised officer.

---

## What it does

- **Tender management** — create tenders, define mandatory and optional
  requirements, run pre-bid meetings and corrigenda.
- **Bidder & document intake** — upload bidder documents (PDF, images, DOCX),
  extract text, classify document type and detect tampering signals.
- **Compliance review** — match each requirement to evidence, flag verified,
  needs-review, non-compliant and missing items, and show the source document
  behind every finding.
- **Verification adapters** — offline structural checks by default, with optional
  live government-data adapters (GSTIN, PAN, MCA21) when credentials are configured.
- **Evaluation & decisions** — technical/financial evaluation, bid comparison,
  QCBS/L1/MSE/Make-in-India support, two-envelope opening, and an officer
  decision step that is permanently recorded.
- **Contracts, inspections, corrective actions, grievances and public
  transparency** — the full lifecycle after award, including a stakeholder view
  and an append-only audit trail.
- **AI assistant** — plain-language explanations via Groq API. Without an API key
  it returns a deterministic 503; add `GROQ_API_KEY` to enable live responses.

---

## Portals & sample accounts

| Portal | Email | Password | Access |
|--------|-------|----------|--------|
| Procurement officer | `officer@demo.gov` | `password` | Tenders, evaluation, decisions |
| Bidder | `bidder@demo.com` | `password` | Tender discovery, bid submission |
| Bidder 2 | `bidder2@demo.com` | `password` | Second bidder for comparison testing |
| Public stakeholder | `citizen@demo.com` | `password` | Transparency, timelines, feedback |

These are seeded local accounts for evaluation. In PostgreSQL mode the first login
automatically upgrades each password to bcrypt — no manual step needed.
Change or remove them before any real deployment.

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────────────┐
│  Frontend       │     │  Backend         │     │  Storage                 │
│  React 18 + Vite│────▶│  Flask 3 (Python)│────▶│  JSON files  (local dev) │
│  Port 3000      │     │  Port 5000       │     │  PostgreSQL  (production) │
└─────────────────┘     └──────────────────┘     └──────────────────────────┘
```

| Layer | Technology |
|-------|-----------|
| Frontend | React 18.3, Vite 8.3, TailwindCSS 3.4, Recharts, Lucide, Axios, i18next |
| Backend | Python 3.10+, Flask 3.0, Flask-CORS, itsdangerous (signed tokens), bcrypt |
| Auth | URLSafeTimedSerializer tokens · bcrypt password hashing · persistent revocation via `revoked_tokens` table |
| Rate limiting | flask-limiter (10 req/min per IP on `/api/auth/login`) |
| Local storage | JSON files under `backend/data/` — zero config, no database required |
| Production storage | PostgreSQL (all 24 tables) + local filesystem or Supabase Storage for file blobs |
| Document AI | PyMuPDF 1.24+ (PDF text + hashing); optional Tesseract OCR for scanned images |
| AI assistant | Deterministic 503 (no key) or live Groq API (`GROQ_API_KEY`) |
| Translation | Self-hosted LibreTranslate (optional Docker service) + MyMemory fallback |

### Dual-mode storage

The app switches storage automatically based on `DATABASE_URL`:

| `DATABASE_URL` | Storage | Use case |
|---|---|---|
| Empty / not set | JSON files in `backend/data/` | Local evaluation, demos |
| Set to a PostgreSQL URL | PostgreSQL (all entities) | Production, persistent data |

In production mode (PostgreSQL) **every** entity is persisted to the database:
tenders, bidders, bids, contracts, inspections, compliance results, audit trail,
grievances, notifications, and more. The app never silently falls back to JSON in
production.

---

## Quick start (local, no database)

### Prerequisites
- Python 3.10+ (3.14 tested)
- Node.js 20.19+ (24 tested)
- No database required for evaluation

### Windows (one command)

```bat
start.bat
```

This starts both the backend and frontend in separate console windows.
On first run it copies `backend/.env.example` → `backend/.env` if no `.env` exists.

### Manual start (Windows — two PowerShell terminals)

**Terminal 1 — Backend**
```powershell
cd D:\your-project\Veritas-AI\backend
pip install -r requirements.txt
python app.py
```

**Terminal 2 — Frontend**
```powershell
cd D:\your-project\Veritas-AI\frontend
npm install
npm run dev
```

- Backend: http://localhost:5000 · health check: http://localhost:5000/api/health
- Frontend: http://localhost:3000 · Vite proxies `/api/*` to the backend automatically

### Linux / macOS

```bash
# Terminal 1
cd backend && pip install -r requirements.txt && python app.py

# Terminal 2
cd frontend && npm install && npm run dev
```

---

## Local development with PostgreSQL

If you want persistent data locally (data survives backend restarts):

### 1. Create the database

```sql
-- In psql
CREATE DATABASE veritas_ai;
-- pgcrypto is NOT required on PostgreSQL 13+
```

### 2. Configure `backend/.env`

```env
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/veritas_ai
```

Do not set `FLASK_ENV=production` for local development — that enables
production guards (mandatory `SECRET_KEY`, no plaintext password fallback).

### 3. Run migrations

```powershell
cd backend
python -m alembic upgrade head
```

This applies all 4 migrations in sequence, creating all 24 tables:

| Migration | Revision | Contents |
|---|---|---|
| Initial schema | `6fd62e526b64` | users, tenders, bidders, requirements, documents + 10 supporting tables |
| Sprint 2 entities | `a3f91b2c8e47` | Full bids, contracts, inspections, corrective_actions, vendor_profiles, compliance_results, feedback, rejection_feedback, ai_overrides, eval_committees, conflict_declarations + extended columns |
| Sprint 3 revocation | `b7d3c2a1f804` | revoked_tokens (persistent logout) |
| Sprint 4 conflict columns | `c9e4d3b2a156` (head) | conflict_declarations: officer_id, officer_name, has_conflict, action |

### 4. Seed demo users (PostgreSQL only)

```powershell
cd backend
python scripts/create_demo_users.py
```

This inserts 4 demo accounts with bcrypt-hashed passwords. It is fully
idempotent — safe to run multiple times.

> **SHA-256 upgrade:** if users already exist with SHA-256 hashes, their
> passwords are automatically upgraded to bcrypt on their first successful login.
> No manual step required.

### 5. Start the app (same as above)

```powershell
# Terminal 1
cd backend && python app.py

# Terminal 2
cd frontend && npm run dev
```

Verify the connection: http://localhost:5000/api/health should return
`"db_connected": true, "db_mode": "postgresql"`.

---

## Configuration reference

Copy `backend/.env.example` to `backend/.env`.

```env
# ── Database ─────────────────────────────────────────────────────────────────
# Leave empty for local JSON mode. Set for PostgreSQL persistence.
DATABASE_URL=postgresql://user:password@localhost:5432/veritas_ai

# ── Security ──────────────────────────────────────────────────────────────────
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
# Required in production — app refuses to start without it when FLASK_ENV=production.
SECRET_KEY=
TOKEN_TTL_HOURS=12

# ── CORS ──────────────────────────────────────────────────────────────────────
# localhost:3000 and localhost:5173 are always allowed; add extra origins here.
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ── AI assistant (optional) ───────────────────────────────────────────────────
# Without a key, /api/chat returns 503 with an informative message.
GROQ_API_KEY=

# ── Government API adapters ───────────────────────────────────────────────────
# MOCK = deterministic offline checks (default). LIVE = real API calls.
GOV_ADAPTER_MODE=MOCK
GSTINAPI_KEY=
DATA_GOV_API_KEY=

# ── Supabase Storage (optional) ───────────────────────────────────────────────
# Without these, uploaded files are stored in backend/uploads/ locally.
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=documents

# ── Rate limiting (multi-worker production) ───────────────────────────────────
# Redis URI for shared rate-limit state across gunicorn workers.
# Omit for single-worker or local dev.
RATELIMIT_STORAGE_URI=

# ── Flask environment ─────────────────────────────────────────────────────────
# Set to 'production' on Render/Railway to enable SECRET_KEY enforcement
# and block plaintext password fallback. Leave unset for local dev.
FLASK_ENV=production

# ── Demo user passwords (production seed only) ────────────────────────────────
# Required by scripts/create_demo_users.py when FLASK_ENV=production.
DEMO_OFFICER_PASS=
DEMO_BIDDER_PASS=
DEMO_BIDDER2_PASS=
DEMO_CITIZEN_PASS=
```

> **Security note:** `.env` is gitignored. Never commit real credentials.
> Only `.env.example` (with empty placeholders) is tracked.

---

## Security model

| Feature | Implementation |
|---|---|
| Password hashing | bcrypt, 12 rounds. Legacy SHA-256 hashes are upgraded automatically on first login. |
| Auth tokens | itsdangerous `URLSafeTimedSerializer` (HMAC-SHA1 signed, 12-hour TTL) |
| Token storage | `localStorage` (known XSS trade-off; HttpOnly cookie migration is a future item) |
| Token revocation | `revoked_tokens` PostgreSQL table — survives server restarts |
| Login brute force | flask-limiter: 10 requests/minute per IP |
| Rate limit storage | In-memory (dev) or Redis via `RATELIMIT_STORAGE_URI` (multi-worker) |
| CORS | Explicit origin allowlist; no wildcard `*` |
| Secret key | App refuses to start in production without `SECRET_KEY` or if set to the known dev fallback |
| Plaintext passwords | Blocked in DB mode and when `FLASK_ENV=production` |
| Admin destructive ops | Require `{"confirm": true}` in request body |

---

## Database tables (24 total)

All 24 tables are created by `alembic upgrade head`. Key tables:

| Table | Purpose |
|---|---|
| `users` | Authentication — UUID PK, bcrypt `password_hash` |
| `tenders` | Tender lifecycle and policy configuration |
| `bidders` | Bidder registrations linked to a tender |
| `requirements` | Per-tender compliance requirements |
| `bids` | Full bid lifecycle including financial data and verifications |
| `documents` | Document metadata, OCR results, tampering signals |
| `compliance_results` | Per-(bidder, requirement) compliance analysis results |
| `contracts` | Awarded contracts and milestones |
| `inspections` | Quality inspection records |
| `corrective_actions` | Post-inspection corrective action orders |
| `audit` | Append-only procurement audit trail |
| `revoked_tokens` | Persistent token revocation (logout survives restarts) |
| `conflict_declarations` | Officer conflict-of-interest declarations |
| `eval_committees` | Technical evaluation committee and scores |
| `grievances` | Grievance submissions and responses |
| `notifications` | System notifications per user/role |
| `rejection_feedback` | Rejection rationale sent to disqualified bidders |
| `ai_overrides` | Officer overrides to AI recommendations |

---

## API overview

All endpoints are under `/api`. Endpoints marked with 🔒 require
`Authorization: Bearer <token>`.

| Area | Endpoints |
|------|----------|
| Auth | `POST /api/auth/login` · `GET /api/auth/me` 🔒 · `POST /api/auth/logout` 🔒 · `POST /api/auth/change-password` 🔒 |
| Health | `GET /api/health` |
| Tenders | `GET/POST /api/tenders` 🔒 · `GET /api/tenders/<id>` 🔒 · extend · cancel · re-tender · corrigendum · pre-bid |
| Bidders | `GET/POST /api/bidders` 🔒 · compliance · tampering · decisions · deletion |
| Documents | `POST /api/documents/upload` 🔒 · view · download · reprocess · duplicate-check |
| Bids | submit · withdraw · modify · versions · advance-stage · open-financial |
| Evaluation | EMD verify · price analysis · preference verify · local-content verify · OEM verify · committee |
| Contracts | CRUD · milestones · inspections · corrective actions · vendor profiles |
| Compliance | `POST /api/bidders/<id>/analyze` 🔒 · `GET /api/bidders/<id>/compliance` 🔒 |
| AI | `POST /api/ai/<type>/<id>/override` 🔒 · `POST /api/chat` 🔒 |
| Grievances | submit · list · assign · respond |
| Reports | bidder report · officer summary · Excel export |
| Search | `GET /api/search?q=` 🔒 |
| Public | `/api/public/tenders` · timelines · feedback · grievance stats |
| Admin 🔒 | status · reset compliance · cleanup reports · cleanup expired tokens |

---

## Testing

```powershell
# Unit + integration tests (no running server needed)
cd backend
python -m pytest tests/test_sprint4.py tests/test_integration.py -v

# Live smoke test (requires running backend at localhost:5000)
python tests/smoke_test.py http://localhost:5000

# Frontend production build check
cd frontend
npm run build
```

---

## Deployment (Render + Vercel + Supabase)

### Backend → Render

| Setting | Value |
|---|---|
| Root directory | `backend` |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn app:app --workers 4 --bind 0.0.0.0:$PORT --timeout 120` |
| Health check path | `/api/health` |

Required environment variables on Render:

```
DATABASE_URL          postgresql://...?sslmode=require
SECRET_KEY            <generate: python -c "import secrets; print(secrets.token_hex(32))">
FLASK_ENV             production
CORS_ORIGINS          https://your-app.vercel.app
GROQ_API_KEY          gsk_...
SUPABASE_URL          https://...supabase.co
SUPABASE_SERVICE_ROLE_KEY  eyJ...
RATELIMIT_STORAGE_URI redis://...   (recommended for multi-worker)
```

**Before first deploy, run in the Render shell:**
```bash
alembic upgrade head
python scripts/create_demo_users.py
```

### Frontend → Vercel

1. Connect your repository to a Vercel project.
2. Set build output directory to `frontend/dist`.
3. Build command: `cd frontend && npm run build`.
4. Update `vercel.json` at the repo root — replace the backend URL placeholder:
   ```json
   {
     "rewrites": [
       { "source": "/api/:path*", "destination": "https://YOUR-APP.onrender.com/api/:path*" },
       { "source": "/(.*)", "destination": "/index.html" }
     ]
   }
   ```

---

## Troubleshooting

**`[config] Database: PostgreSQL (Supabase)` even when pointing to localhost.**
This is a cosmetic log label that fires whenever `DATABASE_URL` is set,
regardless of the actual host. It does not indicate a Supabase connection.
Check the hostname in your `DATABASE_URL`.

**`"db_connected": false` on `/api/health`.**
PostgreSQL is not reachable. Verify the host, port, database name and password
in `backend/.env`. Run `psql -U postgres -d veritas_ai` to test connectivity.

**Tables are missing after `alembic upgrade head`.**
Confirm all 4 migrations applied: `python -m alembic current` should show
`c9e4d3b2a156 (head)`. If it shows `6fd62e526b64`, the last 3 migrations did not
run — check for errors in the alembic output.

**Demo users cannot log in after PostgreSQL setup.**
Run `python scripts/create_demo_users.py` to seed them. The script is idempotent.

**Documents don't appear after upload.**
Check the backend log. In local mode, files go to `backend/uploads/` and
metadata to the `documents` table (or `backend/data/documents.json` in JSON mode).

**OCR returns no text for images.**
Install the Tesseract binary (Windows: https://github.com/UB-Mannheim/tesseract/wiki)
and restart the backend. PDFs with a text layer work without Tesseract.

**CORS errors in the browser.**
Add your frontend origin to `CORS_ORIGINS` in `backend/.env` and restart.

**Frontend port conflict.**
Vite dev server runs on port 3000. Change it with `npm run dev -- --port 3001`.

**`SECRET_KEY` fatal error on startup.**
When `FLASK_ENV=production` the app exits if `SECRET_KEY` is missing or equals
the known dev fallback. Set a strong value or unset `FLASK_ENV` for local dev.

---

## License

MIT License.
#   V e r i t a s - A I  
 