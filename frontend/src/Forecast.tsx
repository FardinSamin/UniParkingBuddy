import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  defaultCampusTarget, fetchForecast,
  type ForecastMode, type ForecastResult, type ForecastLot,
} from './forecastApi.ts'
import './App.css'

const SUGGESTED_HOURS = [
  { label: '8 AM', time: '08:00' },
  { label: 'Noon', time: '12:00' },
  { label: '5 PM', time: '17:00' },
  { label: '9 PM', time: '21:00' },
]

function formatCampusTimestamp(raw: string): string {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
    hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
  }).format(new Date(raw))
}

function forecastRank(lot: ForecastLot): number {
  return lot.estimated_available ?? -1
}

export default function Forecast() {
  const navigate = useNavigate()
  const [target, setTarget] = useState(() => defaultCampusTarget())
  const [mode, setMode] = useState<ForecastMode>('demo')
  const [submitted, setSubmitted] = useState(() => ({
    at: defaultCampusTarget(), mode: 'demo' as ForecastMode,
  }))
  const [result, setResult] = useState<ForecastResult | null>(null)
  const [historicalEnabled, setHistoricalEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setResult(null)
    setError(null)
    setLoading(true)
    fetchForecast(submitted.at, submitted.mode)
      .then((response) => {
        if (!active) return
        setResult(response)
        setHistoricalEnabled(response.historical_enabled)
        setLoading(false)
      })
      .catch(() => {
        if (!active) return
        setError(
          submitted.mode === 'historical'
            ? 'Verified historical forecasting is unavailable. Check the data-provenance gate and PostgreSQL.'
            : 'Could not calculate this scenario. Check the future campus date/time and backend.',
        )
        setLoading(false)
      })
    return () => { active = false }
  }, [submitted])

  const ranked = [...(result?.lots ?? [])]
    .filter((lot) => lot.estimated_available !== null)
    .sort((a, b) => forecastRank(b) - forecastRank(a))
  const best = ranked[0]

  function submit(at: string, selectedMode: ForecastMode) {
    setSubmitted({ at, mode: selectedMode })
  }

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div className="dashboard-header-top">
          <div>
            <p className="dashboard-eyebrow">UniParkingBuddy · Forecasting prototype</p>
            <h1 className="dashboard-title">Future parking availability</h1>
            <p className="forecast-subtitle">
              Compare estimates for Lots 1, 2 and 3 at a chosen campus time.
            </p>
          </div>
          <button className="dashboard-back-btn" onClick={() => navigate('/')}>
            ← All lots
          </button>
        </div>
      </header>

      <main className="forecast-body">
        <section className="forecast-warning" aria-label="Forecast data limitation">
          <strong>Demo scenario — not real campus predictions.</strong>
          <p>
            The default figures are generated from an illustrative weekday schedule.
            They are not trained on campus data and should not be used to decide
            whether a parking space will actually be available.
          </p>
        </section>

        <form
          className="forecast-controls"
          onSubmit={(event) => {
            event.preventDefault()
            submit(target, mode)
          }}
        >
          <div className="forecast-field">
            <label htmlFor="forecast-at">Future date and time (UNCP / Eastern Time)</label>
            <input
              id="forecast-at"
              type="datetime-local"
              required
              value={target}
              onChange={(event) => setTarget(event.target.value)}
            />
          </div>
          <div className="forecast-field">
            <label htmlFor="forecast-mode">Data source</label>
            <select
              id="forecast-mode"
              value={mode}
              onChange={(event) => setMode(event.target.value as ForecastMode)}
            >
              <option value="demo">Illustrative demo scenario</option>
              <option value="historical" disabled={!historicalEnabled}>
                Verified historical baseline (operator enabled)
              </option>
            </select>
          </div>
          <button className="forecast-submit" type="submit" disabled={loading}>
            {loading ? 'Calculating…' : 'Estimate availability'}
          </button>
        </form>

        <div className="forecast-presets" aria-label="Compare sample times">
          <span>Try another time:</span>
          {SUGGESTED_HOURS.map((hour) => (
            <button
              key={hour.time}
              type="button"
              disabled={loading}
              onClick={() => {
                const next = target.slice(0, 10) + 'T' + hour.time
                setTarget(next)
                submit(next, mode)
              }}
            >
              {hour.label}
            </button>
          ))}
        </div>

        {!historicalEnabled && (
          <p className="forecast-note">
            Verified historical forecasting is disabled by default because the
            current prerecorded demo footage does not establish genuine campus
            time-of-day occupancy patterns.
          </p>
        )}

        {loading ? (
          <p role="status" className="forecast-note">Calculating the selected scenario…</p>
        ) : error ? (
          <p role="alert" className="error">{error}</p>
        ) : result ? (
          <section className="forecast-results" aria-labelledby="forecast-results-heading">
            <h2 id="forecast-results-heading">
              Estimates for <time dateTime={result.requested_at}>
                {formatCampusTimestamp(result.requested_at)}
              </time>
            </h2>
            <p className="forecast-mode-label">
              {result.source === 'synthetic_demo'
                ? 'SYNTHETIC DEMONSTRATION DATA'
                : 'HISTORICAL BASELINE · NOT VALIDATED'}
            </p>
            {best ? (
              <p className="forecast-best">
                {result.mode === 'demo' ? 'Illustratively' : 'Based on the recorded history'},
                <strong> {best.display_label} </strong>
                has the most estimated open spaces at this time:
                <strong> {best.estimated_available} of {best.total_spaces}</strong>.
                This is not a reservation or guaranteed vacancy.
              </p>
            ) : (
              <p role="status" className="forecast-note">
                There are not enough verified historical observations to estimate availability.
                No missing values have been filled with fabricated counts.
              </p>
            )}

            <div className="forecast-lots">
              {result.lots.map((lot) => (
                <article className="forecast-lot" key={lot.lot_id} data-lot={lot.lot_id}>
                  <h3>{lot.display_label}</h3>
                  <p className="forecast-count">
                    {lot.estimated_available === null
                      ? 'Estimate unavailable'
                      : String(lot.estimated_available) + ' estimated open'}
                  </p>
                  <p className="forecast-capacity">
                    {lot.estimated_available === null
                      ? String(lot.total_spaces) + ' configured spaces'
                      : String(lot.estimated_occupied) + ' estimated occupied · ' +
                        String(lot.total_spaces) + ' total spaces'}
                  </p>
                  {lot.estimated_open_percent !== null && (
                    <div className="forecast-progress" aria-label={
                      lot.display_label + ': ' + lot.estimated_open_percent + '% estimated open'
                    }>
                      <div style={{ width: lot.estimated_open_percent + '%' }} />
                    </div>
                  )}
                  <p className="forecast-provenance">
                    {lot.status === 'illustrative'
                      ? 'Illustrative only · no historical observations used'
                      : lot.status === 'insufficient_history'
                        ? String(lot.historical_days) + ' matching days · at least 3 required'
                        : String(lot.historical_days) + ' independently dated days · ' +
                          String(lot.historical_snapshots) + ' complete snapshots'}
                  </p>
                </article>
              ))}
            </div>

            <p className="forecast-note">
              <strong>Method:</strong> {result.basis}
              {' '}The results are independent of the live OPEN/FULL dashboard and do not
              predict individual stall availability. Parking conditions can change.
            </p>
          </section>
        ) : null}
      </main>
    </div>
  )
}
