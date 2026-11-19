import type { ParkingStatusState } from './useParkingStatus.ts'

interface Props {
  state: ParkingStatusState
  lastFetchedAt: string | null
  observedAt?: string
  onRetry: () => void
}

const STATE_LABELS: Record<ParkingStatusState, string> = {
  loading: 'Loading',
  current: 'Status received',
  stale: 'Update delayed',
  unavailable: 'Status unavailable',
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'medium',
  }).format(new Date(value))
}

interface FreshnessTextProps {
  lastFetchedAt: string
  observedAt?: string
}

export function FreshnessText({ lastFetchedAt, observedAt }: FreshnessTextProps) {
  return (
    <>
      <p className="freshness-summary">
        Last checked at <time dateTime={lastFetchedAt}>{formatTime(lastFetchedAt)}</time>
        {' · '}
        {observedAt ? (
          <>Occupancy observed at <time dateTime={observedAt}>{formatTime(observedAt)}</time>.</>
        ) : (
          'Observation time unavailable.'
        )}
      </p>
      <details className="freshness-explanation">
        <summary>About these times</summary>
        <p>
          {observedAt
            ? 'Last checked shows when this page successfully retrieved data. Occupancy observed shows when the camera observation was recorded.'
            : 'Last checked shows when this page successfully retrieved data. The camera’s observation time is currently unavailable.'}
        </p>
      </details>
    </>
  )
}

export default function ParkingFreshness({ state, lastFetchedAt, observedAt, onRetry }: Props) {
  return (
    <section className={`status-freshness status-freshness-${state}`} aria-label="Status freshness">
      <p><strong>{STATE_LABELS[state]}</strong></p>
      {lastFetchedAt && (
        <FreshnessText lastFetchedAt={lastFetchedAt} observedAt={observedAt} />
      )}
      {state === 'stale' && <p>Showing the last received occupancy; its age cannot be verified.</p>}
      {state === 'unavailable' && <p>No occupancy counts are available. They are not zero.</p>}
      <button className="status-retry" type="button" onClick={onRetry}>
        {state === 'current' ? 'Refresh status' : 'Retry'}
      </button>
    </section>
  )
}
