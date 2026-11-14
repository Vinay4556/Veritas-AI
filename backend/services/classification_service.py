"""
classification_service.py — Keyword/rule-based tender classification.
No external AI API needed.
"""

CLASSIFICATIONS = [
    'CIVIL_WORKS',
    'ELECTRICAL_POWER',
    'MECHANICAL_INDUSTRIAL',
    'IT_SOFTWARE',
    'GOODS_SUPPLY',
    'HEALTHCARE_MEDICAL',
    'TRANSPORT_LOGISTICS',
    'WATER_SANITATION',
    'CONSULTANCY',
    'MAINTENANCE_REPAIR',
    'SECURITY',
    'OTHER',
]

CLASSIFICATION_LABELS = {
    'CIVIL_WORKS': 'Civil Works & Construction',
    'ELECTRICAL_POWER': 'Electrical & Power',
    'MECHANICAL_INDUSTRIAL': 'Mechanical & Industrial Equipment',
    'IT_SOFTWARE': 'IT & Software',
    'GOODS_SUPPLY': 'Goods & Supply',
    'HEALTHCARE_MEDICAL': 'Healthcare & Medical',
    'TRANSPORT_LOGISTICS': 'Transportation & Logistics',
    'WATER_SANITATION': 'Water & Sanitation',
    'CONSULTANCY': 'Consultancy & Professional Services',
    'MAINTENANCE_REPAIR': 'Maintenance & Repair',
    'SECURITY': 'Security Services',
    'OTHER': 'Other / Unclassified',
}

KEYWORD_MAP = {
    'CIVIL_WORKS': [
        'construction', 'civil', 'road', 'bridge', 'building', 'drainage',
        'renovation', 'rcc', 'foundation', 'pavement', 'structure',
        'flooring', 'plastering', 'masonry', 'concrete', 'excavation',
        'retaining wall', 'compound wall', 'boundary', 'fencing',
        'waterproofing', 'tiling', 'carpentry', 'joinery', 'pathway',
        'footpath', 'approach road', 'township', 'housing', 'quarters',
        'administrative block', 'office block', 'campus', 'complex',
    ],
    'ELECTRICAL_POWER': [
        'electrical', 'power', 'transformer', 'switchgear', 'substation',
        'wiring', 'generator', 'ups', 'solar', 'inverter',
        'capacitor', 'panel', 'hvac', 'feeder', 'distribution',
        'transmission', 'grid', 'metering', 'cable', 'conductor',
        'busbar', 'rectifier', 'battery', 'charger', 'diesel generator',
        'dg set', 'renewable energy', 'wind', 'photovoltaic',
        'street light', 'lighting', 'illumination', 'electric supply',
    ],
    'MECHANICAL_INDUSTRIAL': [
        'iot', 'sensor', 'gateway', 'industrial', 'machinery', 'equipment',
        'plant', 'boiler', 'pump', 'compressor', 'scada', 'monitoring',
        'instrumentation', 'valve', 'pipeline', 'heat exchanger',
        'pressure vessel', 'motor', 'actuator', 'conveyor', 'crane',
        'hoist', 'lathe', 'milling', 'fabrication', 'welding',
        'manufacturing', 'automation', 'plc', 'dcs', 'hvac',
        'refrigeration', 'cooling', 'ventilation', 'fire suppression',
        'mechanical', 'turbine', 'diesel engine', 'alternator',
    ],
    'IT_SOFTWARE': [
        'software', 'it', 'networking', 'server', 'cybersecurity',
        'application', 'database', 'cloud', 'erp', 'website',
        'portal', 'computer', 'hardware', 'network', 'api',
        'mobile app', 'web development', 'system integration', 'data center',
        'storage', 'backup', 'firewall', 'router', 'switch',
        'wi-fi', 'wifi', 'internet', 'broadband', 'fiber optic',
        'email', 'collaboration', 'crm', 'hrms', 'e-governance',
        'digital', 'cyber', 'information technology', 'telecommunications',
        'helpdesk', 'it support', 'managed services', 'saas',
    ],
    'GOODS_SUPPLY': [
        'supply', 'furniture', 'stationery', 'office', 'material',
        'uniform', 'consumable', 'printing', 'procurement',
        'purchase', 'goods', 'items', 'articles', 'products',
        'raw material', 'spares', 'spare parts', 'tools',
        'equipment supply', 'rate contract', 'rate-contract',
        'delivery', 'packaging', 'textile', 'cloth', 'garment',
        'crockery', 'glassware', 'hardware item', 'fittings',
        'fixtures', 'accessories', 'workstation', 'chair', 'table',
        'storage unit', 'shelving', 'cupboard', 'almirah',
    ],
    'HEALTHCARE_MEDICAL': [
        'medical', 'hospital', 'health', 'medicine', 'ambulance',
        'diagnostic', 'pharmaceutical', 'nursing', 'patient',
        'clinical', 'surgery', 'operation theatre', 'icu',
        'ventilator', 'x-ray', 'mri', 'ct scan', 'ultrasound',
        'laboratory', 'pathology', 'blood bank', 'pharmacy',
        'drug', 'vaccine', 'immunization', 'healthcare',
        'wellness', 'cghs', 'dispensary', 'infirmary', 'medical equipment',
        'surgical', 'consumable kit', 'diagnostic kit', 'ppe',
    ],
    'TRANSPORT_LOGISTICS': [
        'vehicle', 'transport', 'logistics', 'fleet', 'bus',
        'truck', 'cargo', 'shipping', 'haulage', 'crane',
        'ambulance vehicle', 'car', 'jeep', 'suv', 'motorcycle',
        'aircraft', 'helicopter', 'vessel', 'boat', 'ferry',
        'freight', 'courier', 'parcel', 'load', 'movement',
        'transit', 'delivery service', 'hiring', 'rental vehicle',
        'chauffeur', 'driver', 'fleet management', 'gps tracking',
        'road transport', 'road haulage', 'light commercial vehicle',
    ],
    'WATER_SANITATION': [
        'water', 'sanitation', 'pipeline', 'sewage', 'effluent',
        'treatment', 'borewell', 'irrigation', 'drainage', 'sewage',
        'water supply', 'water treatment', 'wtp', 'stp',
        'solid waste', 'waste management', 'garbage', 'refuse',
        'storm water', 'flood control', 'reservoir', 'dam',
        'canal', 'aquifer', 'groundwater', 'overhead tank',
        'distribution network', 'pumping station', 'lift irrigation',
        'swachh bharat', 'open defecation', 'toilet', 'latrine', 'mld',
    ],
    'CONSULTANCY': [
        'consultancy', 'consulting', 'audit', 'architecture',
        'design', 'survey', 'feasibility', 'project management',
        'advisory', 'study', 'assessment', 'evaluation', 'review',
        'planning', 'strategy', 'technical assistance', 'capacity building',
        'training', 'workshop', 'inspection', 'third party',
        'quality assurance', 'pmc', 'transaction advisory',
        'financial advisory', 'legal advisory', 'due diligence',
        'environmental impact', 'eia', 'detailed project report', 'dpr',
    ],
    'MAINTENANCE_REPAIR': [
        'maintenance', 'amc', 'repair', 'overhaul', 'servicing',
        'annual contract', 'upkeep', 'refurbishment', 'restoration',
        'preventive maintenance', 'breakdown maintenance', 'corrective',
        'spare parts supply', 'warranty', 'comprehensive maintenance',
        'housekeeping', 'cleaning', 'pest control', 'horticulture',
        'facility management', 'operation and maintenance', 'o&m',
        'annual maintenance', 'cmc', 'comprehensive maintenance contract',
        'baggage handling', 'conveyor maintenance',
    ],
    'SECURITY': [
        'security', 'surveillance', 'cctv', 'guard', 'access control',
        'biometric', 'fire alarm', 'fire detection', 'intrusion',
        'perimeter security', 'patrol', 'manpower', 'guarding',
        'armed guard', 'unarmed guard', 'bodily protection',
        'entry exit', 'visitor management', 'boom barrier',
        'metal detector', 'x-ray baggage', 'atm security',
        'bank security', 'event security', 'investigation',
        'cyber security', 'information security',
    ],
}


def classify_tender(title: str, description: str, department: str, category: str) -> dict:
    """
    Keyword/rule-based classification of a tender.

    Returns a dict with keys:
        classification, secondary_classification, procurement_type,
        classification_confidence, classification_reason,
        classification_source, classification_review_required
    """
    # Combine all text inputs into one lowercase blob for scoring
    combined = ' '.join([
        str(title or ''),
        str(description or ''),
        str(department or ''),
        str(category or ''),
    ]).lower()

    scores = {}
    matched_keywords = {}

    for cls, keywords in KEYWORD_MAP.items():
        hits = [kw for kw in keywords if kw in combined]
        scores[cls] = len(hits)
        if hits:
            matched_keywords[cls] = hits

    # Sort by score descending
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_cls, top_score = sorted_scores[0]
    second_cls, second_score = sorted_scores[1] if len(sorted_scores) > 1 else (None, 0)

    # Determine primary classification
    if top_score == 0:
        primary = 'OTHER'
        secondary = None
        confidence = 0.3
    else:
        primary = top_cls
        secondary = second_cls if second_score > 0 else None

        if second_score == 0:
            # Only one class matched
            confidence = 0.85
        else:
            # Ratio-based confidence, clamped to [0.5, 0.95]
            raw = top_score / (top_score + second_score)
            confidence = max(0.5, min(0.95, raw))

    # Build classification reason from matched keywords
    if primary == 'OTHER':
        reason = 'No classification keywords matched in title, description, department or category'
    else:
        kws = matched_keywords.get(primary, [])
        reason = f'Matched keywords: {", ".join(kws[:8])}' if kws else 'Score-based match'
        if secondary:
            sec_kws = matched_keywords.get(secondary, [])
            if sec_kws:
                reason += f'; secondary keywords ({secondary}): {", ".join(sec_kws[:4])}'

    # Derive procurement_type from category field
    cat_lower = str(category or '').lower()
    if 'work' in cat_lower or 'construction' in cat_lower:
        procurement_type = 'Works'
    elif 'consult' in cat_lower:
        procurement_type = 'Consultancy'
    elif 'service' in cat_lower:
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
