import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import '../App.css'
import { fetchParkingStatus, type ParkingSpaceStatus } from '../parkingStatus'
import LotDiagram from '../lotDiagram.tsx'
import type { DiagramLayout } from '../diagramLayout.ts'

function ParkingLot3() {
  const [spaces, setSpaces] = useState<ParkingSpaceStatus[]>([])
  const [layout, setLayout] = useState<DiagramLayout | null>(null)
  const [layoutError, setLayoutError] = useState(false)
  const [loading, setLoading] = useState(true)
  const [carCount, setCarCount] = useState(0)
  const [outsideCount, setOutsideCount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    fetch('/diagrams/lot3.json')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load layout')
        return res.json()
      })
      .then((data: DiagramLayout) => setLayout(data))
      .catch(() => setLayoutError(true))
  }, [])

  useEffect(() => {
    let active = true
    let requestInProgress = false

    const fetchSpaces = () => {
      if (requestInProgress) return

      requestInProgress = true
      fetchParkingStatus('camera_3')
        .then((data) => {
          if (!active) return
          setSpaces(data.parking_spaces)
          setCarCount(data.cars_detected)
          setOutsideCount(data.vehicles_outside_spaces ?? null)
          setError(null)
          setLoading(false)
        })
        .catch(() => {
          if (!active) return
          setSpaces([])
          setError('Current parking status is unavailable. Check the backend and space configuration.')
          setLoading(false)
        })
        .finally(() => {
          requestInProgress = false
        })
    }

    fetchSpaces()
    const interval = setInterval(fetchSpaces, 1000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  const occupiedCount = spaces.filter((s) => s.occupied).length
  const openCount = spaces.length - occupiedCount

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div className="dashboard-header-top">
          <div>
            <p className="dashboard-eyebrow">Lot 3</p>
            <h1 className="dashboard-title">Parking Status</h1>
          </div>

          <button className="dashboard-back-btn" onClick={() => navigate('/')}>
            ← All lots
          </button>
        </div>
      </div>

      <div className="dashboard-body">
        {loading ? (
          <p role="status">Checking parking availability</p>
        ) : (
          <>
            {error && <p className="error" role="alert">{error}</p>}

            {!error && (
              <div className="dashboard-stats">
                <div className="stat-card">
                  <p className="stat-label">Vehicles detected</p>
                  <p className="stat-value">{carCount}</p>
                </div>

                {outsideCount !== null && (
                  <div className="stat-card">
                    <p className="stat-label">Outside marked spaces</p>
                    <p className="stat-value">{outsideCount}</p>
                  </div>
                )}

                <div className="stat-card">
                  <p className="stat-label">Open now</p>
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

            {layout && <LotDiagram layout={layout} statuses={spaces} />}

            <div className="dashboard-legend">
              <div className="legend-item">
                <span className="legend-swatch legend-open"></span>
                <span>Open</span>
              </div>

              <div className="legend-item">
                <span className="legend-swatch legend-occupied"></span>
                <span>Occupied</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default ParkingLot3