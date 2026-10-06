//Home page for the web app :)
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import './App.css'

interface Lot{
    id: string
    name: string
    gradient: string
    openCount: number
    totalCount: number
    path: string
    camera?: string
    
}
interface StatusResponse {
    cars_detected: number 
    parking_spaces: { id: number; occupied: boolean } []
}

const lots: Lot[] = [
  { id: 'lot1', name: 'Lot 1', gradient: 'linear-gradient(135deg, #242424, #111111)', openCount: 1, totalCount: 5, path: '/parking-lot1', camera: 'camera_1' },
  { id: 'lot2', name: 'Lot 2', gradient: 'linear-gradient(135deg, #262626, #131313)', openCount: 1, totalCount: 5, path: '/parking-lot2' , camera: 'camera_2'}, //mm maybe leeave the 1:5 as fallback i'll see or maybe it should show unavailable ^^
  { id: 'lot3', name: 'Lot 3', gradient: 'linear-gradient(135deg, #282828, #151515)', openCount: 1, totalCount: 5, path: '/parking-lot3' }, //no cam so left alone 
]


function getStatus(open:number, total: number) {
    if(open === 0) return { label: 'FULL', bg: '#F5E0E0', color: '#C0392B' }
    if(open / total < 0.25) return { label: 'LIMITED', bg: '#FFF3D6', color: '#B8860B'}
    return { label: 'OPEN', bg: '#DCF5E4', color: '#1A8A4A' }
}

function Welcome(){
    const navigate = useNavigate()
    const [live, setLive]=useState<Record<string, { open: number; total: number }>>({})

    useEffect(() => {
        const load = () => {
            lots.forEach((lot) => {
                if(!lot.camera) return
                fetch(`http://localhost:5000/api/status/${lot.camera}`)
                    .then((res) => {
                        if(!res.ok) {
                            throw new Error('failed to fetch')
                        
                        }
                        return res.json()
                    }
                )
                .then((data: StatusResponse) => {
                    const total = data.parking_spaces.length 
                    const open = data.parking_spaces.filter((s) => !s.occupied).length
                    setLive((prev) => ({ ...prev, [lot.id]: { open, total }}))
                }
                )
                .catch(() => {})
            }
        )
        }
        load()
        const interval = setInterval(load, 2000)
        return() => clearInterval(interval)


    },[])



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
                    const counts = live[lot.id]
                    const open = counts ? counts.open : lot.openCount
                    const total = counts ? counts.total : lot.totalCount
                    const status = getStatus(open, total)
                    return (
                        <button
                        key={lot.id}
                        className="lot-card"
                        style={{ background: lot.gradient }}
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
                                    {open} of {total} open
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