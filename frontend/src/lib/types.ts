export type Role = 'admin' | 'analyst' | 'viewer'

export interface User {
  id: string
  username: string
  role: Role
  is_active: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface Endpoint {
  ip: string
  port: number | null
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface Alert {
  id: string
  flow_record_id: string
  detection_code: string
  source: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  explanation: string
  occurred_at: string
  protocol: string
  endpoint_a: Endpoint
  endpoint_b: Endpoint
  model_version: string | null
  evidence: Record<string, unknown>
  status: 'new' | 'acknowledged'
  acknowledged_by_user_id: string | null
  acknowledged_at: string | null
  created_at: string
}

export interface Prediction {
  status: string
  predicted_label: string | null
  model_version: string | null
  feature_schema_version: string
  predicted_at: string
  reason: string | null
}

export interface Flow {
  id: string
  capture_id: string
  flow_id: string
  protocol: string
  endpoint_a: Endpoint
  endpoint_b: Endpoint
  started_at: string
  last_seen_at: string
  ended_at: string
  finalization_reason: string
  features: Record<string, number>
  prediction: Prediction | null
  created_at: string
}

export interface TokenCursor {
  after_created_at: string
  after_id: string
}
