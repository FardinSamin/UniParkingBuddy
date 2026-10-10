// Existing campus styling and navigation, driven by configured FastAPI lots.
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './App.css'
import uncpLogo from '../uncp-logo.png'
import { fetchMonitoredLots, type MonitoredLot } from './monitoredLots.ts'

interface LotCard {
  id: string
  name: string
  gradient: string
  path: string
  camera?: string
}

// Existing routes are implemented for Lots 1 and 2. Lot 3 remains a
// visibly disabled placeholder, not a fabricated monitored lot.
const lotCards: LotCard[] = [
  { id: 'lot1', name: 'Lot 1', gradient: 'linear-gradient(135deg, #242424, #111111)', path: '/parking-lot1', camera: 'camera_1' },
  { id: 'lot2', name: 'Lot 2', gradient: 'linear-gradient(135deg, #262626, #131313)', path: '/parking-lot2', camera: 'camera_2' },
  { id: 'lot3', name: 'Lot 3', gradient: 'linear-gradient(135deg, #282828, #151515)', path: '/parking-lot3' },
]

type LotsState =
  | { state: 'loading' }
  | { state: 'unavailable' }
  | { state: 'ready'; lots: MonitoredLot[] }

function occupancyBadge(open: number, total: number) {
  if (open === 0) return { label: 'FULL', bg: '#F5E0E0', color: '#C0392B' }
  if (open / total < 0.25) return { label: 'LIMITED', bg: '#FFF3D6', color: '#B8860B' }
  return { label: 'OPEN', bg: '#DCF5E4', color: '#1A8A4A' }
}

function Welcome() {
  const navigate = useNavigate()
  const [monitoring, setMonitoring] = useState<LotsState>({ state: 'loading' })

  useEffect(() => {
    let active = true
    let requestInProgress = false

    const refresh = () => {
      if (requestInProgress) return
      requestInProgress = true
      fetchMonitoredLots()
        .then((lots) => {
          if (active) setMonitoring({ state: 'ready', lots })
        })
        .catch(() => {
          // A broken backend is unavailable, not FULL or zero open spaces.
          if (active) setMonitoring({ state: 'unavailable' })
        })
        .finally(() => { requestInProgress = false })
    }

    refresh()
    const interval = setInterval(refresh, 2000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  return (
    <div className="welcome-page">
      <div className="welcome-header">
        <div className="welcome-header-top">
          <div>
            <p className="welcome-eyebrow">Welcome UNCP Brave</p>
            <h1 className="welcome-title">UniParkingBuddy</h1>
            <p className="welcome-subtitle">
              Live Spot Tracking For Campus Parking. Choose A Lot To View Availability
            </p>
          </div>
          <img src={uncpLogo} alt="UNCP logo" className="welcome-logo" />
        </div>
      </div>

      <main className="welcome-lots">
        {lotCards.map((card) => {
          const apiLot = monitoring.state === 'ready'
            ? monitoring.lots.find((lot) =>
                lot.lot_id === card.id && lot.camera === card.camera,
              )
            : undefined
          const disabled = !card.camera || !apiLot
          const open = apiLot?.has_current_data ? apiLot.available_spaces : null
          const total = apiLot?.has_current_data ? apiLot.total_spaces : null

          const badge = !card.camera
            ? { label: 'COMING SOON', bg: '#E9E6DF', color: '#5A5A56' }
            : monitoring.state === 'loading'
              ? { label: 'LOADING', bg: '#FFF3D6', color: '#B8860B' }
              : monitoring.state === 'unavailable'
                ? { label: 'UNAVAILABLE', bg: '#E9E6DF', color: '#5A5A56' }
                : !apiLot
                  ? { label: 'NOT MONITORED', bg: '#E9E6DF', color: '#5A5A56' }
                  : open !== null && open !== undefined && total !== null && total !== undefined
                    ? occupancyBadge(open, total)
                    : { label: 'UNAVAILABLE', bg: '#E9E6DF', color: '#5A5A56' }

          const count = !card.camera
            ? 'Monitoring not available yet'
            : monitoring.state === 'loading'
              ? 'Checking availability...'
              : monitoring.state === 'unavailable'
                ? 'Cannot reach the monitoring service'
                : !apiLot
                  ? 'This lot is not currently monitored'
                  : open !== null && open !== undefined && total !== null && total !== undefined
                    ? `${open} of ${total} open`
                    : 'Current status unavailable'

          return (
            <button
              key={card.id}
              className="lot-card"
              style={{ background: card.gradient }}
              disabled={disabled}
              onClick={() => navigate(card.path)}
            >
              <span className="lot-card-status" style={{ background: badge.bg, color: badge.color }}>
                {badge.label}
              </span>
              <div className="lot-card-text">
                <p className="lot-card-name">{apiLot?.display_label ?? card.name}</p>
                <p className="lot-card-count">{count}</p>
              </div>
            </button>
          )
        })}
      </main>
    </div>
  )
}

export default Welcome
