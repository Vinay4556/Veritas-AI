"""
Sprint 2 — Complete schema for all entities.
Extends stubs, adds missing columns, creates new tables.

Revision ID: a3f91b2c8e47
Revises: 6fd62e526b64
Create Date: 2025-07-19 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a3f91b2c8e47'
down_revision = '6fd62e526b64'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Extend tenders — add missing columns ───────────────────────────────
    # First drop the UUID FK constraint on created_by so we can store name strings
    try:
        conn.execute(sa.text(
            "ALTER TABLE tenders DROP CONSTRAINT IF EXISTS tenders_created_by_fkey"
        ))
    except Exception:
        pass

    conn.execute(sa.text(
        "ALTER TABLE tenders ALTER COLUMN created_by TYPE TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE tenders ADD COLUMN IF NOT EXISTS contact_officer VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE tenders ADD COLUMN IF NOT EXISTS cancellation_reason TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE tenders ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE tenders ADD COLUMN IF NOT EXISTS cancelled_by VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE tenders ADD COLUMN IF NOT EXISTS parent_tender_id VARCHAR(100) "
        "REFERENCES tenders(id)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE tenders ADD COLUMN IF NOT EXISTS prebid_date DATE"
    ))
    # Add index on parent_tender_id
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_tenders_parent ON tenders(parent_tender_id)"
    ))

    # ── 2. Extend bidders — add decision fields ───────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS cin VARCHAR(21)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS udyam_no VARCHAR(50)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS officer_decision VARCHAR(20)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS officer_remarks TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS decision_officer VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS decision_officer_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS decision_timestamp TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS rejection_category VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS rejection_stage VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS rejection_reason TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE bidders ADD COLUMN IF NOT EXISTS is_disqualified BOOLEAN DEFAULT FALSE"
    ))

    # ── 3. Replace stub bids table ────────────────────────────────────────────
    # Drop old stub (no production data in it yet — all data is in JSON)
    conn.execute(sa.text("DROP TABLE IF EXISTS bids CASCADE"))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS bids (
            id                         VARCHAR(100)  PRIMARY KEY,
            tender_id                  VARCHAR(100)  REFERENCES tenders(id),
            bidder_id                  VARCHAR(100)  REFERENCES bidders(id),
            bidder_name                VARCHAR(255),
            status                     VARCHAR(50)   NOT NULL DEFAULT 'SUBMITTED',
            submitted_at               TIMESTAMPTZ,
            last_updated               TIMESTAMPTZ,
            compliance_score           INTEGER,
            risk_level                 VARCHAR(50),
            technical_status           VARCHAR(50)   DEFAULT 'PENDING',
            financial_status           VARCHAR(50)   DEFAULT 'PENDING',
            clarifications             INTEGER       DEFAULT 0,
            documents_count            INTEGER       DEFAULT 0,
            quoted_price               BIGINT,
            price_display              VARCHAR(100),
            price_breakdown            JSONB,
            delivery_period_days       INTEGER,
            payment_terms              VARCHAR(255),
            validity_period_days       INTEGER,
            validity_expires_at        DATE,
            emd_reference              VARCHAR(255),
            emd_bank                   VARCHAR(255),
            emd_amount                 BIGINT,
            financial_remarks          TEXT,
            financial_bid_opened       BOOLEAN       DEFAULT FALSE,
            financial_opened_at        TIMESTAMPTZ,
            technical_score            NUMERIC(5,2),
            committee_scores           JSONB         DEFAULT '[]',
            committee_evaluators       INTEGER       DEFAULT 0,
            emd_status                 VARCHAR(50),
            emd_verification           JSONB,
            price_analysis             JSONB,
            preference_verification    JSONB,
            local_content_verification JSONB,
            oem_verification           JSONB,
            withdrawn_at               TIMESTAMPTZ,
            withdrawal_reason          TEXT,
            modified_at                TIMESTAMPTZ,
            version_number             INTEGER       DEFAULT 1,
            versions                   JSONB         DEFAULT '[]',
            ai_overrides               JSONB         DEFAULT '[]',
            is_test_bidder             BOOLEAN       DEFAULT FALSE,
            created_at                 TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at                 TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_bids_tender_id ON bids(tender_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_bids_bidder_id ON bids(bidder_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_bids_status ON bids(status)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_bids_submitted_at ON bids(submitted_at DESC)"
    ))

    # ── 4. Replace stub contracts table ──────────────────────────────────────
    conn.execute(sa.text("DROP TABLE IF EXISTS contracts CASCADE"))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS contracts (
            id                      VARCHAR(100)   PRIMARY KEY,
            tender_id               VARCHAR(100)   REFERENCES tenders(id),
            bid_id                  VARCHAR(100)   REFERENCES bids(id),
            bidder_id               VARCHAR(100)   REFERENCES bidders(id),
            bidder_name             VARCHAR(255),
            awarded_by              VARCHAR(255),
            awarded_by_id           VARCHAR(100),
            awarded_at              TIMESTAMPTZ,
            contract_value          BIGINT,
            contract_value_display  VARCHAR(100),
            contract_reference      VARCHAR(255),
            status                  VARCHAR(50)    NOT NULL DEFAULT 'AWARDED',
            delivery_address        TEXT,
            delivery_deadline       DATE,
            payment_terms           VARCHAR(255),
            advance_payment_pct     INTEGER        DEFAULT 0,
            milestones              JSONB          DEFAULT '[]',
            total_penalty_amount    NUMERIC(15,2)  DEFAULT 0,
            penalty_details         TEXT,
            notes                   TEXT,
            created_at              TIMESTAMPTZ    NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ    NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_contracts_tender_id ON contracts(tender_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_contracts_bidder_id ON contracts(bidder_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_contracts_status ON contracts(status)"
    ))

    # ── 5. Replace stub inspections table ────────────────────────────────────
    conn.execute(sa.text("DROP TABLE IF EXISTS corrective_actions CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS inspections CASCADE"))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS inspections (
            id                         VARCHAR(100)  PRIMARY KEY,
            contract_id                VARCHAR(100)  REFERENCES contracts(id),
            tender_id                  VARCHAR(100)  REFERENCES tenders(id),
            bidder_id                  VARCHAR(100)  REFERENCES bidders(id),
            milestone_id               VARCHAR(100),
            inspection_type            VARCHAR(50)   DEFAULT 'INCOMING_QUALITY',
            inspector                  VARCHAR(255),
            inspector_id               VARCHAR(100),
            inspected_at               TIMESTAMPTZ,
            status                     VARCHAR(50)   DEFAULT 'IN_PROGRESS',
            items                      JSONB         DEFAULT '[]',
            overall_result             VARCHAR(50)   DEFAULT 'PENDING',
            corrective_action_required BOOLEAN       DEFAULT FALSE,
            corrective_action_id       VARCHAR(100),
            report_notes               TEXT,
            attachments                JSONB         DEFAULT '[]',
            created_at                 TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at                 TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_inspections_contract_id ON inspections(contract_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_inspections_bidder_id ON inspections(bidder_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_inspections_status ON inspections(status)"
    ))

    # ── 6. Replace stub corrective_actions table ──────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS corrective_actions (
            id                    VARCHAR(100)  PRIMARY KEY,
            inspection_id         VARCHAR(100)  REFERENCES inspections(id) DEFERRABLE INITIALLY DEFERRED,
            contract_id           VARCHAR(100)  REFERENCES contracts(id),
            bidder_id             VARCHAR(100)  REFERENCES bidders(id),
            issued_by             VARCHAR(255),
            issued_at             TIMESTAMPTZ,
            deadline              DATE,
            type                  VARCHAR(50)   DEFAULT 'REPLACEMENT',
            description           TEXT,
            status                VARCHAR(50)   DEFAULT 'ISSUED',
            resolved_at           TIMESTAMPTZ,
            vendor_response       TEXT,
            re_inspection_required BOOLEAN      DEFAULT TRUE,
            re_inspection_id      VARCHAR(100)  REFERENCES inspections(id) DEFERRABLE INITIALLY DEFERRED,
            impact_on_payment     TEXT,
            created_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ca_contract_id ON corrective_actions(contract_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ca_inspection_id ON corrective_actions(inspection_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ca_bidder_id ON corrective_actions(bidder_id)"
    ))
    # Now add the circular FK from inspections back to corrective_actions
    conn.execute(sa.text("""
        ALTER TABLE inspections
        ADD CONSTRAINT fk_inspections_ca
        FOREIGN KEY (corrective_action_id)
        REFERENCES corrective_actions(id)
        DEFERRABLE INITIALLY DEFERRED
    """))

    # ── 7. Replace stub vendor_profiles table ────────────────────────────────
    conn.execute(sa.text("DROP TABLE IF EXISTS vendor_profiles CASCADE"))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS vendor_profiles (
            id                          VARCHAR(100)  PRIMARY KEY,
            bidder_id                   VARCHAR(100)  UNIQUE REFERENCES bidders(id),
            bidder_name                 VARCHAR(255),
            gstin                       VARCHAR(15),
            pan                         VARCHAR(10),
            registration_date           DATE,
            total_tenders_participated  INTEGER       DEFAULT 0,
            total_contracts_awarded     INTEGER       DEFAULT 0,
            active_contracts            INTEGER       DEFAULT 0,
            completed_contracts         INTEGER       DEFAULT 0,
            cancelled_contracts         INTEGER       DEFAULT 0,
            avg_compliance_score        NUMERIC(5,2)  DEFAULT 0,
            avg_delivery_delay_days     NUMERIC(5,2)  DEFAULT 0,
            on_time_delivery_rate       INTEGER       DEFAULT 0,
            quality_pass_rate           INTEGER       DEFAULT 0,
            total_complaints            INTEGER       DEFAULT 0,
            verified_complaints         INTEGER       DEFAULT 0,
            penalty_incidents           INTEGER       DEFAULT 0,
            blacklisted                 BOOLEAN       DEFAULT FALSE,
            debarment_status            VARCHAR(50)   DEFAULT 'NONE',
            certifications              TEXT[],
            performance_trend           VARCHAR(50)   DEFAULT 'INSUFFICIENT_DATA',
            risk_signal                 VARCHAR(50)   DEFAULT 'UNKNOWN',
            risk_factors                JSONB         DEFAULT '[]',
            last_updated                TIMESTAMPTZ,
            created_at                  TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at                  TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_vendor_profiles_bidder_id ON vendor_profiles(bidder_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_vendor_profiles_gstin ON vendor_profiles(gstin)"
    ))

    # ── 8. Extend audit — add missing columns ─────────────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE audit ADD COLUMN IF NOT EXISTS actor VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE audit ADD COLUMN IF NOT EXISTS detail TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE audit ADD COLUMN IF NOT EXISTS tender_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE audit ADD COLUMN IF NOT EXISTS bidder_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE audit ADD COLUMN IF NOT EXISTS severity VARCHAR(20) DEFAULT 'info'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE audit ADD COLUMN IF NOT EXISTS rejection_category VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE audit ADD COLUMN IF NOT EXISTS rejection_stage VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE audit ADD COLUMN IF NOT EXISTS rejection_reason TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE audit ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ DEFAULT now()"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_audit_tender_id ON audit(tender_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_audit_bidder_id ON audit(bidder_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_audit_timestamp ON audit(timestamp DESC)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_audit_action ON audit(action)"
    ))

    # ── 9. Extend clarifications — add missing columns ────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS bid_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS requirement_id VARCHAR(100) REFERENCES requirements(id)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS requested_by VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS subject VARCHAR(500)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS message TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS response TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS responded_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS officer_notes TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS severity VARCHAR(20) DEFAULT 'MEDIUM'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE clarifications ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_clarifications_bid_id ON clarifications(bid_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_clarifications_status ON clarifications(status)"
    ))

    # ── 10. Extend evaluation_tasks — add missing columns ─────────────────────
    conn.execute(sa.text(
        "ALTER TABLE evaluation_tasks ADD COLUMN IF NOT EXISTS bid_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE evaluation_tasks ADD COLUMN IF NOT EXISTS bidder_name VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE evaluation_tasks ADD COLUMN IF NOT EXISTS assigned_to_name VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE evaluation_tasks ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'MEDIUM'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE evaluation_tasks ADD COLUMN IF NOT EXISTS due_date TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE evaluation_tasks ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE evaluation_tasks ADD COLUMN IF NOT EXISTS comments TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE evaluation_tasks ADD COLUMN IF NOT EXISTS assigned_to_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_eval_tasks_bid_id ON evaluation_tasks(bid_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_eval_tasks_status ON evaluation_tasks(status)"
    ))

    # ── 11. Extend grievances — add missing columns ───────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS bid_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS submitter_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS submitter_name VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS submitter_role VARCHAR(50)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS supporting_documents JSONB DEFAULT '[]'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'MEDIUM'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS public_note TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS internal_notes JSONB DEFAULT '[]'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS officer_response TEXT"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS response_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE grievances ADD COLUMN IF NOT EXISTS assigned_to_name VARCHAR(255)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_grievances_status ON grievances(status)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_grievances_submitted_at ON grievances(submitted_at DESC)"
    ))

    # ── 12. Extend notifications — add missing columns ────────────────────────
    conn.execute(sa.text(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS recipient_role VARCHAR(50)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS broadcast BOOLEAN DEFAULT FALSE"
    ))
    conn.execute(sa.text(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS tender_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS bid_id VARCHAR(100)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'NORMAL'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ"
    ))
    conn.execute(sa.text(
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS recipient_id VARCHAR(100)"
    ))

    # ── 13. Create compliance_results (NEW) ───────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS compliance_results (
            id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
            bidder_id       VARCHAR(100)  NOT NULL REFERENCES bidders(id),
            requirement_id  VARCHAR(100)  NOT NULL REFERENCES requirements(id),
            tender_id       VARCHAR(100)  REFERENCES tenders(id),
            status          VARCHAR(50)   NOT NULL,
            confidence      NUMERIC(4,3),
            source_doc_id   VARCHAR(100),
            extracted_value TEXT,
            required_value  TEXT,
            found_value     TEXT,
            reason          TEXT,
            concern         TEXT,
            overall_score   INTEGER,
            risk_level      VARCHAR(50),
            analyzed_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
            created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cr_bidder_id ON compliance_results(bidder_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cr_requirement_id ON compliance_results(requirement_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cr_tender_id ON compliance_results(tender_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cr_status ON compliance_results(status)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cr_analyzed_at ON compliance_results(analyzed_at DESC)"
    ))

    # ── 14. Create feedback (NEW) ─────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS feedback (
            id              VARCHAR(100)  PRIMARY KEY,
            tender_id       VARCHAR(100)  REFERENCES tenders(id),
            submitted_by    VARCHAR(100),
            submitter_name  VARCHAR(255),
            category        VARCHAR(100),
            subject         VARCHAR(500),
            description     TEXT,
            priority        VARCHAR(20)   DEFAULT 'LOW',
            status          VARCHAR(50)   DEFAULT 'SUBMITTED',
            submitted_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
            assigned_to     VARCHAR(255),
            public_response TEXT,
            internal_notes  TEXT,
            resolved_at     TIMESTAMPTZ,
            ai_category     VARCHAR(100),
            ai_priority     VARCHAR(20),
            ai_tender_id    VARCHAR(100),
            created_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_feedback_tender_id ON feedback(tender_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_feedback_status ON feedback(status)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_feedback_submitted_at ON feedback(submitted_at DESC)"
    ))

    # ── 15. Create rejection_feedback (NEW) ──────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS rejection_feedback (
            id                  VARCHAR(100)  PRIMARY KEY,
            bidder_id           VARCHAR(100)  REFERENCES bidders(id),
            bidder_name         VARCHAR(255),
            tender_id           VARCHAR(100)  REFERENCES tenders(id),
            officer             VARCHAR(255),
            officer_id          VARCHAR(100),
            decision            VARCHAR(20)   DEFAULT 'DISQUALIFY',
            rejection_stage     VARCHAR(255),
            rejection_category  VARCHAR(255),
            rejection_reason    TEXT,
            officer_remarks     TEXT,
            additional_feedback TEXT,
            feedback_sent_at    TIMESTAMPTZ,
            created_at          TIMESTAMPTZ   NOT NULL DEFAULT now(),
            read_by_bidder      BOOLEAN       DEFAULT FALSE,
            read_at             TIMESTAMPTZ
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_rfb_bidder_id ON rejection_feedback(bidder_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_rfb_tender_id ON rejection_feedback(tender_id)"
    ))

    # ── 16. Create ai_overrides (NEW) ─────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ai_overrides (
            id              VARCHAR(100)  PRIMARY KEY,
            entity_type     VARCHAR(50)   NOT NULL,
            entity_id       VARCHAR(100)  NOT NULL,
            ai_result       VARCHAR(255),
            officer_result  VARCHAR(255)  NOT NULL,
            reason          TEXT          NOT NULL,
            officer         VARCHAR(255),
            overridden_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
            field           VARCHAR(100),
            tender_id       VARCHAR(100),
            bidder_id       VARCHAR(100),
            created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ao_entity ON ai_overrides(entity_type, entity_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ao_bidder_id ON ai_overrides(bidder_id)"
    ))

    # ── 17. Create eval_committees (NEW) ──────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS eval_committees (
            id                VARCHAR(100)  PRIMARY KEY,
            tender_id         VARCHAR(100)  UNIQUE REFERENCES tenders(id),
            members           JSONB         DEFAULT '[]',
            formed_by         VARCHAR(255),
            formed_at         TIMESTAMPTZ,
            updated_at        TIMESTAMPTZ,
            scores            JSONB         DEFAULT '[]',
            status            VARCHAR(50)   DEFAULT 'ACTIVE',
            aggregate_method  VARCHAR(20)   DEFAULT 'AVERAGE',
            created_at        TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_ec_tender_id ON eval_committees(tender_id)"
    ))

    # ── 18. Create conflict_declarations (NEW) ────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS conflict_declarations (
            id              VARCHAR(100)  PRIMARY KEY DEFAULT ('CFLCT-' || substr(md5(random()::text), 1, 6)),
            tender_id       VARCHAR(100)  REFERENCES tenders(id),
            bidder_id       VARCHAR(100)  REFERENCES bidders(id),
            declared_by     VARCHAR(100),
            declared_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
            conflict_type   VARCHAR(100),
            description     TEXT,
            resolved        BOOLEAN       DEFAULT FALSE,
            resolved_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cd_tender_id ON conflict_declarations(tender_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_cd_bidder_id ON conflict_declarations(bidder_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()

    # Drop new tables in reverse FK order
    conn.execute(sa.text("DROP TABLE IF EXISTS conflict_declarations CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS eval_committees CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS ai_overrides CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS rejection_feedback CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS feedback CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS compliance_results CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS corrective_actions CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS inspections CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS vendor_profiles CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS contracts CASCADE"))
    conn.execute(sa.text("DROP TABLE IF EXISTS bids CASCADE"))

    # Recreate original stub bids table
    conn.execute(sa.text("""
        CREATE TABLE bids (
            id           UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
            tender_id    VARCHAR(100) REFERENCES tenders(id),
            bidder_id    VARCHAR(100) REFERENCES bidders(id),
            stage        VARCHAR(50) DEFAULT 'draft',
            technical_score NUMERIC(5,2),
            financial_score NUMERIC(5,2),
            total_score  NUMERIC(5,2),
            submitted_at TIMESTAMPTZ,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX ix_bids_tender_id ON bids(tender_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX ix_bids_bidder_id ON bids(bidder_id)"
    ))

    # Recreate original stub contracts table
    conn.execute(sa.text("""
        CREATE TABLE contracts (
            id         VARCHAR(100) PRIMARY KEY,
            tender_id  VARCHAR(100) REFERENCES tenders(id),
            bidder_id  VARCHAR(100) REFERENCES bidders(id),
            title      VARCHAR(500),
            value      BIGINT,
            start_date DATE,
            end_date   DATE,
            status     VARCHAR(50) DEFAULT 'active',
            milestones JSONB DEFAULT '[]',
            inspections JSONB DEFAULT '[]',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))

    # Recreate original stub inspections table
    conn.execute(sa.text("""
        CREATE TABLE inspections (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            contract_id VARCHAR(100) REFERENCES contracts(id),
            data        JSONB NOT NULL DEFAULT '{}',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX ix_inspections_contract_id ON inspections(contract_id)"
    ))

    # Recreate original stub corrective_actions table
    conn.execute(sa.text("""
        CREATE TABLE corrective_actions (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            contract_id   VARCHAR(100) REFERENCES contracts(id),
            inspection_id UUID REFERENCES inspections(id),
            data          JSONB NOT NULL DEFAULT '{}',
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX ix_corrective_actions_contract_id ON corrective_actions(contract_id)"
    ))

    # Recreate original stub vendor_profiles table
    conn.execute(sa.text("""
        CREATE TABLE vendor_profiles (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            bidder_id  VARCHAR(100) REFERENCES bidders(id),
            data       JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX ix_vendor_profiles_bidder_id ON vendor_profiles(bidder_id)"
    ))

    # Note: Column removals on tenders/bidders/audit/clarifications/evaluation_tasks/
    # grievances/notifications are not reversed in downgrade to preserve data safety.
