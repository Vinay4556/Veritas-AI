"""
test_integration.py — Sprint 5 comprehensive integration tests.

Uses Flask test client (no live server needed) and mocks DB functions.

Coverage:
  1. All 4 originally-missing endpoints:
       - POST /api/bids/<id>/local-content/verify
       - POST /api/bids/<id>/oem/verify
       - POST /api/tenders/<id>/conflict-declaration
       - POST /api/rejection-feedback/<id>/send
     Verify: correct status code, auth enforcement, response shape
  2. Admin confirm guard: 400 without confirm=true, 200 with confirm=true (JSON mode)
  3. Officer summary dual-mode: _load_bidders returns DB data when USE_DATABASE=True
  4. Audit integrity: delete_bidder does not filter audit entries
  5. Plaintext password blocked in DB mode
  6. bcrypt password verified correctly
  7. Token revocation: logout then re-use returns 401
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure backend is importable
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ.setdefault('SECRET_KEY', 'test-integration-secret-key')


# ===========================================================================
# 1. THE FOUR ORIGINALLY-MISSING ENDPOINTS
# ===========================================================================

class TestMissingEndpoints:
    """Verify all 4 originally-missing endpoints exist, enforce auth, and
    return the expected response shape."""

    # ── 1a. POST /api/bids/<id>/local-content/verify ─────────────────────

    def test_local_content_verify_requires_auth(self, client):
        """Without a token the endpoint must return 401."""
        resp = client.post(
            '/api/bids/BID-001/local-content/verify',
            json={'verified_local_content_pct': 55, 'status': 'VERIFIED'},
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without auth, got {resp.status_code}"
        )

    def test_local_content_verify_success(self, client, auth_headers):
        """Authenticated POST returns 200 with status='verified' and a local_content key."""
        import routes.officer_portal as portal_mod

        fake_bid = {
            'id': 'BID-001',
            'tender_id': 'TNT-001',
            'bidder_id': 'BIDR-001',
            'local_content': {},
        }

        with (
            patch.object(portal_mod, 'USE_DATABASE', False),
            patch.object(portal_mod, 'load_json', return_value=[fake_bid]),
            patch.object(portal_mod, 'save_json', MagicMock()),
        ):
            resp = client.post(
                '/api/bids/BID-001/local-content/verify',
                json={
                    'declared_local_content_pct': 60,
                    'verified_local_content_pct': 55,
                    'class': 'Class I',
                    'status': 'VERIFIED',
                    'verified_by': 'Test Officer',
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.data}"
        )
        body = resp.get_json()
        assert body is not None
        assert body.get('status') == 'verified', (
            f"Response must contain status='verified', got: {body}"
        )
        assert 'local_content' in body, (
            f"Response must contain 'local_content' key, got: {body}"
        )

    def test_local_content_verify_db_mode(self, client, auth_headers):
        """DB mode: endpoint calls db.update_bid_db and returns 200."""
        import routes.officer_portal as portal_mod

        fake_bid = {'id': 'BID-001', 'local_content': {}}
        mock_update = MagicMock(return_value=fake_bid)
        mock_get = MagicMock(return_value=fake_bid)

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'get_bid_db', mock_get),
            patch.object(portal_mod.db, 'update_bid_db', mock_update),
        ):
            resp = client.post(
                '/api/bids/BID-001/local-content/verify',
                json={'verified_local_content_pct': 55, 'status': 'VERIFIED'},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        mock_update.assert_called_once()

    # ── 1b. POST /api/bids/<id>/oem/verify ───────────────────────────────

    def test_oem_verify_requires_auth(self, client):
        """Without a token the endpoint must return 401."""
        resp = client.post(
            '/api/bids/BID-001/oem/verify',
            json={'oem_name': 'ACME Corp', 'status': 'VERIFIED'},
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without auth, got {resp.status_code}"
        )

    def test_oem_verify_success(self, client, auth_headers):
        """Authenticated POST returns 200 with status='verified' and an oem key."""
        import routes.officer_portal as portal_mod

        fake_bid = {
            'id': 'BID-001',
            'tender_id': 'TNT-001',
            'bidder_id': 'BIDR-001',
            'oem': {},
        }

        with (
            patch.object(portal_mod, 'USE_DATABASE', False),
            patch.object(portal_mod, 'load_json', return_value=[fake_bid]),
            patch.object(portal_mod, 'save_json', MagicMock()),
        ):
            resp = client.post(
                '/api/bids/BID-001/oem/verify',
                json={
                    'oem_name': 'ACME Corp',
                    'status': 'VERIFIED',
                    'verified_by': 'Test Officer',
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.data}"
        )
        body = resp.get_json()
        assert body is not None
        assert body.get('status') == 'verified', (
            f"Response must contain status='verified', got: {body}"
        )
        assert 'oem' in body, (
            f"Response must contain 'oem' key, got: {body}"
        )

    def test_oem_verify_db_mode(self, client, auth_headers):
        """DB mode: endpoint calls db.update_bid_db and returns 200."""
        import routes.officer_portal as portal_mod

        fake_bid = {'id': 'BID-001', 'oem': {}}
        mock_update = MagicMock(return_value=fake_bid)
        mock_get = MagicMock(return_value=fake_bid)

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'get_bid_db', mock_get),
            patch.object(portal_mod.db, 'update_bid_db', mock_update),
        ):
            resp = client.post(
                '/api/bids/BID-001/oem/verify',
                json={'oem_name': 'ACME Corp', 'status': 'VERIFIED'},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        mock_update.assert_called_once()

    # ── 1c. POST /api/tenders/<id>/conflict-declaration ──────────────────

    def test_conflict_declaration_requires_auth(self, client):
        """Without a token the endpoint must return 401."""
        resp = client.post(
            '/api/tenders/TNT-001/conflict-declaration',
            json={'has_conflict': False},
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without auth, got {resp.status_code}"
        )

    def test_conflict_declaration_success(self, client, auth_headers):
        """Authenticated POST returns 201 with status='declared' and a declaration key."""
        import routes.officer_portal as portal_mod

        with (
            patch.object(portal_mod, 'USE_DATABASE', False),
            patch.object(portal_mod, 'load_json', return_value=[]),
            patch.object(portal_mod, 'save_json', MagicMock()),
        ):
            resp = client.post(
                '/api/tenders/TNT-001/conflict-declaration',
                json={
                    'has_conflict': False,
                    'action': 'NONE',
                    'officer_name': 'Test Officer',
                },
                headers=auth_headers,
            )

        assert resp.status_code == 201, (
            f"Expected 201, got {resp.status_code}: {resp.data}"
        )
        body = resp.get_json()
        assert body is not None
        assert body.get('status') == 'declared', (
            f"Response must contain status='declared', got: {body}"
        )
        assert 'declaration' in body, (
            f"Response must contain 'declaration' key, got: {body}"
        )

    def test_conflict_declaration_db_mode(self, client, auth_headers):
        """DB mode: endpoint calls db.create_conflict_declaration_db and appends audit."""
        import routes.officer_portal as portal_mod

        mock_create = MagicMock(return_value={'id': 'CFLCT-001'})
        mock_audit = MagicMock()

        with (
            patch.object(portal_mod, 'USE_DATABASE', True),
            patch.object(portal_mod.db, 'create_conflict_declaration_db', mock_create),
            patch.object(portal_mod.db, 'append_audit', mock_audit),
        ):
            resp = client.post(
                '/api/tenders/TNT-001/conflict-declaration',
                json={
                    'has_conflict': True,
                    'action': 'RECUSE',
                    'officer_name': 'Test Officer',
                    'conflict_reason': 'Family relationship',
                },
                headers=auth_headers,
            )

        assert resp.status_code == 201
        mock_create.assert_called_once()
        mock_audit.assert_called_once()

        # Verify db_record uses post-Sprint-4 column names
        call_kwargs = mock_create.call_args[0][0]
        assert 'officer_id' in call_kwargs, (
            f"db_record must use 'officer_id', not 'declared_by'. Got keys: {list(call_kwargs.keys())}"
        )
        assert 'declared_by' not in call_kwargs

    # ── 1d. POST /api/rejection-feedback/<id>/send ───────────────────────

    def test_rejection_feedback_send_requires_auth(self, client):
        """Without a token the endpoint must return 401."""
        resp = client.post(
            '/api/rejection-feedback/FB-001/send',
            json={'additional_feedback': 'Please resubmit.'},
        )
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without auth, got {resp.status_code}"
        )

    def test_rejection_feedback_send_success(self, client, auth_headers):
        """Authenticated POST returns 200 with status='sent'."""
        import routes.bidders as bidders_mod

        fake_fb = {
            'id': 'FB-001',
            'bidder_id': 'BIDR-001',
            'bidder_name': 'Test Bidder',
            'tender_id': 'TNT-001',
            'officer': 'Test Officer',
            'status': 'PENDING',
        }

        with (
            patch.object(bidders_mod, 'USE_DATABASE', False),
            patch.object(bidders_mod, 'load_cached',
                         return_value=[fake_fb]),
            patch.object(bidders_mod, 'save_cached', MagicMock()),
        ):
            resp = client.post(
                '/api/rejection-feedback/FB-001/send',
                json={'additional_feedback': 'Please improve your documentation.'},
                headers=auth_headers,
            )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.data}"
        )
        body = resp.get_json()
        assert body is not None
        assert body.get('status') == 'sent', (
            f"Response must contain status='sent', got: {body}"
        )

    def test_rejection_feedback_send_db_mode(self, client, auth_headers):
        """DB mode: endpoint calls db.update_rejection_feedback_db."""
        import routes.bidders as bidders_mod

        fake_fb = {
            'id': 'FB-001',
            'bidder_id': 'BIDR-001',
            'bidder_name': 'Test Bidder',
            'tender_id': 'TNT-001',
            'officer': 'Test Officer',
        }
        mock_update = MagicMock()
        mock_audit = MagicMock()

        with (
            patch.object(bidders_mod, 'USE_DATABASE', True),
            patch.object(bidders_mod.db, 'list_rejection_feedback_db',
                         return_value=[fake_fb]),
            patch.object(bidders_mod.db, 'update_rejection_feedback_db', mock_update),
            patch.object(bidders_mod.db, 'append_audit', mock_audit),
        ):
            resp = client.post(
                '/api/rejection-feedback/FB-001/send',
                json={'additional_feedback': 'Please improve.', 'officer': 'Test Officer'},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        mock_update.assert_called_once()


# ===========================================================================
# 2. ADMIN CONFIRM GUARD
# ===========================================================================

class TestAdminConfirmGuard:
    """Admin destructive operations require {"confirm": true}."""

    def test_delete_all_documents_400_without_confirm(self, client, auth_headers):
        """POST /api/admin/delete-all-documents without confirm -> 400."""
        resp = client.post(
            '/api/admin/delete-all-documents',
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400, (
            f"Expected 400 without confirm=true, got {resp.status_code}"
        )

    def test_delete_all_documents_400_with_confirm_false(self, client, auth_headers):
        """POST /api/admin/delete-all-documents with confirm=false -> 400."""
        resp = client.post(
            '/api/admin/delete-all-documents',
            json={'confirm': False},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_delete_all_documents_200_with_confirm_true(self, client, auth_headers):
        """POST /api/admin/delete-all-documents with confirm=true (JSON mode) -> 200."""
        import routes.admin as admin_mod

        with (
            patch.object(admin_mod, 'USE_DATABASE', False),
            patch.object(admin_mod, 'load_cached', return_value=[]),
            patch.object(admin_mod, 'save_cached', MagicMock()),
            patch.object(admin_mod, 'invalidate_all', MagicMock()),
            patch('services.document_service.get_all_documents', return_value=[]),
        ):
            resp = client.post(
                '/api/admin/delete-all-documents',
                json={'confirm': True},
                headers=auth_headers,
            )

        assert resp.status_code == 200, (
            f"Expected 200 with confirm=true, got {resp.status_code}: {resp.data}"
        )
        body = resp.get_json()
        assert body.get('success') is True

    def test_reset_all_compliance_400_without_confirm(self, client, auth_headers):
        """POST /api/admin/reset-all-compliance without confirm -> 400."""
        resp = client.post(
            '/api/admin/reset-all-compliance',
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_reset_all_compliance_200_with_confirm_true(self, client, auth_headers):
        """POST /api/admin/reset-all-compliance with confirm=true (JSON mode) -> 200."""
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
        body = resp.get_json()
        assert body.get('success') is True


# ===========================================================================
# 3. OFFICER SUMMARY DUAL-MODE
# ===========================================================================

class TestOfficerSummaryDualMode:
    """_load_bidders() returns DB data when USE_DATABASE=True."""

    def test_load_bidders_returns_db_data(self):
        """USE_DATABASE=True: _load_bidders uses db.list_bidders_db()."""
        import routes.officer_summary as summary_mod

        mock_bidders = [
            {'id': 'DB-BID-001', 'name': 'DB Bidder One', 'tender_id': 'TNT-001'},
            {'id': 'DB-BID-002', 'name': 'DB Bidder Two', 'tender_id': 'TNT-001'},
        ]
        mock_list_db = MagicMock(return_value=mock_bidders)

        with (
            patch.object(summary_mod, 'USE_DATABASE', True),
            patch.object(summary_mod.db, 'list_bidders_db', mock_list_db),
        ):
            result = summary_mod._load_bidders()

        mock_list_db.assert_called_once()
        assert result == mock_bidders, (
            f"_load_bidders in DB mode must return db.list_bidders_db() result"
        )

    def test_load_bidders_json_mode_does_not_call_db(self):
        """USE_DATABASE=False: _load_bidders reads from JSON cache, not DB."""
        import routes.officer_summary as summary_mod
        import services.json_cache as json_cache_mod

        mock_bidders = [{'id': 'JSON-BID-001', 'name': 'JSON Bidder'}]
        mock_list_db = MagicMock()

        with (
            patch.object(summary_mod, 'USE_DATABASE', False),
            # load_cached is imported inside the function body — patch it at its source
            patch.object(json_cache_mod, 'load_cached', return_value=mock_bidders),
            patch.object(summary_mod.db, 'list_bidders_db', mock_list_db),
        ):
            result = summary_mod._load_bidders()

        mock_list_db.assert_not_called()
        assert result == mock_bidders


# ===========================================================================
# 4. AUDIT INTEGRITY
# ===========================================================================

class TestAuditIntegrity:
    """delete_bidder must not silently filter out audit log entries."""

    def test_delete_bidder_json_mode_preserves_all_audit_entries(
        self, client, auth_headers
    ):
        """Audit entries for OTHER bidders must remain after deleting one bidder."""
        import routes.bidders as bidders_mod
        import services.document_service as doc_svc

        bidder_to_delete = {
            'id': 'BID-DEL', 'name': 'Delete Me', 'tender_id': 'TNT-001',
            'compliance_score': 0, 'status': 'pending',
        }
        other_bidder = {
            'id': 'BID-KEEP', 'name': 'Keep Me', 'tender_id': 'TNT-001',
            'compliance_score': 80, 'status': 'analyzed',
        }
        audit_entries = [
            {'id': 'AUD-001', 'actor': 'officer', 'action': 'ANALYZE',
             'bidder_id': 'BID-DEL', 'tender_id': 'TNT-001', 'timestamp': '2025-01-01T00:00:00'},
            {'id': 'AUD-002', 'actor': 'officer', 'action': 'APPROVE',
             'bidder_id': 'BID-KEEP', 'tender_id': 'TNT-001', 'timestamp': '2025-01-02T00:00:00'},
            {'id': 'AUD-003', 'actor': 'officer', 'action': 'ANALYZE',
             'bidder_id': 'BID-DEL', 'tender_id': 'TNT-001', 'timestamp': '2025-01-03T00:00:00'},
        ]

        saved = {}

        def fake_load_cached(name, default=None):
            if name == 'audit.json':
                return list(audit_entries)
            if name == 'compliance.json':
                return {}
            return default if default is not None else []

        def fake_save_cached(name, data):
            saved[name] = data

        with (
            patch.object(bidders_mod, 'USE_DATABASE', False),
            patch.object(bidders_mod, 'load_cached', side_effect=fake_load_cached),
            patch.object(bidders_mod, 'save_cached', side_effect=fake_save_cached),
            patch.object(bidders_mod, 'load_bidders',
                         return_value=[bidder_to_delete, other_bidder]),
            patch.object(doc_svc, 'load_documents', return_value=[]),
            patch.object(doc_svc, 'save_documents', MagicMock()),
        ):
            resp = client.delete(
                '/api/bidders/BID-DEL',
                json={'officer': 'Test Officer'},
                headers=auth_headers,
            )

        assert resp.status_code in (200, 204), (
            f"Expected 200/204 on delete, got {resp.status_code}: {resp.data}"
        )

        # Audit log must still contain the KEEP entry
        saved_audit = saved.get('audit.json', audit_entries)
        keep_entries = [e for e in saved_audit if e.get('bidder_id') == 'BID-KEEP']
        assert len(keep_entries) >= 1, (
            "Audit entries for BID-KEEP must not be deleted when BID-DEL is removed"
        )


# ===========================================================================
# 5. PLAINTEXT PASSWORD BLOCKED IN DB MODE
# ===========================================================================

class TestPlaintextPasswordBlock:
    """In DB mode the login path must reject plaintext-stored passwords."""

    def test_plaintext_password_blocked_in_db_mode(self):
        """_check_password with a plaintext (non-bcrypt) hash must return False in DB mode."""
        import routes.auth as auth_mod
        import config as config_mod

        # A plaintext-stored password (no $2b$ prefix, not 64-char hex)
        plaintext_stored = 'password123'
        user = {'password': plaintext_stored}

        with patch.object(config_mod, 'USE_DATABASE', True):
            result = auth_mod._check_password(user, 'password123')

        assert result is False, (
            "check_password must return False for plaintext passwords in DB mode"
        )

    def test_plaintext_password_allowed_in_local_mode(self):
        """_check_password with a plaintext (non-bcrypt) hash returns True in JSON mode."""
        import routes.auth as auth_mod
        import config as config_mod

        plaintext_stored = 'password123'
        user = {'password': plaintext_stored}

        with patch.object(config_mod, 'USE_DATABASE', False):
            result = auth_mod._check_password(user, 'password123')

        assert result is True, (
            "check_password must return True for matching plaintext passwords in local mode"
        )


# ===========================================================================
# 6. BCRYPT PASSWORD VERIFICATION
# ===========================================================================

class TestBcryptPasswordVerification:
    """bcrypt-hashed passwords must verify correctly via _check_password()."""

    def test_bcrypt_password_verifies_correctly(self):
        """A bcrypt hash of 'mypassword' must verify against 'mypassword'."""
        import bcrypt
        import routes.auth as auth_mod

        raw = 'mypassword'
        hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
        user = {'password_hash': hashed}

        result = auth_mod._check_password(user, raw)

        assert result is True, (
            f"bcrypt hash must verify correctly, got False for hash: {hashed[:20]}..."
        )

    def test_bcrypt_wrong_password_rejected(self):
        """A bcrypt hash must NOT verify against an incorrect password."""
        import bcrypt
        import routes.auth as auth_mod

        raw = 'mypassword'
        hashed = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()
        user = {'password_hash': hashed}

        result = auth_mod._check_password(user, 'wrongpassword')

        assert result is False, (
            "bcrypt hash must NOT verify against a wrong password"
        )


# ===========================================================================
# 7. TOKEN REVOCATION
# ===========================================================================

class TestTokenRevocation:
    """After logout, a previously valid token must return 401 on re-use."""

    def test_logout_then_reuse_returns_401(self, app):
        """Login, logout, then verify token re-use returns 401 (in-memory mode)."""
        import bcrypt
        import routes.auth as auth_mod
        import config as config_mod

        hashed = bcrypt.hashpw(b'testpass', bcrypt.gensalt()).decode()
        test_user = {
            'id': 'USR-REVOKE-TEST',
            'user_id': 'USR-REVOKE-TEST',
            'email': 'revoke@test.local',
            'name': 'Revoke Test',
            'role': 'OFFICER',
            'password_hash': hashed,
        }

        client = app.test_client()

        # Run in local (JSON) mode so we avoid DB calls for revocation storage.
        # auth.py imports get_user_by_email directly, so we must patch it
        # in the auth module's namespace, not in services.database.
        with (
            patch.object(config_mod, 'USE_DATABASE', False),
            patch.object(auth_mod, 'get_user_by_email', return_value=test_user),
            patch.object(auth_mod, 'get_user_by_id', return_value=test_user),
            patch.object(auth_mod, 'update_user', MagicMock()),
        ):
            # Step 1: Login to get a real token
            login_resp = client.post(
                '/api/auth/login',
                json={'email': 'revoke@test.local', 'password': 'testpass'},
            )
            assert login_resp.status_code == 200, (
                f"Login failed: {login_resp.status_code} {login_resp.data}"
            )
            token = login_resp.get_json().get('token')
            assert token, "Login must return a token"

            # Step 2: Verify token works
            me_resp = client.get(
                '/api/auth/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert me_resp.status_code == 200, (
                f"/auth/me returned {me_resp.status_code} with valid token"
            )

            # Step 3: Logout
            logout_resp = client.post(
                '/api/auth/logout',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert logout_resp.status_code == 200, (
                f"Logout failed: {logout_resp.status_code}"
            )

            # Step 4: Re-use the token — must get 401 (in-memory revocation)
            reuse_resp = client.get(
                '/api/auth/me',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert reuse_resp.status_code == 401, (
                f"Re-used token after logout must return 401, got {reuse_resp.status_code}"
            )
