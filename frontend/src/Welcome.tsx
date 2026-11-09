// Existing campus styling and navigation, driven by configured FastAPI lots.
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './App.css'
import uncpLogo from '../uncp-logo.png'
import { fetchMonitoredLots, type MonitoredLot } from './monitoredLots.ts'

interface LotCard {
  id: string
  name: string
  type: 'Commuter' | 'Residential'
  gradient: string
  path: string
  camera?: string
  image: string
  lat: number // right-click the lot in Google Maps and click the coordinates to copy
  lng: number
}

// Routes exist for Lots 1-3. A card stays disabled unless the API reports
// that lot as monitored.
const lotCards: LotCard[] = [
  { id: 'lot1', name: 'Lot 1', type: 'Commuter', gradient: 'linear-gradient(135deg, #242424, #111111)', path: '/parking-lot1', camera: 'camera_1', image: '/images/parking1lot.png', lat: 34.685327503109605, lng: -79.19927028733267 },
  { id: 'lot2', name: 'Lot 2', type: 'Commuter', gradient: 'linear-gradient(135deg, #262626, #131313)', path: '/parking-lot2', camera: 'camera_2', image: '/images/parking2lot.png', lat: 34.68998633953757, lng: -79.19838459516956 },
  { id: 'lot3', name: 'Lot 3', type: 'Residential', gradient: 'linear-gradient(135deg, #282828, #151515)', path: '/parking-lot3', camera: 'camera_3', image: '/images/parking3lot.png', lat: 34.688842915543916, lng: -79.20368884927892 },
]

type LotsState =
  | { state: 'loading' }
  | { state: 'unavailable' }
  | { state: 'ready'; lots: MonitoredLot[] }

type UserPos = { lat: number; lng: number } | null
type LotSortOption = 'default' | 'nearest' | 'commuter' | 'residential'

function occupancyBadge(open: number, total: number) {
  if (open === 0) return { label: 'FULL', bg: '#F5E0E0', color: '#C0392B' }
  if (open / total < 0.25) return { label: 'LIMITED', bg: '#FFF3D6', color: '#B8860B' }
  return { label: 'OPEN', bg: '#DCF5E4', color: '#1A8A4A' }
}

// Haversine distance in miles
function distanceMiles(lat1: number, lng1: number, lat2: number, lng2: number) {
  const R = 3958.8
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

function formatDistance(miles: number) {
  if (miles < 0.1) return `${Math.round(miles * 5280)} ft away`
  return `${miles.toFixed(1)} mi away`
}

function Welcome() {
  const navigate = useNavigate()
  const [monitoring, setMonitoring] = useState<LotsState>({ state: 'loading' })
  const [userPos, setUserPos] = useState<UserPos>(null)
  const [sortBy, setSortBy] = useState<LotSortOption>('default')

  useEffect(() => {
    if (!('geolocation' in navigator)) return
    const watchId = navigator.geolocation.watchPosition(
      (pos) => setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => setUserPos(null),
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 10000 },
    )
    return () => navigator.geolocation.clearWatch(watchId)
  }, [])

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

  const orderedLotCards = [...lotCards].sort((a, b) => {
    if (sortBy === 'commuter' || sortBy === 'residential') {
      const preferredType = sortBy === 'commuter' ? 'Commuter' : 'Residential'
      return Number(b.type === preferredType) - Number(a.type === preferredType)
    }

    if (sortBy === 'nearest' && userPos) {
      return distanceMiles(userPos.lat, userPos.lng, a.lat, a.lng) -
        distanceMiles(userPos.lat, userPos.lng, b.lat, b.lng)
    }

    return 0
  })

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
        <div className="welcome-sort">
          <label htmlFor="lot-sort">Sort by</label>
          <select
            id="lot-sort"
            className="welcome-sort-select"
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value as LotSortOption)}
          >
            <option value="default">Default order</option>
            <option value="nearest">Nearest distance</option>
            <option value="commuter">Commuter lots first</option>
            <option value="residential">Residential lots first</option>
          </select>
        </div>
        {orderedLotCards.map((card) => {
          const apiLot = monitoring.state === 'ready'
            ? monitoring.lots.find((lot) =>
                lot.lot_id === card.id && lot.camera === card.camera,
              )
            : undefined
          const disabled = !card.camera || !apiLot
          const open = apiLot?.has_current_data ? apiLot.available_spaces : null
          const total = apiLot?.has_current_data ? apiLot.total_spaces : null

          const distance = userPos
            ? formatDistance(distanceMiles(userPos.lat, userPos.lng, card.lat, card.lng))
            : null

          const badge = !card.camera
            ? { label: 'COMING SOON', bg: '#E9E6DF', color: '#5A5A56' }
            : monitoring.state === 'loading'
              ? { label: 'LOADING', bg: '#FFF3D6', color: '#B8860B' }
              : monitoring.state === 'unavailable'
                ? { label: 'UNAVAILABLE', bg: '#E9E6DF', color: '#ff0000' }
                : !apiLot
                  ? { label: 'CURRENTLY UNAVAILABLE', bg: '#E9E6DF', color: '#ff0000' }
                  : open !== null && open !== undefined && total !== null && total !== undefined
                    ? occupancyBadge(open, total)
                    : { label: 'UNAVAILABLE', bg: '#E9E6DF', color: '#ff0000' }

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
            <article
              key={card.id}
              className="lot-card"
              style={{ background: card.gradient }}
            >
              <div className="lot-card-bg" style={{ backgroundImage: `url(${card.image})` }} />
              <div className="lot-card-overlay" />
              <button
                type="button"
                className="lot-card-open"
                disabled={disabled}
                onClick={() => navigate(card.path)}
                aria-label={`View ${apiLot?.display_label ?? card.name}`}
              >
                <span className="lot-card-status" style={{ background: badge.bg, color: badge.color }}>
                  {badge.label}
                </span>
                <span className="lot-card-type">{card.type}</span>
                <span className="lot-card-text">
                  <span className="lot-card-name">{apiLot?.display_label ?? card.name}</span>
                  <span className="lot-card-count">
                    {count}
                    {distance && ` · ${distance}`}
                  </span>
                </span>
              </button>
              <a
                className="lot-card-directions"
                href={`https://www.google.com/maps/dir/?api=1&destination=${card.lat},${card.lng}`}
                target="_blank"
                rel="noreferrer"
                aria-label={`Get directions to ${card.name} in Google Maps`}
              >
                Directions
              </a>
            </article>
          )
        })}
      </main>
    </div>
  )
}

export default Welcome