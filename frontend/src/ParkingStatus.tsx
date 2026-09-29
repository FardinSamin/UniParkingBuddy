<<<<<<< HEAD
//gonna move in app.tsx stuff here so that i can make app the router 
//and this the parking status :)
=======

>>>>>>> da18ab2 (new)
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './App.css'

interface ParkingSpace {
  id: number
  occupied: boolean
<<<<<<< HEAD
  points: number[][]
=======
}

interface StatusResponse {
  cars_detected: number
  parking_spaces: ParkingSpace[]
>>>>>>> da18ab2 (new)
}

function ParkingStatus() {
  const [spaces, setSpaces] = useState<ParkingSpace[]>([])
<<<<<<< HEAD
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
=======
  const [carCount, setCarCount] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchSpaces = () => {
      fetch('http://localhost:5000/api/status')
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

>>>>>>> da18ab2 (new)
    return () => clearInterval(interval)
  }, [])

  const occupiedCount = spaces.filter((s) => s.occupied).length
  const openCount = spaces.length - occupiedCount

  return (
<<<<<<< HEAD
     <div className="dashboard-page">
=======
    <div className="dashboard-page">
>>>>>>> da18ab2 (new)
      <div className="dashboard-header">
        <div className="dashboard-header-top">
          <div>
            <p className="dashboard-eyebrow">Lot 1</p>
            <h1 className="dashboard-title">Parking Status</h1>
          </div>
<<<<<<< HEAD
          <button className="dashboard-back-btn" onClick={() => navigate('/')}>
            ← All lots
=======

          <button className="dashboard-back-btn" onClick={() => navigate('/')}>
          ← All lots
>>>>>>> da18ab2 (new)
          </button>
        </div>
      </div>

      <div className="dashboard-body">
        {error && <p className="error">{error}</p>}

        {!error && (
          <>
            <div className="dashboard-stats">
              <div className="stat-card">
<<<<<<< HEAD
                <p className="stat-label">Open now</p>
                <p className="stat-value stat-open">{openCount}</p>
              </div>
              <div className="stat-card">
                <p className="stat-label">Occupied</p>
                <p className="stat-value stat-occupied">{occupiedCount}</p>
              </div>
=======
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

>>>>>>> da18ab2 (new)
              <div className="stat-card">
                <p className="stat-label">Total spots</p>
                <p className="stat-value">{spaces.length}</p>
              </div>
            </div>

            <div className="dashboard-grid">
              {spaces.map((space) => (
                <div
                  key={space.id}
<<<<<<< HEAD
                  className={`dashboard-space ${space.occupied ? 'occupied' : 'open'}`}
                  >
                    <p className="dashboard-space-id">{space.id}</p>
                    <p className="dashboard-space-status">
                      {space.occupied ? 'Occupied' : 'Open'}
                    </p>
=======
                  className={`dashboard-space ${
                    space.occupied ? 'occupied' : 'open'
                  }`}
                >
                  <p className="dashboard-space-id">{space.id}</p>

                  <p className="dashboard-space-status">
                    {space.occupied ? 'Occupied' : 'Open'}
                  </p>
>>>>>>> da18ab2 (new)
                </div>
              ))}
            </div>

            <div className="dashboard-legend">
              <div className="legend-item">
                <span className="legend-swatch legend-open"></span>
                <span>Open</span>
              </div>
<<<<<<< HEAD
=======

>>>>>>> da18ab2 (new)
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

<<<<<<< HEAD
export default ParkingStatus
    
=======
export default ParkingStatus
>>>>>>> da18ab2 (new)
