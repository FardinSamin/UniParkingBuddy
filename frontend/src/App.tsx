import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Welcome from './Welcome'
import ParkingLot1 from './parkinglotroutes/parkinglot1.tsx'
import ParkingLot2 from './parkinglotroutes/parkinglot2.tsx'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Welcome />} /> 
        <Route path="/parking-lot1" element={<ParkingLot1/>} />
        <Route path="/parking-lot2" element={<ParkingLot2/>} />
      </Routes>
    </BrowserRouter>
  )
}

export default App