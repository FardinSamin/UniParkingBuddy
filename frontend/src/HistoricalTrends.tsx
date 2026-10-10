import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { fetchSpaceHistory, fetchTrends, type SpaceHistoryData, type TrendsData } from './historyApi'
import './App.css'

const HOURS = Array.from({ length: 24 }, (_, index) => index)

export default function HistoricalTrends() {
  const { lotId } = useParams<{ lotId: string }>()
  const navigate = useNavigate()
  const validLot = lotId === 'lot1' || lotId === 'lot2'
  const lotName = lotId === 'lot1' ? 'Lot 1' : 'Lot 2'

  const [trends, setTrends] = useState<TrendsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [spaceId, setSpaceId] = useState('')
  const [history, setHistory] = useState<SpaceHistoryData | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)

  useEffect(() => {
    if (!validLot || !lotId) return
    let active = true
    fetchTrends(lotId)
      .then((data) => {
        if (!active) return
        setTrends(data)
        setSpaceId(data.space_ids[0] ?? '')
        setLoading(false)
        setError(null)
      })
      .catch(() => {
        if (!active) return
        setLoading(false)
        setError('Historical records are unavailable. Check PostgreSQL and the backend.')
      })
    return () => { active = false }
  }, [lotId, validLot])

  useEffect(() => {
    if (!validLot || !lotId || !spaceId) return
    let active = true
    fetchSpaceHistory(lotId, spaceId)
      .then((data) => {
        if (!active) return
        setHistory(data)
        setHistoryError(null)
        setHistoryLoading(false)
      })
      .catch(() => {
        if (!active) return
        setHistory(null)
        setHistoryError('This space’s historical records are unavailable.')
        setHistoryLoading(false)
      })
    return () => { active = false }
  }, [lotId, validLot, spaceId])

  function changeSpace(id: string) {
    setSpaceId(id)
    setHistory(null)
    setHistoryError(null)
    setHistoryLoading(true)
  }

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div className="dashboard-header-top">
          <div>
            <p className="dashboard-eyebrow">{validLot ? lotName : 'Unknown lot'}</p>
            <h1 className="dashboard-title">Historical occupancy</h1>
          </div>
          <button className="dashboard-back-btn" onClick={() => navigate('/')}>
            ← All lots
          </button>
        </div>
      </header>

      <main className="history-body">
        <p className="history-explanation">
          This view summarizes stored occupancy observations, not live availability,
          parked duration, or future predictions. Replayed test-video results do
          not establish actual campus busy times.
        </p>
        {!validLot ? (
          <p role="alert">This lot is not configured for historical monitoring.</p>
        ) : loading ? (
          <p role="status">Loading historical observations...</p>
        ) : error ? (
          <p className="error" role="alert">{error}</p>
        ) : trends ? (
          <>
            <section className="history-section" aria-labelledby="hourly-heading">
              <h2 id="hourly-heading">Observed occupancy by hour (UTC)</h2>
              <p className="history-muted">
                Last {trends.days} days · The percentage is the share of recorded
                per-space observations marked occupied. Missing hours mean no
                records, not 0% occupancy.
              </p>
              {trends.has_history ? (
                <div className="history-chart-scroll">
                  <div className="history-chart" role="group" aria-label="Recorded occupancy shares by UTC hour">
                    {HOURS.map((hour) => {
                      const sample = trends.hourly.find((row) => row.hour_utc === hour)
                      return (
                        <div className="history-hour" key={hour}>
                          <div className="history-column">
                            {sample ? (
                              <div
                                className="history-bar"
                                style={{ height: `${sample.occupied_percent}%` }}
                                title={`${hour}:00 UTC: ${sample.occupied_percent}% occupied among ${sample.observations} observations`}
                                aria-label={`${hour}:00 UTC, ${sample.occupied_percent}% occupied among ${sample.observations} observations`}
                              />
                            ) : (
                              <span className="history-no-sample" title="No observations">—</span>
                            )}
                          </div>
                          <span className="history-hour-label">{String(hour).padStart(2, '0')}</span>
                          <span className="history-percent-label">
                            {sample ? `${sample.occupied_percent}%` : 'No data'}
                          </span>
                          <span className="history-count-label">
                            {sample ? `n=${sample.observations}` : ''}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : (
                <p role="status">No historical observations for this time window yet.</p>
              )}
            </section>

            <section className="history-section" aria-labelledby="space-history-heading">
              <h2 id="space-history-heading">Parking-space observations</h2>
              <p className="history-muted">
                The most recent 100 recorded observations for the selected space.
                Times below use your device’s time zone.
              </p>
              {trends.space_ids.length === 0 ? (
                <p>No configured spaces are available for this lot.</p>
              ) : (
                <>
                  <label className="history-select-label" htmlFor="history-space-select">
                    Parking space
                  </label>
                  <select
                    className="history-select"
                    id="history-space-select"
                    value={spaceId}
                    onChange={(event) => changeSpace(event.target.value)}
                  >
                    {trends.space_ids.map((id) => (
                      <option key={id} value={id}>Space {id}</option>
                    ))}
                  </select>
                  {historyLoading ? (
                    <p role="status">Loading space history...</p>
                  ) : historyError ? (
                    <p role="alert" className="error">{historyError}</p>
                  ) : history && history.space_id === spaceId ? (
                    history.has_history ? (
                      <div className="history-record-list">
                        {history.records.map((record, index) => (
                          <div key={`${record.observed_at}-${index}`} className="history-record">
                            <span>{new Date(record.observed_at).toLocaleString()}</span>
                            <strong>{record.status === 'OCCUPIED' ? 'Occupied' : 'Available'}</strong>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p>No historical observations have been stored for this space yet.</p>
                    )
                  ) : null}
                </>
              )}
            </section>
          </>
        ) : null}
      </main>
    </div>
  )
}
