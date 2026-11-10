import { getApiJson } from './apiClient.ts'

// A forecast is never live occupancy. The default is explicitly synthetic.
export type ForecastMode = 'demo' | 'historical'
export type ForecastStatus = 'illustrative' | 'historical_estimate' | 'insufficient_history'

export interface ForecastLot {
  lot_id: string
  display_label: string
  total_spaces: number
  status: ForecastStatus
  estimated_available: number | null
  estimated_occupied: number | null
  estimated_open_percent: number | null
  historical_days: number
  historical_snapshots: number
}

export interface ForecastResult {
  requested_at: string
  timezone: 'America/New_York'
  mode: ForecastMode
  source: 'synthetic_demo' | 'verified_history'
  model: string
  basis: string
  historical_enabled: boolean
  lots: ForecastLot[]
}

function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Invalid forecast response')
  }
  return value as Record<string, unknown>
}

function integer(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

export function validateForecast(value: unknown, expectedMode: ForecastMode): ForecastResult {
  const result = object(value)
  if (
    result.mode !== expectedMode ||
    result.timezone !== 'America/New_York' ||
    (result.source !== 'synthetic_demo' && result.source !== 'verified_history') ||
    result.source !== (expectedMode === 'demo' ? 'synthetic_demo' : 'verified_history') ||
    result.model !== (expectedMode === 'demo'
      ? 'illustrative_schedule_v1'
      : 'weekday_hour_baseline_v1') ||
    typeof result.requested_at !== 'string' ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/.test(result.requested_at) ||
    !Number.isFinite(Date.parse(result.requested_at)) ||
    typeof result.basis !== 'string' || !result.basis.trim() ||
    typeof result.historical_enabled !== 'boolean' ||
    !Array.isArray(result.lots)
  ) throw new Error('Invalid forecast metadata')

  const ids = new Set<string>()
  for (const raw of result.lots) {
    const lot = object(raw)
    const status = lot.status
    if (
      typeof lot.lot_id !== 'string' || !lot.lot_id.trim() ||
      typeof lot.display_label !== 'string' || !lot.display_label.trim() ||
      ids.has(lot.lot_id) ||
      !integer(lot.total_spaces) || lot.total_spaces === 0 ||
      !integer(lot.historical_days) || !integer(lot.historical_snapshots) ||
      lot.historical_snapshots < lot.historical_days ||
      (status !== 'illustrative' && status !== 'historical_estimate' &&
        status !== 'insufficient_history') ||
      (expectedMode === 'demo' && status !== 'illustrative') ||
      (expectedMode === 'historical' && status === 'illustrative')
    ) throw new Error('Invalid forecast lot')

    if (status === 'insufficient_history') {
      if (
        lot.historical_days >= 3 ||
        lot.estimated_available !== null ||
        lot.estimated_occupied !== null ||
        lot.estimated_open_percent !== null
      ) throw new Error('Insufficient history cannot include numeric predictions')
    } else {
      if (
        !integer(lot.estimated_available) ||
        !integer(lot.estimated_occupied) ||
        lot.estimated_available + lot.estimated_occupied !== lot.total_spaces ||
        typeof lot.estimated_open_percent !== 'number' ||
        !Number.isFinite(lot.estimated_open_percent) ||
        lot.estimated_open_percent < 0 || lot.estimated_open_percent > 100 ||
        Math.abs(lot.estimated_open_percent -
          100 * lot.estimated_available / lot.total_spaces) > 0.051 ||
        (status === 'illustrative' &&
          (lot.historical_days !== 0 || lot.historical_snapshots !== 0)) ||
        (status === 'historical_estimate' && lot.historical_days < 3)
      ) throw new Error('Impossible forecast counts')
    }
    ids.add(lot.lot_id)
  }
  return result as unknown as ForecastResult
}

export async function fetchForecast(at: string, mode: ForecastMode): Promise<ForecastResult> {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(at)) {
    throw new Error('Select a campus date and time')
  }
  if (mode !== 'demo' && mode !== 'historical') {
    throw new Error('Invalid forecast mode')
  }
  const raw = await getApiJson(
    '/api/forecast?at=' + encodeURIComponent(at) + '&mode=' + mode,
  )
  return validateForecast(raw, mode)
}

// Date controls hold the literal CAMPUS wall-clock time. Do not convert
// input through the viewer's local UTC offset (which may not match UNCP).
export function defaultCampusTarget(now = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(now)
  const values: Record<string, string> = {}
  for (const part of parts) values[part.type] = part.value
  const next = new Date(Date.UTC(
    Number(values.year), Number(values.month) - 1, Number(values.day) + 1,
  ))
  return next.toISOString().slice(0, 10) + 'T14:00'
}
