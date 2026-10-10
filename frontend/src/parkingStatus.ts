// Shared validation for parking occupancy data from the backend.
export interface ParkingSpaceStatus {
  id: number
  occupied: boolean
}

export interface ParkingStatusResponse {
  cars_detected: number
  parking_spaces: ParkingSpaceStatus[]
}

function isParkingSpace(value: unknown): value is ParkingSpaceStatus {
  if (typeof value !== 'object' || value === null) return false

  const space = value as Record<string, unknown>
  return (
    typeof space.id === 'number' &&
    Number.isInteger(space.id) &&
    space.id > 0 &&
    typeof space.occupied === 'boolean'
  )
}

function parseParkingStatus(value: unknown): ParkingStatusResponse {
  if (typeof value !== 'object' || value === null) {
    throw new Error('Invalid parking status response')
  }

  const data = value as Record<string, unknown>
  if (
    typeof data.cars_detected !== 'number' ||
    !Number.isInteger(data.cars_detected) ||
    data.cars_detected < 0 ||
    !Array.isArray(data.parking_spaces) ||
    data.parking_spaces.length === 0 ||
    !data.parking_spaces.every(isParkingSpace)
  ) {
    throw new Error('Parking status data is unavailable or invalid')
  }

  const spaces: ParkingSpaceStatus[] = data.parking_spaces
  if (new Set(spaces.map((space) => space.id)).size !== spaces.length) {
    throw new Error('Duplicate parking-space identifiers')
  }

  return { cars_detected: data.cars_detected, parking_spaces: spaces }
}

export async function fetchParkingStatus(camera: string): Promise<ParkingStatusResponse> {
  const response = await fetch(`http://localhost:5000/api/status/${camera}`)

  if (!response.ok) {
    throw new Error('Parking status request failed')
  }

  return parseParkingStatus(await response.json())
}
