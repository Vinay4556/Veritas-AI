# Veritas AI Demo Seed Data Report

Generated: 2026-08-23  
Tender: **GEM-DEMO-2026-001** — Supply and Installation of Industrial IoT Monitoring Equipment (Est. Rs 4.8 Crore)

---

## What Was Seeded

All data lives in `backend/data/*.json`. The app runs in JSON file mode (`USE_DATABASE=False`).

| File | Records | Key Notes |
|---|---|---|
| `documents.json` | 25 docs | 10 for BID-SUB-001, 3 for BID-SUB-002, 12 for BID-SUB-003 |
| `compliance.json` | 3 bidder entries | Keyed by bidder_id; all 20 requirements scored per bidder |
| `bidders.json` | 3 bidders | status=analyzed, compliance_score and risk_level set |
| `bids.json` | 3 bids | status=COMPLIANCE_REVIEW, quoted prices, EMD details |
| `feedback.json` | 7 entries | FB-2026-0001 to FB-2026-0007 |
| `grievances.json` | 3 entries | GRV-2026-001 (EMD), GRV-2026-002 (OEM scope), GRV-2026-003 (ISO flag) |
| `clarifications.json` | 4 entries | CLR-001 (ISO cert), CLR-002 (MSME), CLR-003 (delivery), CLR-004 (OEM name) |
| `audit.json` | 18 entries | AUD-2026-001 to AUD-2026-018, full timeline |
| `notifications.json` | 8 entries | NOTIF-001 to NOTIF-008 |

---

## Compliance Score Derivation

### Scoring Formula

```
MANDATORY_WEIGHT = 5
OPTIONAL_WEIGHT  = 2
Total mandatory reqs = 16  → max mandatory weight = 80
Total optional reqs  =  4  → max optional weight  =  8
Total weight = 88

VERIFIED  → full weight
REVIEW    → 50% weight
NON_COMPLIANT / MISSING → 0

overall_score = round(satisfied_weight / 88 * 100)

Risk:
  score >= 85 AND NON_COMPLIANT == 0  → LOW
  score >= 70 AND NON_COMPLIANT <= 1  → MEDIUM
  else                                → HIGH
```

### BID-SUB-001 — ABC Technologies Pvt Ltd

| Status | REQs | Weight per req | Subtotal |
|---|---|---|---|
| VERIFIED (mandatory) | REQ-001,002,004,005,007,008,010,011,012,016,017,019 (×12) | 5 | 60 |
| VERIFIED (optional)  | — | — | 0 |
| REVIEW (mandatory)   | REQ-006 (ISO, expired), REQ-009 (OEM name mismatch) | 2.5 | 5 |
| MISSING (mandatory)  | REQ-013 (solvency), REQ-014 (BIS/CE) | 0 | 0 |
| MISSING (optional)   | REQ-003, REQ-015, REQ-018, REQ-020 | 0 | 0 |

Satisfied weight = 60 + 5 = **65**  
Score = round(65/88×100) = **80** → `MEDIUM` (0 NON_COMPLIANT, score < 85)

Notable flags:
- REQ-006 REVIEW: ISO 9001 cert expired Jan 2025. Bidder confirmed renewal in progress (CLR-001 responded).
- REQ-009 REVIEW: OEM auth entity name "ABC Technology Solutions" vs registered "ABC Technologies" (CLR-004 pending).

### BID-SUB-002 — Bharat Industrial Systems Pvt Ltd

| Status | REQs | Weight | Subtotal |
|---|---|---|---|
| VERIFIED (mandatory) | REQ-001, REQ-002, REQ-017 (×3) | 5 | 15 |
| REVIEW (mandatory)   | REQ-019 (EMD short Rs 9L) | 2.5 | 2.5 |
| NON_COMPLIANT        | REQ-004 (turnover Rs 6.2Cr < Rs 10Cr) | 0 | 0 |
| MISSING              | 15 reqs | 0 | 0 |

Satisfied weight = 15 + 2.5 = **17.5**  
Score = round(17.5/88×100) = **20** → `HIGH` (1 NON_COMPLIANT)

Notable flags:
- REQ-004 NON_COMPLIANT: Avg turnover Rs 6.2 Cr below mandatory Rs 10 Cr threshold.
- REQ-019 REVIEW: EMD Rs 15L submitted vs Rs 24L required. Grievance GRV-2026-001 filed.
- Only 3 docs submitted; 15 requirements have no document coverage.

### BID-SUB-003 — Nova Engineering Solutions Pvt Ltd

| Status | REQs | Weight | Subtotal |
|---|---|---|---|
| VERIFIED (mandatory) | REQ-001,002,004,005,007,008,009,010,011,012,013,016,017,019 (×14) | 5 | 70 |
| VERIFIED (optional)  | REQ-003 (Udyam), REQ-015 (ISO27001) (×2) | 2 | 4 |
| REVIEW (mandatory)   | REQ-006 (ISO cert name variation) | 2.5 | 2.5 |
| MISSING (mandatory)  | REQ-014 (BIS/CE) | 0 | 0 |
| MISSING (optional)   | REQ-018 (AMC), REQ-020 (NABL) | 0 | 0 |

Satisfied weight = 70 + 4 + 2.5 = **76.5**  
Score = round(76.5/88×100) = **87** → `LOW` (0 NON_COMPLIANT, score ≥ 85)

Notable flags:
- REQ-006 REVIEW: ISO cert entity name uses "Private Limited" vs "Pvt Ltd" in other docs. Certificate is valid to Feb 2027.
- REQ-013 VERIFIED: Net worth Rs 12.5 Cr confirmed from audited financials.

---

## Document Coverage Summary

| Bidder | Docs | Classifications |
|---|---|---|
| BID-SUB-001 | 10 | GST, PAN, ISO9001, FINANCIAL, EXPERIENCE, EPFO, ESIC, OEM, DECLARATION, INCORPORATION |
| BID-SUB-002 | 3 | GST, PAN, FINANCIAL |
| BID-SUB-003 | 12 | GST, PAN, ISO9001, FINANCIAL, EXPERIENCE, EPFO, ESIC, OEM, DECLARATION, INCORPORATION, ISO27001, UDYAM |

All documents point to 5 real sample PDF files in `backend/`:
- `sample_gst_certificate.pdf`
- `sample_pan_card.pdf`
- `sample_iso9001_certificate.pdf`
- `sample_financial_statement.pdf`
- `sample_experience_certificate.pdf`

Multiple document records reuse the same physical file with different `classification` and `requirement_id` values to simulate diverse document uploads.

---

## User → Bidder Mapping

| Email | Role | Bidder ID |
|---|---|---|
| officer@demo.gov | OFFICER (USR-001, Rajesh Kumar) | — |
| bidder@demo.com | BIDDER | BID-SUB-001 (ABC Technologies) |
| bidder2@demo.com | BIDDER | BID-SUB-002 (Bharat Industrial) |
| tenders@novaengineering.co.in | BIDDER | BID-SUB-003 (Nova Engineering) |
| citizen@demo.com | STAKEHOLDER (USR-003, Priya Sharma) | — |

---

## Backend Restart Required

The backend caches data in memory from the JSON files at startup. After seeding, restart the backend to reload all JSON files:

```bash
# From the workspace root
cd backend
python app.py
# or via start.bat
```

Any in-memory state (compliance results, document lists, bid objects) will be replaced with the seeded data on next startup. No cache-busting endpoint is needed in JSON file mode.
