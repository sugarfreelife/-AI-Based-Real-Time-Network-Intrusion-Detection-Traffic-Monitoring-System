import { Filter } from 'lucide-react'
import type { PropsWithChildren, FormEvent } from 'react'
import { DateFilterFields } from './DateFilterFields'

interface RangePanelProps {
  title: string
  formClassName: string
  describedBy: string
  since: string
  until: string
  error: string
  resetDisabled: boolean
  onSinceChange: (value: string) => void
  onUntilChange: (value: string) => void
  onApply: (event: FormEvent<HTMLFormElement>) => void
  onReset: () => void
}

export function RangePanel({
  title,
  formClassName,
  describedBy,
  since,
  until,
  error,
  resetDisabled,
  onSinceChange,
  onUntilChange,
  onApply,
  onReset,
  children,
}: PropsWithChildren<RangePanelProps>) {
  return <section className="filter-panel" aria-labelledby={`${describedBy}-heading`}>
    <div className="section-heading">
      <div><span className="section-icon"><Filter size={15} /></span><h2 id={`${describedBy}-heading`}>{title}</h2></div>
      <span className="filter-scope">Applied values are saved in this URL</span>
    </div>
    <form className={`filter-form ${formClassName}`} onSubmit={onApply} noValidate>
      {children}
      <DateFilterFields
        since={since}
        until={until}
        setSince={onSinceChange}
        setUntil={onUntilChange}
        describedBy={`${describedBy}-error`}
        invalid={Boolean(error)}
      />
      <div className="filter-actions">
        <button className="button button-primary" type="submit">Apply range</button>
        <button className="text-button" type="button" onClick={onReset} disabled={resetDisabled}>Reset</button>
      </div>
    </form>
    {error && <p className="field-error" id={`${describedBy}-error`} role="alert">{error}</p>}
  </section>
}
