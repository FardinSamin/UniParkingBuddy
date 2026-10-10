// Requests stay on the web origin. Vite proxies /api during development,
// and a deployment reverse proxy must forward /api to the FastAPI server.
export async function getApiJson(path: string): Promise<unknown> {
  if (!path.startsWith('/api/')) {
    throw new Error('Invalid API route')
  }
  const response = await fetch(path, { headers: { Accept: 'application/json' } })
  if (!response.ok) {
    throw new Error('Backend information is unavailable')
  }
  return response.json() as Promise<unknown>
}
