import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type Severity = 'low' | 'medium' | 'high' | 'critical'

export interface SeverityDatum {
  severity: Severity
  total: number
}

const colors: Record<Severity, string> = {
  critical: 'var(--critical)',
  high: 'var(--high)',
  medium: 'var(--medium)',
  low: 'var(--low)',
}

export default function SeverityChart({ data }: { data: SeverityDatum[] }) {
  return <ResponsiveContainer width="100%" height="100%">
    <BarChart data={data} layout="vertical" margin={{ top: 1, right: 22, bottom: 0, left: 1 }}>
      <CartesianGrid horizontal={false} stroke="var(--line)" />
      <XAxis type="number" allowDecimals={false} hide />
      <YAxis type="category" dataKey="severity" width={62} tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
      <Tooltip cursor={{ fill: 'rgba(33,78,69,.06)' }} contentStyle={{ border: '1px solid var(--line)', borderRadius: 8, background: 'var(--paper)', fontSize: 12 }} />
      <Bar dataKey="total" name="Alerts on this page" barSize={12} radius={[0, 3, 3, 0]}>
        {data.map((entry) => <Cell key={entry.severity} fill={colors[entry.severity]} />)}
      </Bar>
    </BarChart>
  </ResponsiveContainer>
}
