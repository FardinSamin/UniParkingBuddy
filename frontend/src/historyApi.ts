import { getApiJson } from './apiClient.ts'

// Read-only historical observations. API JSON is untrusted until validated.
export interface HourlySample {
  hour_utc: number
  observations: number
  occupied_observations: number
  occupied_percent: number
}

export interface TrendsData {
  lot_id: string
  days: number
  timezone: 'UTC'
  space_ids: string[]
  has_history: boolean
  hourly: HourlySample[]
  basis: string
}

export interface SpaceHistoryData {
  lot_id: string
  space_id: string
  has_history: boolean
  records: { status: 'AVAILABLE' | 'OCCUPIED'; observed_at: string }[]
}

function object(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Invalid historical data')
  }
  return value as Record<string, unknown>
}

function nonnegativeInteger(n: unknown): n is number {
  return typeof n === 'number' && Number.isInteger(n) && n >= 0
}

async function getJSON(path: string): Promise<unknown> {
  return getApiJson(path)
}

export async function fetchTrends(lot: string, days = 7): Promise<TrendsData> {
  if (!Number.isInteger(days) || days < 1 || days > 31) {
    throw new Error('Invalid history window')
  }
  const data = object(await getJSON(`/api/trends/${encodeURIComponent(lot)}?days=${days}`))
  if (
    data.lot_id !== lot ||
    data.days !== days ||
    data.timezone !== 'UTC' ||
    typeof data.basis !== 'string' ||
    !Array.isArray(data.space_ids) ||
    !data.space_ids.every((id: unknown) => typeof id === 'string' && id.length > 0) ||
    new Set(data.space_ids).size !== data.space_ids.length ||
    typeof data.has_history !== 'boolean' ||
    !Array.isArray(data.hourly)
  ) throw new Error('Invalid historical summary')

  const hourSet = new Set<number>()
  for (const item of data.hourly) {
    const hour = object(item)
    if (
      !nonnegativeInteger(hour.hour_utc) || hour.hour_utc > 23 ||
      !nonnegativeInteger(hour.observations) || hour.observations === 0 ||
      !nonnegativeInteger(hour.occupied_observations) ||
      hour.occupied_observations > hour.observations ||
      typeof hour.occupied_percent !== 'number' ||
      !Number.isFinite(hour.occupied_percent) ||
      hour.occupied_percent < 0 || hour.occupied_percent > 100 ||
      Math.abs(hour.occupied_percent -
        (100 * hour.occupied_observations / hour.observations)) > 0.051 ||
      hourSet.has(hour.hour_utc)
    ) throw new Error('Invalid historical hourly data')
    hourSet.add(hour.hour_utc)
  }
  if (data.has_history !== (data.hourly.length > 0)) {
    throw new Error('Inconsistent historical summary')
  }
  return data as unknown as TrendsData
}

export async function fetchSpaceHistory(lot: string, space: string): Promise<SpaceHistoryData> {
  const data = object(await getJSON(
    `/api/history/${encodeURIComponent(lot)}/${encodeURIComponent(space)}`,
  ))
  if (
    data.lot_id !== lot ||
    data.space_id !== space ||
    typeof data.has_history !== 'boolean' ||
    !Array.isArray(data.records) ||
    data.records.length > 100
  ) throw new Error('Invalid space history')

  for (const item of data.records) {
    const record = object(item)
    if (
      (record.status !== 'AVAILABLE' && record.status !== 'OCCUPIED') ||
      typeof record.observed_at !== 'string' ||
      !Number.isFinite(Date.parse(record.observed_at))
    ) throw new Error('Invalid historical observation')
  }
  if (data.has_history !== (data.records.length > 0)) {
    throw new Error('Inconsistent space history')
  }
  return data as unknown as SpaceHistoryData
}
