import { Activity, BadgeCheck, BrainCircuit, FileSearch, Fingerprint } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthProvider'
import { ErrorState, LoadingState, StaleState } from '../components/ListStates'
import { formatDate } from '../lib/presentation'
import type { EvaluationStatus, ModelStatus } from '../lib/types'

const statusLabels: Record<ModelStatus['status'], string> = {
  not_configured: 'Not configured',
  ready: 'Verified artifact',
  model_missing: 'Artifact missing',
  model_invalid: 'Invalid metadata',
  model_incompatible: 'Incompatible',
  model_corrupt: 'Checksum or file error',
}

const evaluationMessages: Record<EvaluationStatus, string> = {
  not_available: 'An evaluation report is unavailable until a configured model passes verification.',
  verified: 'This report is checksum-matched to the configured model metadata.',
  missing: 'No held-out evaluation report was found beside the configured model.',
  unverified: 'A report exists, but the model metadata does not contain a matching report checksum.',
  invalid: 'The report failed its checksum or held-out report validation and is hidden.',
}

function metric(value: number): string {
  return new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 1 }).format(value)
}

export function ModelPage() {
  const { request } = useAuth()
  const [data, setData] = useState<ModelStatus | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [retry, setRetry] = useState(0)

  const load = useCallback(async (signal?: AbortSignal) => {
    setBusy(true)
    setError('')
    try {
      setData(await request<ModelStatus>('/api/v1/model/status', { signal }))
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === 'AbortError') return
      setError(reason instanceof Error ? reason.message : 'Could not load model status.')
    } finally {
      if (!signal?.aborted) setBusy(false)
    }
  }, [request])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load, retry])

  return <div className="page-content">
    <div className="page-heading-row">
      <div><p className="eyebrow"><span className="eyebrow-marker" />Classifier registry</p><h1>Model &amp; evaluation</h1><p className="page-description">Inspect the configured model and its verified held-out evaluation report.</p></div>
      <div className="heading-stamp"><BrainCircuit size={17} /><span>Verified configured artifact</span></div>
    </div>

    {error && data && <StaleState onRetry={() => setRetry((count) => count + 1)} />}
    {error && !data && <ErrorState message={error} onRetry={() => setRetry((count) => count + 1)} />}
    {!data && busy && <LoadingState label="Checking configured model metadata…" />}

    {data && <>
      <section className="records-panel model-status-panel" aria-labelledby="model-status-heading">
        <div className="records-heading">
          <div><p className="eyebrow">Artifact state</p><h2 id="model-status-heading">Configured model</h2></div>
          <span className={`status-badge model-status model-status-${data.status}`}><i aria-hidden="true" />{statusLabels[data.status]}</span>
        </div>
        <div className="model-status-copy">
          {data.status === 'ready' ? <BadgeCheck size={22} aria-hidden="true" /> : <Activity size={22} aria-hidden="true" />}
          <p role="status">{data.message}{busy && <span className="updating-label"><i />Updating</span>}</p>
        </div>
        {data.model && <dl className="model-metadata-grid">
          <Metadata label="Model version" value={data.model.model_version} mono />
          <Metadata label="Selected estimator" value={data.model.selected_model.replaceAll('_', ' ')} />
          <Metadata label="Feature schema" value={`${data.model.feature_schema_version} · ${data.model.feature_count} features`} />
          <Metadata label="Classes" value={data.model.classes.join(', ')} />
          <Metadata label="Training dataset" value={data.model.dataset_name} />
          <Metadata label="Training rows" value={data.model.dataset_rows.toLocaleString()} />
          <Metadata label="Created" value={data.model.created_at_utc ? formatDate(data.model.created_at_utc) : 'Not recorded'} />
          <Metadata label="Dataset SHA-256" value={data.model.dataset_sha256} mono />
          <Metadata label="Artifact SHA-256" value={data.model.artifact_sha256} mono />
        </dl>}
        {data.status === 'not_configured' && <div className="model-next-step"><FileSearch size={16} /><span>Set <code>MODEL_PATH</code> to a trusted project model and restart the API to inspect it.</span></div>}
        {data.model && <p className="model-trust-note"><Fingerprint size={14} />The checksum verifies the artifact against its metadata; it does not prove who created it. Configure only a trusted artifact and review the dataset provenance.</p>}
      </section>

      <section className="records-panel evaluation-panel" aria-labelledby="evaluation-heading">
        <div className="records-heading">
          <div><p className="eyebrow">Held-out capture groups</p><h2 id="evaluation-heading">Evaluation report</h2></div>
          <span className={`evaluation-integrity evaluation-integrity-${data.evaluation_status}`}>{data.evaluation_status === 'verified' ? 'Integrity verified' : data.evaluation_status.replaceAll('_', ' ')}</span>
        </div>
        <p className="evaluation-message">{evaluationMessages[data.evaluation_status]}</p>
        {data.evaluation && <>
          <p className="evaluation-context">{data.evaluation.evaluation_split} · {data.evaluation.selected_model.replaceAll('_', ' ')} · model <code>{data.evaluation.model_version}</code></p>
          <div className="evaluation-metric-grid" aria-label="Held-out evaluation metrics">
            <Metric label="Accuracy" value={data.evaluation.accuracy} />
            <Metric label="Macro precision" value={data.evaluation.macro_precision} />
            <Metric label="Macro recall" value={data.evaluation.macro_recall} />
            <Metric label="Macro F1" value={data.evaluation.macro_f1} />
          </div>
          <div className="evaluation-detail-grid">
            <section className="evaluation-table-section" aria-labelledby="class-metrics-heading">
              <h3 id="class-metrics-heading">Per-class performance</h3>
              <div className="table-wrap"><table className="data-table evaluation-table">
                <caption className="sr-only">Precision, recall, F1, and support by actual class</caption>
                <thead><tr><th scope="col">Class</th><th scope="col">Precision</th><th scope="col">Recall</th><th scope="col">F1</th><th scope="col">Support</th></tr></thead>
                <tbody>{data.evaluation.classes.map((label) => {
                  const row = data.evaluation?.per_class[label]
                  return row ? <tr key={label}><th scope="row">{label}</th><td>{metric(row.precision)}</td><td>{metric(row.recall)}</td><td>{metric(row.f1)}</td><td>{row.support.toLocaleString()}</td></tr> : null
                })}</tbody>
              </table></div>
            </section>
            <section className="evaluation-table-section" aria-labelledby="confusion-heading">
              <h3 id="confusion-heading">Confusion matrix</h3>
              <div className="table-wrap"><table className="data-table confusion-table">
                <caption className="sr-only">Actual classes as rows; predicted classes as columns</caption>
                <thead><tr><th scope="col">Actual ↓ / Predicted →</th>{data.evaluation.classes.map((label) => <th scope="col" key={label}>{label}</th>)}</tr></thead>
                <tbody>{data.evaluation.classes.map((label, rowIndex) => <tr key={label}>
                  <th scope="row">{label}</th>
                  {data.evaluation?.confusion_matrix[rowIndex]?.map((count, columnIndex) => <td key={`${label}-${columnIndex}`}>{count.toLocaleString()}</td>)}
                </tr>)}</tbody>
              </table></div>
            </section>
          </div>
          <p className="evaluation-caveat">These are measurements from the report's held-out groups. They do not establish performance on other networks or prove a live intrusion.</p>
        </>}
      </section>
    </>}
  </div>
}

function Metadata({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="model-metadata-item"><dt>{label}</dt><dd className={mono ? 'metadata-mono' : undefined}>{value}</dd></div>
}

function Metric({ label, value }: { label: string; value: number }) {
  return <article className="evaluation-metric"><span>{label}</span><strong>{metric(value)}</strong></article>
}
