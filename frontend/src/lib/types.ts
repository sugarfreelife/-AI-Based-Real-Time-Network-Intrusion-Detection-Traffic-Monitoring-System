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

export type CaptureStatus = 'running' | 'completed' | 'partial' | 'failed'

export interface CaptureRun {
  capture_id: string
  source_name: string
  status: CaptureStatus
  started_at: string
  completed_at: string | null
  attempt_count: number
  packets_seen: number
  packets_processed: number
  packets_filtered: number
  parsing_failures: number
  read_failures: number
  flow_count: number
  duplicate_flows: number
  scored_count: number
  unscored_count: number
  alert_count: number
  suppressed_duplicate_alerts: number
  model_status: string
  model_version: string | null
  elapsed_seconds: number | null
  failure_reason: string | null
}

export interface AnalyticsSummary {
  since: string
  until: string
  flow_count: number
  alert_count: number
  capture_run_count: number
  capture_runs_by_status: Record<CaptureStatus, number>
  alerts_by_severity: Record<Alert['severity'], number>
  flows_by_protocol: Record<string, number>
}

export interface AnalyticsBucket {
  timestamp: string
  flow_count: number
  alert_count: number
}

export interface AnalyticsTimeline {
  since: string
  until: string
  bucket: 'hour' | 'day'
  items: AnalyticsBucket[]
}

export type ModelAvailability = 'not_configured' | 'ready' | 'model_missing' | 'model_invalid' | 'model_incompatible' | 'model_corrupt'
export type EvaluationStatus = 'not_available' | 'verified' | 'missing' | 'unverified' | 'invalid'

export interface ModelMetadata {
  model_version: string
  selected_model: 'logistic_regression' | 'random_forest'
  feature_schema_version: string
  feature_count: number
  classes: string[]
  created_at_utc: string | null
  dataset_name: string
  dataset_rows: number
  dataset_sha256: string
  artifact_sha256: string
}

export interface ClassEvaluation {
  precision: number
  recall: number
  f1: number
  support: number
}

export interface EvaluationReport {
  model_version: string
  selected_model: 'logistic_regression' | 'random_forest'
  evaluation_split: string
  accuracy: number
  macro_precision: number
  macro_recall: number
  macro_f1: number
  classes: string[]
  per_class: Record<string, ClassEvaluation>
  confusion_matrix: number[][]
  support: Record<string, number>
}

export interface ModelStatus {
  status: ModelAvailability
  configured: boolean
  message: string
  model: ModelMetadata | null
  evaluation_status: EvaluationStatus
  evaluation: EvaluationReport | null
}

export interface TokenCursor {
  after_created_at: string
  after_id: string
}
