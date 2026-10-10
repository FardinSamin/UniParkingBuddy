// Validate the new FastAPI configured-lot response before using it in React.
import { getApiJson } from './apiClient.ts'

export interface MonitoredLot {
  lot_id: string
  display_label: string
  camera: string
  space_ids: number[]
  total_spaces: number
  has_current_data: boolean
  available_spaces: number | null
  occupied_spaces: number | null
}

function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Invalid monitored-lot information')
  }
  return value as Record<string, unknown>
}

function count(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function spaceId(value: unknown): value is number {
  return count(value) && value > 0
}

export function validateMonitoredLots(raw: unknown): MonitoredLot[] {
  const payload = record(raw)
  if (!Array.isArray(payload.lots)) {
    throw new Error('Monitored lots are unavailable')
  }

  const lots: MonitoredLot[] = []
  const ids = new Set<string>()
  const cameras = new Set<string>()

  for (const rawLot of payload.lots) {
    const lot = record(rawLot)
    if (
      typeof lot.lot_id !== 'string' || !lot.lot_id.trim() ||
      typeof lot.display_label !== 'string' || !lot.display_label.trim() ||
      typeof lot.camera !== 'string' || !lot.camera.trim() ||
      ids.has(lot.lot_id) || cameras.has(lot.camera) ||
      !Array.isArray(lot.space_ids) ||
      !lot.space_ids.every(spaceId) ||
      new Set(lot.space_ids).size !== lot.space_ids.length ||
      !count(lot.total_spaces) || lot.total_spaces !== lot.space_ids.length ||
      typeof lot.has_current_data !== 'boolean'
    ) throw new Error('Invalid configured lot')

    if (lot.has_current_data) {
      if (
        !count(lot.available_spaces) ||
        !count(lot.occupied_spaces) ||
        lot.available_spaces + lot.occupied_spaces !== lot.total_spaces ||
        lot.total_spaces === 0
      ) throw new Error('Invalid live availability totals')
    } else if (lot.available_spaces !== null || lot.occupied_spaces !== null) {
      throw new Error('Unavailable occupancy cannot have numeric counts')
    }

    ids.add(lot.lot_id)
    cameras.add(lot.camera)
    lots.push(lot as unknown as MonitoredLot)
  }
  return lots
}

export async function fetchMonitoredLots(): Promise<MonitoredLot[]> {
  return validateMonitoredLots(await getApiJson('/api/lots'))
}
