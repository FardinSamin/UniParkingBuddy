import { useState, useEffect } from 'react'
import './App.css'

interface ParkingSpace {
  id: number
  occupied: boolean
  points: number[][]
}

function App() {
  const [spaces, setSpaces] = useState<ParkingSpace[]>([])
  const [error, setError] = useState<string | null>(null)

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

  return (
    <div className="app">
      <h1>Parking Status</h1>

      {error && <p className="error">{error}</p>}

      {!error && (
        <>
          <p className="summary">
            {occupiedCount} / {spaces.length} occupied
          </p>

          <div className="grid">
            {spaces.map((space) => (
              <div
                key={space.id}
                className={`space ${space.occupied ? 'occupied' : 'empty'}`}
                title={`Space ${space.id}`}
              >
                {space.id}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export default App