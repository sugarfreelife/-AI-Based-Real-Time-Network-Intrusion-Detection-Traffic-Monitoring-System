import { useId } from 'react'

export function DateFilterFields({ since, until, setSince, setUntil, describedBy, invalid }: {
  since: string
  until: string
  setSince: (value: string) => void
  setUntil: (value: string) => void
  describedBy: string
  invalid: boolean
}) {
  const id = useId()
  return <div className="date-filter-group">
    <div className="filter-field"><label htmlFor={`${id}-since`}>From</label><input id={`${id}-since`} type="datetime-local" value={since} onChange={(event) => setSince(event.target.value)} aria-invalid={invalid || undefined} aria-describedby={invalid ? describedBy : undefined} /></div>
    <div className="filter-field"><label htmlFor={`${id}-until`}>To</label><input id={`${id}-until`} type="datetime-local" value={until} onChange={(event) => setUntil(event.target.value)} aria-invalid={invalid || undefined} aria-describedby={invalid ? describedBy : undefined} /></div>
  </div>
}
