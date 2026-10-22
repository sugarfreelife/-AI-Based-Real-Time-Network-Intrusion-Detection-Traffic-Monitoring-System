import { ChevronDown, ChevronUp, Filter, Waves } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import { DateFilterFields } from '../components/DateFilterFields'
import { EmptyState, ErrorState, LoadingState, StaleState } from '../components/ListStates'
import { Pagination } from '../components/Pagination'
import { formatDate, formatEndpoint, localDateTimeValue, toUtcIso } from '../lib/presentation'
import type { Flow, Page } from '../lib/types'

function queryString(params: URLSearchParams): string {
  const query = new URLSearchParams()
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)
  const limit = [25, 50, 100].includes(Number(params.get('limit'))) ? Number(params.get('limit')) : 25
  query.set('limit', String(limit))
  query.set('offset', String((page - 1) * limit))
  for (const key of ['protocol', 'since', 'until']) {
    const value = params.get(key)
    if (value) query.set(key, value)
  }
  return query.toString()
}

function FlowDetails({ flow }: { flow: Flow }) {
  return <div className="record-details-grid">
    <div><span className="detail-label">Flow record ID</span><code>{flow.id}</code></div>
    <div><span className="detail-label">Capture ID</span><code>{flow.capture_id}</code></div>
    <div><span className="detail-label">Flow key</span><code>{flow.flow_id}</code></div>
    <div><span className="detail-label">Started</span><code>{flow.started_at}</code></div>
    <div><span className="detail-label">Last seen</span><code>{flow.last_seen_at}</code></div>
    <div><span className="detail-label">Finalized</span><span>{flow.finalization_reason}</span></div>
    <div><span className="detail-label">Prediction status</span><span>{flow.prediction?.status ?? 'No prediction record'}</span></div>
    <div><span className="detail-label">Model / feature schema</span><span>{flow.prediction ? `${flow.prediction.model_version ?? 'No model'} / ${flow.prediction.feature_schema_version}` : 'Not available'}</span></div>
    {flow.prediction?.reason && <div><span className="detail-label">Prediction note</span><span>{flow.prediction.reason}</span></div>}
    <div className="evidence-block"><span className="detail-label">Persisted flow features</span><pre>{JSON.stringify(flow.features, null, 2)}</pre></div>
  </div>
}

function FlowEndpoints({ flow }: { flow: Flow }) {
  return <span className="endpoint-pair"><span>{formatEndpoint(flow.endpoint_a)}</span><i aria-hidden="true">→</i><span>{formatEndpoint(flow.endpoint_b)}</span></span>
}

export function FlowsPage() {
  const { request } = useAuth()
  const [params, setParams] = useSearchParams()
  const paramKey = params.toString()
  const limit = [25, 50, 100].includes(Number(params.get('limit'))) ? Number(params.get('limit')) : 25
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)
  const query = useMemo(() => queryString(new URLSearchParams(paramKey)), [paramKey])
  const [data, setData] = useState<Page<Flow> | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [filterError, setFilterError] = useState('')
  const [draft, setDraft] = useState(() => ({
    protocol: params.get('protocol') ?? '',
    since: localDateTimeValue(params.get('since')),
    until: localDateTimeValue(params.get('until')),
  }))

  useEffect(() => {
    const current = new URLSearchParams(paramKey)
    setDraft({
      protocol: current.get('protocol') ?? '',
      since: localDateTimeValue(current.get('since')),
      until: localDateTimeValue(current.get('until')),
    })
  }, [paramKey])

  const load = useCallback(async (signal?: AbortSignal) => {
    setBusy(true)
    setError('')
    try {
      const response = await request<Page<Flow>>(`/api/v1/flows?${query}`, { signal })
      setData(response)
      const lastPage = Math.max(1, Math.ceil(response.total / response.limit))
      if (page > lastPage) {
        setParams((current) => { const next = new URLSearchParams(current); next.set('page', String(lastPage)); return next }, { replace: true })
      }
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      setError(reason instanceof Error ? reason.message : 'Could not load flows.')
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
    setFilterError('')
    if (draft.since && draft.until && new Date(draft.since).getTime() > new Date(draft.until).getTime()) {
      setFilterError('The “From” time must be earlier than or equal to the “To” time.')
      return
    }
    const next = new URLSearchParams({ page: '1', limit: String(limit) })
    if (draft.protocol) next.set('protocol', draft.protocol)
    const since = toUtcIso(draft.since)
    const until = toUtcIso(draft.until)
    if (since) next.set('since', since)
    if (until) next.set('until', until)
    setParams(next)
  }

  const hasFilters = Boolean(params.get('protocol') || params.get('since') || params.get('until'))
  const setPage = (nextPage: number) => setParams((current) => { const next = new URLSearchParams(current); next.set('page', String(nextPage)); return next })
  const setPageSize = (nextSize: number) => setParams((current) => { const next = new URLSearchParams(current); next.set('limit', String(nextSize)); next.set('page', '1'); return next })

  return <div className="page-content">
    <div className="page-heading-row">
      <div><p className="eyebrow"><span className="eyebrow-marker" />Traffic review</p><h1>Flows</h1><p className="page-description">Bidirectional conversations observed during authorized capture or replay.</p></div>
      <div className="heading-stamp"><Waves size={17} /><span>Flow observations</span></div>
    </div>

    <section className="flow-overview" aria-label="Flow summary">
      <article className="summary-card summary-total"><div className="summary-label">Matching flows</div><div className="summary-value">{data ? data.total.toLocaleString() : '—'}</div><div className="summary-foot">Current filters</div><span className="summary-index">01</span></article>
      <article className="summary-card"><div className="summary-label">Scored on this page</div><div className="summary-value">{data ? data.items.filter((flow) => flow.prediction?.status === 'scored').length : '—'}</div><div className="summary-foot">Of {data?.items.length ?? '—'} loaded records</div><span className="summary-index">02</span></article>
      <article className="summary-card"><div className="summary-label">Unscored / unavailable</div><div className="summary-value">{data ? data.items.filter((flow) => flow.prediction?.status !== 'scored').length : '—'}</div><div className="summary-foot">This page only</div><span className="summary-index">03</span></article>
    </section>

    <section className="filter-panel" aria-labelledby="filter-heading">
      <div className="section-heading"><div><span className="section-icon"><Filter size={15} /></span><h2 id="filter-heading">Filter observations</h2></div><span className="filter-scope">Applied filters are saved in this URL</span></div>
      <form className="filter-form flow-filter-form" onSubmit={applyFilters} noValidate>
        <div className="filter-field"><label htmlFor="flow-protocol">Protocol</label><select id="flow-protocol" value={draft.protocol} onChange={(event) => setDraft((current) => ({ ...current, protocol: event.target.value }))}><option value="">All protocols</option><option value="TCP">TCP</option><option value="UDP">UDP</option><option value="ICMP">ICMP</option><option value="ICMPV6">ICMPv6</option><option value="OTHER">Other</option></select></div>
        <DateFilterFields since={draft.since} until={draft.until} setSince={(since) => setDraft((current) => ({ ...current, since }))} setUntil={(until) => setDraft((current) => ({ ...current, until }))} describedBy="flow-date-error" invalid={Boolean(filterError)} />
        <div className="filter-actions"><button className="button button-primary" type="submit">Apply filters</button><button className="text-button" type="button" disabled={!hasFilters} onClick={() => { setFilterError(''); setParams({ page: '1', limit: String(limit) }) }}>Clear</button></div>
      </form>
      {filterError && <p className="field-error" id="flow-date-error" role="alert">{filterError}</p>}
    </section>

    <section className="records-panel" aria-labelledby="records-heading">
      <div className="records-heading"><div><p className="eyebrow">Persisted observations</p><h2 id="records-heading">Flow register</h2></div><div className="records-meta">{data ? <><strong>{data.total.toLocaleString()}</strong> {data.total === 1 ? 'record' : 'records'}{busy && <span className="updating-label"><i />Updating</span>}</> : busy ? <span className="updating-label"><i />Loading</span> : 'No data'}</div></div>
      {error && data && <StaleState onRetry={() => setRetry((count) => count + 1)} />}
      {error && !data && <ErrorState message={error} onRetry={() => setRetry((count) => count + 1)} />}
      {!data && busy && <LoadingState label="Loading persisted flows…" />}
      {data && data.items.length === 0 && !error && <EmptyState filtered={hasFilters} kind="flows" />}
      {data && data.items.length > 0 && <>
        <div className={`table-wrap${busy ? ' is-updating' : ''}`}>
          <table className="data-table flows-table">
            <caption className="sr-only">Persisted network flows sorted by most recently ended</caption>
            <thead><tr><th scope="col">Ended</th><th scope="col">Protocol</th><th scope="col">Endpoints</th><th scope="col">Prediction</th><th scope="col"><span className="sr-only">Details</span></th></tr></thead>
            <tbody>{data.items.map((flow) => <FlowRow key={flow.id} flow={flow} expanded={expanded === flow.id} onExpand={() => setExpanded((current) => current === flow.id ? null : flow.id)} />)}</tbody>
          </table>
        </div>
        <div className="mobile-record-list">{data.items.map((flow) => <FlowCard key={flow.id} flow={flow} expanded={expanded === flow.id} onExpand={() => setExpanded((current) => current === flow.id ? null : flow.id)} />)}</div>
        <Pagination page={page} pageSize={limit} total={data.total} onPage={setPage} onPageSize={setPageSize} />
      </>}
    </section>
  </div>
}

function PredictionBadge({ flow }: { flow: Flow }) {
  const prediction = flow.prediction
  if (!prediction) return <span className="prediction-badge prediction-unknown">No prediction</span>
  const scored = prediction.status === 'scored'
  return <span className={`prediction-badge ${scored ? 'prediction-scored' : 'prediction-unknown'}`}><i />{scored ? prediction.predicted_label ?? 'Scored' : prediction.status.replaceAll('_', ' ')}</span>
}

function FlowRow({ flow, expanded, onExpand }: { flow: Flow; expanded: boolean; onExpand: () => void }) {
  return <>
    <tr>
      <td><time className="time-cell" dateTime={flow.ended_at} title={flow.ended_at}>{formatDate(flow.ended_at)}</time><span className="sub-cell">Started {formatDate(flow.started_at)}</span></td>
      <td><span className="protocol-badge">{flow.protocol}</span></td>
      <td><FlowEndpoints flow={flow} /></td>
      <td><PredictionBadge flow={flow} /></td>
      <td className="row-actions"><button className="detail-toggle" type="button" aria-expanded={expanded} onClick={onExpand}>{expanded ? 'Hide' : 'Details'}{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button></td>
    </tr>
    {expanded && <tr className="detail-row"><td colSpan={5}><FlowDetails flow={flow} /></td></tr>}
  </>
}

function FlowCard({ flow, expanded, onExpand }: { flow: Flow; expanded: boolean; onExpand: () => void }) {
  return <article className="mobile-record-card">
    <div className="mobile-record-top"><span className="protocol-badge">{flow.protocol}</span><PredictionBadge flow={flow} /></div>
    <div className="mobile-endpoints"><FlowEndpoints flow={flow} /></div>
    <time dateTime={flow.ended_at} title={flow.ended_at}>{formatDate(flow.ended_at)}</time>
    <div className="mobile-card-actions"><button type="button" className="detail-toggle" aria-expanded={expanded} onClick={onExpand}>{expanded ? 'Hide details' : 'Show details'}{expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</button></div>
    {expanded && <FlowDetails flow={flow} />}
  </article>
}
