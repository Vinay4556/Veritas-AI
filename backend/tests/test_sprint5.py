"""
test_sprint5.py — Sprint 5 regression test suite.

Groups:
  A — smoke_test.py no longer causes INTERNALERROR during pytest collection
  B — global_search() has a USE_DATABASE branch for all four entity types
  C — conflict_declaration() db_record uses post-Sprint-4 column names
  D — .env.example documents all required environment variables
  E — Excel export endpoint exists and is authenticated
  F — admin.py error responses are guarded by DEBUG_ERRORS
"""
import os
import sys
import ast
import importlib

import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure backend is importable
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-sprint5-tests')


# ===========================================================================
# GROUP A — smoke_test.py import safety
# ===========================================================================

class TestGroupA_SmokeTestImportSafety:
    """Sprint 5 fix: smoke_test.py must be importable by pytest without
    executing network calls or calling sys.exit()."""

    def test_smoke_test_importable_without_network_calls(self, monkeypatch):
        """Importing smoke_test must not call requests.get/post or sys.exit."""
        import_path = os.path.join(BACKEND_DIR, 'tests', 'smoke_test.py')
        assert os.path.exists(import_path), "smoke_test.py not found"

        # Poison requests and sys.exit so any accidental call raises
        import requests as req_mod
        original_request = req_mod.request
        original_exit = sys.exit

        calls = []

        def boom_request(*a, **kw):
            calls.append(('request', a, kw))
            raise AssertionError("requests.request called during import of smoke_test.py!")

        def boom_exit(code=0):
            calls.append(('exit', code))
            raise AssertionError(f"sys.exit({code}) called during import of smoke_test.py!")

        monkeypatch.setattr(req_mod, 'request', boom_request)
        monkeypatch.setattr(sys, 'exit', boom_exit)

        # Remove cached import so the module is freshly imported under our patch
        smoke_key = [k for k in sys.modules if 'smoke_test' in k]
        for k in smoke_key:
            del sys.modules[k]

        try:
            import importlib.util as ilu
            spec = ilu.spec_from_file_location('smoke_test_guarded', import_path)
            mod = ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except AssertionError as exc:
            pytest.fail(str(exc))
        finally:
            monkeypatch.setattr(req_mod, 'request', original_request)
            monkeypatch.setattr(sys, 'exit', original_exit)

        assert calls == [], (
            f"smoke_test.py made {len(calls)} forbidden call(s) during import: {calls}"
        )

    def test_smoke_test_has_main_guard(self):
        """smoke_test.py must contain an 'if __name__ == '__main__':' guard."""
        import_path = os.path.join(BACKEND_DIR, 'tests', 'smoke_test.py')
        with open(import_path) as f:
            source = f.read()
        tree = ast.parse(source)
        has_guard = any(
            isinstance(node, ast.If) and
            isinstance(node.test, ast.Compare) and
            isinstance(node.test.left, ast.Name) and
            node.test.left.id == '__name__'
            for node in ast.walk(tree)
        )
        assert has_guard, "smoke_test.py does not contain an 'if __name__ == \"__main__\":' guard"


# ===========================================================================
# GROUP B — global_search() USE_DATABASE branch
# ===========================================================================

class TestGroupB_GlobalSearchDualMode:
    """Sprint 5 fix: global_search() must read from DB in USE_DATABASE mode."""

    def test_global_search_db_mode_calls_list_tenders_db(self, client, auth_headers):
        """DB mode: global_search must call db.list_tenders_db() (not load_json)."""
        import routes.officer_portal as portal_mod

        mock_tenders = [{'id': 'TNT-SRCH-001', 'title': 'Search Test Tender',
                         'department': 'QA', 'status': 'OPEN'}]
        mock_list_tenders = MagicMock(return_value=mock_tenders)
        mock_list_bidders = MagicMock(return_value=[])
        mock_list_bids = MagicMock(return_value=[])
        mock_list_contracts = MagicMock(return_value=[])
        mock_load_json = MagicMock(return_value=[])  # must NOT be called

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'list_tenders_db', mock_list_tenders),
            patch.object(portal_mod.db, 'list_bidders_db', mock_list_bidders),
            patch.object(portal_mod.db, 'list_bids_db', mock_list_bids),
            patch.object(portal_mod.db, 'list_contracts_db', mock_list_contracts),
            patch.object(portal_mod, 'load_json', mock_load_json),
        ):
            resp = client.get('/api/search?q=search', headers=auth_headers)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        mock_list_tenders.assert_called_once()
        mock_load_json.assert_not_called(), (
            "load_json must NOT be called in DB mode — use db.list_*_db() instead"
        )

    def test_global_search_db_mode_returns_matching_tender(self, client, auth_headers):
        """DB mode: global_search returns a tender whose title matches the query."""
        import routes.officer_portal as portal_mod

        mock_tenders = [
            {'id': 'TNT-MATCH', 'title': 'Procurement Tender', 'department': 'Finance', 'status': 'OPEN'},
            {'id': 'TNT-NOMATCH', 'title': 'Unrelated Record', 'department': 'IT', 'status': 'OPEN'},
        ]

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'list_tenders_db', return_value=mock_tenders),
            patch.object(portal_mod.db, 'list_bidders_db', return_value=[]),
            patch.object(portal_mod.db, 'list_bids_db', return_value=[]),
            patch.object(portal_mod.db, 'list_contracts_db', return_value=[]),
        ):
            resp = client.get('/api/search?q=procurement', headers=auth_headers)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body is not None
        ids = [r['id'] for r in body.get('results', [])]
        assert 'TNT-MATCH' in ids, f"Expected TNT-MATCH in results, got: {ids}"
        assert 'TNT-NOMATCH' not in ids, f"TNT-NOMATCH must not appear in results"

    def test_global_search_db_mode_officer_searches_bidders(self, client, auth_headers):
        """DB mode: officer role triggers db.list_bidders_db() call."""
        import routes.officer_portal as portal_mod

        mock_bidders = [
            {'id': 'BID-TEST', 'name': 'Alpha Supplies', 'gstin': '29AABCU9603R1ZX',
             'pan': 'AABCU9603R', 'udyam_no': '', 'cin': ''},
        ]

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'list_tenders_db', return_value=[]),
            patch.object(portal_mod.db, 'list_bidders_db', return_value=mock_bidders),
            patch.object(portal_mod.db, 'list_bids_db', return_value=[]),
            patch.object(portal_mod.db, 'list_contracts_db', return_value=[]),
        ):
            resp = client.get('/api/search?q=alpha', headers=auth_headers)

        assert resp.status_code == 200
        body = resp.get_json()
        ids = [r['id'] for r in body.get('results', [])]
        assert 'BID-TEST' in ids, f"Expected BID-TEST in bidder search results, got: {ids}"

    def test_global_search_json_mode_reads_load_json(self, client, auth_headers):
        """JSON mode: global_search calls load_json (not db functions)."""
        import routes.officer_portal as portal_mod

        mock_tenders = [{'id': 'TNT-JSON', 'title': 'JSON Tender', 'department': 'QA', 'status': 'OPEN'}]
        mock_list_db = MagicMock()

        def fake_load_json(filename):
            if 'tenders' in filename:
                return mock_tenders
            return []  # empty list for bidders.json, bids.json, contracts.json

        with (
            patch.object(portal_mod, 'USE_DATABASE', False),
            patch.object(portal_mod, 'load_json', side_effect=fake_load_json),
            patch.object(portal_mod.db, 'list_tenders_db', mock_list_db),
        ):
            resp = client.get('/api/search?q=json', headers=auth_headers)

        assert resp.status_code == 200
        mock_list_db.assert_not_called(), (
            "db.list_tenders_db must NOT be called in JSON mode"
        )


# ===========================================================================
# GROUP C — conflict_declaration field name fix
# ===========================================================================

class TestGroupC_ConflictDeclarationFieldNames:
    """Sprint 5 fix: db_record passed to create_conflict_declaration_db must use
    post-Sprint-4 column names: officer_id (not declared_by), action (not conflict_type)."""

    def test_conflict_declaration_db_record_uses_officer_id(self, client, auth_headers):
        """DB mode: db_record passed to create_conflict_declaration_db has officer_id, not declared_by."""
        import routes.officer_portal as portal_mod

        captured_args = {}

        def capture_create(data):
            captured_args['data'] = dict(data)
            return {'id': 'CFLCT-test'}

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'create_conflict_declaration_db', side_effect=capture_create),
            patch.object(portal_mod.db, 'append_audit', MagicMock()),
        ):
            resp = client.post(
                '/api/tenders/TNT-TEST/conflict-declaration',
                json={
                    'has_conflict': True,
                    'action': 'RECUSE',
                    'officer_name': 'Test Officer',
                    'conflict_reason': 'Familial relationship',
                },
                headers=auth_headers,
            )

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.get_json()}"
        assert captured_args, "create_conflict_declaration_db was not called"

        data = captured_args['data']
        assert 'officer_id' in data, (
            f"db_record must contain 'officer_id', got keys: {list(data.keys())}"
        )
        assert 'declared_by' not in data, (
            f"db_record must NOT contain deprecated 'declared_by' key, got: {list(data.keys())}"
        )
        assert 'action' in data, (
            f"db_record must contain 'action', got keys: {list(data.keys())}"
        )
        assert 'conflict_type' not in data, (
            f"db_record must NOT contain deprecated 'conflict_type' key, got: {list(data.keys())}"
        )

    def test_conflict_declaration_action_value_correct(self, client, auth_headers):
        """action in db_record comes from request body field 'action', not 'conflict_type'."""
        import routes.officer_portal as portal_mod

        captured_args = {}

        def capture_create(data):
            captured_args['data'] = dict(data)
            return {'id': 'CFLCT-test2'}

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'create_conflict_declaration_db', side_effect=capture_create),
            patch.object(portal_mod.db, 'append_audit', MagicMock()),
        ):
            resp = client.post(
                '/api/tenders/TNT-TEST2/conflict-declaration',
                json={'action': 'DISCLOSE', 'officer_name': 'Test Officer'},
                headers=auth_headers,
            )

        assert resp.status_code == 201
        data = captured_args.get('data', {})
        assert data.get('action') == 'DISCLOSE', (
            f"Expected action='DISCLOSE', got: {data.get('action')}"
        )


# ===========================================================================
# GROUP D — .env.example completeness
# ===========================================================================

class TestGroupD_EnvExampleCompleteness:
    """Sprint 5 fix: .env.example must document all required environment variables."""

    ENV_EXAMPLE_PATH = os.path.join(BACKEND_DIR, '.env.example')
    REQUIRED_VARS = [
        'DATABASE_URL',
        'SECRET_KEY',
        'FLASK_ENV',
        'CORS_ORIGINS',
        'GROQ_API_KEY',
        'GOV_ADAPTER_MODE',
        'AI_MODE',
        'DEMO_OFFICER_PASS',
        'DEMO_BIDDER_PASS',
        'DEMO_BIDDER2_PASS',
        'DEMO_CITIZEN_PASS',
        'TOKEN_TTL_HOURS',
        'RATELIMIT_STORAGE_URI',
        'DEBUG_ERRORS',
    ]

    def _load_env_example(self):
        assert os.path.exists(self.ENV_EXAMPLE_PATH), ".env.example not found"
        with open(self.ENV_EXAMPLE_PATH) as f:
            return f.read()

    def test_env_example_exists(self):
        assert os.path.exists(self.ENV_EXAMPLE_PATH), ".env.example does not exist"

    @pytest.mark.parametrize('var', REQUIRED_VARS)
    def test_env_example_documents_variable(self, var):
        """Each required env var must appear in .env.example."""
        content = self._load_env_example()
        assert var in content, (
            f"'{var}' is missing from .env.example"
        )

    def test_flask_env_has_production_example(self):
        """FLASK_ENV line in .env.example should mention 'production'."""
        content = self._load_env_example()
        assert 'production' in content, (
            ".env.example must mention 'production' in context with FLASK_ENV"
        )


# ===========================================================================
# GROUP E — Excel export endpoint
# ===========================================================================

class TestGroupE_ExcelExport:
    """Sprint 5 verification: Excel export endpoint exists and enforces auth."""

    def test_excel_export_requires_auth(self, client):
        """GET /api/officer/tenders/<id>/summary/excel without token -> 401."""
        resp = client.get('/api/officer/tenders/TNT-001/summary/excel')
        assert resp.status_code in (401, 403), (
            f"Excel export endpoint must require authentication, got: {resp.status_code}"
        )

    def test_excel_export_endpoint_registered(self, app):
        """The Excel export URL rule must be registered in the Flask app."""
        rules = [str(rule) for rule in app.url_map.iter_rules()]
        excel_rules = [r for r in rules if 'summary/excel' in r]
        assert excel_rules, (
            f"No URL rule containing 'summary/excel' found. All rules: {rules}"
        )


# ===========================================================================
# GROUP F — admin.py DEBUG_ERRORS guard
# ===========================================================================

class TestGroupF_AdminDebugErrorsGuard:
    """Sprint 5 fix: admin.py error responses must hide str(e) unless DEBUG_ERRORS=1."""

    def _trigger_delete_all_docs_error(self, client, auth_headers, env_patch):
        """Helper: trigger the delete_all_documents error path."""
        import routes.admin as admin_mod
        from services import document_service as doc_svc

        def boom():
            raise RuntimeError("Intentional test error — sentinel_12345")

        with (
            patch.object(admin_mod, 'USE_DATABASE', False),
            patch.object(admin_mod, 'invalidate_all', MagicMock()),
            patch.object(doc_svc, 'get_all_documents', side_effect=boom),
            env_patch,
        ):
            return client.post(
                '/api/admin/delete-all-documents',
                json={'confirm': True},
                headers=auth_headers,
            )

    def test_delete_all_documents_hides_error_without_debug_flag(self, client, auth_headers, monkeypatch):
        """Without DEBUG_ERRORS, error detail must not be in the response."""
        monkeypatch.delenv('DEBUG_ERRORS', raising=False)
        resp = self._trigger_delete_all_docs_error(
            client, auth_headers, patch.dict(os.environ, {}, clear=False)
        )
        assert resp.status_code == 500
        body = resp.get_json() or {}
        error_msg = body.get('error', '')
        assert 'sentinel_12345' not in error_msg, (
            f"Exception detail leaked in error response without DEBUG_ERRORS: {error_msg!r}"
        )

    def test_delete_all_documents_shows_error_with_debug_flag(self, client, auth_headers, monkeypatch):
        """With DEBUG_ERRORS=1, error detail IS returned."""
        monkeypatch.setenv('DEBUG_ERRORS', '1')
        resp = self._trigger_delete_all_docs_error(
            client, auth_headers, patch.dict(os.environ, {'DEBUG_ERRORS': '1'}, clear=False)
        )
        assert resp.status_code == 500
        body = resp.get_json() or {}
        error_msg = body.get('error', '')
        assert 'sentinel_12345' in error_msg, (
            f"Exception detail must appear in response when DEBUG_ERRORS=1: {error_msg!r}"
        )

    def test_admin_status_hides_error_without_debug_flag(self, client, auth_headers, monkeypatch):
        """admin_status error response must hide str(e) without DEBUG_ERRORS."""
        import routes.admin as admin_mod

        monkeypatch.delenv('DEBUG_ERRORS', raising=False)

        def boom(*a, **kw):
            raise RuntimeError("status_sentinel_99999")

        with (
            patch.object(admin_mod, 'USE_DATABASE', False),
            patch.object(admin_mod, 'load_cached', side_effect=boom),
        ):
            resp = client.get('/api/admin/status', headers=auth_headers)

        assert resp.status_code == 500
        body = resp.get_json() or {}
        error_msg = body.get('error', '')
        assert 'status_sentinel_99999' not in error_msg, (
            f"Exception detail leaked without DEBUG_ERRORS in admin_status: {error_msg!r}"
        )
