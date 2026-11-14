# Subject-Based Tender Classification — Implementation Report

## What Was Changed and Why

The Veritas AI tender classification system previously used 12 broad industry categories (Civil Works, IT & Software, Electrical & Power, etc.). These broad categories made it impossible for a procurement officer to filter by the actual subject of procurement — for example, finding all steel furniture tenders or all CCTV installation tenders in one click.

### Changes Made

| File | Change |
|---|---|
| `backend/services/classification_service.py` | Fully rewritten with 44 subject-specific classifications and 42 priority-ordered keyword rules |
| `backend/data/tenders.json` | Cleaned (removed 2 test stubs + 12 old synthetic tenders); GEM-DEMO-2026-001 updated; 15 new subject-diverse synthetic tenders added |
| `backend/routes/tenders.py` | `GET /api/tenders/classifications` route updated to return `{key, label, count}` array |
| `frontend/src/pages/Tenders.jsx` | Hardcoded `SHORT_LABELS` / `CLASSIFICATION_COLORS` removed; filter pills now built from API response |
| `docs/subject-based-tender-classification-report.md` | This report |

### Why subject-based?

A procurement officer must be able to answer: "Show me all steel furniture tenders", "Show me all solar panel installation tenders". Broad category tags (IT, Civil Works) cannot support this. Subject-based tags answer the question: **What is being procured?**

---

## New SUBJECT_CLASSIFICATIONS Taxonomy

| Key | Display Label | Category |
|---|---|---|
| STEEL_FURNITURE | Steel Furniture | Furniture |
| WOODEN_FURNITURE | Wooden Furniture | Furniture |
| OFFICE_FURNITURE | Office Furniture | Furniture |
| SCHOOL_FURNITURE | School Furniture | Furniture |
| HOSPITAL_FURNITURE | Hospital Furniture | Furniture |
| ROAD_CONSTRUCTION | Road Construction | Roads & Civil |
| ROAD_REPAIR | Road Repair & Maintenance | Roads & Civil |
| BRIDGE_CONSTRUCTION | Bridge Construction | Roads & Civil |
| BUILDING_CONSTRUCTION | Building Construction | Roads & Civil |
| BUILDING_RENOVATION | Building Renovation | Roads & Civil |
| DRAINAGE_WORK | Drainage & Stormwater Work | Roads & Civil |
| COMPUTER_SUPPLY | Computer & Laptop Supply | IT & Technology |
| NETWORKING_EQUIPMENT | Networking Equipment | IT & Technology |
| CCTV_INSTALLATION | CCTV & Surveillance Installation | IT & Technology |
| SOFTWARE_DEVELOPMENT | Software Development | IT & Technology |
| IT_INFRASTRUCTURE | IT Infrastructure | IT & Technology |
| CYBERSECURITY | Cybersecurity Services | IT & Technology |
| ELECTRICAL_EQUIPMENT | Electrical Equipment Supply | Electrical & Energy |
| ELECTRICAL_INSTALLATION | Electrical Installation | Electrical & Energy |
| ELECTRICAL_MAINTENANCE | Electrical Maintenance | Electrical & Energy |
| SOLAR_INSTALLATION | Solar Panel Installation | Electrical & Energy |
| STREET_LIGHTING | Street Lighting | Electrical & Energy |
| TRANSFORMER_SUPPLY | Transformer Supply | Electrical & Energy |
| MEDICAL_EQUIPMENT | Medical Equipment | Healthcare |
| LABORATORY_EQUIPMENT | Laboratory Equipment | Healthcare |
| MEDICINE_SUPPLY | Medicine & Drug Supply | Healthcare |
| MEDICAL_CONSUMABLES | Medical Consumables | Healthcare |
| WATER_PIPELINE | Water Pipeline Work | Water & Sanitation |
| WATER_TANK | Water Tank Construction | Water & Sanitation |
| WATER_TREATMENT | Water Treatment Equipment | Water & Sanitation |
| SEWAGE_WORK | Sewage & Drainage Work | Water & Sanitation |
| SANITATION_SERVICES | Sanitation Services | Water & Sanitation |
| VEHICLE_SUPPLY | Vehicle Supply | Transportation |
| VEHICLE_MAINTENANCE | Vehicle Maintenance | Transportation |
| TRANSPORT_SERVICES | Transport Services | Transportation |
| INDUSTRIAL_IOT | Industrial IoT & Monitoring Equipment | Industrial Equipment |
| INDUSTRIAL_MACHINERY | Industrial Machinery | Industrial Equipment |
| SAFETY_EQUIPMENT | Safety Equipment | Industrial Equipment |
| OFFICE_SUPPLIES | Office Supplies & Stationery | General Supplies & Services |
| SECURITY_SERVICES | Security Services | General Supplies & Services |
| HOUSEKEEPING | Housekeeping & Facility Management | General Supplies & Services |
| CONSULTANCY | Consultancy Services | General Supplies & Services |
| TRAINING | Training & Capacity Building | General Supplies & Services |
| OTHER | Other / Unclassified | Other |

---

## Classification of GEM-DEMO-2026-001

| Field | Value |
|---|---|
| Tender ID | GEM-DEMO-2026-001 |
| Title | Supply and Installation of Industrial IoT Monitoring Equipment |
| Previous Classification | MECHANICAL_INDUSTRIAL |
| New Classification | **INDUSTRIAL_IOT** |
| Confidence | 0.95 |
| Procurement Type | Goods |

**Rationale:** The tender title and description explicitly state: "Industrial IoT Monitoring Equipment including sensors, gateways, and monitoring software for government industrial facilities." This matches Rule 1 (highest priority):

- IoT keywords present: `iot`, `sensor`, `gateway`
- Industrial/monitoring keywords present: `monitoring`, `industrial`

The old classification `MECHANICAL_INDUSTRIAL` was a broad category that lumped IoT equipment with boilers, pumps and lathes. The new `INDUSTRIAL_IOT` is specific to what is actually being procured.

All original fields (bidder_ids, requirement_ids, prebid_questions, corrigenda, prebid_meeting, policy, workflow_stage, etc.) were preserved exactly.

---

## 15 Synthetic Tenders — Subject Classifications

| # | Tender ID | Title (abbreviated) | Classification | Procurement Type |
|---|---|---|---|---|
| S-01 | CPWD/EE-III/2026/078 | Supply of Steel Office Tables, Chairs and Storage Racks | STEEL_FURNITURE | Goods |
| S-02 | NHAI/NH-48/2026/RC/112 | Construction of New 4-Lane Highway on NH-48 Bypass | ROAD_CONSTRUCTION | Works |
| S-03 | PWD/MH/2026/RR/045 | Repair and Resurfacing of Potholed Sections on SH-27 | ROAD_REPAIR | Works |
| S-04 | NIC/TENDER/2026/IT/045 | Supply of Desktop Computers and Laptops | COMPUTER_SUPPLY | Goods |
| S-05 | CISF/HQ/2026/CCTV/033 | Supply and Installation of IP-Based CCTV Surveillance | CCTV_INSTALLATION | Goods |
| S-06 | NIC/TENDER/2026/SW/061 | Development of Integrated e-District Portal | SOFTWARE_DEVELOPMENT | Services |
| S-07 | ESIC/HQ/2026/MED/023 | Supply and Installation of Diagnostic Medical Equipment | MEDICAL_EQUIPMENT | Goods |
| S-08 | MNRE/RESCO/2026/SOL/019 | Installation of Rooftop Solar Photovoltaic Systems | SOLAR_INSTALLATION | Works |
| S-09 | JNURM/2026/WP/031 | Construction of Water Supply Distribution Pipeline Network | WATER_PIPELINE | Works |
| S-10 | AAI/CHE/2026/ELEC/AMC/017 | Annual Maintenance Contract for HT/LT Electrical Systems | ELECTRICAL_MAINTENANCE | Services |
| S-11 | MCD/TR/2026/VEH/008 | Supply of Refuse Collection Vehicles and Dump Trucks | VEHICLE_SUPPLY | Goods |
| S-12 | CPWD/EE-V/2026/BC/091 | Construction of New Office Complex for Income Tax Dept | BUILDING_CONSTRUCTION | Works |
| S-13 | DGS/RC/2026/OS/055 | Rate Contract for Supply of Office Stationery | OFFICE_SUPPLIES | Goods |
| S-14 | DRDO/HQ/2026/SEC/044 | Provision of Unarmed Security Guard Services at DRDO | SECURITY_SERVICES | Services |
| S-15 | NITI/2026/CON/012 | Consultancy for State-Level EV Transition Roadmap | CONSULTANCY | Consultancy |

Each synthetic tender covers a different subject classification to demonstrate the breadth of the new taxonomy.

---

## How the Filter System Works End-to-End

### 1. API — `GET /api/tenders/classifications`

The backend reads `tenders.json`, counts how many tenders have each classification key, and returns only classifications with count ≥ 1:

```json
{
  "classifications": [
    {"key": "INDUSTRIAL_IOT", "label": "Industrial IoT & Monitoring Equipment", "count": 1},
    {"key": "STEEL_FURNITURE", "label": "Steel Furniture", "count": 1},
    ...
  ],
  "total": 16
}
```

Classifications with zero tenders are excluded so the filter bar stays clean.

### 2. Frontend — Classification Pills

`Tenders.jsx` calls `getClassifications()` on mount and stores the result in `classificationList` state. It renders one pill per entry. Each pill shows the subject label and a count badge.

When a pill is clicked, `classificationFilter` is set to the classification key (e.g. `"STEEL_FURNITURE"`). Clicking again clears the filter.

### 3. API — `GET /api/tenders?classification=STEEL_FURNITURE`

The list endpoint filters the in-memory tenders array by `t.get('classification') === filter_classification`. Only matching tenders are returned.

### 4. Badge on Tender Cards

Each tender card looks up its classification label from `classificationList` by key. If not found in the list (e.g. for a new tender not yet classified), it falls back to `tender.classification_name` then to the raw key string. Badge color is neutral `bg-blue-50 text-blue-700` for all subjects.

---

## Build / Import Verification Results

```
# Backend import check
python -c "import routes.tenders; import services.classification_service; print('OK')"
# Result: OK

# Frontend build
npm run build
# Result: 0 errors, build completed successfully
```

The `CLASSIFICATION_LABELS` and `CLASSIFICATIONS` names in `classification_service.py` are preserved as aliases to `SUBJECT_CLASSIFICATIONS` and `list(SUBJECT_CLASSIFICATIONS.keys())` respectively, so all existing imports in `routes/tenders.py` and elsewhere continue to work without change.

*Content was rephrased for compliance with licensing restrictions.*
