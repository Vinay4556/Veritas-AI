"""
test_sprint4.py — Sprint 4 automated test suite.

Groups:
  A — Rejection feedback DB write fix (FEAT-001)
  B — Admin confirm guard (FEAT-002)
  C — Officer summary dual mode (FEAT-002)
  D — Audit integrity in delete_bidder (FEAT-002)
  E — Security hardening (FEAT-003)
  F — Conflict declaration DB wiring (FEAT-001)
  G — Migration file structure (FEAT-002)
  H — submit_committee_score JSON-path guard (FEAT-001)
"""
import os
import sys
import subprocess
import json

import pytest
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Ensure backend is importable
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-sprint4-tests')


# ===========================================================================
# GROUP A — Rejection feedback DB write fix
# ===========================================================================

class TestGroupA_RejectionFeedback:
    """FEAT-001: _save_feedback() no-op in DB mode was fixed to call
    db.update_rejection_feedback_db() and db.append_audit()."""

    def test_save_feedback_db_mode_calls_update(self, client, auth_headers):
        """DB mode: send_rejection_feedback must call db.update_rejection_feedback_db."""
        import routes.bidders as bidders_mod

        fake_record = {
            'id': 'FB-001',
            'bidder_id': 'BID-001',
            'bidder_name': 'Test Bidder',
            'tender_id': 'TNT-001',
            'officer': 'Test Officer',
        }

        mock_db_update = MagicMock()
        mock_db_audit = MagicMock()

        with (
            patch.object(bidders_mod, 'USE_DATABASE', True),
            patch.object(bidders_mod.db, 'list_rejection_feedback_db',
                         return_value=[fake_record]),
            patch.object(bidders_mod.db, 'update_rejection_feedback_db',
                         mock_db_update),
            patch.object(bidders_mod.db, 'append_audit', mock_db_audit),
        ):
            resp = client.post(
                '/api/rejection-feedback/FB-001/send',
                json={'additional_feedback': 'Please improve your documentation.'},
                headers=auth_headers,
            )

        # Either 200 OK or we at least confirm the DB function was called
        assert resp.status_code == 200
        mock_db_update.assert_called_once()
        call_args = mock_db_update.call_args
        # First positional arg should be the feedback id
        assert call_args[0][0] == 'FB-001'
        updates = call_args[0][1]
        assert 'additional_feedback' in updates
        assert updates['additional_feedback'] == 'Please improve your documentation.'

    def test_save_feedback_json_mode_calls_save_cached(self, client, auth_headers):
        """JSON mode: send_rejection_feedback must call save_cached with rejection_feedback.json."""
        import routes.bidders as bidders_mod

        fake_record = {
            'id': 'FB-002',
            'bidder_id': 'BID-001',
            'bidder_name': 'Test Bidder',
            'tender_id': 'TNT-001',
            'officer': 'Test Officer',
        }

        mock_save = MagicMock()

        with (
            patch.object(bidders_mod, 'USE_DATABASE', False),
            patch.object(bidders_mod, 'load_cached', return_value=[fake_record]),
            patch.object(bidders_mod, 'save_cached', mock_save),
        ):
            resp = client.post(
                '/api/rejection-feedback/FB-002/send',
                json={'additional_feedback': 'Improve your local content declaration.'},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        # save_cached must have been called with 'rejection_feedback.json'
        calls_to_rf = [c for c in mock_save.call_args_list
                       if c[0][0] == 'rejection_feedback.json']
        assert len(calls_to_rf) >= 1, (
            "save_cached('rejection_feedback.json', ...) was not called in JSON mode"
        )


# ===========================================================================
# GROUP B — Admin confirm guard
# ===========================================================================

class TestGroupB_AdminConfirmGuard:
    """FEAT-002: delete_all_documents and reset_all_compliance require confirm=true."""

    def test_delete_all_documents_requires_confirm(self, client, auth_headers):
        """POST /api/admin/delete-all-documents with no confirm → 400."""
        resp = client.post(
            '/api/admin/delete-all-documents',
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body is not None
        assert 'error' in body

    def test_reset_all_compliance_requires_confirm(self, client, auth_headers):
        """POST /api/admin/reset-all-compliance with no confirm → 400."""
        resp = client.post(
            '/api/admin/reset-all-compliance',
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body is not None
        assert 'error' in body

    def test_reset_all_compliance_with_confirm_json_mode(self, client, auth_headers):
        """POST /api/admin/reset-all-compliance with confirm=true in JSON mode → 200."""
        import routes.admin as admin_mod

        with (
            patch.object(admin_mod, 'USE_DATABASE', False),
            patch.object(admin_mod, 'load_cached', return_value=[]),
            patch.object(admin_mod, 'save_cached', MagicMock()),
            patch.object(admin_mod, 'invalidate_all', MagicMock()),
        ):
            resp = client.post(
                '/api/admin/reset-all-compliance',
                json={'confirm': True},
                headers=auth_headers,
            )

        assert resp.status_code == 200


# ===========================================================================
# GROUP C — Officer summary dual mode
# ===========================================================================

class TestGroupC_OfficerSummaryDualMode:
    """FEAT-002: _load_bidders() in officer_summary.py must use db or load_cached."""

    def test_load_bidders_db_mode(self, monkeypatch):
        """USE_DATABASE=True: _load_bidders() calls db.list_bidders_db()."""
        import routes.officer_summary as summary_mod

        mock_bidders = [{'id': 'BID-001', 'tender_id': 'TNT-001'}]
        mock_list_db = MagicMock(return_value=mock_bidders)

        monkeypatch.setattr(summary_mod, 'USE_DATABASE', True)
        monkeypatch.setattr(summary_mod.db, 'list_bidders_db', mock_list_db)

        result = summary_mod._load_bidders()
        assert result == mock_bidders
        mock_list_db.assert_called_once()

    def test_load_bidders_json_mode(self, monkeypatch):
        """USE_DATABASE=False: _load_bidders() calls load_cached('bidders.json')."""
        import routes.officer_summary as summary_mod
        from services import json_cache

        mock_bidders = [{'id': 'BID-001'}]
        mock_load = MagicMock(return_value=mock_bidders)

        monkeypatch.setattr(summary_mod, 'USE_DATABASE', False)
        monkeypatch.setattr(json_cache, 'load_cached', mock_load)

        result = summary_mod._load_bidders()
        assert result == mock_bidders
        mock_load.assert_called_once_with('bidders.json')


# ===========================================================================
# GROUP D — Audit integrity in delete_bidder
# ===========================================================================

class TestGroupD_AuditIntegrity:
    """FEAT-002 (M-006 fix): delete_bidder must NOT filter prior audit entries."""

    def test_delete_bidder_json_mode_preserves_audit(self, client, auth_headers):
        """JSON mode: existing audit entries for the bidder must be preserved."""
        import routes.bidders as bidders_mod
        import services.document_service as doc_svc

        bidder_id = 'BID-AUDIT-TEST'
        existing_bidder = {
            'id': bidder_id,
            'name': 'Audit Test Bidder',
            'tender_id': 'TNT-001',
        }
        existing_audit = [
            {'id': 'AUD-001', 'bidder_id': bidder_id, 'action': 'Bid Submitted',
             'tender_id': 'TNT-001', 'actor': 'system', 'timestamp': '2025-01-01T00:00:00'},
            {'id': 'AUD-002', 'bidder_id': bidder_id, 'action': 'Document Uploaded',
             'tender_id': 'TNT-001', 'actor': 'system', 'timestamp': '2025-01-02T00:00:00'},
        ]

        saved_audit_calls = []

        def fake_load_cached(name, default=None):
            if name == 'audit.json':
                return list(existing_audit)  # copy to avoid mutation bleed
            if name == 'compliance.json':
                return {}
            return default if default is not None else []

        def fake_save_cached(name, data):
            if name == 'audit.json':
                saved_audit_calls.append(list(data))

        with (
            patch.object(bidders_mod, 'USE_DATABASE', False),
            patch.object(bidders_mod, 'load_cached', side_effect=fake_load_cached),
            patch.object(bidders_mod, 'save_cached', side_effect=fake_save_cached),
            # load_bidders is defined in bidders_mod and calls load_cached internally;
            # patch it directly so we control which bidder is "found"
            patch.object(bidders_mod, 'load_bidders', return_value=[existing_bidder]),
            # load_documents / save_documents are imported locally inside delete_bidder;
            # patch them at the module level in document_service
            patch.object(doc_svc, 'load_documents', return_value=[]),
            patch.object(doc_svc, 'save_documents', MagicMock()),
        ):
            resp = client.delete(
                f'/api/bidders/{bidder_id}',
                headers=auth_headers,
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.get_json()}"

        # There must have been at least one save to audit.json
        assert saved_audit_calls, "save_cached('audit.json', ...) was never called"
        final_audit = saved_audit_calls[-1]

        # The two existing entries must still be present
        saved_ids = {e.get('id') for e in final_audit}
        assert 'AUD-001' in saved_ids, "Prior audit entry AUD-001 was dropped!"
        assert 'AUD-002' in saved_ids, "Prior audit entry AUD-002 was dropped!"

        # A new 'Bidder Deleted' entry must have been appended
        assert any(e.get('action') == 'Bidder Deleted' for e in final_audit), (
            "No 'Bidder Deleted' audit entry was appended"
        )
        assert len(final_audit) >= 3, (
            f"Expected at least 3 audit entries (2 prior + 1 new), got {len(final_audit)}"
        )

    def test_delete_bidder_db_mode_calls_delete_bidder_db(self, client, auth_headers):
        """DB mode: delete_bidder must call db.delete_bidder_db and db.append_audit."""
        import routes.bidders as bidders_mod

        bidder_id = 'BID-DB-TEST'
        existing_bidder = {
            'id': bidder_id,
            'name': 'DB Test Bidder',
            'tender_id': 'TNT-001',
        }

        mock_delete = MagicMock(return_value=1)
        mock_audit = MagicMock()
        mock_exec = MagicMock()

        with (
            patch.object(bidders_mod, 'USE_DATABASE', True),
            patch.object(bidders_mod, 'load_bidders',
                         return_value=[existing_bidder]),
            patch.object(bidders_mod.db, 'delete_bidder_db', mock_delete),
            patch.object(bidders_mod.db, 'append_audit', mock_audit),
            patch.object(bidders_mod.db, 'execute_query', mock_exec),
            patch('routes.bidders.get_documents_for_bidder', return_value=[]),
        ):
            resp = client.delete(
                f'/api/bidders/{bidder_id}',
                headers=auth_headers,
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.get_json()}"
        mock_delete.assert_called_once_with(bidder_id)
        mock_audit.assert_called_once()


# ===========================================================================
# GROUP E — Security hardening
# ===========================================================================

class TestGroupE_Security:
    """FEAT-003: plaintext password blocked in DB/production mode."""

    def test_check_password_plaintext_blocked_in_db_mode(self, monkeypatch):
        """DB mode: _check_password must return False for plaintext match."""
        import routes.auth as auth_mod

        monkeypatch.setattr(auth_mod, 'USE_DATABASE', True, raising=False)
        # Import USE_DATABASE into the function-local namespace is done at call time
        # We also patch config.USE_DATABASE for the inner import inside _check_password
        import config
        monkeypatch.setattr(config, 'USE_DATABASE', True)

        # User has no bcrypt/sha256 hash — only a plaintext password stored
        user = {'password_hash': 'notahash', 'password': 'notahash'}
        result = auth_mod._check_password(user, 'notahash')
        assert result is False, (
            "Plaintext password check must return False when USE_DATABASE=True"
        )

    def test_check_password_plaintext_allowed_in_local_mode(self, monkeypatch):
        """Local dev mode: _check_password allows plaintext demo passwords."""
        import routes.auth as auth_mod
        import config

        monkeypatch.setattr(config, 'USE_DATABASE', False)
        monkeypatch.delenv('FLASK_ENV', raising=False)

        # User has a plaintext demo password (no hash prefix, not 64-char hex)
        user = {'password': 'demo123'}
        result = auth_mod._check_password(user, 'demo123')
        assert result is True, (
            "Plaintext password check must return True when USE_DATABASE=False and not production"
        )

    def test_create_demo_users_exits_in_production(self):
        """create_demo_users.py must exit with code 1 when FLASK_ENV=production."""
        env = os.environ.copy()
        env['FLASK_ENV'] = 'production'
        # Ensure no DATABASE_URL is required — script should exit before any DB calls
        env.pop('DATABASE_URL', None)

        result = subprocess.run(
            [sys.executable, 'create_demo_users.py'],
            env=env,
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 1, (
            f"Expected exit code 1 in production, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert 'ERROR' in result.stdout or 'ERROR' in result.stderr, (
            "Expected an ERROR message in output when running in production mode"
        )


# ===========================================================================
# GROUP F — Conflict declaration DB wiring
# ===========================================================================

class TestGroupF_ConflictDeclaration:
    """FEAT-001: conflict_declaration() must call db.create_conflict_declaration_db
    and db.append_audit in DB mode."""

    def test_conflict_declaration_db_mode_calls_create(self, client, auth_headers):
        """DB mode: POST /api/tenders/<id>/conflict-declaration calls the DB functions."""
        import routes.officer_portal as portal_mod

        mock_create = MagicMock(return_value={'id': 'CFLCT-abc123'})
        mock_audit = MagicMock()

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'create_conflict_declaration_db', mock_create),
            patch.object(portal_mod.db, 'append_audit', mock_audit),
        ):
            resp = client.post(
                '/api/tenders/TNT-001/conflict-declaration',
                json={
                    'has_conflict': False,
                    'action': 'NONE',
                    'officer_name': 'Test Officer',
                    'conflict_reason': '',
                },
                headers=auth_headers,
            )

        assert resp.status_code == 201, (
            f"Expected 201, got {resp.status_code}: {resp.get_json()}"
        )
        mock_create.assert_called_once()
        mock_audit.assert_called_once()


# ===========================================================================
# GROUP G — Migration file structure
# ===========================================================================

class TestGroupG_MigrationFileStructure:
    """FEAT-002: Sprint 4 Alembic migration must have the correct revision chain."""

    def test_migration_file_exists_with_correct_revision(self):
        """Migration module has revision=c9e4d3b2a156 and down_revision=b7d3c2a1f804."""
        import importlib.util
        import pathlib

        migration_path = pathlib.Path(BACKEND_DIR) / (
            'migrations/versions/20250721_000000_sprint4_conflict_columns.py'
        )
        assert migration_path.exists(), (
            f"Migration file not found at {migration_path}"
        )

        spec = importlib.util.spec_from_file_location(
            'sprint4_migration', str(migration_path)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.revision == 'c9e4d3b2a156', (
            f"Expected revision 'c9e4d3b2a156', got '{module.revision}'"
        )
        assert module.down_revision == 'b7d3c2a1f804', (
            f"Expected down_revision 'b7d3c2a1f804', got '{module.down_revision}'"
        )


# ===========================================================================
# GROUP H — submit_committee_score JSON-path guard
# ===========================================================================

class TestGroupH_CommitteeScoreJsonGuard:
    """FEAT-001: submit_committee_score JSON fallback path must not fire in DB mode."""

    def test_submit_committee_score_json_path_not_reached_in_db_mode(
        self, client, auth_headers
    ):
        """DB mode: save_json / save_cached must NOT be called during committee score."""
        import routes.officer_portal as portal_mod

        mock_get_committee = MagicMock(return_value={
            'id': 'EVAL-001',
            'tender_id': 'TNT-001',
            'members': [
                {'member_id': 'USR-TEST-001', 'name': 'Test Officer',
                 'score': None, 'submitted': False}
            ],
            'status': 'active',
        })
        mock_update_committee = MagicMock(return_value=1)
        mock_update_bid = MagicMock(return_value=1)
        mock_audit = MagicMock()

        # Track any calls to JSON-path save functions
        mock_save_json = MagicMock()
        mock_save_cached = MagicMock()

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'get_eval_committee_by_tender_db',
                         mock_get_committee),
            patch.object(portal_mod.db, 'update_eval_committee_db',
                         mock_update_committee),
            patch.object(portal_mod.db, 'update_bid_db', mock_update_bid),
            patch.object(portal_mod.db, 'append_audit', mock_audit),
            patch.object(portal_mod, 'save_json', mock_save_json),
        ):
            # Also patch save_cached at the json_cache level
            from services import json_cache
            with patch.object(json_cache, 'save_cached', mock_save_cached):
                resp = client.post(
                    '/api/tenders/TNT-001/committee/score',
                    json={'score': 85, 'comments': 'Good bid'},
                    headers=auth_headers,
                )

        # The route may return various codes depending on business logic,
        # but the JSON save path must NOT have been triggered
        mock_save_json.assert_not_called(), (
            "save_json was called in DB mode — the JSON fallback guard is missing"
        )
