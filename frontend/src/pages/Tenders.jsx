import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, ArrowRight, Calendar, Building2, IndianRupee, Users, Plus, ChevronDown, ChevronRight as ChevronRightIcon } from 'lucide-react'
import { getTenders, getTendersFiltered, getClassifications } from '../services/api.js'
import { PageLoader } from '../components/LoadingSkeleton.jsx'
import { useLanguage } from '../context/LanguageContext.jsx'

const STATUS_OPTIONS = ['Active', 'Closed', 'Evaluation', 'Awarded']

// ── Grouped classification definitions ───────────────────────
const CLASSIFICATION_GROUPS = [
  {
    label: 'Furniture',
    keys: ['STEEL_FURNITURE', 'WOODEN_FURNITURE', 'OFFICE_FURNITURE', 'SCHOOL_FURNITURE', 'HOSPITAL_FURNITURE'],
  },
  {
    label: 'Roads & Civil',
    keys: ['ROAD_CONSTRUCTION', 'ROAD_REPAIR', 'BRIDGE_CONSTRUCTION', 'BUILDING_CONSTRUCTION', 'BUILDING_RENOVATION', 'DRAINAGE_WORK'],
  },
  {
    label: 'IT & Technology',
    keys: ['COMPUTER_SUPPLY', 'NETWORKING_EQUIPMENT', 'CCTV_INSTALLATION', 'SOFTWARE_DEVELOPMENT', 'IT_INFRASTRUCTURE', 'CYBERSECURITY'],
  },
  {
    label: 'Electrical & Energy',
    keys: ['ELECTRICAL_EQUIPMENT', 'ELECTRICAL_INSTALLATION', 'ELECTRICAL_MAINTENANCE', 'SOLAR_INSTALLATION', 'STREET_LIGHTING', 'TRANSFORMER_SUPPLY'],
  },
  {
    label: 'Healthcare',
    keys: ['MEDICAL_EQUIPMENT', 'LABORATORY_EQUIPMENT', 'MEDICINE_SUPPLY', 'MEDICAL_CONSUMABLES'],
  },
  {
    label: 'Water & Sanitation',
    keys: ['WATER_PIPELINE', 'WATER_TANK', 'WATER_TREATMENT', 'SEWAGE_WORK', 'SANITATION_SERVICES'],
  },
  {
    label: 'Transportation',
    keys: ['VEHICLE_SUPPLY', 'VEHICLE_MAINTENANCE', 'TRANSPORT_SERVICES'],
  },
  {
    label: 'Industrial Equipment',
    keys: ['INDUSTRIAL_IOT', 'INDUSTRIAL_MACHINERY', 'SAFETY_EQUIPMENT'],
  },
  {
    label: 'General Supplies',
    keys: ['OFFICE_SUPPLIES', 'SECURITY_SERVICES', 'HOUSEKEEPING', 'CONSULTANCY', 'TRAINING'],
  },
  {
    label: 'Other',
    keys: ['OTHER'],
  },
]

export default function Tenders() {
  const [tenders, setTenders] = useState([])
  const [loading, setLoading] = useState(true)
  const [classificationFilter, setClassificationFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  // classificationList: [{key, label, count}, ...]
  const [classificationList, setClassificationList] = useState([])
  // Track which classification groups are expanded; expand group containing active filter
  const [expandedGroups, setExpandedGroups] = useState({})

  const navigate = useNavigate()
  const { t } = useLanguage()

  // Load classification list once on mount
  useEffect(() => {
    getClassifications()
      .then((res) => {
        const data = res.data || {}
        // New API returns: { classifications: [{key, label, count}, ...], total: N }
        if (Array.isArray(data.classifications)) {
          setClassificationList(data.classifications)
        } else {
          setClassificationList([])
        }
      })
      .catch(() => {
        setClassificationList([])
      })
  }, [])

  // Load tenders whenever any filter changes
  const loadTenders = useCallback(() => {
    setLoading(true)
    const raw = {
      classification: classificationFilter || undefined,
      status: statusFilter ? statusFilter.toLowerCase() : undefined,
      search: searchQuery.trim() || undefined,
    }
    // Strip undefined keys so axios doesn't send empty params
    const params = Object.fromEntries(Object.entries(raw).filter(([, v]) => v !== undefined))

    const fetcher = Object.keys(params).length > 0 ? getTendersFiltered(params) : getTenders()
    fetcher
      .then((res) => setTenders(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [classificationFilter, statusFilter, searchQuery])

  useEffect(() => {
    loadTenders()
  }, [loadTenders])

  // Auto-expand the group that contains the active classification filter
  useEffect(() => {
    if (!classificationFilter) return
    const group = CLASSIFICATION_GROUPS.find((g) => g.keys.includes(classificationFilter))
    if (group) {
      setExpandedGroups((prev) => ({ ...prev, [group.label]: true }))
    }
  }, [classificationFilter])

  const toggleGroup = (label) => {
    setExpandedGroups((prev) => ({ ...prev, [label]: !prev[label] }))
  }

  if (loading && !tenders.length) return <PageLoader />

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">{t('tenders')}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t('tenders_subtitle')}</p>
        </div>
        <button className="btn-primary" onClick={() => navigate('/tenders/new')}>
          <Plus size={14} /> {t('create_tender')}
        </button>
      </div>

      {/* Search input */}
      <div>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search tenders by title, department…"
          className="w-full md:w-80 px-3 py-2 text-sm border border-gray-200 focus:outline-none focus:border-blue-400 bg-white"
          style={{ borderRadius: '2px' }}
        />
      </div>

      {/* Classification filter pills — data-driven from API */}
      <div className="overflow-x-auto">
        <div className="flex items-center gap-2 pb-1 min-w-max">
          <button
            onClick={() => setClassificationFilter('')}
            className={`px-3 py-1.5 text-xs font-semibold transition-colors flex-shrink-0 ${
              classificationFilter === ''
                ? 'bg-blue-600 text-white border border-blue-600'
                : 'bg-white border border-gray-200 text-gray-600 hover:border-blue-300'
            }`}
            style={{ borderRadius: '2px' }}
          >
            All
          </button>
          {classificationList.map((item) => {
            const isActive = classificationFilter === item.key
            return (
              <button
                key={item.key}
                onClick={() => setClassificationFilter(isActive ? '' : item.key)}
                className={`px-3 py-1.5 text-xs font-semibold transition-colors flex items-center gap-1.5 flex-shrink-0 ${
                  isActive
                    ? 'bg-blue-600 text-white border border-blue-600'
                    : 'bg-white border border-gray-200 text-gray-600 hover:border-blue-300'
                }`}
                style={{ borderRadius: '2px' }}
              >
                {item.label}
                {item.count > 0 && (
                  <span
                    className={`inline-flex items-center justify-center w-4 h-4 text-[10px] font-bold rounded-full ${
                      isActive ? 'bg-white text-blue-600' : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {item.count}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Grouped classification filter — collapsible groups */}
      {classificationList.length > 0 && (
        <div className="card p-3 space-y-1">
          <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide px-1 pb-1">Filter by Category</p>
          {CLASSIFICATION_GROUPS.map((group) => {
            // Only show items with count > 0; skip group if none match
            const items = group.keys
              .map((key) => classificationList.find((c) => c.key === key))
              .filter(Boolean)
            if (items.length === 0) return null
            const isExpanded = !!expandedGroups[group.label]
            const groupActive = items.some((i) => i.key === classificationFilter)
            return (
              <div key={group.label}>
                <button
                  onClick={() => toggleGroup(group.label)}
                  className={`w-full flex items-center justify-between px-2 py-1.5 text-xs font-semibold transition-colors ${
                    groupActive
                      ? 'text-blue-700 bg-blue-50'
                      : 'text-slate-700 hover:bg-gray-50'
                  }`}
                  style={{ borderRadius: '2px' }}
                >
                  <span className="flex items-center gap-1.5">
                    {group.label}
                    {groupActive && (
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-600 inline-block" />
                    )}
                  </span>
                  {isExpanded
                    ? <ChevronDown size={12} className="flex-shrink-0" />
                    : <ChevronRightIcon size={12} className="flex-shrink-0" />
                  }
                </button>
                {isExpanded && (
                  <div className="pl-3 pb-1 space-y-0.5">
                    {items.map((item) => {
                      const isActive = classificationFilter === item.key
                      return (
                        <button
                          key={item.key}
                          onClick={() => setClassificationFilter(isActive ? '' : item.key)}
                          className={`w-full flex items-center justify-between px-2 py-1 text-xs transition-colors ${
                            isActive
                              ? 'bg-blue-600 text-white font-semibold'
                              : 'text-slate-600 hover:bg-gray-100'
                          }`}
                          style={{ borderRadius: '2px' }}
                        >
                          <span>{item.label}</span>
                          <span
                            className={`inline-flex items-center justify-center min-w-[18px] h-4 px-1 text-[10px] font-bold rounded-full ${
                              isActive ? 'bg-white text-blue-600' : 'bg-gray-100 text-gray-500'
                            }`}
                          >
                            {item.count}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Status filter pills */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setStatusFilter('')}
          className={`px-3 py-1.5 text-xs font-semibold transition-colors ${
            statusFilter === ''
              ? 'bg-blue-600 text-white border border-blue-600'
              : 'bg-white border border-gray-200 text-gray-600 hover:border-blue-300'
          }`}
          style={{ borderRadius: '2px' }}
        >
          All
        </button>
        {STATUS_OPTIONS.map((s) => {
          const isActive = statusFilter === s
          return (
            <button
              key={s}
              onClick={() => setStatusFilter(isActive ? '' : s)}
              className={`px-3 py-1.5 text-xs font-semibold transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white border border-blue-600'
                  : 'bg-white border border-gray-200 text-gray-600 hover:border-blue-300'
              }`}
              style={{ borderRadius: '2px' }}
            >
              {s}
            </button>
          )
        })}
      </div>

      {/* Tender list */}
      {loading ? (
        <div className="text-sm text-gray-500 py-4">Loading…</div>
      ) : (
        <div className="space-y-4">
          {tenders.length === 0 && (
            <div className="text-sm text-gray-500 py-8 text-center">No tenders match the selected filters.</div>
          )}
          {tenders.map((tender) => {
            // Look up label from classificationList, fall back to classification_name or raw key
            const clsEntry = classificationList.find((c) => c.key === tender.classification)
            const clsLabel = clsEntry
              ? clsEntry.label
              : tender.classification_name || tender.classification || null

            return (
              <div
                key={tender.id}
                className="card p-5 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => navigate(`/tenders/${tender.id}`)}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                        {tender.id}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        tender.status === 'active' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {tender.status?.toUpperCase()}
                      </span>
                      {clsLabel && (
                        <span
                          className="text-xs px-2 py-0.5 font-medium bg-blue-50 text-blue-700"
                          style={{ borderRadius: '2px' }}
                        >
                          {clsLabel}
                        </span>
                      )}
                    </div>
                    <h2 className="text-base font-semibold text-slate-800 leading-snug">{tender.title}</h2>
                    <div className="flex flex-wrap items-center gap-4 mt-2">
                      <span className="flex items-center gap-1.5 text-xs text-gray-500">
                        <Building2 size={12} /> {tender.department}
                      </span>
                      <span className="flex items-center gap-1.5 text-xs text-gray-500">
                        <IndianRupee size={12} /> {tender.estimated_value_display}
                      </span>
                      <span className="flex items-center gap-1.5 text-xs text-gray-500">
                        <Calendar size={12} /> {t('deadline')}: {new Date(tender.submission_deadline).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-6 flex-shrink-0">
                    <div className="text-center hidden sm:block">
                      <p className="text-xl font-bold text-blue-700">{tender.total_requirements}</p>
                      <p className="text-[10px] text-gray-500">{t('requirements')}</p>
                    </div>
                    <div className="text-center hidden sm:block">
                      <p className="text-xl font-bold text-purple-700">{tender.bidder_count}</p>
                      <p className="text-[10px] text-gray-500">{t('bidders')}</p>
                    </div>
                    <ArrowRight size={18} className="text-gray-400" />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
