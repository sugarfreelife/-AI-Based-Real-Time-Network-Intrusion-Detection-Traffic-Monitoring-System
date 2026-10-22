import { lazy, Suspense } from 'react'
import { Check, ChevronDown, ChevronUp, Filter, Search, ShieldAlert } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { DateFilterFields } from '../components/DateFilterFields'
import { EmptyState, ErrorState, LoadingState, StaleState } from '../components/ListStates'
import { Pagination } from '../components/Pagination'
import { ApiError } from '../lib/api'
import { formatDate, formatEndpoint, localDateTimeValue, toUtcIso } from '../lib/presentation'
import type { Alert, Page } from '../lib/types'
import type { SeverityDatum } from '../components/SeverityChart'
import { useAlertStream } from '../components/AppShell'

const SeverityChart = lazy(() => import('../components/SeverityChart'))
const severityOrder: Alert['severity'][] = ['critical', 'high', 'medium', 'low']
const severityColor: Record<Alert['severity'], string> = {
  critical: 'var(--critical)', high: 'var(--high)', medium: 'var(--medium)', low: 'var(--low)',
}

function queryString(params: URLSearchParams): string {
  const query = new URLSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)
  const limit = [25, 50, 100].includes(Number(params.get('limit'))) ? Number(params.get('limit')) : 25
  query.set('limit', String(limit))
  query.set('offset', String((page - 1) * limit))
  for (const key of ['severity', 'status', 'detection_code', 'since', 'until']) {
    const value = params.get(key)
    if (value) query.set(key, value)
  }
  return query.toString()
}

function EndpointPair({ alert }: { alert: Alert }) {
  return <span className="endpoint-pair"><span>{formatEndpoint(alert.endpoint_a)}</span><i aria-hidden="true">→</i><span>{formatEndpoint(alert.endpoint_b)}</span></span>
}

function AlertDetails({ alert }: { alert: Alert }) {
  return <div className="record-details-grid">
    <div><span className="detail-label">Explanation</span><p>{alert.explanation}</p></div>
    <div><span className="detail-label">Alert ID</span><code>{alert.id}</code></div>
    <div><span className="detail-label">Flow record</span><code>{alert.flow_record_id}</code></div>
    <div><span className="detail-label">Exact event time</span><code>{alert.occurred_at}</code></div>
    <div><span className="detail-label">Persisted at</span><code>{alert.created_at}</code></div>
    <div><span className="detail-label">Source</span><span>{alert.source}</span></div>
    <div><span className="detail-label">Model version</span><span>{alert.model_version ?? 'Not available'}</span></div>
    <div className="evidence-block"><span className="detail-label">Detection evidence</span><pre>{JSON.stringify(alert.evidence, null, 2)}</pre></div>
  </div>
}

export function AlertsPage() {
  const { request, user } = useAuth()
  const [params, setParams] = useSearchParams()
  const paramKey = params.toString()
  const { receivedCount } = useAlertStream()
  const limit = [25, 50, 100].includes(Number(params.get('limit'))) ? Number(params.get('limit')) : 25
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)
  const query = useMemo(() => queryString(new URLSearchParams(paramKey)), [paramKey])
  const [data, setData] = useState<Page<Alert> | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const [actionFailed, setActionFailed] = useState(false)
  const lastStreamCount = useRef(0)
  const [draft, setDraft] = useState(() => ({
    severity: params.get('severity') ?? '',
    status: params.get('status') ?? '',
    detectionCode: params.get('detection_code') ?? '',
    since: localDateTimeValue(params.get('since')),
    until: localDateTimeValue(params.get('until')),
  }))
  const [filterError, setFilterError] = useState('')
  const detectionInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const current = new URLSearchParams(paramKey)
    setDraft({
      severity: current.get('severity') ?? '',
      status: current.get('status') ?? '',
      detectionCode: current.get('detection_code') ?? '',
      since: localDateTimeValue(current.get('since')),
      until: localDateTimeValue(current.get('until')),
    })
  }, [paramKey])

  const load = useCallback(async (signal?: AbortSignal) => {
    setBusy(true)
    setError('')
    try {
      const response = await request<Page<Alert>>(`/api/v1/alerts?${query}`, { signal })
      setData(response)
      const lastPage = Math.max(1, Math.ceil(response.total / response.limit))
      if (page > lastPage) {
        setParams((current) => {
          const next = new URLSearchParams(current)
          next.set('page', String(lastPage))
          return next
        }, { replace: true })
      }
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      setError(reason instanceof Error ? reason.message : 'Could not load alerts.')
    } finally {
      if (!signal?.aborted) setBusy(false)
    }
  }, [page, query, request, setParams])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load, retry])

  useEffect(() => {
    if (receivedCount > lastStreamCount.current) {
      lastStreamCount.current = receivedCount
      setRetry((count) => count + 1)
    }
  }, [receivedCount])

  const setPage = (nextPage: number) => {
    setParams((current) => { const next = new URLSearchParams(current); next.set('page', String(nextPage)); return next })
  }
  const setPageSize = (nextSize: number) => {
    setParams((current) => { const next = new URLSearchParams(current); next.set('limit', String(nextSize)); next.set('page', '1'); return next })
  }

  const applyFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFilterError('')
    if (draft.since && draft.until && new Date(draft.since).getTime() > new Date(draft.until).getTime()) {
      setFilterError('The “From” time must be earlier than or equal to the “To” time.')
      return
    }
    const next = new URLSearchParams()
    next.set('page', '1')
    next.set('limit', String(limit))
    if (draft.severity) next.set('severity', draft.severity)
    if (draft.status) next.set('status', draft.status)
    if (draft.detectionCode.trim()) next.set('detection_code', draft.detectionCode.trim())
    const since = toUtcIso(draft.since)
    const until = toUtcIso(draft.until)
    if (since) next.set('since', since)
    if (until) next.set('until', until)
    setParams(next)
  }

  const clearFilters = () => {
    setFilterError('')
    setParams({ page: '1', limit: String(limit) })
  }

  const acknowledge = async (alert: Alert) => {
    if (pendingId) return
    setPendingId(alert.id)
    setActionMessage('')
    setActionFailed(false)
    try {
      const updated = await request<Alert>(`/api/v1/alerts/${encodeURIComponent(alert.id)}/acknowledge`, { method: 'PATCH' })
      setData((current) => current ? { ...current, items: current.items.map((item) => item.id === updated.id ? updated : item) } : current)
      setActionMessage(`Alert ${alert.detection_code} acknowledged.`)
      setRetry((count) => count + 1)
    } catch (reason) {
      const message = reason instanceof ApiError && reason.status === 403
        ? 'This account cannot acknowledge alerts. An analyst or administrator is required.'
        : reason instanceof Error ? reason.message : 'The alert could not be acknowledged.'
      setActionMessage(message)
      setActionFailed(true)
    } finally {
      setPendingId(null)
    }
  }

  const hasFilters = Boolean(params.get('severity') || params.get('status') || params.get('detection_code') || params.get('since') || params.get('until'))
  const counts = severityOrder.map((severity) => ({ severity, total: data?.items.filter((alert) => alert.severity === severity).length ?? 0 }))
  const chartData = counts.filter((entry) => entry.total > 0)
  const totalOnPage = data?.items.length ?? 0

  return <div className="page-content">
    <div className="page-heading-row">
      <div><p className="eyebrow"><span className="eyebrow-marker" />Detection review</p><h1>Alerts</h1><p className="page-description">Explainable events persisted by your monitoring pipeline.</p></div>
      <div className="heading-stamp"><ShieldAlert size={17} /><span>Persisted evidence</span></div>
    </div>

    <section className="summary-grid" aria-label="Alert summary">
      <article className="summary-card summary-total"><div className="summary-label">Matching alerts</div><div className="summary-value">{data ? data.total.toLocaleString() : '—'}</div><div className="summary-foot">Current filters</div><span className="summary-index">01</span></article>
      <article className="summary-card"><div className="summary-label">Showing on this page</div><div className="summary-value">{data ? totalOnPage : '—'}</div><div className="summary-foot">Maximum {limit} records</div><span className="summary-index">02</span></article>
      <article className="summary-card severity-summary"><div className="summary-label">Severity · loaded page</div>{chartData.length > 0 ? <div className="severity-chart" role="img" aria-label={`Severity counts among the ${totalOnPage} alerts loaded on this page`}><Suspense fallback={<span className="chart-empty">Preparing chart…</span>}><SeverityChart data={chartData as SeverityDatum[]} /></Suspense><div className="severity-legend">{chartData.map((entry) => <span key={entry.severity}><i style={{ background: severityColor[entry.severity] }} />{entry.severity}<b>{entry.total}</b></span>)}</div></div> : <div className="chart-empty">{data ? 'No severity counts on this page' : 'Waiting for alert data'}</div>}<span className="summary-index">03</span></article>
    </section>

    <section className="filter-panel" aria-labelledby="filter-heading">
      <div className="section-heading"><div><span className="section-icon"><Filter size={15} /></span><h2 id="filter-heading">Filter observations</h2></div><span className="filter-scope">Applied filters are saved in this URL</span></div>
      <form className="filter-form" onSubmit={applyFilters} noValidate>
        <div className="filter-field"><label htmlFor="alert-severity">Severity</label><select id="alert-severity" value={draft.severity} onChange={(event) => setDraft((current) => ({ ...current, severity: event.target.value }))}><option value="">All severities</option>{severityOrder.map((severity) => <option key={severity} value={severity}>{severity.charAt(0).toUpperCase() + severity.slice(1)}</option>)}</select></div>
        <div className="filter-field"><label htmlFor="alert-status">Status</label><select id="alert-status" value={draft.status} onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value }))}><option value="">All statuses</option><option value="new">New</option><option value="acknowledged">Acknowledged</option></select></div>
        <div className="filter-field filter-detection"><label htmlFor="detection-code">Detection code</label><div className="search-input-wrap"><Search size={15} /><input ref={detectionInput} id="detection-code" value={draft.detectionCode} onChange={(event) => setDraft((current) => ({ ...current, detectionCode: event.target.value }))} placeholder="e.g. SYN_SCAN" maxLength={128} /><button className="clear-search" type="button" aria-label="Clear detection code" title="Clear detection code" disabled={!draft.detectionCode} onClick={() => { setDraft((current) => ({ ...current, detectionCode: '' })); detectionInput.current?.focus() }}>×</button></div></div>
        <DateFilterFields since={draft.since} until={draft.until} setSince={(since) => setDraft((current) => ({ ...current, since }))} setUntil={(until) => setDraft((current) => ({ ...current, until }))} describedBy="alert-date-error" invalid={Boolean(filterError)} />
        <div className="filter-actions"><button className="button button-primary" type="submit">Apply filters</button><button className="text-button" type="button" onClick={clearFilters} disabled={!hasFilters}>Clear</button></div>
      </form>
      {filterError && <p className="field-error" id="alert-date-error" role="alert">{filterError}</p>}
    </section>

    <section className="records-panel" aria-labelledby="records-heading">
      <div className="records-heading"><div><p className="eyebrow">Persisted observations</p><h2 id="records-heading">Alert register</h2></div><div className="records-meta">{data ? <><strong>{data.total.toLocaleString()}</strong> {data.total === 1 ? 'record' : 'records'}{busy && <span className="updating-label"><i />Updating</span>}</> : busy ? <span className="updating-label"><i />Loading</span> : 'No data'}</div></div>
      {error && data && <StaleState onRetry={() => setRetry((count) => count + 1)} />}
      {error && !data && <ErrorState message={error} onRetry={() => setRetry((count) => count + 1)} />}
      {!data && busy && <LoadingState label="Loading persisted alerts…" />}
      {data && data.items.length === 0 && !error && <EmptyState filtered={hasFilters} kind="alerts" />}
      {data && data.items.length > 0 && <>
        {actionMessage && <div className={`action-live${actionFailed ? ' action-failed' : ''}`} role={actionFailed ? 'alert' : 'status'} aria-live={actionFailed ? 'assertive' : 'polite'}>{actionMessage}</div>}
        <div className={`table-wrap${busy ? ' is-updating' : ''}`}>
          <table className="data-table alerts-table">
            <caption className="sr-only">Persisted alerts sorted by most recent event</caption>
            <thead><tr><th scope="col">Observed</th><th scope="col">Severity</th><th scope="col">Detection</th><th scope="col">Traffic</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>{data.items.map((alert) => <AlertRow key={alert.id} alert={alert} userRole={user?.role ?? 'viewer'} expanded={expanded === alert.id} onExpand={() => setExpanded((current) => current === alert.id ? null : alert.id)} pending={pendingId === alert.id} onAcknowledge={() => void acknowledge(alert)} />)}</tbody>
          </table>
        </div>
        <div className="mobile-record-list">{data.items.map((alert) => <AlertCard key={alert.id} alert={alert} userRole={user?.role ?? 'viewer'} expanded={expanded === alert.id} onExpand={() => setExpanded((current) => current === alert.id ? null : alert.id)} pending={pendingId === alert.id} onAcknowledge={() => void acknowledge(alert)} />)}</div>
        <Pagination page={page} pageSize={limit} total={data.total} onPage={setPage} onPageSize={setPageSize} />
      </>}
    </section>
  </div>
}

function AlertRow({ alert, userRole, expanded, onExpand, pending, onAcknowledge }: {
  alert: Alert; userRole: string; expanded: boolean; onExpand: () => void; pending: boolean; onAcknowledge: () => void
}) {
  const allowed = userRole === 'admin' || userRole === 'analyst'
  return <>
    <tr className="alert-row">
      <td><time className="time-cell" dateTime={alert.occurred_at} title={alert.occurred_at}>{formatDate(alert.occurred_at)}</time><span className="sub-cell">{alert.protocol}</span></td>
      <td><span className={`severity-badge severity-${alert.severity}`}><i aria-hidden="true" />{alert.severity}</span></td>
      <td><span className="detection-title">{alert.title}</span><code className="sub-cell code-cell">{alert.detection_code}</code></td>
      <td><EndpointPair alert={alert} /></td>
      <td><span className={`status-badge status-${alert.status}`}>{alert.status}</span></td>
      <td className="row-actions"><button type="button" className="detail-toggle" aria-expanded={expanded} onClick={onExpand}>{expanded ? 'Hide' : 'Details'}{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button>{alert.status === 'new' && (allowed ? <button type="button" className="ack-button" disabled={pending} aria-busy={pending} onClick={onAcknowledge}>{pending ? <span className="spinner spinner-small" /> : <Check size={14} />}{pending ? 'Saving' : 'Acknowledge'}</button> : <span className="permission-hint"><button className="ack-button disabled-action" type="button" disabled title="An analyst or administrator is required">Acknowledge</button><span>An analyst or administrator is required</span></span>)}</td>
    </tr>
    {expanded && <tr className="detail-row"><td colSpan={6}><AlertDetails alert={alert} /></td></tr>}
  </>
}

function AlertCard({ alert, userRole, expanded, onExpand, pending, onAcknowledge }: {
  alert: Alert; userRole: string; expanded: boolean; onExpand: () => void; pending: boolean; onAcknowledge: () => void
}) {
  const allowed = userRole === 'admin' || userRole === 'analyst'
  return <article className="mobile-record-card">
    <div className="mobile-record-top"><span className={`severity-badge severity-${alert.severity}`}><i />{alert.severity}</span><span className={`status-badge status-${alert.status}`}>{alert.status}</span></div>
    <h3>{alert.title}</h3><code className="code-cell">{alert.detection_code}</code>
    <div className="mobile-endpoints"><EndpointPair alert={alert} /></div>
    <time dateTime={alert.occurred_at} title={alert.occurred_at}>{formatDate(alert.occurred_at)}</time><span className="mobile-protocol">{alert.protocol}</span>
    <div className="mobile-card-actions"><button type="button" className="detail-toggle" aria-expanded={expanded} onClick={onExpand}>{expanded ? 'Hide details' : 'Show details'}{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button>{alert.status === 'new' && (allowed ? <button type="button" className="ack-button" disabled={pending} aria-busy={pending} onClick={onAcknowledge}>{pending ? 'Saving…' : 'Acknowledge'}</button> : <span className="permission-hint"><button className="ack-button disabled-action" type="button" disabled title="An analyst or administrator is required">Acknowledge</button><span>An analyst or administrator is required</span></span>)}</div>
    {expanded && <AlertDetails alert={alert} />}
  </article>
}
