import { Activity, Clock3, Database, Radio } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { RangePanel } from '../components/RangePanel'
import { ErrorState, LoadingState, StaleState } from '../components/ListStates'
import { TrafficTimelineChart } from '../components/TrafficTimelineChart'
import { defaultUtcRange, formatDate, localDateTimeValue, toUtcIso, validateDateRange } from '../lib/presentation'
import type { AnalyticsSummary, AnalyticsTimeline } from '../lib/types'

interface OverviewData {
  summary: AnalyticsSummary
  timeline: AnalyticsTimeline
}

function valuesPresent(values: Record<string, number>): Array<[string, number]> {
  return Object.entries(values).filter(([, count]) => count > 0).sort(([left], [right]) => left.localeCompare(right))
}

export function OverviewPage() {
  const { request } = useAuth()
  const [params, setParams] = useSearchParams()
  const paramKey = params.toString()
  const [defaultRange] = useState(() => defaultUtcRange())
  const sinceUrl = params.get('since') || defaultRange.since
  const untilUrl = params.get('until') || defaultRange.until
  const bucket = params.get('bucket') === 'day' ? 'day' : 'hour'
  const [draft, setDraft] = useState(() => ({
    since: localDateTimeValue(sinceUrl),
    until: localDateTimeValue(untilUrl),
    bucket,
  }))
  const [data, setData] = useState<OverviewData | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const [filterError, setFilterError] = useState('')
  const query = useMemo(() => {
    const values = new URLSearchParams({ since: sinceUrl, until: untilUrl, bucket })
    return values.toString()
  }, [bucket, sinceUrl, untilUrl])

  useEffect(() => {
    const current = new URLSearchParams(paramKey)
    let changed = false
    if (!current.get('since')) { current.set('since', defaultRange.since); changed = true }
    if (!current.get('until')) { current.set('until', defaultRange.until); changed = true }
    if (current.get('bucket') !== bucket) { current.set('bucket', bucket); changed = true }
    if (changed) setParams(current, { replace: true })
  }, [bucket, defaultRange, paramKey, setParams])

  useEffect(() => {
    setDraft({
      since: localDateTimeValue(sinceUrl),
      until: localDateTimeValue(untilUrl),
      bucket,
    })
    setFilterError('')
  }, [bucket, sinceUrl, untilUrl])

  const load = useCallback(async (signal?: AbortSignal) => {
    setBusy(true)
    setError('')
    try {
      const [summary, timeline] = await Promise.all([
        request<AnalyticsSummary>(`/api/v1/analytics/summary?since=${encodeURIComponent(sinceUrl)}&until=${encodeURIComponent(untilUrl)}`, { signal }),
        request<AnalyticsTimeline>(`/api/v1/analytics/timeline?${query}`, { signal }),
      ])
      setData({ summary, timeline })
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      setError(reason instanceof Error ? reason.message : 'Could not load overview data.')
    } finally {
      if (!signal?.aborted) setBusy(false)
    }
  }, [query, request, sinceUrl, untilUrl])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load, retry])

  const applyRange = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const maximumHours = draft.bucket === 'hour' ? 31 * 24 : 366 * 24
    const message = validateDateRange(draft.since, draft.until, maximumHours)
    setFilterError(message)
    if (message) return
    const since = toUtcIso(draft.since)
    const until = toUtcIso(draft.until)
    if (!since || !until) return
    setParams({ since, until, bucket: draft.bucket })
  }

  const resetRange = () => {
    setFilterError('')
    setParams({ since: defaultRange.since, until: defaultRange.until, bucket: 'hour' })
  }
  const hasDefaultRange = sinceUrl === defaultRange.since && untilUrl === defaultRange.until && bucket === 'hour'
  const protocolRows = data ? valuesPresent(data.summary.flows_by_protocol) : []
  const severityRows = data ? valuesPresent(data.summary.alerts_by_severity) : []
  const captureRows = data ? Object.entries(data.summary.capture_runs_by_status) : []
  const chartTotals = data?.timeline.items.reduce((totals, item) => ({
    flows: totals.flows + item.flow_count,
    alerts: totals.alerts + item.alert_count,
  }), { flows: 0, alerts: 0 })

  return <div className="page-content">
    <div className="page-heading-row">
      <div>
        <p className="eyebrow"><span className="eyebrow-marker" />Network activity</p>
        <h1>Overview</h1>
        <p className="page-description">Stored flows, alerts, and capture runs for the selected period.</p>
      </div>
      <div className="heading-stamp"><Activity size={17} /><span>Persisted records only</span></div>
    </div>

    <RangePanel
      title="Review a time range"
      formClassName="analytics-filter-form"
      describedBy="overview-range"
      since={draft.since}
      until={draft.until}
      error={filterError}
      resetDisabled={hasDefaultRange}
      onSinceChange={(since) => setDraft((current) => ({ ...current, since }))}
      onUntilChange={(until) => setDraft((current) => ({ ...current, until }))}
      onApply={applyRange}
      onReset={resetRange}
    >
      <div className="filter-field">
        <label htmlFor="timeline-bucket">Timeline interval</label>
        <select id="timeline-bucket" value={draft.bucket} onChange={(event) => setDraft((current) => ({ ...current, bucket: event.target.value as 'hour' | 'day' }))}>
          <option value="hour">Hourly · up to 31 days</option>
          <option value="day">Daily · up to 366 days</option>
        </select>
      </div>
    </RangePanel>

    {error && data && <StaleState onRetry={() => setRetry((count) => count + 1)} />}
    {error && !data && <ErrorState message={error} onRetry={() => setRetry((count) => count + 1)} />}
    {!data && busy && <LoadingState label="Loading persisted network activity…" />}

    <section className="analytics-summary-grid" aria-label="Persisted activity totals">
      <article className="summary-card summary-total">
        <div className="summary-label">Flows</div>
        <div className="summary-value">{data ? data.summary.flow_count.toLocaleString() : '—'}</div>
        <div className="summary-foot">Finalized in this period</div><span className="summary-index">01</span>
      </article>
      <article className="summary-card">
        <div className="summary-label">Alerts</div>
        <div className="summary-value">{data ? data.summary.alert_count.toLocaleString() : '—'}</div>
        <div className="summary-foot">Persisted detections</div><span className="summary-index">02</span>
      </article>
      <article className="summary-card">
        <div className="summary-label">Capture runs</div>
        <div className="summary-value">{data ? data.summary.capture_run_count.toLocaleString() : '—'}</div>
        <div className="summary-foot">Started in this period</div><span className="summary-index">03</span>
      </article>
    </section>

    <div className="analytics-detail-grid">
      <section className="records-panel timeline-panel" aria-labelledby="timeline-heading">
        <div className="records-heading">
          <div><p className="eyebrow">Time series</p><h2 id="timeline-heading">Flows and alerts</h2></div>
          <div className="records-meta">{data && <><Clock3 size={13} /><span>{formatDate(data.summary.since)} — {formatDate(data.summary.until)}</span></>}{busy && data && <span className="updating-label" role="status"><i />Updating</span>}</div>
        </div>
        {data && chartTotals && chartTotals.flows + chartTotals.alerts > 0
          ? <>
            <div className="timeline-legend"><span><i className="legend-flow" />Flows <strong>{chartTotals.flows.toLocaleString()}</strong></span><span><i className="legend-alert" />Alerts <strong>{chartTotals.alerts.toLocaleString()}</strong></span></div>
            <TrafficTimelineChart data={data.timeline.items} bucket={data.timeline.bucket} />
            <table className="sr-only"><caption>Timeline values in {data.timeline.bucket} intervals</caption><thead><tr><th scope="col">Time</th><th scope="col">Flows</th><th scope="col">Alerts</th></tr></thead><tbody>{data.timeline.items.map((item) => <tr key={item.timestamp}><th scope="row">{item.timestamp}</th><td>{item.flow_count}</td><td>{item.alert_count}</td></tr>)}</tbody></table>
          </>
          : data
            ? <div className="analytics-empty"><span className="empty-icon"><Radio size={20} /></span><strong>No persisted activity in this range</strong><p>Flows and alerts will appear here after an authorized capture is replayed.</p></div>
            : !error && <LoadingState label="Preparing the timeline…" />}
      </section>

      <section className="records-panel analytics-breakdowns" aria-labelledby="breakdowns-heading">
        <div className="records-heading"><div><p className="eyebrow">Database counts</p><h2 id="breakdowns-heading">Activity breakdown</h2></div><Database size={16} aria-hidden="true" /></div>
        {!data && !error && <LoadingState label="Loading counts…" />}
        {data && <div className="breakdown-list">
          <Breakdown title="Flows by protocol" empty="No flows in this period" rows={protocolRows} />
          <Breakdown title="Alerts by severity" empty="No alerts in this period" rows={severityRows} />
          <Breakdown title="Capture run status" empty="No capture runs in this period" rows={captureRows} />
        </div>}
      </section>
    </div>
  </div>
}

function Breakdown({ title, empty, rows }: { title: string; empty: string; rows: Array<[string, number]> }) {
  return <section className="breakdown-section" aria-label={title}>
    <h3>{title}</h3>
    {rows.length === 0
      ? <p className="breakdown-empty">{empty}</p>
      : <ul>{rows.map(([label, count]) => <li key={label}><span>{label.replaceAll('_', ' ')}</span><strong>{count.toLocaleString()}</strong></li>)}</ul>}
  </section>
}
