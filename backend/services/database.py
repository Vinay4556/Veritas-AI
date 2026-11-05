"""
Database Service - Veritas AI
PostgreSQL database layer using psycopg2 with connection pooling.
Primary storage backend - no JSON fallback.
"""
import os
import json
import uuid
import logging
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Optional, List, Dict
from datetime import datetime, date

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, Json

from config import DATABASE_URL

logger = logging.getLogger(__name__)

# Connection pool
_connection_pool: Optional[pool.ThreadedConnectionPool] = None


def get_connection_pool() -> Optional[pool.ThreadedConnectionPool]:
    """Get or create the connection pool."""
    global _connection_pool
    if _connection_pool is None and DATABASE_URL:
        try:
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DATABASE_URL,
                cursor_factory=RealDictCursor
            )
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {e}")
            _connection_pool = None
    return _connection_pool


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    pool = get_connection_pool()
    if pool is None:
        raise RuntimeError("Database connection pool not initialized. Check DATABASE_URL.")
    
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_db_cursor(commit: bool = True):
    """Context manager for database cursors."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database cursor error: {e}")
            raise
        finally:
            cursor.close()


def execute_query(query: str, params: tuple = None, fetch: bool = False) -> Any:
    """Execute a query and optionally fetch results."""
    with get_db_cursor() as cursor:
        cursor.execute(query, params)
        if fetch:
            return cursor.fetchall()
        return cursor.rowcount


def execute_one(query: str, params: tuple = None) -> Optional[Dict]:
    """Execute a query and fetch one result."""
    with get_db_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchone()


def execute_all(query: str, params: tuple = None) -> List[Dict]:
    """Execute a query and fetch all results."""
    with get_db_cursor() as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def _json_dumps(obj: Any) -> str:
    """json.dumps that tolerates datetime / Decimal / UUID inside JSONB payloads."""
    return json.dumps(obj, default=str)


def _prepare_values(data: Dict) -> tuple:
    """Convert dict/list values for PostgreSQL."""
    from psycopg2.extras import Json
    prepared = []
    for v in data.values():
        if isinstance(v, dict):
            prepared.append(Json(v, dumps=_json_dumps))
        elif isinstance(v, list):
            if not v:
                # Empty array - use NULL for text[] columns
                prepared.append(None)
            elif all(isinstance(item, (str, int, float, bool)) or item is None for item in v):
                # Simple array for text[] columns
                prepared.append(v)
            else:
                prepared.append(Json(v, dumps=_json_dumps))
        else:
            prepared.append(v)
    return tuple(prepared)


def insert_record(table: str, data: Dict, returning: str = 'id') -> Optional[str]:
    """Insert a record and return the specified column."""
    columns = ', '.join(data.keys())
    placeholders = ', '.join(['%s'] * len(data))
    values = _prepare_values(data)
    
    query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING {returning}"
    
    with get_db_cursor() as cursor:
        cursor.execute(query, values)
        result = cursor.fetchone()
        return result[returning] if result else None


def insert_ignore(table: str, data: Dict, conflict_col: str = 'id') -> bool:
    """INSERT ... ON CONFLICT DO NOTHING. Returns True if a new row was written."""
    columns = ', '.join(data.keys())
    placeholders = ', '.join(['%s'] * len(data))
    values = _prepare_values(data)
    query = (f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
             f"ON CONFLICT ({conflict_col}) DO NOTHING")
    with get_db_cursor() as cursor:
        cursor.execute(query, values)
        return cursor.rowcount > 0


def update_record(table: str, data: Dict, where: str, where_params: tuple) -> int:
    """Update records matching the where clause."""
    if not data:
        return 0
    set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
    values = _prepare_values(data) + where_params
    
    query = f"UPDATE {table} SET {set_clause} WHERE {where}"
    
    with get_db_cursor() as cursor:
        cursor.execute(query, values)
        return cursor.rowcount


def delete_record(table: str, where: str, where_params: tuple) -> int:
    """Delete records matching the where clause."""
    query = f"DELETE FROM {table} WHERE {where}"
    
    with get_db_cursor() as cursor:
        cursor.execute(query, where_params)
        return cursor.rowcount


def get_record(table: str, where: str, where_params: tuple) -> Optional[Dict]:
    """Get a single record."""
    query = f"SELECT * FROM {table} WHERE {where}"
    return execute_one(query, where_params)


def get_records(table: str, where: str = '', where_params: tuple = None,
                order_by: str = '', limit: int = 0, offset: int = 0) -> List[Dict]:
    """Get multiple records."""
    query = f"SELECT * FROM {table}"
    if where:
        query += f" WHERE {where}"
    if order_by:
        query += f" ORDER BY {order_by}"
    if limit > 0:
        query += f" LIMIT {int(limit)}"
    if offset > 0:
        query += f" OFFSET {int(offset)}"

    params = where_params or ()
    return execute_all(query, params)


# Document-specific queries
def _is_uuid(value: Any) -> bool:
    """True if ``value`` is a valid UUID (documents.id / users.id are UUID columns;
    querying them with anything else makes PostgreSQL raise instead of returning no rows)."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def normalize_document(row: Optional[Dict]) -> Optional[Dict]:
    """Make a ``documents`` row JSON-friendly and add the legacy field names
    (``filename``, ``saved_path``) that compliance, report, dashboard and the
    frontend still read. UUID / Decimal / datetime values become str / float / ISO str."""
    if not row:
        return row
    d = dict(row)
    for k, v in list(d.items()):
        if isinstance(v, uuid.UUID):
            d[k] = str(v)
        elif isinstance(v, Decimal):
            d[k] = float(v)
        elif isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
    d['filename'] = d.get('original_filename')
    d['saved_path'] = d.get('storage_path')
    d['entities'] = d.get('extracted_entities') or {}
    return d


def get_documents_for_user(user_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
    """Get documents for a specific user with pagination."""
    if not _is_uuid(user_id):
        return []
    rows = get_records(
        'documents',
        where='user_id = %s',
        where_params=(user_id,),
        order_by='created_at DESC',
        limit=limit,
        offset=offset,
    )
    return [normalize_document(r) for r in rows]


def get_all_documents() -> List[Dict]:
    """Every document row (newest first) - used by dashboard / admin / activity feeds."""
    rows = get_records('documents', order_by='created_at DESC')
    return [normalize_document(r) for r in rows]


def get_documents_for_bidder(bidder_id: str, user_id: str = None) -> List[Dict]:
    """Get documents for a bidder, optionally filtered by user ownership."""
    if user_id:
        if not _is_uuid(user_id):
            return []
        rows = get_records(
            'documents',
            where='bidder_id = %s AND user_id = %s',
            where_params=(bidder_id, user_id),
            order_by='created_at DESC'
        )
    else:
        rows = get_records(
            'documents',
            where='bidder_id = %s',
            where_params=(bidder_id,),
            order_by='created_at DESC'
        )
    return [normalize_document(r) for r in rows]


def get_document_by_id(doc_id: str, user_id: str = None) -> Optional[Dict]:
    """Get a single document by ID, optionally filtered by user ownership."""
    if not _is_uuid(doc_id):
        return None
    if user_id:
        if not _is_uuid(user_id):
            return None
        return normalize_document(get_record('documents', 'id = %s AND user_id = %s', (doc_id, user_id)))
    return normalize_document(get_record('documents', 'id = %s', (doc_id,)))


def create_document(data: Dict) -> Optional[str]:
    """Create a new document record."""
    new_id = insert_record('documents', data)
    return str(new_id) if new_id is not None else None


def update_document(doc_id: str, data: Dict, user_id: str = None) -> int:
    """Update a document record."""
    if not _is_uuid(doc_id):
        return 0
    if user_id:
        return update_record('documents', data, 'id = %s AND user_id = %s', (doc_id, user_id))
    return update_record('documents', data, 'id = %s', (doc_id,))


def delete_document(doc_id: str, user_id: str = None) -> int:
    """Delete a document record."""
    if not _is_uuid(doc_id):
        return 0
    if user_id:
        return delete_record('documents', 'id = %s AND user_id = %s', (doc_id, user_id))
    return delete_record('documents', 'id = %s', (doc_id,))


def update_document_status(doc_id: str, status: str, user_id: str = None, **extra_fields) -> int:
    """Update document status with optional extra fields."""
    data = {'status': status, 'updated_at': datetime.now()}
    data.update(extra_fields)
    return update_document(doc_id, data, user_id)


# User queries
# When DATABASE_URL is not configured at all (plain local demo run) the seeded
# data/users.json is used so login still works; the rest of the app reads the
# JSON store anyway. Document upload still needs PostgreSQL.
def _json_users() -> List[Dict]:
    from services.json_cache import load_cached
    return load_cached('users.json') or []


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email."""
    if not DATABASE_URL:
        return next((u for u in _json_users() if (u.get('email') or '').lower() == email.lower()), None)
    return get_record('users', 'email = %s', (email.lower(),))


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """Get user by ID."""
    if not DATABASE_URL:
        return next((u for u in _json_users() if u.get('id') == user_id), None)
    if not _is_uuid(user_id):
        return None
    return get_record('users', 'id = %s', (user_id,))


def create_user(data: Dict) -> Optional[str]:
    """Create a new user."""
    return insert_record('users', data)


def update_user(user_id: str, data: Dict) -> int:
    """Update user record."""
    if not DATABASE_URL:
        return 0  # JSON demo users are read-only
    if not _is_uuid(user_id):
        return 0
    return update_record('users', data, 'id = %s', (user_id,))


# Tender queries
def get_tenders(limit: int = 100, offset: int = 0) -> List[Dict]:
    """Get all tenders with pagination."""
    return get_records('tenders', order_by='created_at DESC', limit=limit)


def get_tender_by_id(tender_id: str) -> Optional[Dict]:
    """Get tender by ID."""
    return get_record('tenders', 'id = %s', (tender_id,))


def create_tender(data: Dict) -> Optional[str]:
    """Create a new tender."""
    return insert_record('tenders', data)


def update_tender(tender_id: str, data: Dict) -> int:
    """Update tender record."""
    return update_record('tenders', data, 'id = %s', (tender_id,))


def delete_tender(tender_id: str) -> int:
    """Delete tender record."""
    return delete_record('tenders', 'id = %s', (tender_id,))


# Bidder queries
def get_bidders_for_tender(tender_id: str) -> List[Dict]:
    """Get all bidders for a tender."""
    return get_records('bidders', where='tender_id = %s', where_params=(tender_id,), order_by='created_at DESC')


def get_bidder_by_id(bidder_id: str) -> Optional[Dict]:
    """Get bidder by ID."""
    return get_record('bidders', 'id = %s', (bidder_id,))


def create_bidder(data: Dict) -> Optional[str]:
    """Create a new bidder."""
    return insert_record('bidders', data)


def update_bidder(bidder_id: str, data: Dict) -> int:
    """Update bidder record."""
    return update_record('bidders', data, 'id = %s', (bidder_id,))


def delete_bidder(bidder_id: str) -> int:
    """Delete bidder record."""
    return delete_record('bidders', 'id = %s', (bidder_id,))


# Requirement queries
def get_requirements_for_tender(tender_id: str) -> List[Dict]:
    """Get all requirements for a tender."""
    return get_records('requirements', where='tender_id = %s', where_params=(tender_id,), order_by='created_at')


def get_requirement_by_id(req_id: str) -> Optional[Dict]:
    """Get requirement by ID."""
    return get_record('requirements', 'id = %s', (req_id,))


def create_requirement(data: Dict) -> Optional[str]:
    """Create a new requirement."""
    return insert_record('requirements', data)


# Health check
def db_health_check() -> Dict[str, Any]:
    """Check database connectivity."""
    if not DATABASE_URL:
        return {
            'status': 'error',
            'database': 'postgresql',
            'connected': False,
            'error': 'DATABASE_URL not configured'
        }
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
            return {
                'status': 'ok',
                'database': 'postgresql',
                'connected': True
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'error',
            'database': 'postgresql',
            'connected': False,
            'error': str(e)
        }


def close_pool():
    """Close the connection pool."""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("Database connection pool closed")


# Migration helper - load from JSON and save to database
def migrate_from_json(table: str, records: List[Dict]) -> bool:
    """Migrate records from JSON to database (used for initial data migration)."""
    try:
        with get_db_cursor() as cursor:
            # Clear existing data
            cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
            for record in records:
                columns = ', '.join(record.keys())
                placeholders = ', '.join(['%s'] * len(record))
                values = tuple(record.values())
                cursor.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
        logger.info(f"Migrated {len(records)} records to {table}")
        return True
    except Exception as e:
        logger.error(f"Migration failed for {table}: {e}")
        return False


# ────────────────────────────────────────────────────────────────────────────
# Sprint 2 entity service functions
# Pattern: parameterised %s queries, no f-string user data, explicit commits,
# return dict(s) so route code needs minimal changes.
# ────────────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now().isoformat()


# ── Audit (append-only) ──────────────────────────────────────────────────────

def append_audit(entry: Dict) -> Optional[str]:
    """Insert one audit record. Never DELETE from audit in application code."""
    entry.setdefault('created_at', datetime.now())
    entry.setdefault('timestamp', datetime.now())
    return insert_record('audit', entry, returning='id')


def list_audits(tender_id: str = None, bidder_id: str = None,
                limit: int = 200) -> List[Dict]:
    """List audit records, newest first, with optional FK filters."""
    if tender_id and bidder_id:
        rows = get_records('audit', 'tender_id = %s AND bidder_id = %s',
                           (tender_id, bidder_id), order_by='created_at DESC', limit=limit)
    elif tender_id:
        rows = get_records('audit', 'tender_id = %s', (tender_id,),
                           order_by='created_at DESC', limit=limit)
    elif bidder_id:
        rows = get_records('audit', 'bidder_id = %s', (bidder_id,),
                           order_by='created_at DESC', limit=limit)
    else:
        rows = get_records('audit', order_by='created_at DESC', limit=limit)
    return [dict(r) for r in rows]


def get_audit_entry(entry_id: str) -> Optional[Dict]:
    row = get_record('audit', 'id = %s', (entry_id,))
    return dict(row) if row else None


# ── Tenders ──────────────────────────────────────────────────────────────────

def list_tenders_db(filters: Dict = None) -> List[Dict]:
    """List tenders. filters may contain status, department, cancelled."""
    if not filters:
        rows = get_records('tenders', order_by='created_at DESC')
    else:
        clauses, params = [], []
        if 'status' in filters:
            clauses.append('status = %s'); params.append(filters['status'])
        if 'department' in filters:
            clauses.append('department = %s'); params.append(filters['department'])
        if 'cancelled' in filters:
            clauses.append('cancelled = %s'); params.append(filters['cancelled'])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('tenders', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_tender_db(tender_id: str) -> Optional[Dict]:
    row = get_record('tenders', 'id = %s', (tender_id,))
    return dict(row) if row else None


def create_tender_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    insert_record('tenders', data, returning='id')
    return get_tender_db(data['id'])


def update_tender_db(tender_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('tenders', updates, 'id = %s', (tender_id,))
    return get_tender_db(tender_id)


def delete_tender_db(tender_id: str) -> int:
    return delete_record('tenders', 'id = %s', (tender_id,))


# ── Requirements ─────────────────────────────────────────────────────────────

def list_requirements_db(tender_id: str) -> List[Dict]:
    rows = get_records('requirements', 'tender_id = %s', (tender_id,),
                       order_by='created_at')
    return [dict(r) for r in rows]


def get_requirement_db(req_id: str) -> Optional[Dict]:
    row = get_record('requirements', 'id = %s', (req_id,))
    return dict(row) if row else None


def create_requirement_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    insert_record('requirements', data, returning='id')
    return get_requirement_db(data['id'])


def update_requirement_db(req_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('requirements', updates, 'id = %s', (req_id,))
    return get_requirement_db(req_id)


def delete_requirement_db(req_id: str) -> int:
    return delete_record('requirements', 'id = %s', (req_id,))


# ── Bidders ──────────────────────────────────────────────────────────────────

def list_bidders_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('bidders', order_by='created_at DESC')
    else:
        clauses, params = [], []
        if 'tender_id' in filters:
            clauses.append('tender_id = %s'); params.append(filters['tender_id'])
        if 'status' in filters:
            clauses.append('status = %s'); params.append(filters['status'])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('bidders', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_bidder_db(bidder_id: str) -> Optional[Dict]:
    row = get_record('bidders', 'id = %s', (bidder_id,))
    return dict(row) if row else None


def create_bidder_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    insert_record('bidders', data, returning='id')
    return get_bidder_db(data['id'])


def update_bidder_db(bidder_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('bidders', updates, 'id = %s', (bidder_id,))
    return get_bidder_db(bidder_id)


def delete_bidder_db(bidder_id: str) -> int:
    return delete_record('bidders', 'id = %s', (bidder_id,))


# ── Bids ─────────────────────────────────────────────────────────────────────

def list_bids_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('bids', order_by='submitted_at DESC')
    else:
        clauses, params = [], []
        for col in ('tender_id', 'bidder_id', 'status'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('bids', where=where, where_params=tuple(params),
                           order_by='submitted_at DESC')
    return [dict(r) for r in rows]


def get_bid_db(bid_id: str) -> Optional[Dict]:
    row = get_record('bids', 'id = %s', (bid_id,))
    return dict(row) if row else None


def create_bid_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    insert_record('bids', data, returning='id')
    return get_bid_db(data['id'])


def update_bid_db(bid_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('bids', updates, 'id = %s', (bid_id,))
    return get_bid_db(bid_id)


def delete_bid_db(bid_id: str) -> int:
    return delete_record('bids', 'id = %s', (bid_id,))


# ── Contracts ────────────────────────────────────────────────────────────────

def list_contracts_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('contracts', order_by='created_at DESC')
    else:
        clauses, params = [], []
        for col in ('tender_id', 'bidder_id', 'status'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('contracts', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_contract_db(contract_id: str) -> Optional[Dict]:
    row = get_record('contracts', 'id = %s', (contract_id,))
    return dict(row) if row else None


def create_contract_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    insert_record('contracts', data, returning='id')
    return get_contract_db(data['id'])


def update_contract_db(contract_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('contracts', updates, 'id = %s', (contract_id,))
    return get_contract_db(contract_id)


def delete_contract_db(contract_id: str) -> int:
    return delete_record('contracts', 'id = %s', (contract_id,))


# ── Inspections ──────────────────────────────────────────────────────────────

def list_inspections_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('inspections', order_by='created_at DESC')
    else:
        clauses, params = [], []
        for col in ('contract_id', 'bidder_id', 'tender_id', 'status'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('inspections', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_inspection_db(inspection_id: str) -> Optional[Dict]:
    row = get_record('inspections', 'id = %s', (inspection_id,))
    return dict(row) if row else None


def create_inspection_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    insert_record('inspections', data, returning='id')
    return get_inspection_db(data['id'])


def update_inspection_db(inspection_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('inspections', updates, 'id = %s', (inspection_id,))
    return get_inspection_db(inspection_id)


def delete_inspection_db(inspection_id: str) -> int:
    return delete_record('inspections', 'id = %s', (inspection_id,))


# ── Corrective Actions ───────────────────────────────────────────────────────

def list_corrective_actions_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('corrective_actions', order_by='created_at DESC')
    else:
        clauses, params = [], []
        for col in ('contract_id', 'inspection_id', 'bidder_id', 'status'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('corrective_actions', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_corrective_action_db(ca_id: str) -> Optional[Dict]:
    row = get_record('corrective_actions', 'id = %s', (ca_id,))
    return dict(row) if row else None


def create_corrective_action_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    insert_record('corrective_actions', data, returning='id')
    return get_corrective_action_db(data['id'])


def update_corrective_action_db(ca_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('corrective_actions', updates, 'id = %s', (ca_id,))
    return get_corrective_action_db(ca_id)


def delete_corrective_action_db(ca_id: str) -> int:
    return delete_record('corrective_actions', 'id = %s', (ca_id,))


# ── Vendor Profiles ──────────────────────────────────────────────────────────

def list_vendor_profiles_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('vendor_profiles', order_by='created_at DESC')
    else:
        clauses, params = [], []
        if 'bidder_id' in filters:
            clauses.append('bidder_id = %s'); params.append(filters['bidder_id'])
        if 'gstin' in filters:
            clauses.append('gstin = %s'); params.append(filters['gstin'])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('vendor_profiles', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_vendor_profile_db(profile_id: str) -> Optional[Dict]:
    row = get_record('vendor_profiles', 'id = %s', (profile_id,))
    return dict(row) if row else None


def get_vendor_profile_by_bidder_db(bidder_id: str) -> Optional[Dict]:
    row = get_record('vendor_profiles', 'bidder_id = %s', (bidder_id,))
    return dict(row) if row else None


def get_vendor_profile_by_gstin_db(gstin: str) -> Optional[Dict]:
    row = get_record('vendor_profiles', 'gstin = %s', (gstin,))
    return dict(row) if row else None


def create_vendor_profile_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    insert_record('vendor_profiles', data, returning='id')
    return get_vendor_profile_db(data['id'])


def update_vendor_profile_db(profile_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('vendor_profiles', updates, 'id = %s', (profile_id,))
    return get_vendor_profile_db(profile_id)


def delete_vendor_profile_db(profile_id: str) -> int:
    return delete_record('vendor_profiles', 'id = %s', (profile_id,))


# ── Compliance Results ───────────────────────────────────────────────────────

def list_compliance_results_db(bidder_id: str, tender_id: str = None) -> List[Dict]:
    """Return the most recent compliance result per requirement for a bidder."""
    if tender_id:
        rows = get_records(
            'compliance_results',
            'bidder_id = %s AND tender_id = %s',
            (bidder_id, tender_id),
            order_by='analyzed_at DESC',
        )
    else:
        rows = get_records(
            'compliance_results',
            'bidder_id = %s',
            (bidder_id,),
            order_by='analyzed_at DESC',
        )
    return [dict(r) for r in rows]


def create_compliance_result_db(data: Dict) -> Optional[str]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('analyzed_at', datetime.now())
    return insert_record('compliance_results', data, returning='id')


def delete_compliance_results_db(bidder_id: str) -> int:
    """Remove all compliance results for a bidder (used when re-analysing)."""
    return delete_record('compliance_results', 'bidder_id = %s', (bidder_id,))


# ── Grievances ───────────────────────────────────────────────────────────────

def list_grievances_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('grievances', order_by='submitted_at DESC')
    else:
        clauses, params = [], []
        for col in ('tender_id', 'bidder_id', 'status', 'submitter_id'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('grievances', where=where, where_params=tuple(params),
                           order_by='submitted_at DESC')
    return [dict(r) for r in rows]


def get_grievance_db(grievance_id: str) -> Optional[Dict]:
    row = get_record('grievances', 'id = %s', (grievance_id,))
    return dict(row) if row else None


def create_grievance_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    data.setdefault('submitted_at', datetime.now())
    insert_record('grievances', data, returning='id')
    return get_grievance_db(data['id'])


def update_grievance_db(grievance_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('grievances', updates, 'id = %s', (grievance_id,))
    return get_grievance_db(grievance_id)


def delete_grievance_db(grievance_id: str) -> int:
    return delete_record('grievances', 'id = %s', (grievance_id,))


# ── Feedback ─────────────────────────────────────────────────────────────────

def list_feedback_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('feedback', order_by='submitted_at DESC')
    else:
        clauses, params = [], []
        for col in ('tender_id', 'status', 'submitted_by'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('feedback', where=where, where_params=tuple(params),
                           order_by='submitted_at DESC')
    return [dict(r) for r in rows]


def get_feedback_db(feedback_id: str) -> Optional[Dict]:
    row = get_record('feedback', 'id = %s', (feedback_id,))
    return dict(row) if row else None


def create_feedback_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    data.setdefault('submitted_at', datetime.now())
    insert_record('feedback', data, returning='id')
    return get_feedback_db(data['id'])


def update_feedback_db(feedback_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('feedback', updates, 'id = %s', (feedback_id,))
    return get_feedback_db(feedback_id)


def delete_feedback_db(feedback_id: str) -> int:
    return delete_record('feedback', 'id = %s', (feedback_id,))


# ── Rejection Feedback ───────────────────────────────────────────────────────

def list_rejection_feedback_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('rejection_feedback', order_by='created_at DESC')
    else:
        clauses, params = [], []
        for col in ('bidder_id', 'tender_id', 'read_by_bidder'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('rejection_feedback', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_rejection_feedback_db(rfb_id: str) -> Optional[Dict]:
    row = get_record('rejection_feedback', 'id = %s', (rfb_id,))
    return dict(row) if row else None


def create_rejection_feedback_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    insert_record('rejection_feedback', data, returning='id')
    return get_rejection_feedback_db(data['id'])


def update_rejection_feedback_db(rfb_id: str, updates: Dict) -> Optional[Dict]:
    update_record('rejection_feedback', updates, 'id = %s', (rfb_id,))
    return get_rejection_feedback_db(rfb_id)


def delete_rejection_feedback_db(rfb_id: str) -> int:
    return delete_record('rejection_feedback', 'id = %s', (rfb_id,))


# ── AI Overrides ─────────────────────────────────────────────────────────────

def list_ai_overrides_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('ai_overrides', order_by='overridden_at DESC')
    else:
        clauses, params = [], []
        for col in ('entity_type', 'entity_id', 'bidder_id', 'tender_id'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('ai_overrides', where=where, where_params=tuple(params),
                           order_by='overridden_at DESC')
    return [dict(r) for r in rows]


def get_ai_override_db(override_id: str) -> Optional[Dict]:
    row = get_record('ai_overrides', 'id = %s', (override_id,))
    return dict(row) if row else None


def create_ai_override_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('overridden_at', datetime.now())
    insert_record('ai_overrides', data, returning='id')
    return get_ai_override_db(data['id'])


def update_ai_override_db(override_id: str, updates: Dict) -> Optional[Dict]:
    update_record('ai_overrides', updates, 'id = %s', (override_id,))
    return get_ai_override_db(override_id)


def delete_ai_override_db(override_id: str) -> int:
    return delete_record('ai_overrides', 'id = %s', (override_id,))


# ── Eval Committees ──────────────────────────────────────────────────────────

def list_eval_committees_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('eval_committees', order_by='created_at DESC')
    else:
        clauses, params = [], []
        if 'tender_id' in filters:
            clauses.append('tender_id = %s'); params.append(filters['tender_id'])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('eval_committees', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_eval_committee_db(committee_id: str) -> Optional[Dict]:
    row = get_record('eval_committees', 'id = %s', (committee_id,))
    return dict(row) if row else None


def get_eval_committee_by_tender_db(tender_id: str) -> Optional[Dict]:
    row = get_record('eval_committees', 'tender_id = %s', (tender_id,))
    return dict(row) if row else None


def create_eval_committee_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    insert_record('eval_committees', data, returning='id')
    return get_eval_committee_db(data['id'])


def update_eval_committee_db(committee_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('eval_committees', updates, 'id = %s', (committee_id,))
    return get_eval_committee_db(committee_id)


def delete_eval_committee_db(committee_id: str) -> int:
    return delete_record('eval_committees', 'id = %s', (committee_id,))


# ── Clarifications ───────────────────────────────────────────────────────────

def list_clarifications_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('clarifications', order_by='created_at DESC')
    else:
        clauses, params = [], []
        for col in ('tender_id', 'bidder_id', 'bid_id', 'status'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('clarifications', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_clarification_db(clr_id: str) -> Optional[Dict]:
    row = get_record('clarifications', 'id = %s', (clr_id,))
    return dict(row) if row else None


def create_clarification_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    data.setdefault('requested_at', datetime.now())
    insert_record('clarifications', data, returning='id')
    return get_clarification_db(data['id'])


def update_clarification_db(clr_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('clarifications', updates, 'id = %s', (clr_id,))
    return get_clarification_db(clr_id)


def delete_clarification_db(clr_id: str) -> int:
    return delete_record('clarifications', 'id = %s', (clr_id,))


# ── Evaluation Tasks ─────────────────────────────────────────────────────────

def list_eval_tasks_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('evaluation_tasks', order_by='created_at DESC')
    else:
        clauses, params = [], []
        for col in ('tender_id', 'bidder_id', 'bid_id', 'status', 'assigned_to_id'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('evaluation_tasks', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_eval_task_db(task_id: str) -> Optional[Dict]:
    row = get_record('evaluation_tasks', 'id = %s', (task_id,))
    return dict(row) if row else None


def create_eval_task_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    data.setdefault('updated_at', datetime.now())
    insert_record('evaluation_tasks', data, returning='id')
    return get_eval_task_db(data['id'])


def update_eval_task_db(task_id: str, updates: Dict) -> Optional[Dict]:
    updates['updated_at'] = datetime.now()
    update_record('evaluation_tasks', updates, 'id = %s', (task_id,))
    return get_eval_task_db(task_id)


def delete_eval_task_db(task_id: str) -> int:
    return delete_record('evaluation_tasks', 'id = %s', (task_id,))


# ── Notifications ────────────────────────────────────────────────────────────

def list_notifications_db(filters: Dict = None) -> List[Dict]:
    if not filters:
        rows = get_records('notifications', order_by='created_at DESC')
    else:
        clauses, params = [], []
        for col in ('recipient_id', 'recipient_role', 'tender_id', 'bid_id', 'read'):
            if col in filters:
                clauses.append(f'{col} = %s'); params.append(filters[col])
        if 'broadcast' in filters:
            clauses.append('broadcast = %s'); params.append(filters['broadcast'])
        where = ' AND '.join(clauses) if clauses else ''
        rows = get_records('notifications', where=where, where_params=tuple(params),
                           order_by='created_at DESC')
    return [dict(r) for r in rows]


def get_notification_db(notif_id: str) -> Optional[Dict]:
    row = get_record('notifications', 'id = %s', (notif_id,))
    return dict(row) if row else None


def create_notification_db(data: Dict) -> Optional[Dict]:
    data.setdefault('created_at', datetime.now())
    insert_record('notifications', data, returning='id')
    return get_notification_db(data['id'])


def update_notification_db(notif_id: str, updates: Dict) -> Optional[Dict]:
    update_record('notifications', updates, 'id = %s', (notif_id,))
    return get_notification_db(notif_id)


def delete_notification_db(notif_id: str) -> int:
    return delete_record('notifications', 'id = %s', (notif_id,))


# ── Token Revocation (Sprint 3) ──────────────────────────────────────────────

def revoke_token_db(raw_token: str, ttl_seconds: int) -> None:
    """Store SHA-256(raw_token) in revoked_tokens.

    Never stores the raw token itself. Raises on DB error so callers can fail
    closed — a logout that fails to write its revocation record must not
    succeed silently in production.
    """
    import hashlib
    from datetime import timedelta
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
    query = (
        "INSERT INTO revoked_tokens (token_hash, revoked_at, expires_at) "
        "VALUES (%s, %s, %s) ON CONFLICT (token_hash) DO NOTHING"
    )
    with get_db_cursor() as cursor:
        cursor.execute(query, (token_hash, datetime.now(), expires_at))


def is_token_revoked_db(raw_token: str) -> bool:
    """True if the token is in revoked_tokens and has not yet expired.

    Raises RuntimeError on DB error so the caller can fail closed (treat as
    revoked) — never returns False on a DB failure.
    """
    import hashlib
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    query = (
        "SELECT 1 FROM revoked_tokens "
        "WHERE token_hash = %s AND expires_at > now()"
    )
    try:
        row = execute_one(query, (token_hash,))
        return row is not None
    except Exception as exc:
        raise RuntimeError(f'is_token_revoked_db DB error: {exc}') from exc


def cleanup_expired_revocations() -> int:
    """Delete rows where expires_at < now(). Returns the number of rows deleted.

    Safe to call at any time — expired tokens cannot be re-used regardless of
    whether their revocation record exists.
    """
    query = "DELETE FROM revoked_tokens WHERE expires_at < now()"
    with get_db_cursor() as cursor:
        cursor.execute(query)
        return cursor.rowcount