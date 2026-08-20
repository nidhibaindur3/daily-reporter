const configuredApiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

const apiBaseUrl = configuredApiBaseUrl.replace(/\/$/, '')

export async function getJson(
  path: string,
  signal: AbortSignal,
): Promise<unknown> {
  return requestJson(path, 'GET', signal)
}

export async function postJsonBody(
  path: string,
  body: unknown,
  signal: AbortSignal,
): Promise<unknown> {
  return requestJson(path, 'POST', signal, body)
}

async function requestJson(
  path: string,
  method: 'GET' | 'POST',
  signal: AbortSignal,
  body?: unknown,
): Promise<unknown> {
  const response = await fetch(apiBaseUrl + path, {
    method,
    signal,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error('API request failed with status ' + response.status)
  }

  return response.json()
}
