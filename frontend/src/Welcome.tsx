//Home page for the web app :)
import { useNavigate } from 'react-router-dom'
import './App.css'

interface Lot{
    id: string
    name: string
    gradient: string
    openCount: number
    totalCount: number
    path: string
}

const lots: Lot[] = [
  { id: 'lot1', name: 'Lot 1', gradient: 'linear-gradient(135deg, #242424, #111111)', openCount: 1, totalCount: 5, path: '/dashboard' },
  { id: 'lot2', name: 'Lot 2', gradient: 'linear-gradient(135deg, #262626, #131313)', openCount: 1, totalCount: 5, path: '/dashboard' },
  { id: 'lot3', name: 'Lot 3', gradient: 'linear-gradient(135deg, #282828, #151515)', openCount: 1, totalCount: 5, path: '/dashboard' },
]


function getStatus(open:number, total: number) {
    if(open === 0) return { label: 'FULL', bg: '#F5E0E0', color: '#C0392B' }
    if(open / total < 0.25) return { label: 'LIMITED', bg: '#FFF3D6', color: '#B8860B'}
    return { label: 'OPEN', bg: '#DCF5E4', color: '#1A8A4A' }
}

function Welcome(){
    const navigate = useNavigate()

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
                    const status = getStatus(lot.openCount, lot.totalCount)
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
                                    {lot.openCount} of {lot.totalCount} open
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