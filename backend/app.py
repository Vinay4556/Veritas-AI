"""
Veritas AI - Flask Backend
SIH26100 Demo — v2.2 (file-based storage)
"""
import gzip as _gzip
import hashlib
import io as _io
import os
import re

from dotenv import load_dotenv

# Load backend/.env regardless of the directory the server is started from.
# override=False -> real environment variables always win over the file.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'), override=False)

from flask import Flask, jsonify, request  # noqa: E402
from flask_cors import CORS  # noqa: E402
from werkzeug.exceptions import HTTPException  # noqa: E402

from config import UPLOAD_DIR, REPORTS_DIR, DATA_DIR  # noqa: E402
from routes.dashboard import dashboard_bp  # noqa: E402
from routes.tenders import tenders_bp  # noqa: E402
from routes.bidders import bidders_bp  # noqa: E402
from routes.documents import documents_bp  # noqa: E402
from routes.reports import reports_bp  # noqa: E402
from routes.auth import auth_bp  # noqa: E402
from routes.bidder_portal import bidder_portal_bp  # noqa: E402
from routes.officer_portal import officer_portal_bp  # noqa: E402
from routes.officer_summary import officer_summary_bp  # noqa: E402
from routes.public_portal import public_portal_bp  # noqa: E402
from routes.contracts import contracts_bp  # noqa: E402
from routes.verification import verification_bp  # noqa: E402
from routes.grievance import grievance_bp  # noqa: E402
from routes.chat import chat_bp  # noqa: E402
from routes.translate import translate_bp  # noqa: E402
from routes.admin import admin_bp  # noqa: E402

VERSION = '2.2.0'

# Ensure directories exist
for d in (UPLOAD_DIR, REPORTS_DIR, DATA_DIR):
    try:
        os.makedirs(d, exist_ok=True)
    except OSError as exc:  # read-only volume etc. — not fatal
        print(f'[boot] could not create {d}: {exc}')

# Copy seed data to writable DATA_DIR if on cloud and DATA_DIR is empty
if DATA_DIR != os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'):
    import shutil
    seed_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if os.path.exists(seed_data_dir) and os.path.isdir(DATA_DIR):
        # Copy JSON seed files if they don't exist in DATA_DIR
        for filename in os.listdir(seed_data_dir):
            if filename.endswith('.json'):
                src = os.path.join(seed_data_dir, filename)
                dst = os.path.join(DATA_DIR, filename)
                if not os.path.exists(dst):
                    try:
                        shutil.copy2(src, dst)
                        print(f'[boot] copied seed data: {filename} → {DATA_DIR}')
                    except Exception as e:
                        print(f'[boot] could not copy {filename}: {e}')

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB max upload
app.json.sort_keys = False  # keep field order as written (Flask 3 API)


# ── Secret key (signs login tokens) ───────────────────────────────────────────
# Set SECRET_KEY in the environment for production.
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    _secret = hashlib.sha256(('veritas-ai::local-dev').encode()).hexdigest()
    print('[boot] SECRET_KEY not set - using a derived key. Set SECRET_KEY in your environment for production.')
app.config['SECRET_KEY'] = _secret


# ── CORS ──────────────────────────────────────────────────────────────────────
# Auth uses a Bearer token header (no cookies), so credentials mode isn't needed.
# Extra origins: CORS_ORIGINS="https://my-domain.com,https://other.example"
_cors_origins = [
    'http://localhost:3000', 'http://127.0.0.1:3000',
    'http://localhost:5173', 'http://127.0.0.1:5173',
    'https://parakh-ai-kfhf.vercel.app',
    'https://parakh-ai-kfhf.aevovera.vercel.app',
    'https://parakh-ai-kfhf-git-main-aevovera.vercel.app',  # Git branch deployments
    # Vercel preview deployments - match any variation:
    # parakh-ai-*.vercel.app (simple previews)
    # parakh-ai-*.<team>.vercel.app (team-scoped)
    # parakh-ai-kfhf-*.vercel.app (branch previews)
    # parakh-ai-kfhf-*.<team>.vercel.app (team branch previews)
    re.compile(r'^https://parakh-ai(-kfhf)?(-[a-z0-9]+)?\.vercel\.app$'),
    re.compile(r'^https://parakh-ai(-kfhf)?(-[a-z0-9]+)?\.aevovera\.vercel\.app$'),
    re.compile(r'^https://parakh-ai(-kfhf)?(-git-[a-z0-9-]+)?-[a-z0-9]+\.vercel\.app$'),  # Git deployments
    re.compile(r'^https://parakh-ai(-kfhf)?(-[a-z0-9]+)?\.[a-z0-9-]+\.vercel\.app$'),
]
_cors_origins += [o.strip().rstrip('/') for o in os.environ.get('CORS_ORIGINS', '').split(',') if o.strip()]

CORS(
    app,
    resources={r'/api/*': {'origins': _cors_origins}},
    supports_credentials=False,
    allow_headers=['Content-Type', 'Authorization'],
    methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    expose_headers=['Content-Disposition'],
    max_age=86400,
)


# ── Response compression (≥ 1 KB JSON / text) ─────────────────────────────────
@app.after_request
def compress_response(response):
    if (response.direct_passthrough            # send_file() streams — leave alone
            or response.status_code < 200 or response.status_code >= 300
            or 'gzip' not in request.headers.get('Accept-Encoding', '')
            or 'Content-Encoding' in response.headers):
        return response
    if not any(ct in (response.content_type or '') for ct in ('json', 'text', 'javascript')):
        return response
    data = response.get_data()
    if len(data) < 1024:
        return response
    buf = _io.BytesIO()
    with _gzip.GzipFile(mode='wb', fileobj=buf, compresslevel=6) as gz:
        gz.write(data)
    compressed = buf.getvalue()
    if len(compressed) >= len(data):
        return response
    response.set_data(compressed)
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Length'] = len(compressed)
    response.headers.add('Vary', 'Accept-Encoding')
    return response


# ── Blueprints ────────────────────────────────────────────────────────────────
for _bp in (auth_bp, dashboard_bp, tenders_bp, bidders_bp, documents_bp, reports_bp,
            bidder_portal_bp, officer_portal_bp, officer_summary_bp, public_portal_bp,
            contracts_bp, verification_bp, grievance_bp, chat_bp, translate_bp, admin_bp):
    app.register_blueprint(_bp)


@app.route('/', methods=['GET'])
@app.route('/api', methods=['GET'])
def index():
    return {'service': 'Veritas AI API', 'version': VERSION, 'health': '/api/health'}


@app.route('/api/health', methods=['GET'])
def health():
    return {
        'status': 'ok',
        'service': 'Veritas AI',
        'version': VERSION,
        'database': 'file-based',
        'storage': 'JSON files in data/',
    }


# ── Errors: always JSON, never leak internals ─────────────────────────────────
@app.errorhandler(HTTPException)
def http_error(e):
    body = {'error': e.description or e.name}
    if e.code == 404:
        body['error'] = 'Endpoint not found'
    elif e.code == 405:
        body['error'] = 'Method not allowed'
        body['allowed'] = sorted(getattr(e, 'valid_methods', None) or [])
    elif e.code == 413:
        body['error'] = 'File too large. Maximum upload size is 20MB.'
    return jsonify(body), e.code


@app.errorhandler(Exception)
def unhandled(e):
    app.logger.exception('Unhandled error on %s %s', request.method, request.path)
    body = {'error': 'Internal server error'}
    if os.environ.get('DEBUG_ERRORS') == '1':
        body['detail'] = str(e)
    return jsonify(body), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print('=' * 55)
    print('  Veritas AI — SIH26100 · Team Aevora · v' + VERSION)
    print(f'  Backend running at http://localhost:{port}')
    print('=' * 55)
    app.run(debug=False, port=port, host='0.0.0.0', threaded=True)