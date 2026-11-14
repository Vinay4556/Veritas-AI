"""
classification_service.py — Subject-based tender classification.
Classifies by WHAT is being procured, not which department is buying.
"""

SUBJECT_CLASSIFICATIONS = {
    # Furniture
    "STEEL_FURNITURE": "Steel Furniture",
    "WOODEN_FURNITURE": "Wooden Furniture",
    "OFFICE_FURNITURE": "Office Furniture",
    "SCHOOL_FURNITURE": "School Furniture",
    "HOSPITAL_FURNITURE": "Hospital Furniture",
    # Roads & Civil
    "ROAD_CONSTRUCTION": "Road Construction",
    "ROAD_REPAIR": "Road Repair & Maintenance",
    "BRIDGE_CONSTRUCTION": "Bridge Construction",
    "BUILDING_CONSTRUCTION": "Building Construction",
    "BUILDING_RENOVATION": "Building Renovation",
    "DRAINAGE_WORK": "Drainage & Stormwater Work",
    # IT & Technology
    "COMPUTER_SUPPLY": "Computer & Laptop Supply",
    "NETWORKING_EQUIPMENT": "Networking Equipment",
    "CCTV_INSTALLATION": "CCTV & Surveillance Installation",
    "SOFTWARE_DEVELOPMENT": "Software Development",
    "IT_INFRASTRUCTURE": "IT Infrastructure",
    "CYBERSECURITY": "Cybersecurity Services",
    # Electrical & Energy
    "ELECTRICAL_EQUIPMENT": "Electrical Equipment Supply",
    "ELECTRICAL_INSTALLATION": "Electrical Installation",
    "ELECTRICAL_MAINTENANCE": "Electrical Maintenance",
    "SOLAR_INSTALLATION": "Solar Panel Installation",
    "STREET_LIGHTING": "Street Lighting",
    "TRANSFORMER_SUPPLY": "Transformer Supply",
    # Healthcare
    "MEDICAL_EQUIPMENT": "Medical Equipment",
    "LABORATORY_EQUIPMENT": "Laboratory Equipment",
    "MEDICINE_SUPPLY": "Medicine & Drug Supply",
    "MEDICAL_CONSUMABLES": "Medical Consumables",
    # Water & Sanitation
    "WATER_PIPELINE": "Water Pipeline Work",
    "WATER_TANK": "Water Tank Construction",
    "WATER_TREATMENT": "Water Treatment Equipment",
    "SEWAGE_WORK": "Sewage & Drainage Work",
    "SANITATION_SERVICES": "Sanitation Services",
    # Transportation
    "VEHICLE_SUPPLY": "Vehicle Supply",
    "VEHICLE_MAINTENANCE": "Vehicle Maintenance",
    "TRANSPORT_SERVICES": "Transport Services",
    # Industrial Equipment
    "INDUSTRIAL_IOT": "Industrial IoT & Monitoring Equipment",
    "INDUSTRIAL_MACHINERY": "Industrial Machinery",
    "SAFETY_EQUIPMENT": "Safety Equipment",
    # General Supplies & Services
    "OFFICE_SUPPLIES": "Office Supplies & Stationery",
    "SECURITY_SERVICES": "Security Services",
    "HOUSEKEEPING": "Housekeeping & Facility Management",
    "CONSULTANCY": "Consultancy Services",
    "TRAINING": "Training & Capacity Building",
    # Other
    "OTHER": "Other / Unclassified",
}

# Aliases for backward compatibility with routes/tenders.py imports
CLASSIFICATION_LABELS = SUBJECT_CLASSIFICATIONS
CLASSIFICATIONS = list(SUBJECT_CLASSIFICATIONS.keys())


def _has_any(text: str, keywords: list) -> bool:
    """Return True if any keyword is found in text."""
    return any(kw in text for kw in keywords)


def classify_tender(title: str, description: str, department: str, category: str) -> dict:
    """
    Subject-based classification of a tender.
    Classifies by WHAT is being procured using priority-ordered rules.

    Returns a dict with keys:
        classification, secondary_classification, procurement_type,
        classification_confidence, classification_reason,
        classification_source, classification_review_required
    """
    combined = ' '.join([
        str(title or ''),
        str(description or ''),
        str(department or ''),
        str(category or ''),
    ]).lower()

    primary = None
    confidence = 0.5
    reason = ''

    # ── 1. INDUSTRIAL_IOT (highest priority for IoT/SCADA/industrial monitoring)
    iot_kw1 = ('iot', 'industrial iot', 'scada', 'plc', 'sensor', 'gateway')
    iot_kw2 = ('monitoring', 'industrial', 'automation')
    if _has_any(combined, iot_kw1) and _has_any(combined, iot_kw2):
        primary = 'INDUSTRIAL_IOT'
        confidence = 0.92
        reason = 'Tender involves IoT/SCADA/PLC sensors, gateways or monitoring for industrial/automation use'

    # ── 2. STEEL_FURNITURE
    if primary is None:
        if 'steel' in combined and _has_any(combined, ('furniture', 'table', 'chair', 'almirah', 'rack', 'shelving', 'cupboard', 'locker', 'bench', 'desk')):
            primary = 'STEEL_FURNITURE'
            confidence = 0.93
            reason = 'Tender is for supply of steel furniture items (tables, chairs, racks, almirahs, etc.)'

    # ── 3. WOODEN_FURNITURE
    if primary is None:
        if _has_any(combined, ('wooden', 'wood', 'teak', 'timber')) and _has_any(combined, ('furniture', 'table', 'chair', 'desk', 'bench', 'almirah')):
            primary = 'WOODEN_FURNITURE'
            confidence = 0.92
            reason = 'Tender is for supply of wooden furniture items'

    # ── 4. SCHOOL_FURNITURE
    if primary is None:
        if _has_any(combined, ('school', 'classroom', 'student', 'pupil')) and _has_any(combined, ('furniture', 'desk', 'bench', 'chair', 'table')):
            primary = 'SCHOOL_FURNITURE'
            confidence = 0.93
            reason = 'Tender is for supply of school/classroom furniture'

    # ── 5. HOSPITAL_FURNITURE
    if primary is None:
        if _has_any(combined, ('hospital bed', 'patient bed', 'stretcher', 'trolley', 'ward furniture')):
            primary = 'HOSPITAL_FURNITURE'
            confidence = 0.93
            reason = 'Tender is for hospital/patient furniture such as beds, trolleys, stretchers'

    # ── 6. OFFICE_FURNITURE (fallback furniture)
    if primary is None:
        if _has_any(combined, ('office furniture', 'workstation', 'office chair', 'office table')):
            primary = 'OFFICE_FURNITURE'
            confidence = 0.88
            reason = 'Tender is for office furniture — workstations, office chairs or office tables'

    # ── 7. ROAD_REPAIR (check before road_construction)
    if primary is None:
        road_kw = ('road', 'highway', 'street', 'pavement')
        repair_kw = ('repair', 'resurfacing', 'patching', 'pothole', 'maintenance', 'strengthening', 'overlay', 'white topping')
        if _has_any(combined, repair_kw) and _has_any(combined, road_kw):
            primary = 'ROAD_REPAIR'
            confidence = 0.92
            reason = 'Tender involves repair, resurfacing or maintenance of existing road/highway'

    # ── 8. ROAD_CONSTRUCTION (only if ROAD_REPAIR did not match)
    if primary is None:
        road_kw = ('road', 'highway', 'street')
        construction_kw = ('construction', 'laying', 'widening', 'new road', 'rural road', 'highway')
        if _has_any(combined, construction_kw) and _has_any(combined, road_kw):
            primary = 'ROAD_CONSTRUCTION'
            confidence = 0.92
            reason = 'Tender is for new road/highway construction, pavement laying or widening'

    # ── 9. BRIDGE_CONSTRUCTION
    if primary is None:
        if _has_any(combined, ('bridge', 'flyover', 'viaduct', 'culvert', 'overpass')):
            primary = 'BRIDGE_CONSTRUCTION'
            confidence = 0.93
            reason = 'Tender is for construction of a bridge, flyover, culvert or viaduct'

    # ── 10. BUILDING_RENOVATION (check before BUILDING_CONSTRUCTION)
    if primary is None:
        bldg_kw = ('building', 'block', 'quarters', 'hostel', 'office building')
        renov_kw = ('repair', 'renovation', 'retrofitting', 'refurbishment', 'restoration')
        if _has_any(combined, renov_kw) and _has_any(combined, bldg_kw):
            primary = 'BUILDING_RENOVATION'
            confidence = 0.90
            reason = 'Tender is for repair, renovation or refurbishment of an existing building'

    # ── 11. BUILDING_CONSTRUCTION (only if BUILDING_RENOVATION did not match)
    if primary is None:
        bldg_kw = ('building', 'block', 'campus', 'complex', 'auditorium', 'hostel')
        if 'construction' in combined and _has_any(combined, bldg_kw):
            primary = 'BUILDING_CONSTRUCTION'
            confidence = 0.92
            reason = 'Tender is for construction of a new building, campus, complex or hostel'

    # ── 12. DRAINAGE_WORK
    if primary is None:
        if _has_any(combined, ('drain', 'stormwater', 'nala', 'storm water', 'drainage')):
            primary = 'DRAINAGE_WORK'
            confidence = 0.90
            reason = 'Tender is for drainage, stormwater or nala work'

    # ── 13. SEWAGE_WORK
    if primary is None:
        if _has_any(combined, ('sewage', 'sewer', 'sewerage', 'stp', 'effluent', 'wastewater', 'underground drainage')):
            primary = 'SEWAGE_WORK'
            confidence = 0.93
            reason = 'Tender is for sewage, sewer, STP or wastewater work'

    # ── 14. WATER_PIPELINE
    if primary is None:
        if _has_any(combined, ('water pipeline', 'water supply pipeline', 'distribution network', 'water main', 'water supply')):
            primary = 'WATER_PIPELINE'
            confidence = 0.92
            reason = 'Tender is for water supply pipeline or distribution network'

    # ── 15. WATER_TANK
    if primary is None:
        if _has_any(combined, ('water tank', 'overhead tank', 'reservoir', 'sump')):
            primary = 'WATER_TANK'
            confidence = 0.92
            reason = 'Tender is for water tank, overhead tank or reservoir construction'

    # ── 16. WATER_TREATMENT
    if primary is None:
        if _has_any(combined, ('water treatment', 'wtp', 'filtration', 'chlorination', 'desalination', 'reverse osmosis')):
            primary = 'WATER_TREATMENT'
            confidence = 0.93
            reason = 'Tender is for water treatment plant or water purification equipment'

    # ── 17. CCTV_INSTALLATION (higher priority than SECURITY_SERVICES)
    if primary is None:
        if _has_any(combined, ('cctv', 'surveillance camera', 'ip camera', 'video surveillance', 'nvr', 'dvr')):
            primary = 'CCTV_INSTALLATION'
            confidence = 0.93
            reason = 'Tender is for supply and installation of CCTV / IP cameras / NVR / surveillance systems'

    # ── 18. COMPUTER_SUPPLY
    if primary is None:
        comp_kw1 = ('desktop', 'laptop', 'computer', 'personal computer', 'workstation pc', 'all-in-one pc', 'notebook')
        comp_kw2 = ('supply', 'purchase', 'procurement', 'delivery')
        if _has_any(combined, comp_kw1) and _has_any(combined, comp_kw2):
            primary = 'COMPUTER_SUPPLY'
            confidence = 0.93
            reason = 'Tender is for supply/procurement of desktop computers, laptops or notebooks'

    # ── 19. NETWORKING_EQUIPMENT
    if primary is None:
        if _has_any(combined, ('switch', 'router', 'firewall', 'network', 'structured cabling', 'wi-fi', 'wifi', 'access point', 'lan', 'wan', 'fiber optic')):
            primary = 'NETWORKING_EQUIPMENT'
            confidence = 0.90
            reason = 'Tender is for networking equipment — switches, routers, firewalls, cabling, Wi-Fi, etc.'

    # ── 20. SOFTWARE_DEVELOPMENT
    if primary is None:
        if _has_any(combined, ('software development', 'application development', 'web development', 'portal development', 'mobile app', 'erp', 'system development', 'e-governance', 'custom software')):
            primary = 'SOFTWARE_DEVELOPMENT'
            confidence = 0.93
            reason = 'Tender is for software/application/portal/mobile app development'

    # ── 21. IT_INFRASTRUCTURE
    if primary is None:
        if _has_any(combined, ('server', 'data center', 'storage', 'backup', 'cloud', 'virtual', 'hosting', 'it infrastructure')):
            primary = 'IT_INFRASTRUCTURE'
            confidence = 0.90
            reason = 'Tender is for IT infrastructure — servers, data center, storage, cloud or hosting'

    # ── 22. CYBERSECURITY
    if primary is None:
        if _has_any(combined, ('cybersecurity', 'cyber security', 'information security', 'vulnerability', 'penetration', 'soc', 'siem', 'endpoint protection')):
            primary = 'CYBERSECURITY'
            confidence = 0.93
            reason = 'Tender is for cybersecurity services — SOC, SIEM, vulnerability assessment, endpoint protection'

    # ── 23. TRANSFORMER_SUPPLY
    if primary is None:
        if _has_any(combined, ('transformer', '33kv', '66kv', '132kv', '220kv', '400kv', 'power transformer', 'distribution transformer')):
            primary = 'TRANSFORMER_SUPPLY'
            confidence = 0.93
            reason = 'Tender is for supply of power or distribution transformers'

    # ── 24. SOLAR_INSTALLATION
    if primary is None:
        if _has_any(combined, ('solar', 'photovoltaic', 'pv panel', 'solar panel', 'rooftop solar', 'solar power plant')):
            primary = 'SOLAR_INSTALLATION'
            confidence = 0.93
            reason = 'Tender is for installation of solar / photovoltaic panel systems'

    # ── 25. STREET_LIGHTING
    if primary is None:
        if _has_any(combined, ('street light', 'street lighting', 'road lighting', 'led street', 'lamp post', 'high mast')):
            primary = 'STREET_LIGHTING'
            confidence = 0.93
            reason = 'Tender is for street lighting, LED lamp posts or high mast lighting'

    # ── 26. ELECTRICAL_MAINTENANCE
    if primary is None:
        maint_kw = ('amc', 'annual maintenance', 'comprehensive maintenance', 'preventive maintenance', 'electrical maintenance')
        elec_kw = ('electrical', 'substation', 'switchgear', 'panel')
        if _has_any(combined, maint_kw) and _has_any(combined, elec_kw):
            primary = 'ELECTRICAL_MAINTENANCE'
            confidence = 0.90
            reason = 'Tender is for AMC or maintenance of electrical systems, switchgear or substations'

    # ── 27. ELECTRICAL_INSTALLATION (only if ELECTRICAL_MAINTENANCE did not match)
    if primary is None:
        if _has_any(combined, ('electrical installation', 'wiring', 'electrification', 'switchgear installation', 'substation installation')):
            primary = 'ELECTRICAL_INSTALLATION'
            confidence = 0.90
            reason = 'Tender is for electrical installation, wiring or electrification works'

    # ── 28. ELECTRICAL_EQUIPMENT (fallback electrical)
    if primary is None:
        if _has_any(combined, ('electrical equipment', 'switchgear', 'circuit breaker', 'capacitor bank', 'ups', 'generator', 'dg set')):
            primary = 'ELECTRICAL_EQUIPMENT'
            confidence = 0.88
            reason = 'Tender is for supply of electrical equipment — switchgear, UPS, generator, DG set, etc.'

    # ── 29. MEDICAL_EQUIPMENT
    if primary is None:
        if _has_any(combined, ('medical equipment', 'diagnostic equipment', 'imaging', 'ultrasound', 'x-ray', 'mri', 'ct scan', 'ecg', 'ventilator', 'operation theatre', 'ot equipment', 'hospital equipment')):
            primary = 'MEDICAL_EQUIPMENT'
            confidence = 0.93
            reason = 'Tender is for supply of diagnostic or medical equipment for hospitals/clinics'

    # ── 30. LABORATORY_EQUIPMENT
    if primary is None:
        if _has_any(combined, ('lab equipment', 'laboratory equipment', 'pathology', 'blood bank', 'centrifuge', 'microscope', 'spectrophotometer', 'lab instrument')):
            primary = 'LABORATORY_EQUIPMENT'
            confidence = 0.93
            reason = 'Tender is for supply of laboratory or pathology equipment'

    # ── 31. MEDICINE_SUPPLY
    if primary is None:
        if _has_any(combined, ('medicine', 'drug', 'pharmaceutical', 'vaccine', 'immunization', 'generic medicine', 'essential medicine')):
            primary = 'MEDICINE_SUPPLY'
            confidence = 0.93
            reason = 'Tender is for supply of medicines, drugs or pharmaceuticals'

    # ── 32. MEDICAL_CONSUMABLES
    if primary is None:
        if _has_any(combined, ('surgical consumable', 'disposable', 'ppe', 'diagnostic kit', 'test kit', 'bandage', 'suture', 'syringe', 'glove', 'mask')):
            primary = 'MEDICAL_CONSUMABLES'
            confidence = 0.90
            reason = 'Tender is for supply of medical consumables — PPE, disposables, surgical supplies, kits'

    # ── 33. VEHICLE_SUPPLY
    if primary is None:
        if _has_any(combined, ('supply of vehicle', 'purchase of vehicle', 'procurement of vehicle', 'ambulance', 'bus', 'truck', 'car supply', 'motorcycle supply')):
            primary = 'VEHICLE_SUPPLY'
            confidence = 0.92
            reason = 'Tender is for supply or procurement of vehicles'

    # ── 34. VEHICLE_MAINTENANCE
    if primary is None:
        if _has_any(combined, ('vehicle maintenance', 'vehicle repair', 'fleet maintenance', 'automobile repair', 'tyre', 'spare parts vehicle')):
            primary = 'VEHICLE_MAINTENANCE'
            confidence = 0.90
            reason = 'Tender is for vehicle maintenance, fleet repair or automobile servicing'

    # ── 35. TRANSPORT_SERVICES
    if primary is None:
        if _has_any(combined, ('hiring', 'rental vehicle', 'vehicle hire', 'transport service', 'logistics', 'cargo', 'freight', 'chauffeur', 'driver service')):
            primary = 'TRANSPORT_SERVICES'
            confidence = 0.88
            reason = 'Tender is for transport/logistics services — vehicle hiring, cargo, freight, chauffeur'

    # ── 36. INDUSTRIAL_MACHINERY (only if INDUSTRIAL_IOT did not match)
    if primary is None:
        if _has_any(combined, ('machinery', 'machine tool', 'lathe', 'milling machine', 'cnc', 'press', 'boiler', 'compressor', 'pump', 'turbine', 'diesel engine')):
            primary = 'INDUSTRIAL_MACHINERY'
            confidence = 0.90
            reason = 'Tender is for supply of industrial machinery — lathes, boilers, compressors, pumps, etc.'

    # ── 37. SAFETY_EQUIPMENT
    if primary is None:
        if _has_any(combined, ('safety equipment', 'ppe kit', 'helmet', 'safety shoe', 'harness', 'fire extinguisher', 'fire alarm', 'smoke detector')):
            primary = 'SAFETY_EQUIPMENT'
            confidence = 0.90
            reason = 'Tender is for safety equipment — PPE kits, helmets, fire extinguishers, alarms'

    # ── 38. OFFICE_SUPPLIES
    if primary is None:
        if _has_any(combined, ('stationery', 'office supplies', 'paper', 'toner', 'cartridge', 'pen', 'notebook supply')):
            primary = 'OFFICE_SUPPLIES'
            confidence = 0.90
            reason = 'Tender is for office supplies and stationery — paper, toner, pens, notebooks'

    # ── 39. SECURITY_SERVICES (lower priority than CCTV_INSTALLATION)
    if primary is None:
        if _has_any(combined, ('security guard', 'guarding service', 'manpower security', 'armed guard', 'unarmed guard', 'security personnel')):
            primary = 'SECURITY_SERVICES'
            confidence = 0.90
            reason = 'Tender is for manned security guard / guarding services'

    # ── 40. HOUSEKEEPING
    if primary is None:
        if _has_any(combined, ('housekeeping', 'cleaning service', 'facility management', 'janitorial', 'pest control', 'horticulture')):
            primary = 'HOUSEKEEPING'
            confidence = 0.90
            reason = 'Tender is for housekeeping, cleaning, facility management or pest control'

    # ── 41. CONSULTANCY
    if primary is None:
        if _has_any(combined, ('consultancy', 'consulting', 'advisory', 'feasibility study', 'policy advisory', 'technical assistance', 'project management consultant', 'pmc', 'transaction advisory')):
            primary = 'CONSULTANCY'
            confidence = 0.90
            reason = 'Tender is for consultancy / advisory / feasibility study / PMC services'

    # ── 42. TRAINING
    if primary is None:
        if _has_any(combined, ('training', 'capacity building', 'skill development', 'workshop', 'seminar')):
            primary = 'TRAINING'
            confidence = 0.88
            reason = 'Tender is for training, capacity building or skill development programmes'

    # ── Fallback
    if primary is None:
        primary = 'OTHER'
        confidence = 0.30
        reason = 'No subject-specific keywords matched in title, description, department or category'

    # ── Secondary classification: re-run with primary excluded
    secondary = None
    secondary_confidence = 0.0
    # Quick second-pass: check a reduced set for any other strong signal
    # Only assign secondary if it has clear keywords and differs from primary
    _secondary_checks = [
        ('INDUSTRIAL_IOT',       lambda c: _has_any(c, ('iot', 'scada', 'plc', 'sensor')) and _has_any(c, ('monitoring', 'industrial'))),
        ('SOFTWARE_DEVELOPMENT', lambda c: _has_any(c, ('software development', 'portal development', 'mobile app', 'e-governance'))),
        ('NETWORKING_EQUIPMENT', lambda c: _has_any(c, ('network', 'switch', 'router', 'firewall', 'wifi', 'wi-fi'))),
        ('IT_INFRASTRUCTURE',    lambda c: _has_any(c, ('server', 'data center', 'cloud', 'storage'))),
        ('ELECTRICAL_EQUIPMENT', lambda c: _has_any(c, ('electrical', 'switchgear', 'ups', 'generator'))),
        ('BUILDING_CONSTRUCTION',lambda c: 'construction' in c and _has_any(c, ('building', 'campus', 'complex'))),
        ('ROAD_CONSTRUCTION',    lambda c: _has_any(c, ('road', 'highway')) and 'construction' in c),
        ('SEWAGE_WORK',          lambda c: _has_any(c, ('sewage', 'sewer', 'stp'))),
        ('WATER_PIPELINE',       lambda c: _has_any(c, ('water supply', 'pipeline', 'distribution network'))),
        ('MEDICAL_CONSUMABLES',  lambda c: _has_any(c, ('surgical consumable', 'disposable', 'ppe', 'diagnostic kit'))),
        ('CONSULTANCY',          lambda c: _has_any(c, ('consultancy', 'advisory', 'pmc'))),
    ]
    for sec_key, check_fn in _secondary_checks:
        if sec_key != primary and check_fn(combined):
            secondary = sec_key
            break

    # ── Procurement type from category or primary classification
    cat_lower = str(category or '').lower()
    works_classifications = {
        'ROAD_CONSTRUCTION', 'ROAD_REPAIR', 'BRIDGE_CONSTRUCTION',
        'BUILDING_CONSTRUCTION', 'BUILDING_RENOVATION', 'DRAINAGE_WORK',
        'SEWAGE_WORK', 'WATER_PIPELINE', 'WATER_TANK',
        'ELECTRICAL_INSTALLATION', 'SOLAR_INSTALLATION',
    }
    services_classifications = {
        'TRANSPORT_SERVICES', 'SECURITY_SERVICES', 'HOUSEKEEPING',
        'TRAINING', 'SOFTWARE_DEVELOPMENT', 'ELECTRICAL_MAINTENANCE',
        'VEHICLE_MAINTENANCE', 'SANITATION_SERVICES',
    }
    consultancy_classifications = {'CONSULTANCY'}

    if 'work' in cat_lower or 'construction' in cat_lower or primary in works_classifications:
        procurement_type = 'Works'
    elif 'consult' in cat_lower or primary in consultancy_classifications:
        procurement_type = 'Consultancy'
    elif 'service' in cat_lower or primary in services_classifications:
        procurement_type = 'Services'
    else:
        procurement_type = 'Goods'

    return {
        'classification': primary,
        'secondary_classification': secondary,
        'procurement_type': procurement_type,
        'classification_confidence': round(confidence, 4),
        'classification_reason': reason,
        'classification_source': 'auto',
        'classification_review_required': confidence < 0.7,
    }
