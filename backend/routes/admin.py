"""
Admin Routes - Veritas AI
Administrative endpoints for maintenance and cleanup tasks.
Dual-mode: PostgreSQL (USE_DATABASE=True) or JSON cache (USE_DATABASE=False).
"""
from flask import Blueprint, jsonify, request
from config import USE_DATABASE
from services.json_cache import load_cached, save_cached, invalidate_all
from routes.auth import require_role
import services.database as db

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/api/admin/delete-all-documents', methods=['POST'])
@require_role('OFFICER')
def delete_all_documents():
    """
    Delete ALL documents from storage.
    WARNING: This is irreversible! Requires {"confirm": true} in the request body.
    """
    data = request.get_json(silent=True) or {}
    if data.get('confirm') is not True:
        return jsonify({
            'error': 'This operation is destructive. Send {"confirm": true} to proceed.'
        }), 400

    try:
        from services.document_service import get_all_documents, delete_document as _delete_doc

        if USE_DATABASE:
            # ── DB mode ─────────────────────────────────────────────────
            count_before = 0
            # Delete every uploaded document via document_service (already dual-mode)
            for _d in get_all_documents():
                try:
                    if _delete_doc(_d['id'], None):
                        count_before += 1
                except Exception:
                    pass

            # Clear document_ids on all bidders in DB
            bidders = db.list_bidders_db()
            for bidder in bidders:
                db.update_bidder_db(bidder['id'], {'document_ids': []})

            invalidate_all()

            return jsonify({
                'success': True,
                'message': 'All documents deleted',
                'documents_deleted': count_before,
                'documents_remaining': 0
            }), 200

        else:
            # ── JSON mode ────────────────────────────────────────────────
            documents = load_cached('documents.json')
            count_before = len(documents)

            # Delete all documents (keep only demo seed docs without saved_path)
            remaining = [d for d in documents if not d.get('saved_path')]
            save_cached('documents.json', remaining)

            # Uploaded documents live in PostgreSQL (+ storage) - remove those too
            for _d in get_all_documents():
                try:
                    if _delete_doc(_d['id'], None):
                        count_before += 1
                except Exception:
                    pass

            # Update bidders to remove document references
            bidders = load_cached('bidders.json')
            for bidder in bidders:
                bidder['document_ids'] = []
            save_cached('bidders.json', bidders)

            invalidate_all()

            return jsonify({
                'success': True,
                'message': 'All documents deleted',
                'documents_deleted': count_before - len(remaining),
                'documents_remaining': len(remaining)
            }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Delete failed: {str(e)}'
        }), 500


@admin_bp.route('/api/admin/reset-all-compliance', methods=['POST'])
@require_role('OFFICER')
def reset_all_compliance():
    """
    FORCEFULLY reset ALL bidders to 0% compliance, regardless of documents.
    Use this to completely clear demo data.
    Requires {"confirm": true} in the request body.
    """
    data = request.get_json(silent=True) or {}
    if data.get('confirm') is not True:
        return jsonify({
            'error': 'This operation is destructive. Send {"confirm": true} to proceed.'
        }), 400

    try:
        results = {
            'json_reset': [],
            'compliance_cleared': [],
            'errors': []
        }

        if USE_DATABASE:
            # ── DB mode ─────────────────────────────────────────────────
            try:
                bidders = db.list_bidders_db()
                for bidder in bidders:
                    bidder_id = bidder.get('id')
                    old_score = bidder.get('compliance_score', 0)
                    db.update_bidder_db(bidder_id, {
                        'compliance_score': 0,
                        'risk_level': 'UNKNOWN',
                        'status': 'pending',
                        'analyzed_at': None,
                        'document_ids': [],
                    })
                    results['json_reset'].append({
                        'id': bidder_id,
                        'name': bidder.get('name'),
                        'old_score': old_score,
                        'new_score': 0
                    })

                # Clear all compliance results
                db.execute_query('DELETE FROM compliance_results')
                results['compliance_cleared'] = [b.get('id') for b in bidders]

            except Exception as e:
                results['errors'].append(f"DB reset error: {str(e)}")

        else:
            # ── JSON mode ────────────────────────────────────────────────
            try:
                bidders = load_cached('bidders.json')
                compliance = load_cached('compliance.json')

                for bidder in bidders:
                    bidder_id = bidder.get('id')
                    old_score = bidder.get('compliance_score', 0)

                    if old_score > 0 or bidder.get('status') != 'pending':
                        bidder['compliance_score'] = 0
                        bidder['risk_level'] = 'UNKNOWN'
                        bidder['status'] = 'pending'
                        bidder['analyzed_at'] = None
                        bidder['document_ids'] = []

                        results['json_reset'].append({
                            'id': bidder_id,
                            'name': bidder.get('name'),
                            'old_score': old_score,
                            'new_score': 0
                        })

                # Clear ALL compliance analysis
                cleared_ids = list(compliance.keys())
                compliance.clear()
                results['compliance_cleared'] = cleared_ids

                save_cached('bidders.json', bidders)
                save_cached('compliance.json', compliance)

            except Exception as e:
                results['errors'].append(f"JSON reset error: {str(e)}")

        # Clear all caches
        invalidate_all()

        return jsonify({
            'success': True,
            'message': 'ALL compliance data forcefully reset to 0%',
            'json_bidders_reset': len(results['json_reset']),
            'compliance_cleared': len(results['compliance_cleared']),
            'details': results
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Reset failed: {str(e)}'
        }), 500


@admin_bp.route('/api/admin/reset-demo-compliance', methods=['POST'])
@require_role('OFFICER')
def reset_demo_compliance():
    """
    Reset compliance scores to 0 for bidders with no uploaded documents.
    This cleans up demo data after deployment.
    """
    try:
        results = {
            'json_reset': [],
            'compliance_cleared': [],
            'errors': []
        }

        from services.document_service import get_all_documents
        documents = get_all_documents()

        # Count uploaded documents per bidder (dual-mode: get_all_documents is already dual-mode)
        docs_by_bidder = {}
        for doc in documents:
            if doc.get('saved_path'):
                bidder_id = doc.get('bidder_id')
                if bidder_id:
                    docs_by_bidder[bidder_id] = docs_by_bidder.get(bidder_id, 0) + 1

        if USE_DATABASE:
            # ── DB mode ─────────────────────────────────────────────────
            try:
                bidders = db.list_bidders_db()
                for bidder in bidders:
                    bidder_id = bidder.get('id')
                    doc_count = docs_by_bidder.get(bidder_id, 0)

                    if doc_count == 0:
                        old_score = bidder.get('compliance_score', 0)
                        db.update_bidder_db(bidder_id, {
                            'compliance_score': 0,
                            'risk_level': 'UNKNOWN',
                            'status': 'pending',
                            'analyzed_at': None,
                            'document_ids': [],
                        })
                        db.execute_query(
                            'DELETE FROM compliance_results WHERE bidder_id=%s',
                            (bidder_id,)
                        )
                        results['compliance_cleared'].append(bidder_id)
                        results['json_reset'].append({
                            'id': bidder_id,
                            'name': bidder.get('name'),
                            'old_score': old_score,
                            'new_score': 0
                        })

            except Exception as e:
                results['errors'].append(f"DB reset error: {str(e)}")

        else:
            # ── JSON mode ────────────────────────────────────────────────
            try:
                bidders = load_cached('bidders.json')
                compliance = load_cached('compliance.json')

                for bidder in bidders:
                    bidder_id = bidder.get('id')
                    doc_count = docs_by_bidder.get(bidder_id, 0)

                    if doc_count == 0:
                        old_score = bidder.get('compliance_score', 0)
                        bidder['compliance_score'] = 0
                        bidder['risk_level'] = 'UNKNOWN'
                        bidder['status'] = 'pending'
                        bidder['analyzed_at'] = None
                        bidder['document_ids'] = []

                        # Clear compliance analysis results
                        if bidder_id in compliance:
                            del compliance[bidder_id]
                            results['compliance_cleared'].append(bidder_id)

                        results['json_reset'].append({
                            'id': bidder_id,
                            'name': bidder.get('name'),
                            'old_score': old_score,
                            'new_score': 0
                        })

                if results['json_reset'] or results['compliance_cleared']:
                    save_cached('bidders.json', bidders)
                    save_cached('compliance.json', compliance)

            except Exception as e:
                results['errors'].append(f"JSON reset error: {str(e)}")

        # ── Return results ───────────────────────────────────────
        return jsonify({
            'success': True,
            'message': 'Demo compliance data reset completed',
            'json_bidders_reset': len(results['json_reset']),
            'compliance_cleared': len(results['compliance_cleared']),
            'details': results,
            'note': 'Bidders with no uploaded documents now show 0% compliance'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Reset failed: {str(e)}'
        }), 500


@admin_bp.route('/api/admin/cleanup-old-reports', methods=['POST'])
@require_role('OFFICER')
def cleanup_old_reports():
    """
    Delete old generated HTML reports.
    Reports are regenerated on demand, so old ones can be safely removed.
    """
    try:
        import os
        from config import REPORTS_DIR

        deleted = []
        for filename in os.listdir(REPORTS_DIR):
            if filename.endswith('.html'):
                filepath = os.path.join(REPORTS_DIR, filename)
                os.remove(filepath)
                deleted.append(filename)

        return jsonify({
            'success': True,
            'message': f'Deleted {len(deleted)} old reports',
            'deleted_files': deleted
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Cleanup failed: {str(e)}'
        }), 500


@admin_bp.route('/api/admin/cleanup-expired-tokens', methods=['POST'])
@require_role('OFFICER')
def cleanup_expired_tokens():
    """
    Delete expired revoked tokens from the database.
    Only meaningful in database mode — no-op in JSON mode.
    """
    try:
        if USE_DATABASE:
            from services.database import cleanup_expired_revocations
            deleted = cleanup_expired_revocations()
            return jsonify({'success': True, 'deleted': deleted}), 200
        else:
            return jsonify({
                'success': True,
                'deleted': 0,
                'note': 'Token cleanup only applies in database mode'
            }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Cleanup failed: {str(e)}'
        }), 500


@admin_bp.route('/api/admin/status', methods=['GET'])
@require_role('OFFICER')
def admin_status():
    """
    Get administrative status and statistics.
    """
    try:
        if USE_DATABASE:
            bidders = db.list_bidders_db()
        else:
            bidders = load_cached('bidders.json')

        from services.document_service import get_all_documents
        documents = get_all_documents()

        # Count documents per bidder
        docs_by_bidder = {}
        uploaded_docs = [d for d in documents if d.get('saved_path')]
        for doc in uploaded_docs:
            bid = doc.get('bidder_id')
            if bid:
                docs_by_bidder[bid] = docs_by_bidder.get(bid, 0) + 1

        # Stats
        total_bidders = len(bidders)
        bidders_with_docs = len([b for b in bidders if docs_by_bidder.get(b['id'], 0) > 0])
        bidders_no_docs = total_bidders - bidders_with_docs

        bidders_with_scores = len([b for b in bidders if (b.get('compliance_score') or 0) > 0])
        bidders_pending = len([b for b in bidders if b.get('status') == 'pending'])

        return jsonify({
            'total_bidders': total_bidders,
            'bidders_with_documents': bidders_with_docs,
            'bidders_no_documents': bidders_no_docs,
            'bidders_with_scores': bidders_with_scores,
            'bidders_pending': bidders_pending,
            'total_uploaded_documents': len(uploaded_docs),
            'needs_reset': bidders_no_docs > 0 and bidders_with_scores > bidders_with_docs
        }), 200

    except Exception as e:
        return jsonify({
            'error': f'Status check failed: {str(e)}'
        }), 500
