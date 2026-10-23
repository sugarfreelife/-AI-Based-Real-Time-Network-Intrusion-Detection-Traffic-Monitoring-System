import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { AnalyticsBucket } from '../lib/types'

function timeLabel(value: string, bucket: 'hour' | 'day'): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const options: Intl.DateTimeFormatOptions = bucket === 'hour'
    ? { month: 'short', day: 'numeric', hour: 'numeric' }
    : { month: 'short', day: 'numeric' }
  return new Intl.DateTimeFormat(undefined, options).format(date)
}

export function TrafficTimelineChart({ data, bucket }: { data: AnalyticsBucket[]; bucket: 'hour' | 'day' }) {
  return <div
    className="traffic-chart"
    role="img"
    aria-label={`${bucket === 'hour' ? 'Hourly' : 'Daily'} counts of persisted flows and alerts. A text table follows the chart.`}
  >
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 10, right: 17, bottom: 1, left: 0 }}>
        <CartesianGrid vertical={false} stroke="var(--line)" strokeDasharray="3 4" />
        <XAxis
          dataKey="timestamp"
          tickFormatter={(value: string) => timeLabel(value, bucket)}
          tick={{ fill: 'var(--muted)', fontSize: 10 }}
          tickLine={false}
          axisLine={{ stroke: 'var(--line)' }}
          minTickGap={25}
        />
        <YAxis
          allowDecimals={false}
          width={36}
          tick={{ fill: 'var(--muted)', fontSize: 10 }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip
          labelFormatter={(label) => timeLabel(String(label), bucket)}
          contentStyle={{ border: '1px solid var(--line)', borderRadius: 8, background: 'var(--paper)', fontSize: 11 }}
          cursor={{ stroke: 'var(--line)' }}
        />
        <Line type="monotone" dataKey="flow_count" name="Flows" stroke="var(--forest)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
        <Line type="monotone" dataKey="alert_count" name="Alerts" stroke="var(--rust)" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  </div>
}
