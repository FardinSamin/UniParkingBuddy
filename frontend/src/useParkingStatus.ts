import { useCallback, useEffect, useState } from 'react'
import { fetchParkingStatus, type ParkingStatusResponse } from './parkingStatus.ts'

export type ParkingStatusState = 'loading' | 'current' | 'stale' | 'unavailable'

export interface ParkingStatusResult {
  state: ParkingStatusState
  data: ParkingStatusResponse | null
  lastFetchedAt: string | null
  error: string | null
  retry: () => void
}

const POLL_INTERVAL_MS = 1000

export function useParkingStatus(camera: string): ParkingStatusResult {
  const [state, setState] = useState<ParkingStatusState>('loading')
  const [data, setData] = useState<ParkingStatusResponse | null>(null)
  const [lastFetchedAt, setLastFetchedAt] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retryVersion, setRetryVersion] = useState(0)

  const retry = useCallback(() => setRetryVersion((version) => version + 1), [])

  useEffect(() => {
    let active = true
    let requestInProgress = false

    const refresh = () => {
      if (requestInProgress) return
      requestInProgress = true
      fetchParkingStatus(camera)
        .then((response) => {
          if (!active) return
          setData(response)
          setLastFetchedAt(new Date().toISOString())
          setError(null)
          setState('current')
        })
        .catch(() => {
          if (!active) return
          setError('Could not refresh parking status.')
          setState((previous) => previous === 'current' || previous === 'stale'
            ? 'stale'
            : 'unavailable')
        })
        .finally(() => {
          requestInProgress = false
        })
    }

    refresh()
    const interval = window.setInterval(refresh, POLL_INTERVAL_MS)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [camera, retryVersion])

  return { state, data, lastFetchedAt, error, retry }
}
