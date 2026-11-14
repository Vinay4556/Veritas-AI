"""
Tenders Routes — Veritas AI
Full procurement lifecycle: tender creation, configuration, deadline management,
corrigendum, pre-bid, cancellation, re-tender.
"""
import json
import os
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from config import DATA_DIR, USE_DATABASE
from services.audit_utils import next_audit_id
from services.tender_service import (
    get_all_tenders, get_tender_by_id,
    get_requirements_for_tender, get_tender_summary
)
from routes.auth import require_role, get_session
import services.database as db
from services.classification_service import classify_tender, CLASSIFICATION_LABELS, CLASSIFICATIONS

tenders_bp = Blueprint('tenders', __name__)


# All persistence goes through the JSON file store (see services/json_cache.py)
from services.json_cache import load_cached as load_json, save_cached as save_json  # noqa: E402


def _audit(action, detail, tender_id=None, bidder_id=None, actor='Procurement Officer', severity='info'):
    if USE_DATABASE:
        try:
            db.append_audit({
                'action': action,
                'detail': detail,
                'tender_id': tender_id,
                'bidder_id': bidder_id,
                'actor': actor,
                'severity': severity,
                'timestamp': datetime.now(),
                'created_at': datetime.now(),
            })
            return
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error('DB audit write failed: %s', exc)
            raise
    audit = load_json('audit.json')
    audit.append({
        'id': next_audit_id(audit),
        'timestamp': datetime.now().isoformat(),
        'actor': actor,
        'action': action,
        'detail': detail,
        'tender_id': tender_id,
        'bidder_id': bidder_id,
        'severity': severity,
    })
    save_json('audit.json', audit)


def _format_estimated_value(value):
    """Format estimated value, accepting int, float, or numeric string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _format_estimated_value_display(value):
    """Format estimated value as ₹ string for display."""
    if value is None:
        return ''
    try:
        v = float(value)
        if v < 0:
            return ''
        return f'₹{v:,.2f}'
    except (ValueError, TypeError):
        return ''


# ── List / Get Tenders ────────────────────────────────────────
@tenders_bp.route('/api/tenders', methods=['GET'])
def list_tenders():
    if USE_DATABASE:
        filters = {}
        if request.args.get('status'):
            filters['status'] = request.args.get('status')
        records = db.list_tenders_db(filters or None)
        result = []
        for t in records:
            t_dict = dict(t)
            result.append(t_dict)
        return jsonify(result)
    tenders = get_all_tenders()

    # Optional query filters
    filter_classification = request.args.get('classification', '').strip()
    filter_procurement_type = request.args.get('procurement_type', '').strip()
    filter_search = request.args.get('search', '').strip().lower()
    filter_status = request.args.get('status', '').strip()

    summaries = []
    for t in tenders:
        # Apply status filter
        if filter_status and str(t.get('status', '')).lower() != filter_status.lower():
            continue
        # Apply classification filter
        if filter_classification and t.get('classification') != filter_classification:
            continue
        # Apply procurement_type filter
        if filter_procurement_type and str(t.get('procurement_type', '')).lower() != filter_procurement_type.lower():
            continue
        # Apply keyword search on title and department
        if filter_search:
            searchable = (str(t.get('title', '')) + ' ' + str(t.get('department', ''))).lower()
            if filter_search not in searchable:
                continue
        summary = get_tender_summary(t['id'])
        if summary:
            summaries.append(summary)
    return jsonify(summaries)


@tenders_bp.route('/api/tenders/<tender_id>', methods=['GET'])
def get_tender(tender_id):
    if USE_DATABASE:
        record = db.get_tender_db(tender_id)
        if not record:
            return jsonify({'error': 'Tender not found'}), 404
        return jsonify(record)
    summary = get_tender_summary(tender_id)
    if not summary:
        return jsonify({'error': 'Tender not found'}), 404
    return jsonify(summary)


@tenders_bp.route('/api/tenders/<tender_id>/requirements', methods=['GET'])
def get_requirements(tender_id):
    if USE_DATABASE:
        reqs = db.list_requirements_db(tender_id)
        return jsonify(reqs or [])
    reqs = get_requirements_for_tender(tender_id)
    return jsonify(reqs or [])


# ── Classification Lookup ─────────────────────────────────────
@tenders_bp.route('/api/tenders/classifications', methods=['GET'])
def get_classifications():
    """Returns subject-based classification keys, labels and counts.
    Only returns classifications that have at least 1 tender.
    Response format:
    {
      "classifications": [
        {"key": "INDUSTRIAL_IOT", "label": "Industrial IoT & Monitoring Equipment", "count": 1},
        ...
      ],
      "total": 16
    }
    """
    tenders = load_json('tenders.json')
    counts = {}
    for t in tenders:
        c = t.get('classification')
        if c:
            counts[c] = counts.get(c, 0) + 1
    result = []
    for key, label in CLASSIFICATION_LABELS.items():
        count = counts.get(key, 0)
        if count > 0:
            result.append({'key': key, 'label': label, 'count': count})
    result.sort(key=lambda x: x['count'], reverse=True)
    return jsonify({'classifications': result, 'total': len(tenders)})


@tenders_bp.route('/api/tenders/<tender_id>/classify', methods=['POST'])
@require_role('OFFICER')
def manual_classify(tender_id):
    """Officer manually overrides the classification of a tender."""
    data = request.get_json() or {}
    classification = data.get('classification', '').strip()
    if classification not in CLASSIFICATIONS:
        return jsonify({'error': f'Invalid classification. Must be one of: {CLASSIFICATIONS}'}), 400
    tenders = load_json('tenders.json')
    tender = next((t for t in tenders if t['id'] == tender_id), None)
    if not tender:
        return jsonify({'error': 'Tender not found'}), 404
    old_classification = tender.get('classification', 'NONE')
    for t in tenders:
        if t['id'] == tender_id:
            t['classification'] = classification
            t['secondary_classification'] = data.get('secondary_classification')
            t['procurement_type'] = data.get('procurement_type', t.get('procurement_type'))
            t['classification_confidence'] = 1.0
            t['classification_reason'] = data.get('reason', 'Manual classification by officer')
            t['classification_source'] = 'manual'
            t['classification_review_required'] = False
    save_json('tenders.json', tenders)
    session = get_session(request)
    actor = session.get('name', 'Officer') if session else 'Officer'
    _audit('CLASSIFICATION_UPDATED',
           f'Tender {tender_id} classification changed from {old_classification} to {classification}',
           tender_id=tender_id, actor=actor, severity='info')
    updated = next((t for t in tenders if t['id'] == tender_id), None)
    return jsonify(updated)


# ── Create Tender — with full configuration engine ────────────
@tenders_bp.route('/api/tenders', methods=['POST'])
@require_role('OFFICER')
def create_tender():
    data = request.get_json() or {}
    required_fields = ['title', 'department', 'estimated_value', 'submission_deadline', 'category']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    year = datetime.now().year
    tender_id = f"TND-{year}-{str(uuid.uuid4())[:6].upper()}"

    # ── Policy / Evaluation Configuration ──────────────────────
    policy = {
        'procurement_method':         data.get('procurement_method', 'L1'),
        'bid_type':                    data.get('bid_type', 'TWO_ENVELOPE'),
        'tender_type':                 data.get('tender_type', 'GOODS'),
        'technical_weight':            data.get('technical_weight', 70),
        'financial_weight':            data.get('financial_weight', 30),
        'min_technical_score':         data.get('min_technical_score', 60),
        'reverse_auction_applicable':  data.get('reverse_auction_applicable', False),
        'emd_applicable':              data.get('emd_applicable', True),
        'mse_preference_applicable':   data.get('mse_preference_applicable', False),
        'startup_preference_applicable': data.get('startup_preference_applicable', False),
        'make_in_india_applicable':    data.get('make_in_india_applicable', True),
        'oem_authorization_mandatory': data.get('oem_authorization_mandatory', False),
        'consortium_allowed':          data.get('consortium_allowed', False),
        'price_preference_pct':        data.get('price_preference_pct', 0),
        'local_content_threshold':     data.get('local_content_threshold', 50),
    }

    tender = {
        'id': tender_id,
        'title': data['title'],
        'department': data['department'],
        'organisation': data.get('organisation', 'CPCL'),
        'estimated_value': _format_estimated_value(data.get('estimated_value')),
        'estimated_value_display': data.get('estimated_value_display') or _format_estimated_value_display(data.get('estimated_value')),
        'submission_deadline': data['submission_deadline'],
        'original_submission_deadline': data['submission_deadline'],
        'deadline_extensions': [],
        'opening_date': data.get('opening_date'),
        'prebid_date': data.get('prebid_date'),
        'prebid_meeting': None,
        'category': data['category'],
        'location': data.get('location', ''),
        'description': data.get('description', ''),
        'status': data.get('status', 'OPEN'),
        'workflow_stage': 'TENDER_PUBLISHED',
        'cancelled': False,
        'cancellation_reason': None,
        'cancelled_at': None,
        'parent_tender_id': data.get('parent_tender_id'),
        'emd_amount': data.get('emd_amount', 0),
        'emd_amount_display': data.get('emd_amount_display', ''),
        'performance_security_pct': data.get('performance_security_pct', 5),
        'created_by': data.get('created_by', 'Procurement Officer'),
        'created_at': datetime.now().isoformat(),
        'requirement_ids': [],
        'bidder_ids': [],
        'policy': policy,
        'corrigenda': [],
        'prebid_questions': [],
    }

    requirements = data.get('requirements', [])

    if USE_DATABASE:
        db.create_tender_db(tender)
        for i, req in enumerate(requirements):
            req_id = f"REQ-{tender_id}-{i+1:03d}"
            req_data = {
                'id': req_id,
                'tender_id': tender_id,
                'title': req.get('title', ''),
                'description': req.get('description', ''),
                'category': req.get('category', 'Technical'),
                'mandatory': req.get('mandatory', True),
                'required_evidence': req.get('required_evidence', []),
                'verification_type': req.get('verification_type', 'document_presence'),
                'threshold': req.get('threshold'),
                'threshold_display': req.get('threshold_display', ''),
                'unit': req.get('unit'),
            }
            db.create_requirement_db(req_data)
            tender['requirement_ids'].append(req_id)
        # Update tender with requirement_ids
        db.update_tender_db(tender_id, {'requirement_ids': tender['requirement_ids']})
        _audit('TENDER_CREATED', f"Tender '{data['title']}' (ID: {tender_id}) created.",
               tender_id=tender_id, actor=data.get('created_by', 'Procurement Officer'))
        return jsonify(tender), 201

    # JSON path
    tenders = load_json('tenders.json')
    req_list = load_json('requirements.json')
    for i, req in enumerate(requirements):
        req_id = f"REQ-{tender_id}-{i+1:03d}"
        req_list.append({
            'id': req_id,
            'tender_id': tender_id,
            'title': req.get('title', ''),
            'description': req.get('description', ''),
            'category': req.get('category', 'Technical'),
            'mandatory': req.get('mandatory', True),
            'required_evidence': req.get('required_evidence', []),
            'verification_type': req.get('verification_type', 'document_presence'),
            'threshold': req.get('threshold'),
            'threshold_display': req.get('threshold_display', ''),
            'unit': req.get('unit'),
        })
        tender['requirement_ids'].append(req_id)
    save_json('requirements.json', req_list)

    tenders.append(tender)
    save_json('tenders.json', tenders)

    _audit('TENDER_CREATED', f"Tender '{data['title']}' (ID: {tender_id}) created.",
           tender_id=tender_id, actor=data.get('created_by', 'Procurement Officer'))

    return jsonify(tender), 201


# ── Extend Deadline ───────────────────────────────────────────
@tenders_bp.route('/api/tenders/<tender_id>/extend', methods=['POST'])
@require_role('OFFICER')
def extend_deadline(tender_id):
    """Extend tender submission deadline. All prior extensions are preserved."""
    data = request.get_json() or {}
    new_deadline = data.get('new_deadline', '').strip()
    reason = data.get('reason', '').strip()
    authority = data.get('authority', 'Procurement Officer')

    if not new_deadline:
        return jsonify({'error': 'new_deadline is required (YYYY-MM-DD)'}), 400
    if not reason:
        return jsonify({'error': 'Extension reason is required'}), 400

    try:
        nd = datetime.strptime(new_deadline[:10], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    if nd <= datetime.now().date():
        return jsonify({'error': 'New deadline must be in the future'}), 400

    if USE_DATABASE:
        tender = db.get_tender_db(tender_id)
        if not tender:
            return jsonify({'error': 'Tender not found'}), 404
        if tender.get('cancelled'):
            return jsonify({'error': 'Cannot extend a cancelled tender'}), 400
        old_deadline = tender.get('submission_deadline', '')
        extensions = tender.get('deadline_extensions') or []
        extension_record = {
            'extension_number': len(extensions) + 1,
            'old_deadline': str(old_deadline) if old_deadline else '',
            'new_deadline': new_deadline,
            'reason': reason,
            'authority': authority,
            'extended_at': datetime.now().isoformat(),
        }
        extensions.append(extension_record)
        db.update_tender_db(tender_id, {
            'submission_deadline': new_deadline,
            'deadline_extensions': extensions,
        })
        _audit('DEADLINE_EXTENDED',
               f'Deadline extended: {old_deadline} → {new_deadline}. Reason: {reason}',
               tender_id=tender_id, actor=authority, severity='warning')
        return jsonify({'status': 'extended', 'new_deadline': new_deadline, 'extension': extension_record}), 200

    tenders = load_json('tenders.json')
    tender = next((t for t in tenders if t['id'] == tender_id), None)
    if not tender:
        return jsonify({'error': 'Tender not found'}), 404
    if tender.get('cancelled'):
        return jsonify({'error': 'Cannot extend a cancelled tender'}), 400
    old_deadline = tender.get('submission_deadline', '')
    extension_record = {
        'extension_number': len(tender.get('deadline_extensions', [])) + 1,
        'old_deadline': old_deadline,
        'new_deadline': new_deadline,
        'reason': reason,
        'authority': authority,
        'extended_at': datetime.now().isoformat(),
    }
    for t in tenders:
        if t['id'] == tender_id:
            t['submission_deadline'] = new_deadline
            if 'deadline_extensions' not in t:
                t['deadline_extensions'] = []
            t['deadline_extensions'].append(extension_record)
    save_json('tenders.json', tenders)
    _audit('DEADLINE_EXTENDED',
           f'Deadline extended: {old_deadline} → {new_deadline}. Reason: {reason}',
           tender_id=tender_id, actor=authority, severity='warning')
    return jsonify({'status': 'extended', 'new_deadline': new_deadline, 'extension': extension_record}), 200


# ── Cancel Tender ─────────────────────────────────────────────
@tenders_bp.route('/api/tenders/<tender_id>/cancel', methods=['POST'])
@require_role('OFFICER')
def cancel_tender(tender_id):
    data = request.get_json() or {}
    reason = data.get('reason', '').strip()
    authority = data.get('authority', 'Procurement Officer')

    if not reason:
        return jsonify({'error': 'Cancellation reason is required'}), 400

    if USE_DATABASE:
        tender = db.get_tender_db(tender_id)
        if not tender:
            return jsonify({'error': 'Tender not found'}), 404
        if tender.get('cancelled'):
            return jsonify({'error': 'Tender already cancelled'}), 400
        db.update_tender_db(tender_id, {
            'cancelled': True,
            'status': 'CANCELLED',
            'cancellation_reason': reason,
            'cancelled_by': authority,
            'cancelled_at': datetime.now(),
        })
        # Cancel all open bids
        bids = db.list_bids_db({'tender_id': tender_id})
        for b in bids:
            if b.get('status') not in ('AWARDED', 'WITHDRAWN'):
                db.update_bid_db(b['id'], {'status': 'CANCELLED', 'last_updated': datetime.now()})
        _audit('TENDER_CANCELLED',
               f'Tender {tender_id} cancelled by {authority}. Reason: {reason}',
               tender_id=tender_id, actor=authority, severity='error')
        return jsonify({'status': 'cancelled', 'tender_id': tender_id, 'reason': reason})

    tenders = load_json('tenders.json')
    tender = next((t for t in tenders if t['id'] == tender_id), None)
    if not tender:
        return jsonify({'error': 'Tender not found'}), 404
    if tender.get('cancelled'):
        return jsonify({'error': 'Tender already cancelled'}), 400

    for t in tenders:
        if t['id'] == tender_id:
            t['cancelled'] = True
            t['status'] = 'CANCELLED'
            t['cancellation_reason'] = reason
            t['cancelled_by'] = authority
            t['cancelled_at'] = datetime.now().isoformat()

    save_json('tenders.json', tenders)

    # Lock all bids for this tender
    bids = load_json('bids.json')
    for b in bids:
        if b.get('tender_id') == tender_id and b.get('status') not in ('AWARDED', 'WITHDRAWN'):
            b['status'] = 'CANCELLED'
            b['last_updated'] = datetime.now().isoformat()
    save_json('bids.json', bids)

    _audit('TENDER_CANCELLED',
           f'Tender {tender_id} cancelled by {authority}. Reason: {reason}',
           tender_id=tender_id, actor=authority, severity='error')

    return jsonify({'status': 'cancelled', 'tender_id': tender_id, 'reason': reason})


# ── Re-Tender (links to parent) ───────────────────────────────
@tenders_bp.route('/api/tenders/<tender_id>/re-tender', methods=['POST'])
@require_role('OFFICER')
def re_tender(tender_id):
    """Create a new tender linked to a cancelled/failed parent."""
    data = request.get_json() or {}

    if not isinstance(data, dict):
        return jsonify({'error': 'Invalid request body'}), 400

    submission_deadline = data.get('submission_deadline')
    if not submission_deadline:
        return jsonify({'error': 'submission_deadline is required'}), 400

    if USE_DATABASE:
        parent = db.get_tender_db(tender_id)
    else:
        parent = get_tender_by_id(tender_id)

    if not parent:
        return jsonify({'error': 'Parent tender not found'}), 404

    year = datetime.now().year
    new_tender_id = f"TND-{year}-{str(uuid.uuid4())[:6].upper()}"
    new_tender = {
        **parent,
        'id': new_tender_id,
        'status': 'OPEN',
        'cancelled': False,
        'cancellation_reason': None,
        'cancelled_at': None,
        'submission_deadline': data['submission_deadline'],
        'original_submission_deadline': data['submission_deadline'],
        'deadline_extensions': [],
        'parent_tender_id': tender_id,
        'created_at': datetime.now().isoformat(),
        'created_by': data.get('created_by', 'Procurement Officer'),
        'bidder_ids': [],
        'corrigenda': [],
        'prebid_questions': [],
        'requirement_ids': parent.get('requirement_ids') or [],
        # Reset stale workflow fields from parent tender
        'workflow_stage': 'TENDER_PUBLISHED',
        'officer_decision': None,
        'analyzed_at': None,
        'ai_recommendation': None,
        'scoring_summary': None,
    }
    if data.get('title'):
        new_tender['title'] = data['title']
    if data.get('estimated_value'):
        new_tender['estimated_value'] = data['estimated_value']

    if USE_DATABASE:
        db.create_tender_db(new_tender)
    else:
        tenders = load_json('tenders.json')
        tenders.append(new_tender)
        save_json('tenders.json', tenders)

    _audit('RE_TENDER_CREATED',
           f'Re-tender {new_tender_id} created from cancelled tender {tender_id}.',
           tender_id=new_tender_id, actor=data.get('created_by', 'Procurement Officer'))

    return jsonify({'status': 'created', 'new_tender_id': new_tender_id, 'tender': new_tender}), 201


# ── Corrigendum — upgraded ────────────────────────────────────
@tenders_bp.route('/api/tenders/<tender_id>/corrigendum', methods=['POST'])
@require_role('OFFICER')
def issue_corrigendum(tender_id):
    """Issue a corrigendum. Supports field-level changes with old/new versioning."""
    data = request.get_json() or {}
    description = data.get('description', '').strip()
    if not description:
        return jsonify({'error': 'Corrigendum description is required'}), 400

    if USE_DATABASE:
        tender = db.get_tender_db(tender_id)
    else:
        tenders = load_json('tenders.json')
        tender = next((t for t in tenders if t['id'] == tender_id), None)

    if not tender:
        return jsonify({'error': 'Tender not found'}), 404
    if tender.get('cancelled'):
        return jsonify({'error': 'Cannot issue corrigendum for cancelled tender'}), 400

    changes = data.get('changes', [])
    corrigendum = {
        'number': len(tender.get('corrigenda') or []) + 1,
        'description': description,
        'changes': changes,
        'issued_by': data.get('issued_by', 'Procurement Officer'),
        'issued_at': datetime.now().isoformat(),
        'affects_deadline': data.get('affects_deadline', False),
        'new_deadline': data.get('new_deadline'),
        'acknowledged_by': [],
    }

    updates = {}
    corrigenda = list(tender.get('corrigenda') or [])
    corrigenda.append(corrigendum)
    updates['corrigenda'] = corrigenda

    if data.get('affects_deadline') and data.get('new_deadline'):
        updates['submission_deadline'] = data['new_deadline']

    if USE_DATABASE:
        # Apply requirement changes
        if changes:
            for change in changes:
                req_id = change.get('affected_requirement')
                field = change.get('field')
                new_val = change.get('new_value')
                if req_id and field and new_val is not None:
                    db.update_requirement_db(req_id, {field: new_val})
        db.update_tender_db(tender_id, updates)
    else:
        if changes:
            req_list = load_json('requirements.json')
            for change in changes:
                req_id = change.get('affected_requirement')
                field = change.get('field')
                new_val = change.get('new_value')
                if req_id and field and new_val is not None:
                    for r in req_list:
                        if r['id'] == req_id:
                            r[f'_v{corrigendum["number"]}_{field}'] = change.get('old_value')
                            r[field] = new_val
            save_json('requirements.json', req_list)

        for t in tenders:
            if t['id'] == tender_id:
                for k, v in updates.items():
                    t[k] = v
        save_json('tenders.json', tenders)

    _audit(f'CORRIGENDUM_ISSUED',
           f"Corrigendum #{corrigendum['number']} for {tender_id}: {description[:120]}",
           tender_id=tender_id, actor=data.get('issued_by', 'Procurement Officer'),
           severity='warning')

    return jsonify({'status': 'published', 'corrigendum': corrigendum}), 201


# ── Corrigendum Acknowledge (bidder) ──────────────────────────
@tenders_bp.route('/api/tenders/<tender_id>/corrigendum/<int:corrigendum_number>/acknowledge', methods=['POST'])
def acknowledge_corrigendum(tender_id, corrigendum_number):
    """Bidder acknowledges a corrigendum."""
    session = get_session(request)
    bidder_id = (session or {}).get('organization_id') or (request.get_json() or {}).get('bidder_id')

    if USE_DATABASE:
        tender = db.get_tender_db(tender_id)
        if not tender:
            return jsonify({'error': 'Tender not found'}), 404
        corrigenda = list(tender.get('corrigenda') or [])
        for c in corrigenda:
            if c.get('number') == corrigendum_number:
                ack = c.get('acknowledged_by') or []
                if bidder_id and bidder_id not in ack:
                    ack.append(bidder_id)
                    c['acknowledged_by'] = ack
        db.update_tender_db(tender_id, {'corrigenda': corrigenda})
        return jsonify({'status': 'acknowledged', 'corrigendum_number': corrigendum_number})

    tenders = load_json('tenders.json')
    tender = next((t for t in tenders if t['id'] == tender_id), None)
    if not tender:
        return jsonify({'error': 'Tender not found'}), 404

    for t in tenders:
        if t['id'] == tender_id:
            for c in t.get('corrigenda', []):
                if c['number'] == corrigendum_number:
                    if bidder_id and bidder_id not in c.get('acknowledged_by', []):
                        c.setdefault('acknowledged_by', []).append(bidder_id)
    save_json('tenders.json', tenders)
    return jsonify({'status': 'acknowledged', 'corrigendum_number': corrigendum_number})


# ── Pre-Bid Meeting ───────────────────────────────────────────
@tenders_bp.route('/api/tenders/<tender_id>/prebid', methods=['GET'])
def get_prebid(tender_id):
    if USE_DATABASE:
        tender = db.get_tender_db(tender_id)
    else:
        tender = get_tender_by_id(tender_id)
    if not tender:
        return jsonify({'error': 'Tender not found'}), 404
    meeting = tender.get('prebid_meeting') or {}
    questions = tender.get('prebid_questions') or []
    public_questions = [q for q in questions if q.get('published', False)]
    return jsonify({
        'meeting': meeting,
        'questions': questions,
        'public_questions': public_questions,
        'question_count': len(questions),
    })


@tenders_bp.route('/api/tenders/<tender_id>/prebid/schedule', methods=['POST'])
@require_role('OFFICER')
def schedule_prebid(tender_id):
    """Schedule or update a pre-bid meeting."""
    data = request.get_json() or {}

    if USE_DATABASE:
        tender = db.get_tender_db(tender_id)
        if not tender:
            return jsonify({'error': 'Tender not found'}), 404
        meeting = {
            'date': data.get('date'),
            'time': data.get('time', '11:00'),
            'mode': data.get('mode', 'ONLINE'),
            'location': data.get('location', ''),
            'meeting_link': data.get('meeting_link', ''),
            'agenda': data.get('agenda', ''),
            'scheduled_by': data.get('scheduled_by', 'Procurement Officer'),
            'scheduled_at': datetime.now().isoformat(),
            'status': 'SCHEDULED',
        }
        db.update_tender_db(tender_id, {
            'prebid_meeting': meeting,
            'prebid_date': data.get('date'),
        })
        _audit('PRE_BID_SCHEDULED',
               f"Pre-bid meeting scheduled for {data.get('date')} ({data.get('mode', 'ONLINE')}).",
               tender_id=tender_id, actor=data.get('scheduled_by', 'Procurement Officer'))
        return jsonify({'status': 'scheduled', 'meeting': meeting})

    tenders = load_json('tenders.json')
    tender = next((t for t in tenders if t['id'] == tender_id), None)
    if not tender:
        return jsonify({'error': 'Tender not found'}), 404
    meeting = {
        'date': data.get('date'),
        'time': data.get('time', '11:00'),
        'mode': data.get('mode', 'ONLINE'),
        'location': data.get('location', ''),
        'meeting_link': data.get('meeting_link', ''),
        'agenda': data.get('agenda', ''),
        'scheduled_by': data.get('scheduled_by', 'Procurement Officer'),
        'scheduled_at': datetime.now().isoformat(),
        'status': 'SCHEDULED',
    }
    for t in tenders:
        if t['id'] == tender_id:
            t['prebid_meeting'] = meeting
            t['prebid_date'] = data.get('date')
    save_json('tenders.json', tenders)
    _audit('PRE_BID_SCHEDULED',
           f"Pre-bid meeting scheduled for {data.get('date')} ({data.get('mode', 'ONLINE')}).",
           tender_id=tender_id, actor=data.get('scheduled_by', 'Procurement Officer'))
    return jsonify({'status': 'scheduled', 'meeting': meeting})


@tenders_bp.route('/api/tenders/<tender_id>/prebid/questions', methods=['POST'])
def submit_prebid_question(tender_id):
    """Bidder submits a pre-bid question."""
    data = request.get_json() or {}
    session = get_session(request)
    bidder_id = (session or {}).get('organization_id') or data.get('bidder_id', 'ANON')

    question_text = data.get('question', '').strip()
    if not question_text:
        return jsonify({'error': 'Question text is required'}), 400

    q = {
        'id': f'PBQ-{str(uuid.uuid4())[:6].upper()}',
        'bidder_id': bidder_id,
        'question': question_text,
        'category': data.get('category', 'General'),
        'submitted_at': datetime.now().isoformat(),
        'answer': None,
        'answered_at': None,
        'answered_by': None,
        'published': False,
        'status': 'PENDING',
    }

    if USE_DATABASE:
        tender = db.get_tender_db(tender_id)
        if not tender:
            return jsonify({'error': 'Tender not found'}), 404
        questions = list(tender.get('prebid_questions') or [])
        questions.append(q)
        db.update_tender_db(tender_id, {'prebid_questions': questions})
        return jsonify({'status': 'submitted', 'question_id': q['id'], 'question': q}), 201

    tenders = load_json('tenders.json')
    tender = next((t for t in tenders if t['id'] == tender_id), None)
    if not tender:
        return jsonify({'error': 'Tender not found'}), 404
    for t in tenders:
        if t['id'] == tender_id:
            t.setdefault('prebid_questions', []).append(q)
    save_json('tenders.json', tenders)
    return jsonify({'status': 'submitted', 'question_id': q['id'], 'question': q}), 201


@tenders_bp.route('/api/tenders/<tender_id>/prebid/questions/<question_id>/answer', methods=['POST'])
@require_role('OFFICER')
def answer_prebid_question(tender_id, question_id):
    """Officer answers and optionally publishes a pre-bid question."""
    data = request.get_json() or {}
    answer = data.get('answer', '').strip()
    if not answer:
        return jsonify({'error': 'Answer is required'}), 400

    if USE_DATABASE:
        tender = db.get_tender_db(tender_id)
        if not tender:
            return jsonify({'error': 'Tender not found'}), 404
        questions = list(tender.get('prebid_questions') or [])
        updated = None
        for q in questions:
            if q.get('id') == question_id:
                q['answer'] = answer
                q['answered_at'] = datetime.now().isoformat()
                q['answered_by'] = data.get('answered_by', 'Procurement Officer')
                q['published'] = data.get('publish', True)
                q['status'] = 'ANSWERED'
                updated = q
        db.update_tender_db(tender_id, {'prebid_questions': questions})
        if updated:
            _audit('PRE_BID_QUESTION_ANSWERED',
                   f'Q&A published for {tender_id}: {updated["question"][:80]}',
                   tender_id=tender_id, actor=data.get('answered_by', 'Procurement Officer'))
        return jsonify({'status': 'answered', 'question': updated})

    tenders = load_json('tenders.json')
    tender = next((t for t in tenders if t['id'] == tender_id), None)
    if not tender:
        return jsonify({'error': 'Tender not found'}), 404
    updated = None
    for t in tenders:
        if t['id'] == tender_id:
            for q in t.get('prebid_questions', []):
                if q['id'] == question_id:
                    q['answer'] = answer
                    q['answered_at'] = datetime.now().isoformat()
                    q['answered_by'] = data.get('answered_by', 'Procurement Officer')
                    q['published'] = data.get('publish', True)
                    q['status'] = 'ANSWERED'
                    updated = q
    save_json('tenders.json', tenders)
    if updated:
        _audit('PRE_BID_QUESTION_ANSWERED',
               f'Q&A published for {tender_id}: {updated["question"][:80]}',
               tender_id=tender_id, actor=data.get('answered_by', 'Procurement Officer'))
    return jsonify({'status': 'answered', 'question': updated})
