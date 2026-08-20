import { getJson } from './client'

export type HealthResponse = {
  status: 'ok'
}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== 'object' || value === null) {
    return false
  }

  return 'status' in value && value.status === 'ok'
}

export async function fetchHealth(signal: AbortSignal): Promise<HealthResponse> {
  const payload = await getJson('/api/health', signal)
  if (!isHealthResponse(payload)) {
    throw new Error('Backend returned an invalid health response')
  }

  return payload
}
