import { describe, expect, it } from 'vitest'
import { formatEndpoint, localDateTimeValue, toUtcIso } from '../lib/presentation'

describe('network record presentation', () => {
  it('formats IPv4 and IPv6 endpoints without ambiguity', () => {
    expect(formatEndpoint({ ip: '192.0.2.10', port: 443 })).toBe('192.0.2.10:443')
    expect(formatEndpoint({ ip: '2001:db8::1', port: 53 })).toBe('[2001:db8::1]:53')
    expect(formatEndpoint({ ip: '192.0.2.11', port: null })).toBe('192.0.2.11')
  })

  it('keeps timezone offsets explicit in API date filters', () => {
    expect(toUtcIso('2026-10-22T10:30')).toMatch(/Z$/)
    expect(localDateTimeValue('not-a-date')).toBe('')
  })
})
