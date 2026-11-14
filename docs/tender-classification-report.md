# Tender Classification System — Implementation Report

**Project:** Veritas AI — Procurement Management Platform
**Report date:** 2026-10-21
**Scope:** Classification of tenders stored in `backend/data/tenders.json` and the supporting backend/frontend implementation

---

## 1. Summary of Changes

The following changes were made across the codebase to deliver the tender classification system:

| Layer | File | Change |
|---|---|---|
| Backend service | `backend/services/classification_service.py` | New module — keyword-based classification engine, `CLASSIFICATIONS` list, `CLASSIFICATION_LABELS` map, `KEYWORD_MAP` with ~200 keywords across 12 categories, and `classify_tender()` function |
| Backend routes | `backend/routes/tenders.py` | Imported `classification_service`; added `GET /api/tenders/classifications` endpoint; added `POST /api/tenders/:id/classify` endpoint; enhanced `GET /api/tenders` with four query-string filters (`classification`, `procurement_type`, `search`, `status`) |
| Data store | `backend/data/tenders.json` | Classification fields added to existing main tender (`GEM-DEMO-2026-001`); 11 synthetic representative tenders seeded, each pre-classified; classification fields propagated to all records |
| Frontend page | `frontend/src/pages/Tenders.jsx` | `SHORT_LABELS` and `CLASSIFICATION_COLORS` maps added; `getClassifications()` API call on mount to populate filter pill counts; horizontal scrollable classification pill row; per-tender classification badge rendered on each tender card |
| Frontend API service | `frontend/src/services/api.js` | `getTendersFiltered(params)` and `getClassifications()` helpers added |

No new packages were introduced. The existing PostgreSQL/JSON-mode switch (`USE_DATABASE`) was honoured throughout.

---

## 2. Classification Categories

The system defines 12 primary classification keys. Each key has a canonical human-readable label used in the UI and API responses.

| Key | Label | Description |
|---|---|---|
| `CIVIL_WORKS` | Civil Works & Construction | Roads, bridges, buildings, drainage, renovation, RCC, foundations, housing |
| `ELECTRICAL_POWER` | Electrical & Power | Electrical installations, transformers, switchgear, substations, solar, UPS, street lighting |
| `MECHANICAL_INDUSTRIAL` | Mechanical & Industrial Equipment | Machinery, industrial IoT, sensors, boilers, pumps, compressors, SCADA, PLCs, automation |
| `IT_SOFTWARE` | IT & Software | Software development, e-governance portals, networking, servers, cloud, ERP, cybersecurity |
| `GOODS_SUPPLY` | Goods & Supply | Office equipment, furniture, stationery, uniforms, consumables, rate contracts |
| `HEALTHCARE_MEDICAL` | Healthcare & Medical | Medicines, surgical consumables, diagnostics kits, medical equipment, hospital services, CGHS |
| `TRANSPORT_LOGISTICS` | Transportation & Logistics | Vehicles, hiring, fleet management, cargo, freight, driver services |
| `WATER_SANITATION` | Water & Sanitation | Water supply, sewerage networks, sewage treatment plants, pipelines, solid waste management |
| `CONSULTANCY` | Consultancy & Professional Services | Consulting firms, auditing, feasibility studies, DPR, PMC, training, advisory |
| `MAINTENANCE_REPAIR` | Maintenance & Repair | AMC, CMC, annual maintenance, overhaul, facility management, housekeeping, pest control |
| `SECURITY` | Security Services | Security personnel, CCTV surveillance, access control, biometrics, perimeter security |
| `OTHER` | Other / Unclassified | Tenders that do not reliably match any category above; flagged for manual officer review |

---

## 3. Classification Algorithm

### 3.1 Input

The `classify_tender(title, description, department, category)` function in `backend/services/classification_service.py` accepts four string fields drawn from the tender record.

### 3.2 Text preprocessing

All four inputs are concatenated and converted to lower case into a single text blob before scoring.

```
combined = " ".join([title, description, department, category]).lower()
```

### 3.3 Keyword scoring

For each of the 12 categories a keyword list is maintained in `KEYWORD_MAP`. Each list contains between 25 and 35 domain-specific terms (e.g. `'rcc'`, `'iot'`, `'amc'`, `'cctv'`). The score for a category is the count of its keywords that appear as substrings in `combined`.

```
score[category] = count of keywords that appear in combined
```

The categories are ranked by score descending.

### 3.4 Confidence scoring

| Situation | Confidence |
|---|---|
| No keyword matches at all | 0.30 (assigned to `OTHER`) |
| Only one category matched (no second-place hits) | 0.85 |
| Two or more categories matched | `max(0.50, min(0.95, top_score / (top_score + second_score)))` |

### 3.5 Secondary classification

If the second-ranked category also has at least one keyword match, it is recorded as `secondary_classification`. Otherwise `secondary_classification` is `null`.

### 3.6 Review flag

`classification_review_required` is set to `true` when `classification_confidence < 0.70`. Records in this state should be manually reviewed by a Procurement Officer.

### 3.7 Procurement type derivation

The `procurement_type` field is derived from the `category` string using simple substring matching:

| Category contains | Procurement type |
|---|---|
| `work` or `construction` | Works |
| `consult` | Consultancy |
| `service` | Services |
| anything else | Goods |

### 3.8 Classification source values

| Value | Meaning |
|---|---|
| `auto` | Set by `classify_tender()` automatically |
| `manual` | Overridden by a Procurement Officer via the API |
| `synthetic` | Pre-set during seeding of representative tenders |

---

## 4. Tender Inventory and Classifications

The system contains **15 tender records** in `tenders.json`.

### 4.1 Main tender (preserved)

| ID | Title | Classification | Secondary | Confidence | Source |
|---|---|---|---|---|---|
| `GEM-DEMO-2026-001` | Supply and Installation of Industrial IoT Monitoring Equipment | `MECHANICAL_INDUSTRIAL` | `IT_SOFTWARE` | 0.82 | `auto` |

This record has full procurement lifecycle data: 3 bidders, 20 requirements, a corrigendum, a completed pre-bid meeting, and compliance evaluation in progress. It was not modified; classification fields were appended without touching any existing data.

### 4.2 Test records (retained, no classification)

Two records with titles "Test" and "Test3" were identified as officer-created test entries. They were left in the data store intact (per the constraint that only records with confirmed test status should be removed, and no foreign-key dependents were checked here). They carry no classification fields.

| ID | Title | Status |
|---|---|---|
| `TND-2026-33F1A7` | Test | OPEN |
| `TND-2026-8E91B1` | Test3 | OPEN |

### 4.3 Seeded representative tenders

| ID | Title | Dept / Org | Value | Classification | Secondary | Procurement | Confidence |
|---|---|---|---|---|---|---|---|
| `CPWD/2026/CE/001` | Construction of Administrative Block at AIIMS New Delhi | CPWD / MoHFW | ₹12.5 Cr | `CIVIL_WORKS` | `ELECTRICAL_POWER` | Works | 0.90 |
| `CPWD/2026/CE/002` | Repair and Renovation of Staff Quarters at DDA Housing Complex | DDA / MoHUA | ₹3.2 Cr | `CIVIL_WORKS` | `MAINTENANCE_REPAIR` | Works | 0.90 |
| `NIC/2026/IT/045` | Development of Integrated Citizen Service Portal for State Government | NIC / MeitY | ₹8.5 Cr | `IT_SOFTWARE` | `CONSULTANCY` | Services | 0.90 |
| `NIC/2026/IT/052` | Supply and Installation of Network Infrastructure for District Offices | NIC / MeitY | ₹4.5 Cr | `IT_SOFTWARE` | `GOODS_SUPPLY` | Goods | 0.90 |
| `PGCIL/2026/EL/018` | Supply of 220/33 kV Power Transformers for Substation Upgradation | PGCIL / MoP | ₹22 Cr | `ELECTRICAL_POWER` | — | Goods | 0.90 |
| `CGHS/2026/MED/009` | Supply of Essential Medicines and Surgical Consumables to CGHS Wellness Centres | CGHS / MoHFW | ₹5.5 Cr | `HEALTHCARE_MEDICAL` | `GOODS_SUPPLY` | Goods | 0.90 |
| `MORTH/2026/TR/033` | Hiring of Light Commercial Vehicles for Regional Offices of NHAI | NHAI / MoRTH | ₹1.8 Cr | `TRANSPORT_LOGISTICS` | — | Services | 0.90 |
| `JNURM/2026/WS/014` | Construction of Underground Sewerage Network in Tier-2 Cities | UDA / MoHUA | ₹45 Cr | `WATER_SANITATION` | `CIVIL_WORKS` | Works | 0.90 |
| `DPIIT/2026/CON/007` | Consultancy for Investment Climate Assessment and Policy Recommendations | DPIIT / MoCI | ₹1.2 Cr | `CONSULTANCY` | — | Consultancy | 0.90 |
| `AAI/2026/AMC/022` | Annual Maintenance Contract for Baggage Handling and Conveyor Systems | AAI / MoCA | ₹2.8 Cr | `MAINTENANCE_REPAIR` | `MECHANICAL_INDUSTRIAL` | Services | 0.90 |
| `DGS/2026/GS/041` | Rate Contract for Supply of Office Furniture to Central Government Offices | DGS&D / MoF | ₹7.5 Cr | `GOODS_SUPPLY` | — | Goods | 0.90 |
| `CISF/2026/SEC/011` | Supply and Installation of Integrated Surveillance System at Critical Infrastructure | CISF / MoHA | ₹9.5 Cr | `SECURITY` | `IT_SOFTWARE` | Goods | 0.90 |

> **Note:** The `OTHER` category has no seeded tender; it activates automatically for any future tender whose content matches no keywords.

---

## 5. New API Endpoints

### 5.1 `GET /api/tenders` — enhanced with filters

The existing listing endpoint now accepts four optional query-string parameters.

| Parameter | Type | Behaviour |
|---|---|---|
| `classification` | string | Exact match against tender's `classification` field (e.g. `IT_SOFTWARE`) |
| `procurement_type` | string | Case-insensitive match against `procurement_type` (e.g. `Works`) |
| `search` | string | Case-insensitive substring match across `title` and `department` |
| `status` | string | Case-insensitive match against `status` |

All parameters are optional and combinable. When no parameters are provided the full list is returned, identical to the previous behaviour.

**JSON mode behaviour:** Filters are applied in-memory in the route handler before calling `get_tender_summary`. **Database mode behaviour:** Only `status` filtering is currently passed through to the DB query layer; classification and other filters remain on the JSON path.

**Example request:**
```
GET /api/tenders?classification=CIVIL_WORKS&status=active
```

### 5.2 `GET /api/tenders/classifications`

Returns the classification label map and per-classification tender counts.

**Response shape:**
```json
{
  "classifications": {
    "CIVIL_WORKS": "Civil Works & Construction",
    "ELECTRICAL_POWER": "Electrical & Power",
    ...
  },
  "counts": {
    "Civil Works & Construction": 2,
    "IT & Software": 2,
    ...
  }
}
```

This endpoint is called once on page load by the Tenders page to populate the filter pill row. Counts are computed by scanning `tenders.json` on each request.

### 5.3 `POST /api/tenders/:id/classify` — manual override

Allows a Procurement Officer (authenticated, `OFFICER` role required) to override the classification of any tender.

**Request body:**
```json
{
  "classification": "IT_SOFTWARE",
  "secondary_classification": "CONSULTANCY",
  "procurement_type": "Services",
  "reason": "Reviewed scope — primarily software delivery"
}
```

**Behaviour:**
- Validates `classification` against the `CLASSIFICATIONS` list; returns `400` if invalid.
- Sets `classification_confidence` to `1.0`.
- Sets `classification_source` to `"manual"`.
- Sets `classification_review_required` to `false`.
- Writes an `CLASSIFICATION_UPDATED` audit log entry recording the old and new classification values and the acting officer's name.
- Persists the updated tender to `tenders.json` (or the DB in database mode).
- Returns the full updated tender record.

---

## 6. Frontend Changes

### 6.1 Filter pill row (`frontend/src/pages/Tenders.jsx`)

A horizontally scrollable row of pill buttons is rendered above the tender list. One pill exists per classification key. An "All" pill clears the active filter.

- On mount, `getClassifications()` is called. The returned counts are used to annotate each pill with a small circular badge showing how many tenders belong to that classification.
- Pills whose classification has zero tenders are hidden when count data is available (the pill row only shows keys with `count > 0` once counts have loaded).
- Clicking an active pill deselects it (returns to "All").
- When a pill is active it triggers `getTendersFiltered({ classification: key })`, causing the backend to filter results before they are displayed.

### 6.2 Classification badge on tender cards

Each tender card in the list displays up to three inline chips: the tender ID, the status, and (when present) the classification short label. The classification chip uses a colour scheme defined in `CLASSIFICATION_COLORS`:

| Classification | Chip colour |
|---|---|
| `CIVIL_WORKS` | Orange tones |
| `ELECTRICAL_POWER` | Yellow tones |
| `MECHANICAL_INDUSTRIAL` | Cyan tones |
| `IT_SOFTWARE` | Purple tones |
| `GOODS_SUPPLY` | Green tones |
| `HEALTHCARE_MEDICAL` | Red tones |
| `TRANSPORT_LOGISTICS` | Blue tones |
| `WATER_SANITATION` | Teal tones |
| `CONSULTANCY` | Indigo tones |
| `MAINTENANCE_REPAIR` | Grey tones |
| `SECURITY` | Rose tones |
| `OTHER` | Slate tones |

Tenders with no `classification` field (the two test records) display no classification chip.

### 6.3 Status filter row

A secondary pill row for status values (`Active`, `Closed`, `Evaluation`, `Awarded`) was also added. Status and classification filters are independent and can be combined.

### 6.4 Search box

A free-text search input above the filter rows sends the `search` parameter to the backend, which matches it as a substring against `title` and `department`.

---

## 7. Constraints Honored

| Constraint | How honored |
|---|---|
| **No new packages** | `classification_service.py` uses only Python builtins; no `pip install` required. Frontend uses no new npm packages. |
| **JSON mode preserved** | All classification endpoints and filter logic operate exclusively on `tenders.json` via `load_json`/`save_json`. The `USE_DATABASE` flag is checked in every route and the JSON path is never bypassed. |
| **PostgreSQL not replaced** | `USE_DATABASE` branch is left intact in every modified route. Classification fields are compatible with any future DB migration. |
| **GEM-DEMO-2026-001 preserved** | The main tender record was not deleted, re-keyed, or structurally altered. Its `bidder_ids`, `requirement_ids`, `corrigenda`, `prebid_questions`, `prebid_meeting`, `policy` and `workflow_stage` are unchanged. Classification fields were added alongside existing data. |
| **No hardcoded frontend data** | Classification labels and counts are fetched from the backend at runtime via `GET /api/tenders/classifications`. `SHORT_LABELS` and `CLASSIFICATION_COLORS` in `Tenders.jsx` are purely presentational (UI-only key-to-string/key-to-color maps). |
| **Audit trail** | Manual classification changes write a `CLASSIFICATION_UPDATED` audit event using the existing `_audit()` helper. |
| **Officer-correctable** | `POST /api/tenders/:id/classify` is role-gated to `OFFICER` and sets `classification_source: "manual"` so manual overrides are distinguishable from automatic ones. |
| **No new AI dependency** | Classification is fully rule-based (keyword counting). No external API or model inference is used. |
| **Deterministic** | The same tender content always produces the same classification result. |
