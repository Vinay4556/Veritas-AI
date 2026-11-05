#!/usr/bin/env python3
"""
import_json_to_db.py — Idempotent JSON-to-PostgreSQL data importer for Veritas AI.

Usage (from backend/ directory):
    python scripts/import_json_to_db.py

Environment variables required:
    DATABASE_URL  — PostgreSQL connection string (same as main app).

Behaviour:
    - Reads all JSON data files from DATA_DIR (configured in config.py).
    - Validates required fields per entity type.
    - Inserts using ON CONFLICT DO NOTHING (safe to run multiple times).
    - Each entity type is wrapped in its own transaction.
    - Imports in FK-dependency order (users → tenders → … → audit).
    - Logs results: inserted / skipped / errors per entity type.
    - Writes a report to backend/data/import_report.json.
    - Exits with code 0 on success, code 1 if any entity had errors.
    - Never deletes source JSON files.
"""
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Allow importing from the backend package root
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from config import DATABASE_URL, DATA_DIR
from services.database import (
    get_db_connection, insert_ignore, _prepare_values, _json_dumps
)
from psycopg2.extras import Json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger('import_json_to_db')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json(filename: str):
    """Load a JSON file from DATA_DIR. Returns [] or {} on missing/error."""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        log.warning('File not found: %s — skipping', path)
        return []
    try:
        with open(path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception as exc:
        log.error('Failed to load %s: %s', filename, exc)
        return []


def _validate(record: dict, required: list, entity: str) -> list:
    """Return a list of missing required field names."""
    return [f for f in required if not record.get(f)]


def _insert_record(conn, table: str, record: dict, conflict_col: str = 'id') -> str:
    """INSERT … ON CONFLICT DO NOTHING. Returns 'inserted' or 'skipped'."""
    from psycopg2.extras import Json as PgJson
    prepared = {}
    for k, v in record.items():
        if isinstance(v, dict):
            prepared[k] = PgJson(v, dumps=_json_dumps)
        elif isinstance(v, list):
            if not v:
                prepared[k] = None
            elif all(isinstance(i, (str, int, float, bool)) or i is None for i in v):
                prepared[k] = v
            else:
                prepared[k] = PgJson(v, dumps=_json_dumps)
        else:
            prepared[k] = v

    cols = ', '.join(prepared.keys())
    placeholders = ', '.join(['%s'] * len(prepared))
    sql = (f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) "
           f"ON CONFLICT ({conflict_col}) DO NOTHING")
    with conn.cursor() as cur:
        cur.execute(sql, list(prepared.values()))
        return 'inserted' if cur.rowcount > 0 else 'skipped'


def _run_entity(conn, table: str, records: list, required_fields: list,
                entity_name: str, conflict_col: str = 'id',
                transform_fn=None) -> dict:
    """
    Import all records for one entity type in a single transaction.
    Returns stats dict: {inserted, skipped, errors, error_details}.
    """
    stats = {'inserted': 0, 'skipped': 0, 'errors': 0, 'error_details': []}
    if not records:
        log.info('[%s] No records to import', entity_name)
        return stats

    conn.autocommit = False
    try:
        for rec in records:
            # Validate
            missing = _validate(rec, required_fields, entity_name)
            if missing:
                msg = f'Record {rec.get("id", "?")} missing fields: {missing}'
                stats['errors'] += 1
                stats['error_details'].append(msg)
                log.warning('[%s] %s', entity_name, msg)
                continue

            # Optional transformation
            if transform_fn:
                try:
                    rec = transform_fn(rec)
                except Exception as e:
                    msg = f'Transform error for {rec.get("id", "?")}: {e}'
                    stats['errors'] += 1
                    stats['error_details'].append(msg)
                    log.warning('[%s] %s', entity_name, msg)
                    continue

            try:
                result = _insert_record(conn, table, rec, conflict_col)
                stats[result] += 1
            except Exception as exc:
                msg = f'DB insert error for {rec.get("id", "?")}: {exc}'
                stats['errors'] += 1
                stats['error_details'].append(msg)
                log.warning('[%s] %s', entity_name, msg)
                conn.rollback()

        conn.commit()
        log.info('[%s] inserted=%d skipped=%d errors=%d',
                 entity_name, stats['inserted'], stats['skipped'], stats['errors'])
    except Exception as outer:
        conn.rollback()
        msg = f'Transaction failed: {outer}'
        stats['errors'] += 1
        stats['error_details'].append(msg)
        log.error('[%s] %s', entity_name, msg)
    finally:
        conn.autocommit = True
    return stats


# ── Transform helpers ─────────────────────────────────────────────────────────

def _clean_tender(rec: dict) -> dict:
    """Strip uuid FK from created_by (JSON has name string, not UUID)."""
    r = dict(rec)
    # created_by in JSON is a name string; DB column is now TEXT (not UUID FK)
    # Nothing to change — the migration already altered it to TEXT.
    # Ensure JSONB fields are present
    for field, default in [
        ('policy', {}), ('corrigenda', []), ('prebid_questions', []),
        ('deadline_extensions', []), ('bidder_ids', None), ('requirement_ids', None),
    ]:
        if field not in r:
            r[field] = default
    return r


def _clean_bid(rec: dict) -> dict:
    """Normalise bid record for PG schema."""
    r = dict(rec)
    # Ensure JSONB fields
    for field, default in [
        ('price_breakdown', None), ('emd_verification', None), ('price_analysis', None),
        ('preference_verification', None), ('local_content_verification', None),
        ('oem_verification', None), ('versions', []), ('ai_overrides', []),
        ('committee_scores', []),
    ]:
        if r.get(field) is None:
            r[field] = default
    return r


def _clean_compliance(bidder_id: str, tender_id: str, results: dict,
                      score: dict, analyzed_at: str) -> list:
    """Flatten compliance.json nested structure into list of row dicts."""
    rows = []
    for req_id, res in results.items():
        rows.append({
            'bidder_id': bidder_id,
            'requirement_id': req_id,
            'tender_id': tender_id,
            'status': res.get('status', 'MISSING'),
            'confidence': res.get('confidence'),
            'source_doc_id': res.get('source_doc'),
            'extracted_value': res.get('extracted_value'),
            'required_value': res.get('required_value'),
            'found_value': res.get('found_value'),
            'reason': res.get('reason', ''),
            'concern': res.get('concern', ''),
            'overall_score': (score or {}).get('overall_score'),
            'risk_level': (score or {}).get('risk_level'),
            'analyzed_at': analyzed_at,
            'created_at': analyzed_at,
        })
    return rows


# ── Main import ───────────────────────────────────────────────────────────────

def main():
    if not DATABASE_URL:
        log.error('DATABASE_URL is not set — cannot import to database.')
        sys.exit(1)

    report = {
        'generated_at': datetime.now().isoformat(),
        'entities': {},
        'total_errors': 0,
    }
    any_errors = False

    from services.database import get_connection_pool
    pool = get_connection_pool()
    if not pool:
        log.error('Could not create database connection pool. Check DATABASE_URL.')
        sys.exit(1)

    conn = pool.getconn()
    conn.autocommit = True

    try:
        # ── 1. Users ──────────────────────────────────────────
        # Note: JSON users have string IDs (USR-001); PG uses UUID.
        # We skip users from JSON — they must be seeded via create_demo_users.py
        # to get proper UUIDs. Importing them here would violate the UUID PK constraint.
        log.info('[users] Skipping JSON import — users require UUID PK (seed via create_demo_users.py)')
        report['entities']['users'] = {
            'inserted': 0, 'skipped': 0, 'errors': 0,
            'note': 'Skipped — JSON IDs are USR-XXX strings, PG table requires UUID PK.',
        }

        # ── 2. Tenders ────────────────────────────────────────
        tenders = _load_json('tenders.json')
        if isinstance(tenders, list):
            stats = _run_entity(conn, 'tenders', tenders, ['id', 'title'],
                                'tenders', transform_fn=_clean_tender)
            report['entities']['tenders'] = stats
            if stats['errors']:
                any_errors = True

        # ── 3. Requirements ───────────────────────────────────
        requirements = _load_json('requirements.json')
        if isinstance(requirements, list):
            stats = _run_entity(conn, 'requirements', requirements, ['id', 'tender_id', 'title'],
                                'requirements')
            report['entities']['requirements'] = stats
            if stats['errors']:
                any_errors = True

        # ── 4. Bidders ────────────────────────────────────────
        bidders = _load_json('bidders.json')
        if isinstance(bidders, list):
            stats = _run_entity(conn, 'bidders', bidders, ['id', 'name'],
                                'bidders')
            report['entities']['bidders'] = stats
            if stats['errors']:
                any_errors = True

        # ── 5. Bids ───────────────────────────────────────────
        bids = _load_json('bids.json')
        if isinstance(bids, list):
            stats = _run_entity(conn, 'bids', bids, ['id', 'tender_id', 'bidder_id'],
                                'bids', transform_fn=_clean_bid)
            report['entities']['bids'] = stats
            if stats['errors']:
                any_errors = True

        # ── 6. Contracts ──────────────────────────────────────
        contracts = _load_json('contracts.json')
        if isinstance(contracts, list):
            stats = _run_entity(conn, 'contracts', contracts, ['id', 'tender_id', 'bidder_id'],
                                'contracts')
            report['entities']['contracts'] = stats
            if stats['errors']:
                any_errors = True

        # ── 7. Inspections (with corrective_action_id=NULL first) ──
        inspections = _load_json('inspections.json')
        if isinstance(inspections, list):
            # Nullify circular FK for first pass
            clean_ins = [dict(i, corrective_action_id=None) for i in inspections]
            stats = _run_entity(conn, 'inspections', clean_ins, ['id', 'contract_id'],
                                'inspections')
            report['entities']['inspections'] = stats
            if stats['errors']:
                any_errors = True

        # ── 8. Corrective Actions ─────────────────────────────
        cas = _load_json('corrective_actions.json')
        if isinstance(cas, list):
            stats = _run_entity(conn, 'corrective_actions', cas, ['id', 'inspection_id'],
                                'corrective_actions')
            report['entities']['corrective_actions'] = stats
            if stats['errors']:
                any_errors = True

        # ── 9. Update inspections.corrective_action_id ────────
        if isinstance(inspections, list):
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    for ins in inspections:
                        ca_id = ins.get('corrective_action_id')
                        if ca_id and ins.get('id'):
                            cur.execute(
                                'UPDATE inspections SET corrective_action_id = %s WHERE id = %s',
                                (ca_id, ins['id'])
                            )
                conn.commit()
                log.info('[inspections] Updated corrective_action_id back-references')
            except Exception as e:
                conn.rollback()
                log.warning('Failed to update inspection corrective_action_id: %s', e)
            finally:
                conn.autocommit = True

        # ── 10. Vendor Profiles ───────────────────────────────
        vps = _load_json('vendor_profiles.json')
        if isinstance(vps, list):
            stats = _run_entity(conn, 'vendor_profiles', vps, ['id', 'bidder_id'],
                                'vendor_profiles')
            report['entities']['vendor_profiles'] = stats
            if stats['errors']:
                any_errors = True

        # ── 11. Compliance Results ────────────────────────────
        compliance_raw = _load_json('compliance.json')
        if isinstance(compliance_raw, dict):
            cr_rows = []
            for bidder_id, entry in compliance_raw.items():
                if not isinstance(entry, dict):
                    continue
                results = entry.get('results', {})
                score = entry.get('score', {})
                analyzed_at = entry.get('analyzed_at', datetime.now().isoformat())
                tender_id = entry.get('tender_id')
                cr_rows.extend(
                    _clean_compliance(bidder_id, tender_id, results, score, analyzed_at)
                )
            stats = _run_entity(conn, 'compliance_results', cr_rows,
                                ['bidder_id', 'requirement_id', 'status'],
                                'compliance_results', conflict_col='id')
            report['entities']['compliance_results'] = stats
            if stats['errors']:
                any_errors = True

        # ── 12. Clarifications ────────────────────────────────
        clarifications = _load_json('clarifications.json')
        if isinstance(clarifications, list):
            stats = _run_entity(conn, 'clarifications', clarifications, ['id'],
                                'clarifications')
            report['entities']['clarifications'] = stats
            if stats['errors']:
                any_errors = True

        # ── 13. Evaluation Tasks ──────────────────────────────
        eval_tasks = _load_json('evaluation_tasks.json')
        if isinstance(eval_tasks, list):
            stats = _run_entity(conn, 'evaluation_tasks', eval_tasks, ['id'],
                                'evaluation_tasks')
            report['entities']['evaluation_tasks'] = stats
            if stats['errors']:
                any_errors = True

        # ── 14. Eval Committees ───────────────────────────────
        committees = _load_json('eval_committees.json')
        if isinstance(committees, list):
            stats = _run_entity(conn, 'eval_committees', committees, ['id'],
                                'eval_committees')
            report['entities']['eval_committees'] = stats
            if stats['errors']:
                any_errors = True

        # ── 15. Grievances ────────────────────────────────────
        grievances = _load_json('grievances.json')
        if isinstance(grievances, list):
            stats = _run_entity(conn, 'grievances', grievances, ['id'],
                                'grievances')
            report['entities']['grievances'] = stats
            if stats['errors']:
                any_errors = True

        # ── 16. Feedback ──────────────────────────────────────
        feedback = _load_json('feedback.json')
        if isinstance(feedback, list):
            stats = _run_entity(conn, 'feedback', feedback, ['id'],
                                'feedback')
            report['entities']['feedback'] = stats
            if stats['errors']:
                any_errors = True

        # ── 17. Rejection Feedback ────────────────────────────
        rfb = _load_json('rejection_feedback.json')
        if isinstance(rfb, list):
            stats = _run_entity(conn, 'rejection_feedback', rfb, ['id'],
                                'rejection_feedback')
            report['entities']['rejection_feedback'] = stats
            if stats['errors']:
                any_errors = True

        # ── 18. AI Overrides ──────────────────────────────────
        ai_ov = _load_json('ai_overrides.json')
        if isinstance(ai_ov, list):
            stats = _run_entity(conn, 'ai_overrides', ai_ov, ['id'],
                                'ai_overrides')
            report['entities']['ai_overrides'] = stats
            if stats['errors']:
                any_errors = True

        # ── 19. Notifications ─────────────────────────────────
        notifs = _load_json('notifications.json')
        if isinstance(notifs, list):
            stats = _run_entity(conn, 'notifications', notifs, ['id'],
                                'notifications')
            report['entities']['notifications'] = stats
            if stats['errors']:
                any_errors = True

        # ── 20. Audit (last — append-only) ────────────────────
        audit = _load_json('audit.json')
        if isinstance(audit, list):
            stats = _run_entity(conn, 'audit', audit, ['id', 'action'],
                                'audit')
            report['entities']['audit'] = stats
            if stats['errors']:
                any_errors = True

    finally:
        pool.putconn(conn)

    # ── Write report ──────────────────────────────────────────
    report['total_errors'] = sum(
        e.get('errors', 0) for e in report['entities'].values()
        if isinstance(e, dict)
    )
    report_path = os.path.join(DATA_DIR, 'import_report.json')
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        log.info('Import report written to %s', report_path)
    except Exception as exc:
        log.error('Could not write import report: %s', exc)

    # ── Summary ───────────────────────────────────────────────
    log.info('=== IMPORT SUMMARY ===')
    for entity, stats in report['entities'].items():
        if isinstance(stats, dict):
            log.info('  %-30s inserted=%-4d skipped=%-4d errors=%-4d',
                     entity,
                     stats.get('inserted', 0),
                     stats.get('skipped', 0),
                     stats.get('errors', 0))

    if any_errors:
        log.error('Import completed WITH ERRORS — check report at %s', report_path)
        sys.exit(1)
    else:
        log.info('Import completed successfully.')
        sys.exit(0)


if __name__ == '__main__':
    main()
