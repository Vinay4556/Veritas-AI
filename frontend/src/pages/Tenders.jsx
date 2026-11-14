import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, ArrowRight, Calendar, Building2, IndianRupee, Users, Plus } from 'lucide-react'
import { getTenders, getTendersFiltered, getClassifications } from '../services/api.js'
import { PageLoader } from '../components/LoadingSkeleton.jsx'
import { useLanguage } from '../context/LanguageContext.jsx'

// ── Classification short labels ──────────────────────────────
const SHORT_LABELS = {
  CIVIL_WORKS:              'Civil Works',
  ELECTRICAL_POWER:         'Electrical',
  MECHANICAL_INDUSTRIAL:    'Mechanical',
  IT_SOFTWARE:              'IT & Software',
  GOODS_SUPPLY:             'Goods',
  HEALTHCARE_MEDICAL:       'Healthcare',
  TRANSPORT_LOGISTICS:      'Transport',
  WATER_SANITATION:         'Water',
  CONSULTANCY:              'Consultancy',
  MAINTENANCE_REPAIR:       'Maintenance',
  SECURITY:                 'Security',
  OTHER:                    'Other',
}

// ── Classification badge colors ──────────────────────────────
const CLASSIFICATION_COLORS = {
  CIVIL_WORKS:           'bg-orange-50 text-orange-700',
  ELECTRICAL_POWER:      'bg-yellow-50 text-yellow-700',
  MECHANICAL_INDUSTRIAL: 'bg-cyan-50 text-cyan-700',
  IT_SOFTWARE:           'bg-purple-50 text-purple-700',
  GOODS_SUPPLY:          'bg-green-50 text-green-700',
  HEALTHCARE_MEDICAL:    'bg-red-50 text-red-700',
  TRANSPORT_LOGISTICS:   'bg-blue-50 text-blue-700',
  WATER_SANITATION:      'bg-teal-50 text-teal-700',
  CONSULTANCY:           'bg-indigo-50 text-indigo-700',
  MAINTENANCE_REPAIR:    'bg-gray-50 text-gray-700',
  SECURITY:              'bg-rose-50 text-rose-700',
  OTHER:                 'bg-slate-50 text-slate-700',
}

const STATUS_OPTIONS = ['Active', 'Closed', 'Evaluation', 'Awarded']

export default function Tenders() {
  const [tenders, setTenders] = useState([])
  const [loading, setLoading] = useState(true)
  const [classificationFilter, setClassificationFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [classificationCounts, setClassificationCounts] = useState({})
  const [classifications, setClassifications] = useState({})

  const navigate = useNavigate()
  const { t } = useLanguage()

  // Load classification counts + labels once on mount
  useEffect(() => {
    getClassifications()
      .then((res) => {
        const data = res.data || {}
        // Backend may return { counts: {}, labels: {} } or just a flat counts object
        if (data.counts) {
          setClassificationCounts(data.counts)
          setClassifications(data.labels || {})
        } else {
          // Flat counts map
          setClassificationCounts(data)
        }
      })
      .catch(() => {
        // Not critical — filters still work, just no counts
        setClassificationCounts({})
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

  // ── Classification pills — only show keys with count > 0 (or all keys if no counts)
  const classificationKeys = Object.keys(SHORT_LABELS).filter(
    (k) => !Object.keys(classificationCounts).length || (classificationCounts[k] || 0) > 0
  )

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

      {/* Classification filter pills */}
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
          {classificationKeys.map((key) => {
            const count = classificationCounts[key] || 0
            const isActive = classificationFilter === key
            return (
              <button
                key={key}
                onClick={() => setClassificationFilter(isActive ? '' : key)}
                className={`px-3 py-1.5 text-xs font-semibold transition-colors flex items-center gap-1.5 flex-shrink-0 ${
                  isActive
                    ? 'bg-blue-600 text-white border border-blue-600'
                    : 'bg-white border border-gray-200 text-gray-600 hover:border-blue-300'
                }`}
                style={{ borderRadius: '2px' }}
              >
                {SHORT_LABELS[key]}
                {count > 0 && (
                  <span
                    className={`inline-flex items-center justify-center w-4 h-4 text-[10px] font-bold rounded-full ${
                      isActive ? 'bg-white text-blue-600' : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {count}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

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
            const cls = tender.classification
            const clsColor = cls ? (CLASSIFICATION_COLORS[cls] || 'bg-slate-50 text-slate-700') : null
            const clsLabel = cls ? (SHORT_LABELS[cls] || cls) : null

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
                          className={`text-xs px-2 py-0.5 font-medium ${clsColor}`}
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
