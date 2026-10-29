import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import LotDiagram from './lotDiagram.tsx'
import { buildStalls, type DiagramLayout } from './diagramLayout.ts'
import './App.css'

interface FakeStatus {
  id: number
  occupied: boolean
}

// test data only since lot 3 not working rn
function fakeStatuses(layout: DiagramLayout): FakeStatus[] {
  return buildStalls(layout)
    .filter((stall) => stall.column !== 'C2')
    .map((stall) => ({ id: stall.id, occupied: Math.random() < 0.75 }))
}

function DiagramDemo() {
  const navigate = useNavigate()
  const [layout, setLayout] = useState<DiagramLayout | null>(null)
  const [statuses, setStatuses] = useState<FakeStatus[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('diagrams/lot3.json')
      .then((res) => {
        if (!res.ok) {
          throw new Error('Failed to load layout')
        }
        return res.json()
      })
      .then((data: DiagramLayout) => {
        setLayout(data)
        setStatuses(fakeStatuses(data))
      })
      .catch(() => setError('Could not load the lot layout'))
  }, [])

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <div className="dashboard-header-top">
          <div>
            <p className="dashboard-eyebrow">Preview</p>
            <h1 className="dashboard-title">Lot diagram</h1>
          </div>

          <button className="dashboard-back-btn" onClick={() => navigate('/')}>
            ← All lots
          </button>
        </div>
      </div>

      <div className="dashboard-body">
        <p className="history-muted">
          Test data only: random statuses, not live detection. Dashed outlines are
          stalls that are not monitored.
        </p>

        {error && <p className="error">{error}</p>}

        {layout && (
          <>
            <LotDiagram layout={layout} statuses={statuses} />

            <button
              className="dashboard-back-btn"
              style={{ marginTop: 16, color: '#5A5A56', borderColor: '#B5B0A7' }}
              onClick={() => setStatuses(fakeStatuses(layout))}
            >
              Shuffle test data
            </button>

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

export default DiagramDemo