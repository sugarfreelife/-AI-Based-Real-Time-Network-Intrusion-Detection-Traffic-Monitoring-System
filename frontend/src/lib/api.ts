import type { TokenPair } from './types'

const configuredBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ?? ''
export const API_BASE = configuredBase.replace(/\/$/, '')

export function websocketUrl(path: string): string {
  const absolute = new URL(`${API_BASE}${path}`, window.location.origin)
  absolute.protocol = absolute.protocol === 'https:' ? 'wss:' : 'ws:'
  return absolute.toString()
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function responseError(response: Response): Promise<ApiError> {
  if (response.status === 401) return new ApiError('Your session has ended. Sign in again to continue.', 401)
  if (response.status === 403) return new ApiError('Your account does not have permission for this action.', 403)
  if (response.status === 422) return new ApiError('Some filter values are invalid. Review them and try again.', 422)
  if (response.status === 503) return new ApiError('The API cannot reach its database right now.', 503)
  if (response.status >= 500) return new ApiError('The API could not complete that request. Try again shortly.', response.status)
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string' && response.status === 401) {
      return new ApiError('The username or password did not match.', 401)
    }
  } catch {
    // Keep a stable, user-facing fallback when a response has no JSON body.
  }
  return new ApiError('The request could not be completed. Check the values and try again.', response.status)
}

export async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) throw await responseError(response)
  return (await response.json()) as T
}

export async function requestTokenPair(path: string, body: unknown): Promise<TokenPair> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'omit',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    if (path.endsWith('/token') && response.status === 401) {
      throw new ApiError('The username or password did not match.', 401)
    }
    throw await responseError(response)
  }
  return (await response.json()) as TokenPair
}

export async function requestRefresh(refreshToken: string): Promise<TokenPair> {
  return requestTokenPair('/api/v1/auth/refresh', { refresh_token: refreshToken })
}
