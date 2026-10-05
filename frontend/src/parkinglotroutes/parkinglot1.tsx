import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import '../App.css'

interface ParkingLot1 {
  id: number
  occupied: boolean
}

interface StatusResponse {
  cars_detected: number
  parking_spaces: ParkingLot1[]
}

function ParkingLot1() {
  const [spaces, setSpaces] = useState<ParkingLot1[]>([])
  const [carCount, setCarCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchSpaces = () => {
      fetch('http://localhost:5000/api/status/camera_1')
        .then((res) => {
          if (!res.ok) {
            throw new Error('Failed to fetch')
          }
          return res.json()
        })
        .then((data: StatusResponse) => {
          setSpaces(data.parking_spaces)
          setCarCount(data.cars_detected)
          setError(null)
        })
        .catch(() => {
          setError('Could not reach parking status server')
        })
    }

    fetchSpaces()

    const interval = setInterval(fetchSpaces, 1000)

    return () => clearInterval(interval)
  }, [])

  const occupiedCount = spaces.filter((s) => s.occupied).length
  const openCount = spaces.length - occupiedCount

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div className="dashboard-header-top">
          <div>
            <p className="dashboard-eyebrow">Lot 1</p>
            <h1 className="dashboard-title">Parking Status</h1>
          </div>

          <button className="dashboard-back-btn" onClick={() => navigate('/')}>
          ← All lots
          </button>
        </div>
      </div>

      <div className="dashboard-body">
        {error && <p className="error">{error}</p>}

        {!error && (
          <>
            <div className="dashboard-stats">
              <div className="stat-card">
                <p className="stat-label">Cars detected</p>
                <p className="stat-value">{carCount}</p>
              </div>

              <div className="stat-card">
                <p className="stat-label">Open now</p>
                <p className="stat-value stat-open">{openCount}</p>
              </div>

              <div className="stat-card">
                <p className="stat-label">Occupied</p>
                <p className="stat-value stat-occupied">
                  {occupiedCount}
                </p>
              </div>

              <div className="stat-card">
                <p className="stat-label">Total spots</p>
                <p className="stat-value">{spaces.length}</p>
              </div>
            </div>

            <div className="dashboard-grid">
              {spaces.map((space) => (
                <div
                  key={space.id}
                  className={`dashboard-space ${
                    space.occupied ? 'occupied' : 'open'
                  }`}
                >
                  <p className="dashboard-space-id">{space.id}</p>

                  <p className="dashboard-space-status">
                    {space.occupied ? 'Occupied' : 'Open'}
                  </p>
                </div>
              ))}
            </div>

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

export default ParkingLot1
