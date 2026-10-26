import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, ArrowRight, Check, CircleDot, FlaskConical, Network, RotateCcw, ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'

type Alert = { detection_code: string; title: string; severity: string; explanation: string; evidence: Record<string, number> }
type Flow = { protocol: string; source: { ip: string; port: number }; destination: { ip: string; port: number }; packets: number; bytes: number; syn_count: number; feature_schema: string; prediction_status: string; prediction_reason: string; alerts: Alert[] }
type Simulation = { mode: string; persisted: boolean; packet_count: number; flow_count: number; flows: Flow[] }
const stages = [
  { title: 'Packet source', detail: '24 controlled TCP SYN packets', icon: Network },
  { title: 'Metadata parser', detail: 'IP, ports, flags and length', icon: Activity },
  { title: 'Flow builder', detail: 'Bidirectional flow + counters', icon: CircleDot },
  { title: 'Feature & model', detail: 'Versioned features · model unavailable', icon: FlaskConical },
  { title: 'Rule detector', detail: 'SYN burst threshold: 20', icon: ShieldCheck },
]
export function SimulationPage() {
  const { request } = useAuth()
  const [result, setResult] = useState<Simulation | null>(null)
  const [step, setStep] = useState(-1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!busy || !result) return
    const timer = window.setInterval(() => setStep((current) => {
      if (current >= stages.length - 1) { window.clearInterval(timer); setBusy(false); return current }
      return current + 1
    }), 420)
    return () => window.clearInterval(timer)
  }, [busy, result])
  const run = async () => {
    setBusy(true); setError(''); setResult(null); setStep(-1)
    try { const response = await request<Simulation>('/api/v1/simulation', { method: 'POST' }); setResult(response); setStep(0) }
    catch (cause) { setBusy(false); setError(cause instanceof Error ? cause.message : 'Simulation could not be completed.') }
  }
  const alert = result?.flows.flatMap((flow) => flow.alerts)[0]
  const complete = Boolean(result && step === stages.length - 1 && !busy)
  return <div className="page-content simulation-page">
    <div className="page-heading-row"><div><p className="eyebrow"><span className="eyebrow-marker" /> Controlled demonstration</p><h1>Detection simulation</h1><p className="page-description">Watch synthetic traffic pass through the same packet, flow and detection code used by the monitor.</p></div>
      <button className="button button-primary" type="button" onClick={() => void run()} disabled={busy}><FlaskConical size={15} />{busy ? 'Running simulation…' : result ? 'Run again' : 'Run simulation'}</button>
    </div>
    <section className="simulation-notice" aria-label="Simulation scope"><AlertTriangle size={18} /><p><strong>Isolated synthetic data</strong><span>Reserved documentation IPs are used. This run does not capture live traffic or save records to the database.</span></p><span className="simulation-tag">DEMO MODE</span></section>
    {error && <section className="inline-error" role="alert"><div><strong>Simulation unavailable</strong><p>{error}</p></div></section>}
    <section className="records-panel simulation-panel" aria-labelledby="pipeline-heading"><div className="records-heading"><div><h2 id="pipeline-heading">Packet-to-alert pipeline</h2><p>Each stage lights up after the API completes the real pipeline run.</p></div><span className={`simulation-status ${complete ? 'is-complete' : busy ? 'is-running' : ''}`}><i />{complete ? 'Run complete' : busy ? 'Processing' : 'Ready'}</span></div>
      <div className="pipeline-grid" aria-label="Simulation pipeline progress">
        {stages.map((stage, index) => { const Icon = stage.icon; const passed = index <= step; return <div className={`pipeline-node ${passed ? 'is-passed' : ''} ${index === step && busy ? 'is-current' : ''}`} key={stage.title}>
          <div className="pipeline-node-icon">{passed && complete ? <Check size={18} /> : <Icon size={18} />}</div><span className="pipeline-index">0{index + 1}</span><strong>{stage.title}</strong><small>{result && index === 0 ? `${result.packet_count} controlled packets` : stage.detail}</small>
          {index < stages.length - 1 && <div className={`pipeline-connector ${index < step ? 'is-passed' : ''}`} aria-hidden="true"><ArrowRight size={15} /></div>}
        </div> })}
      </div>
      <div className="simulation-track" aria-hidden="true"><span className={busy ? 'is-moving' : complete ? 'is-done' : ''} /></div>
      {complete && <div className="simulation-result" role="status"><div className="simulation-result-heading"><ShieldCheck size={18} /><strong>Heuristic alert generated</strong><span>MEDIUM</span></div><div className="simulation-result-grid"><div><small>Detection rule</small><strong>{alert?.detection_code ?? 'No matching rule'}</strong></div><div><small>Evidence</small><strong>{alert ? `${alert.evidence.tcp_syn_count} SYN · ${alert.evidence.threshold} threshold` : 'No alert'}</strong></div><div><small>Model status</small><strong>Unavailable · rules only</strong></div></div><p>{alert?.explanation ?? 'No alert was generated for this sample.'}</p></div>}
    </section>
    {complete && result && <section className="simulation-lower-grid"><article className="records-panel simulation-panel"><div className="records-heading"><div><h2>Flow evidence</h2><p>Constructed from parsed packet metadata.</p></div></div><div className="simulation-endpoints"><div><small>Source</small><strong>{result.flows[0]?.source.ip}:{result.flows[0]?.source.port}</strong></div><ArrowRight size={16} /><div><small>Destination</small><strong>{result.flows[0]?.destination.ip}:{result.flows[0]?.destination.port}</strong></div></div><dl className="simulation-metrics"><div><dt>Flows</dt><dd>{result.flow_count}</dd></div><div><dt>Packets</dt><dd>{result.packet_count}</dd></div><div><dt>TCP SYN</dt><dd>{result.flows[0]?.syn_count}</dd></div><div><dt>Feature schema</dt><dd>{result.flows[0]?.feature_schema}</dd></div></dl></article><article className="records-panel simulation-panel"><div className="records-heading"><div><h2>Run notes</h2><p>How to interpret this demonstration.</p></div><RotateCcw size={16} /></div><ul className="simulation-notes"><li>Packets are generated server-side for this request only.</li><li>The flow is passed to the project’s production rule detector.</li><li>No model is configured; the result is a rule-based heuristic.</li><li>The alert is not persisted and does not indicate a real attack.</li></ul></article></section>}
  </div>
}
