#!/usr/bin/env python3
"""
Migration script to load JSON data files into PostgreSQL database.
Run this after creating the database schema with alembic.
"""
import os
import sys
import json
import logging
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load .env with override=True before importing config
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'), override=True)

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_DIR, DATABASE_URL
from services.database import (
    get_connection_pool, migrate_from_json, db_health_check,
    get_user_by_email, create_user, get_tender_by_id, create_tender,
    get_bidder_by_id, create_bidder, get_requirement_by_id, create_requirement
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ID mappings: old_string_id -> new_uuid
ID_MAP = {
    'users': {},
    'tenders': {},
    'bidders': {},
    'requirements': {},
}


def load_json_file(filename):
    """Load JSON file from DATA_DIR."""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        logger.warning(f"Could not load {filename}: {e}")
        return []


def parse_dt(value):
    """Parse ISO datetime string to datetime object."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def migrate_users():
    """Migrate users from JSON to database."""
    users = load_json_file('users.json')
    if not users:
        logger.info("No users to migrate")
        return

    for user in users:
        existing = get_user_by_email(user['email'])
        if existing:
            ID_MAP['users'][user['id']] = existing['id']
            logger.info(f"User {user['email']} already exists, skipping")
            continue

        new_id = str(uuid.uuid4())
        ID_MAP['users'][user['id']] = new_id

        user_data = {
            'id': new_id,
            'email': user['email'],
            'password_hash': user['password'],
            'name': user.get('name'),
            'role': user.get('role'),
            'department': user.get('department'),
            'employee_id': user.get('employee_id'),
            'organization_id': user.get('organization_id'),
            'organization_name': user.get('organization_name'),
            'active': user.get('active', True),
            'last_login': parse_dt(user.get('last_login')),
        }

        created_id = create_user(user_data)
        if created_id:
            logger.info(f"Migrated user: {user['email']} ({created_id})")
        else:
            logger.error(f"Failed to migrate user: {user['email']}")


def migrate_tenders():
    """Migrate tenders from JSON to database."""
    tenders = load_json_file('tenders.json')
    if not tenders:
        logger.info("No tenders to migrate")
        return

    for tender in tenders:
        existing = get_tender_by_id(tender['id'])
        if existing:
            ID_MAP['tenders'][tender['id']] = existing['id']
            logger.info(f"Tender {tender['id']} already exists, skipping")
            continue

        new_id = tender['id']  # Keep string ID for tenders (varchar PK)
        ID_MAP['tenders'][tender['id']] = new_id

        tender_data = {
            'id': new_id,
            'title': tender['title'],
            'department': tender.get('department'),
            'organisation': tender.get('organisation'),
            'estimated_value': tender.get('estimated_value'),
            'estimated_value_display': tender.get('estimated_value_display'),
            'submission_deadline': parse_dt(tender.get('submission_deadline')),
            'opening_date': parse_dt(tender.get('opening_date')),
            'category': tender.get('category'),
            'location': tender.get('location'),
            'description': tender.get('description'),
            'status': tender.get('status', 'active'),
            'emd_amount': tender.get('emd_amount'),
            'emd_amount_display': tender.get('emd_amount_display'),
            'performance_security_pct': tender.get('performance_security_pct', 5),
            'workflow_stage': tender.get('workflow_stage'),
            'cancelled': tender.get('cancelled', False),
            'original_submission_deadline': parse_dt(tender.get('original_submission_deadline')),
            'policy': tender.get('policy', {}),
            'corrigenda': tender.get('corrigenda', []),
            'prebid_questions': tender.get('prebid_questions', []),
            'prebid_meeting': tender.get('prebid_meeting'),
            'deadline_extensions': tender.get('deadline_extensions', []),
            'bidder_ids': tender.get('bidder_ids', []),
            'requirement_ids': tender.get('requirement_ids', []),
        }

        created_id = create_tender(tender_data)
        if created_id:
            logger.info(f"Migrated tender: {tender['id']}")
        else:
            logger.error(f"Failed to migrate tender: {tender['id']}")


def migrate_bidders():
    """Migrate bidders from JSON to database."""
    bidders = load_json_file('bidders.json')
    if not bidders:
        logger.info("No bidders to migrate")
        return

    for bidder in bidders:
        existing = get_bidder_by_id(bidder['id'])
        if existing:
            ID_MAP['bidders'][bidder['id']] = existing['id']
            logger.info(f"Bidder {bidder['id']} already exists, skipping")
            continue

        new_id = bidder['id']  # Keep string ID for bidders (varchar PK)
        ID_MAP['bidders'][bidder['id']] = new_id

        # Map tender_id
        tender_id = bidder.get('tender_id')
        if tender_id and tender_id in ID_MAP['tenders']:
            tender_id = ID_MAP['tenders'][tender_id]

        bidder_data = {
            'id': new_id,
            'tender_id': tender_id,
            'name': bidder['name'],
            'short_name': bidder.get('short_name'),
            'gstin': bidder.get('gstin'),
            'pan': bidder.get('pan'),
            'email': bidder.get('email'),
            'phone': bidder.get('phone'),
            'address': bidder.get('address'),
            'state': bidder.get('state'),
            'incorporation_year': bidder.get('incorporation_year'),
            'type': bidder.get('type'),
            'status': bidder.get('status', 'pending'),
            'compliance_score': bidder.get('compliance_score', 0),
            'risk_level': bidder.get('risk_level', 'UNKNOWN'),
            'submitted_at': parse_dt(bidder.get('submitted_at')),
            'analyzed_at': parse_dt(bidder.get('analyzed_at')),
            'document_ids': bidder.get('document_ids', []),
            'contact_person': bidder.get('contact_person'),
        }

        created_id = create_bidder(bidder_data)
        if created_id:
            logger.info(f"Migrated bidder: {bidder['id']}")
        else:
            logger.error(f"Failed to migrate bidder: {bidder['id']}")


def migrate_requirements():
    """Migrate requirements from JSON to database."""
    requirements = load_json_file('requirements.json')
    if not requirements:
        logger.info("No requirements to migrate")
        return

    for req in requirements:
        existing = get_requirement_by_id(req['id'])
        if existing:
            ID_MAP['requirements'][req['id']] = existing['id']
            logger.info(f"Requirement {req['id']} already exists, skipping")
            continue

        new_id = req['id']  # Keep string ID for requirements (varchar PK)
        ID_MAP['requirements'][req['id']] = new_id

        # Map tender_id
        tender_id = req.get('tender_id')
        if tender_id and tender_id in ID_MAP['tenders']:
            tender_id = ID_MAP['tenders'][tender_id]

        req_data = {
            'id': new_id,
            'tender_id': tender_id,
            'title': req['title'],
            'category': req.get('category'),
            'mandatory': req.get('mandatory', False),
            'description': req.get('description'),
            'required_evidence': req.get('required_evidence', []),
            'verification_type': req.get('verification_type'),
            'threshold': req.get('threshold'),
            'threshold_display': req.get('threshold_display'),
            'unit': req.get('unit'),
        }

        created_id = create_requirement(req_data)
        if created_id:
            logger.info(f"Migrated requirement: {req['id']}")
        else:
            logger.error(f"Failed to migrate requirement: {req['id']}")


def migrate_other_tables():
    """Migrate other tables using bulk migration with ID remapping."""
    tables = [
        'bids', 'contracts', 'inspections', 'corrective_actions',
        'vendor_profiles', 'audit', 'clarifications', 'evaluation_tasks',
        'eval_committees', 'feedback', 'notifications', 'grievances',
        'ai_overrides', 'conflict_declarations', 'rejection_feedback',
        'translations', 'kv_store'
    ]

    for table in tables:
        records = load_json_file(f'{table}.json')
        if not records:
            logger.info(f"No records to migrate for {table}")
            continue

        # Remap foreign keys in records
        for record in records:
            # user_id -> UUID
            if 'user_id' in record and record['user_id'] in ID_MAP['users']:
                record['user_id'] = ID_MAP['users'][record['user_id']]
            
            # tender_id -> string
            if 'tender_id' in record and record['tender_id'] in ID_MAP['tenders']:
                record['tender_id'] = ID_MAP['tenders'][record['tender_id']]
            
            # bidder_id -> string
            if 'bidder_id' in record and record['bidder_id'] in ID_MAP['bidders']:
                record['bidder_id'] = ID_MAP['bidders'][record['bidder_id']]
            
            # requirement_id -> string
            if 'requirement_id' in record and record['requirement_id'] in ID_MAP['requirements']:
                record['requirement_id'] = ID_MAP['requirements'][record['requirement_id']]
            
            # contract_id -> string
            if 'contract_id' in record:
                pass  # contracts use string IDs
            
            # inspection_id -> UUID (if exists in map)
            if 'inspection_id' in record:
                pass  # inspections use UUID PK

        success = migrate_from_json(table, records)
        if success:
            logger.info(f"Migrated {len(records)} records to {table}")
        else:
            logger.error(f"Failed to migrate {table}")


def main():
    logger.info("Starting JSON to PostgreSQL migration...")
    
    # Check database connection
    health = db_health_check()
    if not health.get('connected'):
        logger.error(f"Database not connected: {health}")
        sys.exit(1)
    
    logger.info(f"Database connected: {health}")

    # Run migrations in dependency order
    migrate_users()
    migrate_tenders()
    migrate_bidders()
    migrate_requirements()
    migrate_other_tables()

    logger.info("Migration completed!")
    logger.info(f"ID Mappings: {ID_MAP}")


if __name__ == '__main__':
    main()