import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import '../App.css'
import { useParkingStatus } from '../useParkingStatus.ts'
import ParkingFreshness from '../ParkingFreshness.tsx'
import LotDiagram from '../lotDiagram.tsx'
import type { DiagramLayout } from '../diagramLayout.ts'

function ParkingLot2() {
  const [layout, setLayout] = useState<DiagramLayout | null>(null)
  const [layoutError, setLayoutError] = useState(false)
  const { state, data, lastFetchedAt, retry } = useParkingStatus('camera_2')
  const spaces = data?.parking_spaces ?? []
  const loading = state === 'loading'
  const navigate = useNavigate()
  const showDebug = new URLSearchParams(window.location.search).has('debug')

  useEffect(() => {
    fetch('/diagrams/lot2.json')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load layout')
        return res.json()
      })
      .then((data: DiagramLayout) => setLayout(data))
      .catch(() => setLayoutError(true))
  }, [])

  const occupiedCount = spaces.filter((s) => s.occupied).length
  const openCount = spaces.length - occupiedCount

  return (
    <div className="dashboard-page">
      <header className="dashboard-header">
        <div className="dashboard-header-top">
          <div>
            <p className="dashboard-eyebrow">Lot 2</p>
            <h1 className="dashboard-title">Parking Status</h1>
          </div>

          <div className="history-header-actions">
            <button className="dashboard-back-btn" onClick={() => navigate('/history/lot2')}>
              Historical trends
            </button>
            <a
              className="dashboard-back-btn dashboard-directions-btn"
              href="https://www.google.com/maps/dir/?api=1&destination=34.68998633953757%2C-79.19838459516956"
              target="_blank"
              rel="noreferrer"
            >
              Directions
            </a>
            <button className="dashboard-back-btn" onClick={() => navigate('/')}>
              ← All lots
            </button>
          </div>
        </div>
      </header>

      <main className="dashboard-body">
        {loading && <p role="status">Checking parking availability...</p>}
        {!loading && (
          <>
            <ParkingFreshness
              state={state}
              lastFetchedAt={lastFetchedAt}
              observedAt={data?.observed_at}
              onRetry={retry}
            />
            {data && (
              <div className="dashboard-stats">
                {showDebug && (
                  <>
                    <div className="stat-card">
                      <p className="stat-label">Vehicles detected</p>
                      <p className="stat-value">{data.cars_detected}</p>
                    </div>

                    {data.vehicles_outside_spaces !== undefined && (
                      <div className="stat-card">
                        <p className="stat-label">Outside marked spaces</p>
                        <p className="stat-value">{data.vehicles_outside_spaces}</p>
                      </div>
                    )}
                  </>
                )}


                <div className="stat-card">
                  <p className="stat-label">Available now</p>
                  <p className="stat-value stat-open">{openCount}</p>
                </div>

                <div className="stat-card">
                  <p className="stat-label">Occupied</p>
                  <p className="stat-value stat-occupied">{occupiedCount}</p>
                </div>

                <div className="stat-card">
                  <p className="stat-label">Total spots</p>
                  <p className="stat-value">{spaces.length}</p>
                </div>
              </div>
            )}

            {layoutError && <p className="error">Could not load the lot layout</p>}

            {layout && data && <LotDiagram layout={layout} statuses={spaces} />}

            {data && (
              <div className="dashboard-legend" aria-label="Parking-space status key">
                <div className="legend-item">
                  <span className="legend-swatch legend-open" aria-hidden="true"></span>
                  <span>Available</span>
                </div>

                <div className="legend-item">
                  <span className="legend-swatch legend-occupied" aria-hidden="true"></span>
                  <span>Occupied</span>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

export default ParkingLot2