import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { CaptureHistoryPage } from '../pages/CaptureHistoryPage'
import { OverviewPage } from '../pages/OverviewPage'

const { requestMock } = vi.hoisted(() => ({ requestMock: vi.fn() }))

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ request: requestMock }) }))
vi.mock('../components/TrafficTimelineChart', () => ({ TrafficTimelineChart: () => <div role="img" aria-label="Persisted activity chart" /> }))

const summary = {
  since: '2026-10-22T00:00:00Z',
  until: '2026-10-23T00:00:00Z',
  flow_count: 127,
  alert_count: 4,
  capture_run_count: 2,
  capture_runs_by_status: { running: 0, completed: 1, partial: 1, failed: 0 },
  alerts_by_severity: { low: 1, medium: 1, high: 2, critical: 0 },
  flows_by_protocol: { TCP: 91, UDP: 36 },
}

const timeline = {
  since: summary.since,
  until: summary.until,
  bucket: 'hour',
  items: [
    { timestamp: '2026-10-22T00:00:00Z', flow_count: 91, alert_count: 3 },
    { timestamp: '2026-10-22T01:00:00Z', flow_count: 36, alert_count: 1 },
  ],
}

const captureRun = {
  capture_id: 'capture-a',
  source_name: 'authorized-demo.pcap',
  status: 'completed',
  started_at: '2026-10-22T12:00:00Z',
  completed_at: '2026-10-22T12:00:10Z',
  attempt_count: 2,
  packets_seen: 240,
  packets_processed: 238,
  packets_filtered: 1,
  parsing_failures: 1,
  read_failures: 0,
  flow_count: 8,
  duplicate_flows: 2,
  scored_count: 0,
  unscored_count: 8,
  alert_count: 0,
  suppressed_duplicate_alerts: 0,
  model_status: 'unavailable',
  model_version: null,
  elapsed_seconds: 10,
  failure_reason: null,
}

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="Current URL">{location.pathname}{location.search}</output>
}

function renderPage(path: string, element: React.ReactNode) {
  return render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/overview" element={<>{element}<LocationProbe /></>} />
    <Route path="/history" element={<>{element}<LocationProbe /></>} />
  </Routes></MemoryRouter>)
}

function mockDashboardResponses() {
  requestMock.mockImplementation(async (path: string) => {
    if (path.startsWith('/api/v1/analytics/summary')) return summary
    if (path.startsWith('/api/v1/analytics/timeline')) return timeline
    return { items: [captureRun], total: 30, limit: 25, offset: 0 }
  })
}

afterEach(() => {
  cleanup()
  requestMock.mockReset()
})

describe('overview and capture history dashboard', () => {
  it('shows persisted overview counts and an accessible timeline table', async () => {
    mockDashboardResponses()
    renderPage('/overview?since=2026-10-22T00%3A00%3A00Z&until=2026-10-23T00%3A00%3A00Z&bucket=hour', <OverviewPage />)

    expect((await screen.findAllByText('127')).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('4').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByRole('table', { name: /timeline values/i })).toHaveTextContent('91')
    expect(screen.getByRole('img', { name: /persisted activity chart/i })).toBeInTheDocument()
    expect(requestMock).toHaveBeenCalledWith(expect.stringContaining('/api/v1/analytics/summary?since='), expect.any(Object))
    expect(requestMock).toHaveBeenCalledWith(expect.stringContaining('/api/v1/analytics/timeline?'), expect.any(Object))
  })

  it('saves overview time range and interval in the URL', async () => {
    mockDashboardResponses()
    const user = userEvent.setup()
    renderPage('/overview?since=2026-10-22T00%3A00%3A00Z&until=2026-10-23T00%3A00%3A00Z&bucket=hour', <OverviewPage />)

    await screen.findAllByText('127')
    await user.selectOptions(screen.getByLabelText('Timeline interval'), 'day')
    await user.click(screen.getByRole('button', { name: 'Apply range' }))

    await waitFor(() => expect(screen.getByLabelText('Current URL')).toHaveTextContent('bucket=day'))
    await waitFor(() => expect(requestMock).toHaveBeenCalledWith(expect.stringContaining('bucket=day'), expect.any(Object)))
  })

  it('loads run details and applies the selected history status', async () => {
    mockDashboardResponses()
    const user = userEvent.setup()
    renderPage('/history?since=2026-10-22T00%3A00%3A00Z&until=2026-10-23T00%3A00%3A00Z&limit=25&page=1', <CaptureHistoryPage />)

    expect((await screen.findAllByText('authorized-demo.pcap')).length).toBeGreaterThanOrEqual(1)
    const [detailsButton] = screen.getAllByRole('button', { name: 'Details' })
    if (!detailsButton) throw new Error('Expected a capture details button')
    await user.click(detailsButton)
    expect(screen.getAllByText('Packets seen / processed').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('240 / 238').length).toBeGreaterThanOrEqual(1)

    await user.selectOptions(screen.getByLabelText('Run status'), 'completed')
    await user.click(screen.getByRole('button', { name: 'Apply range' }))
    await waitFor(() => expect(screen.getByLabelText('Current URL')).toHaveTextContent('status=completed'))
    await waitFor(() => expect(requestMock).toHaveBeenCalledWith(expect.stringContaining('status=completed'), expect.any(Object)))
  })

  it('keeps pagination state in the URL and translates it to the API offset', async () => {
    mockDashboardResponses()
    const user = userEvent.setup()
    renderPage('/history?since=2026-10-22T00%3A00%3A00Z&until=2026-10-23T00%3A00%3A00Z&limit=25&page=1', <CaptureHistoryPage />)

    await screen.findAllByText('authorized-demo.pcap')
    await user.click(screen.getByRole('button', { name: 'Next page' }))

    await waitFor(() => expect(screen.getByLabelText('Current URL')).toHaveTextContent('page=2'))
    await waitFor(() => expect(requestMock).toHaveBeenCalledWith(expect.stringContaining('offset=25'), expect.any(Object)))
  })

  it('shows a recoverable empty-load error and retries the analytics request', async () => {
    let summaryAttempts = 0
    requestMock.mockImplementation((path: string) => {
      if (path.startsWith('/api/v1/analytics/summary')) {
        summaryAttempts += 1
        return summaryAttempts === 1 ? Promise.reject(new Error('Analytics unavailable')) : Promise.resolve(summary)
      }
      return Promise.resolve(timeline)
    })
    const user = userEvent.setup()
    renderPage('/overview?since=2026-10-22T00%3A00%3A00Z&until=2026-10-23T00%3A00%3A00Z&bucket=hour', <OverviewPage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Analytics unavailable')
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect((await screen.findAllByText('127')).length).toBeGreaterThanOrEqual(1)
  })
})
