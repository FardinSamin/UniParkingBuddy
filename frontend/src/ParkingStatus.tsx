//gonna move in app.tsx stuff here so that i can make app the router 
//and this the parking status :)
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './App.css'

interface ParkingSpace {
  id: number
  occupied: boolean
  points: number[][]
}

function ParkingStatus() {
  const [spaces, setSpaces] = useState<ParkingSpace[]>([])
  const [error, setError] = useState<string | null>(null)
   const navigate = useNavigate()

  useEffect(() => {
    const fetchSpaces = () => {
      fetch('http://localhost:5000/api/spaces')
        .then((res) => {
          if (!res.ok) throw new Error('Failed to fetch')
          return res.json()
        })
        .then((data: ParkingSpace[]) => {
          setSpaces(data)
          setError(null)
        })
        .catch(() => setError('Could not reach parking status server'))
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

            <div className="dashboard-grid">
              {spaces.map((space) => (
                <div
                  key={space.id}
                  className={`dashboard-space ${space.occupied ? 'occupied' : 'open'}`}
                  title={`Space ${space.id}`}
                >
                  {space.id}
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

export default ParkingStatus
    
