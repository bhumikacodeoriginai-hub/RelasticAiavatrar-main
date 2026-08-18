import { Routes, Route } from 'react-router-dom'
import ReceptionistPage from './pages/ReceptionistPage'
import DashboardPage from './pages/DashboardPage'
import Navbar from './components/Navbar'

function App() {
  return (
    <div className="min-h-screen bg-gray-900">
      <Navbar />
      <Routes>
        <Route path="/" element={<ReceptionistPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
      </Routes>
    </div>
  )
}

export default App
