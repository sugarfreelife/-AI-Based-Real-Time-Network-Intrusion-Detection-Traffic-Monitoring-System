import { AlertCircle, Inbox, RefreshCw } from 'lucide-react'

export function LoadingState({ label }: { label: string }) {
  return <div className="list-state loading-state" role="status" aria-live="polite"><span className="spinner" aria-hidden="true" />{label}</div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="inline-error" role="alert"><AlertCircle size={18} /><div><strong>Data could not be refreshed</strong><p>{message}</p></div><button className="button button-secondary" type="button" onClick={onRetry}><RefreshCw size={14} />Retry</button></div>
}

export function EmptyState({ filtered, kind }: { filtered: boolean; kind: string }) {
  return <div className="list-state empty-state"><span className="empty-icon"><Inbox size={22} /></span><strong>{filtered ? 'No matching records' : `No ${kind} recorded yet`}</strong><p>{filtered ? 'Adjust or clear the filters to see more records.' : 'When this pipeline persists new observations, they will appear here.'}</p></div>
}

export function StaleState({ onRetry }: { onRetry: () => void }) {
  return <div className="stale-banner" role="status"><span>Showing the last loaded results. The latest refresh did not complete.</span><button className="text-button" type="button" onClick={onRetry}>Try again</button></div>
}
