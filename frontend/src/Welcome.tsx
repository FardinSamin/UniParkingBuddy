//Home page for the web app :)
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './App.css'
import { fetchParkingStatus } from './parkingStatus'

interface Lot{
    id: string
    name: string
    gradient: string
    path: string
    camera?: string
    
}
type LiveAvailability =
    | { state: 'ready'; open: number; total: number }
    | { state: 'unavailable' }

const lots: Lot[] = [
  { id: 'lot1', name: 'Lot 1', gradient: 'linear-gradient(135deg, #242424, #111111)', path: '/parking-lot1', camera: 'camera_1' },
  { id: 'lot2', name: 'Lot 2', gradient: 'linear-gradient(135deg, #262626, #131313)', path: '/parking-lot2', camera: 'camera_2' },
  { id: 'lot3', name: 'Lot 3', gradient: 'linear-gradient(135deg, #282828, #151515)', path: '/parking-lot3' }, 
]


function getStatus(open:number, total: number) {
    if(open === 0) return { label: 'FULL', bg: '#F5E0E0', color: '#C0392B' }
    if(open / total < 0.25) return { label: 'LIMITED', bg: '#FFF3D6', color: '#B8860B'}
    return { label: 'OPEN', bg: '#DCF5E4', color: '#1A8A4A' }
}

function Welcome(){
    const navigate = useNavigate()
    const [live, setLive] = useState<Record<string, LiveAvailability>>({})

    useEffect(() => {
        let active = true
        const requestsInProgress = new Set<string>()

        const load = () => {
            lots.forEach((lot) => {
                if (!lot.camera || requestsInProgress.has(lot.id)) return

                requestsInProgress.add(lot.id)
                fetchParkingStatus(lot.camera)
                    .then((data) => {
                        if (!active) return
                        const total = data.parking_spaces.length
                        const open = data.parking_spaces.filter((space) => !space.occupied).length
                        setLive((prev) => ({ ...prev, [lot.id]: { state: 'ready', open, total } }))
                    })
                    .catch(() => {
                        if (!active) return
                        setLive((prev) => ({ ...prev, [lot.id]: { state: 'unavailable' } }))
                    })
                    .finally(() => requestsInProgress.delete(lot.id))
            })
        }

        load()
        const interval = setInterval(load, 2000)
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
            <img src="/uncp-logo.png" alt="UNCP logo" className="welcome-logo" />
            </div>
            </div>

            <div className="welcome-lots">
                {lots.map((lot) => {
                    const availability = live[lot.id]
                    const disabled = !lot.camera
                    const status = disabled
                        ? { label: 'COMING SOON', bg: '#E9E6DF', color: '#5A5A56' }
                        : availability?.state === 'ready'
                            ? getStatus(availability.open, availability.total)
                            : availability?.state === 'unavailable'
                                ? { label: 'UNAVAILABLE', bg: '#E9E6DF', color: '#5A5A56' }
                                : { label: 'LOADING', bg: '#FFF3D6', color: '#B8860B' }
                    return (
                        <button
                        key={lot.id}
                        className="lot-card"
                        style={{ background: lot.gradient }}
                        disabled={disabled}
                        onClick={() => navigate(lot.path)}

                        >
                            <span
                            className="lot-card-status"
                            style={{ background: status.bg, color: status.color }}
                            >
                                {status.label}
                            </span>
                            <div className="lot-card-text">
                                <p className="lot-card-name">{lot.name}</p>
                                <p className="lot-card-count">
                                    {disabled
                                        ? 'Monitoring not available yet'
                                        : availability?.state === 'ready'
                                            ? `${availability.open} of ${availability.total} open`
                                            : availability?.state === 'unavailable'
                                                ? 'Current status unavailable'
                                                : 'Checking availability...'}
                                </p>
                            </div>
                        </button>
                    )
                })}
            </div>
        </div>
    )
}

export default Welcome
