import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Welcome from './Welcome'
import ParkingStatus from './ParkingStatus'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Welcome />} />
        <Route path="/dashboard" element={<ParkingStatus />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App