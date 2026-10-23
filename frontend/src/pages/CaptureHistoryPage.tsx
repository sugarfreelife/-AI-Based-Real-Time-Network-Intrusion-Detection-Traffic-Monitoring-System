import { CalendarDays, ChevronDown, ChevronUp, FileClock } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { Pagination } from '../components/Pagination'
import { RangePanel } from '../components/RangePanel'
import { EmptyState, ErrorState, LoadingState, StaleState } from '../components/ListStates'
import { defaultUtcRange, formatDate, localDateTimeValue, toUtcIso, validateDateRange } from '../lib/presentation'
import type { CaptureRun, CaptureStatus, Page } from '../lib/types'

const statuses: CaptureStatus[] = ['running', 'completed', 'partial', 'failed']

function selectedLimit(value: string | null): number {
  const parsed = Number(value)
  return [25, 50, 100].includes(parsed) ? parsed : 25
}

function queryString(params: URLSearchParams, since: string, until: string): string {
  const limit = selectedLimit(params.get('limit'))
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)
  const query = new URLSearchParams({ limit: String(limit), offset: String((page - 1) * limit), since, until })
  const status = params.get('status')
  if (status && statuses.includes(status as CaptureStatus)) query.set('status', status)
  return query.toString()
}

export function CaptureHistoryPage() {
  const { request } = useAuth()
  const [params, setParams] = useSearchParams()
  const paramKey = params.toString()
  const [defaultRange] = useState(() => defaultUtcRange())
  const sinceUrl = params.get('since') || defaultRange.since
  const untilUrl = params.get('until') || defaultRange.until
  const statusUrl = params.get('status') || ''
  const limit = selectedLimit(params.get('limit'))
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)
  const query = useMemo(
    () => queryString(new URLSearchParams(paramKey), sinceUrl, untilUrl),
    [paramKey, sinceUrl, untilUrl],
  )
  const [draft, setDraft] = useState(() => ({
    since: localDateTimeValue(sinceUrl),
    until: localDateTimeValue(untilUrl),
    status: statusUrl,
  }))
  const [data, setData] = useState<Page<CaptureRun> | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const [filterError, setFilterError] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    const current = new URLSearchParams(paramKey)
    let changed = false
    if (!current.get('since')) { current.set('since', defaultRange.since); changed = true }
    if (!current.get('until')) { current.set('until', defaultRange.until); changed = true }
    if (!current.get('limit')) { current.set('limit', '25'); changed = true }
    if (!current.get('page')) { current.set('page', '1'); changed = true }
    if (changed) setParams(current, { replace: true })
  }, [defaultRange, paramKey, setParams])

  useEffect(() => {
    setDraft({
      since: localDateTimeValue(sinceUrl),
      until: localDateTimeValue(untilUrl),
      status: statusUrl,
    })
    setFilterError('')
  }, [sinceUrl, statusUrl, untilUrl])

  const load = useCallback(async (signal?: AbortSignal) => {
    setBusy(true)
    setError('')
    try {
      const response = await request<Page<CaptureRun>>(`/api/v1/captures?${query}`, { signal })
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
      setError(reason instanceof Error ? reason.message : 'Could not load capture history.')
    } finally {
      if (!signal?.aborted) setBusy(false)
    }
  }, [page, query, request, setParams])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load, retry])

  const applyFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const message = validateDateRange(draft.since, draft.until)
    setFilterError(message)
    if (message) return
    const since = toUtcIso(draft.since)
    const until = toUtcIso(draft.until)
    if (!since || !until) return
    const next = new URLSearchParams({ page: '1', limit: String(limit), since, until })
    if (draft.status) next.set('status', draft.status)
    setParams(next)
  }

  const resetFilters = () => {
    setFilterError('')
    setParams({ page: '1', limit: String(limit), since: defaultRange.since, until: defaultRange.until })
  }
  const hasFilters = Boolean(statusUrl || sinceUrl !== defaultRange.since || untilUrl !== defaultRange.until)
  const setPage = (nextPage: number) => setParams((current) => { const next = new URLSearchParams(current); next.set('page', String(nextPage)); return next })
  const setPageSize = (nextSize: number) => setParams((current) => { const next = new URLSearchParams(current); next.set('limit', String(nextSize)); next.set('page', '1'); return next })

  return <div className="page-content">
    <div className="page-heading-row">
      <div><p className="eyebrow"><span className="eyebrow-marker" />Replay records</p><h1>Capture history</h1><p className="page-description">Review completed and interrupted capture runs with their persisted counters.</p></div>
      <div className="heading-stamp"><FileClock size={17} /><span>Run ledger</span></div>
    </div>

    <RangePanel
      title="Filter capture runs"
      formClassName="history-filter-form"
      describedBy="capture-history-range"
      since={draft.since}
      until={draft.until}
      error={filterError}
      resetDisabled={!hasFilters}
      onSinceChange={(since) => setDraft((current) => ({ ...current, since }))}
      onUntilChange={(until) => setDraft((current) => ({ ...current, until }))}
      onApply={applyFilters}
      onReset={resetFilters}
    >
      <div className="filter-field">
        <label htmlFor="capture-status">Run status</label>
        <select id="capture-status" value={draft.status} onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value }))}>
          <option value="">All statuses</option>
          {statuses.map((status) => <option key={status} value={status}>{status.charAt(0).toUpperCase() + status.slice(1)}</option>)}
        </select>
      </div>
    </RangePanel>

    <section className="records-panel" aria-labelledby="capture-records-heading">
      <div className="records-heading">
        <div><p className="eyebrow">Stored execution summaries</p><h2 id="capture-records-heading">Capture register</h2></div>
        <div className="records-meta">{data ? <><strong>{data.total.toLocaleString()}</strong> {data.total === 1 ? 'run' : 'runs'}{busy && <span className="updating-label" role="status"><i />Updating</span>}</> : busy ? <span className="updating-label" role="status"><i />Loading</span> : 'No data'}</div>
      </div>
      {error && data && <StaleState onRetry={() => setRetry((count) => count + 1)} />}
      {error && !data && <ErrorState message={error} onRetry={() => setRetry((count) => count + 1)} />}
      {!data && busy && <LoadingState label="Loading capture runs…" />}
      {data && data.items.length === 0 && !error && (hasFilters
        ? <EmptyState filtered kind="capture runs" />
        : <div className="list-state empty-state"><span className="empty-icon"><CalendarDays size={21} /></span><strong>No recent capture runs</strong><p>No run started in the last 24 hours. Choose another range to check older history.</p></div>)}
      {data && data.items.length > 0 && <>
        <div className={`table-wrap${busy ? ' is-updating' : ''}`}>
          <table className="data-table capture-table">
            <caption className="sr-only">Capture runs ordered by most recent start time</caption>
            <thead><tr><th scope="col">Started</th><th scope="col">Source</th><th scope="col">Status</th><th scope="col">Packets</th><th scope="col">Flows / alerts</th><th scope="col">Retries</th><th scope="col"><span className="sr-only">Details</span></th></tr></thead>
            <tbody>{data.items.map((run) => <CaptureRunRow key={run.capture_id} run={run} expanded={expanded === run.capture_id} onExpand={() => setExpanded((current) => current === run.capture_id ? null : run.capture_id)} />)}</tbody>
          </table>
        </div>
        <div className="mobile-record-list">{data.items.map((run) => <CaptureRunCard key={run.capture_id} run={run} expanded={expanded === run.capture_id} onExpand={() => setExpanded((current) => current === run.capture_id ? null : run.capture_id)} />)}</div>
        <Pagination page={page} pageSize={limit} total={data.total} onPage={setPage} onPageSize={setPageSize} />
      </>}
    </section>
  </div>
}

function CaptureRunDetails({ run }: { run: CaptureRun }) {
  return <div className="record-details-grid">
    <div><span className="detail-label">Capture ID</span><code>{run.capture_id}</code></div>
    <div><span className="detail-label">Started at</span><code>{run.started_at}</code></div>
    <div><span className="detail-label">Completed at</span><code>{run.completed_at ?? 'Still running'}</code></div>
    <div><span className="detail-label">Packets seen / processed</span><span>{run.packets_seen.toLocaleString()} / {run.packets_processed.toLocaleString()}</span></div>
    <div><span className="detail-label">Filtered / parsing / read failures</span><span>{run.packets_filtered.toLocaleString()} / {run.parsing_failures.toLocaleString()} / {run.read_failures.toLocaleString()}</span></div>
    <div><span className="detail-label">Flows / duplicate flows</span><span>{run.flow_count.toLocaleString()} / {run.duplicate_flows.toLocaleString()}</span></div>
    <div><span className="detail-label">Predictions scored / unscored</span><span>{run.scored_count.toLocaleString()} / {run.unscored_count.toLocaleString()}</span></div>
    <div><span className="detail-label">Alerts / suppressed duplicates</span><span>{run.alert_count.toLocaleString()} / {run.suppressed_duplicate_alerts.toLocaleString()}</span></div>
    <div><span className="detail-label">Model</span><span>{run.model_status}{run.model_version ? ` · ${run.model_version}` : ''}</span></div>
    <div><span className="detail-label">Elapsed</span><span>{run.elapsed_seconds === null ? 'Not available' : `${run.elapsed_seconds.toFixed(2)} seconds`}</span></div>
    {run.failure_reason && <div><span className="detail-label">Failure reason</span><code>{run.failure_reason}</code></div>}
  </div>
}

function StatusBadge({ status }: { status: CaptureStatus }) {
  return <span className={`status-badge capture-status capture-status-${status}`}><i aria-hidden="true" />{status}</span>
}

function CaptureRunRow({ run, expanded, onExpand }: { run: CaptureRun; expanded: boolean; onExpand: () => void }) {
  return <>
    <tr>
      <td><time className="time-cell" dateTime={run.started_at} title={run.started_at}>{formatDate(run.started_at)}</time><span className="sub-cell">{run.completed_at ? `Finished ${formatDate(run.completed_at)}` : 'Still running'}</span></td>
      <td className="capture-source">{run.source_name}</td>
      <td><StatusBadge status={run.status} />{run.failure_reason && <span className="sub-cell">{run.failure_reason}</span>}</td>
      <td>{run.packets_seen.toLocaleString()}<span className="sub-cell">{run.packets_processed.toLocaleString()} processed</span></td>
      <td>{run.flow_count.toLocaleString()} flows<span className="sub-cell">{run.alert_count.toLocaleString()} alerts</span></td>
      <td>{run.attempt_count.toLocaleString()}<span className="sub-cell">{run.duplicate_flows.toLocaleString()} duplicates</span></td>
      <td className="row-actions"><button className="detail-toggle" type="button" aria-expanded={expanded} onClick={onExpand}>{expanded ? 'Hide' : 'Details'}{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button></td>
    </tr>
    {expanded && <tr className="detail-row"><td colSpan={7}><CaptureRunDetails run={run} /></td></tr>}
  </>
}

function CaptureRunCard({ run, expanded, onExpand }: { run: CaptureRun; expanded: boolean; onExpand: () => void }) {
  return <article className="mobile-record-card capture-card">
    <div className="mobile-record-top"><StatusBadge status={run.status} /><span className="mobile-protocol">{run.attempt_count.toLocaleString()} {run.attempt_count === 1 ? 'attempt' : 'attempts'}</span></div>
    <h3 className="capture-source">{run.source_name}</h3>
    <time dateTime={run.started_at} title={run.started_at}>{formatDate(run.started_at)}</time>
    <div className="capture-card-counts"><span>{run.flow_count.toLocaleString()} flows</span><span>{run.alert_count.toLocaleString()} alerts</span><span>{run.duplicate_flows.toLocaleString()} duplicates</span></div>
    {run.failure_reason && <span className="capture-failure">{run.failure_reason}</span>}
    <div className="mobile-card-actions"><button className="detail-toggle" type="button" aria-expanded={expanded} onClick={onExpand}>{expanded ? 'Hide details' : 'Show details'}{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button></div>
    {expanded && <CaptureRunDetails run={run} />}
  </article>
}
