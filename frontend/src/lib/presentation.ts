import type { Endpoint } from './types'

export function formatEndpoint(endpoint: Endpoint): string {
  const address = endpoint.ip.includes(':') ? `[${endpoint.ip}]` : endpoint.ip
  return endpoint.port === null ? address : `${address}:${endpoint.port}`
}

export function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown time'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date)
}

export function localDateTimeValue(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export function toUtcIso(value: string): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

export function defaultUtcRange(now = new Date(), hours = 24): { since: string; until: string } {
  const until = now.toISOString()
  const since = new Date(now.getTime() - hours * 60 * 60 * 1000).toISOString()
  return { since, until }
}

export function validateDateRange(since: string, until: string, maximumHours?: number): string {
  const start = new Date(since).getTime()
  const end = new Date(until).getTime()
  if (!since || !until || Number.isNaN(start) || Number.isNaN(end)) {
    return 'Enter both a valid start time and end time.'
  }
  if (start > end) return 'The “From” time must be earlier than or equal to the “To” time.'
  if (maximumHours !== undefined && end - start > maximumHours * 60 * 60 * 1000) {
    return `This interval supports up to ${maximumHours.toLocaleString()} hours. Choose a shorter range or a wider bucket.`
  }
  return ''
}
