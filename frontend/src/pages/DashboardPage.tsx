import { useState, useEffect } from 'react'
import { useWebSocket } from '../hooks/useWebSocket'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

interface DashboardStats {
  total_visitors_today: number
  new_visitors_today: number
  returning_visitors_today: number
  active_visitors: number
  total_registered: number
  total_employees: number
  active_conversations: number
}

interface RecentVisitor {
  person_id: string
  name: string
  company: string | null
  arrival_time: string
  status: string
  visit_type: string
}

interface SystemStatus {
  camera_active: boolean
  ai_service_active: boolean
  tts_active: boolean
  database_active: boolean
  uptime_seconds: number
}

function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [recentVisitors, setRecentVisitors] = useState<RecentVisitor[]>([])
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  // WebSocket for real-time updates (optional - dashboard works without it)
  const { isConnected } = useWebSocket(`${WS_URL}/ws/dashboard`, {
    onMessage: (data) => {
      if (data.type === 'new_session' || data.type === 'session_ended') {
        fetchStats()
        fetchRecentVisitors()
      }
    },
    autoConnect: true,
    reconnectInterval: 10000,
    maxReconnectAttempts: 3,
  })

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/dashboard/stats`)
      if (res.ok) {
        const data = await res.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error)
    }
  }

  const fetchRecentVisitors = async () => {
    try {
      const res = await fetch(`${API_URL}/api/dashboard/recent-visitors`)
      if (res.ok) {
        const data = await res.json()
        setRecentVisitors(data)
      }
    } catch (error) {
      console.error('Failed to fetch visitors:', error)
    }
  }

  const fetchSystemStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/dashboard/system-status`)
      if (res.ok) {
        const data = await res.json()
        setSystemStatus(data)
      }
    } catch (error) {
      console.error('Failed to fetch system status:', error)
    }
  }

  useEffect(() => {
    const loadAll = async () => {
      setLoading(true)
      await Promise.all([fetchStats(), fetchRecentVisitors(), fetchSystemStatus()])
      setLoading(false)
      setLastUpdate(new Date())
    }
    loadAll()

    // Poll every 30 seconds
    const interval = setInterval(loadAll, 30000)
    return () => clearInterval(interval)
  }, [])

  const formatUptime = (seconds: number): string => {
    const hrs = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return `${hrs}h ${mins}m`
  }

  return (
    <div className="min-h-screen pt-20 pb-6 px-4 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">Management Dashboard</h1>
            <p className="text-sm text-gray-400 mt-1">
              Real-time visitor monitoring and system status
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-xs text-gray-400">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </span>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 mb-6">
          <StatCard
            label="Today's Visitors"
            value={stats?.total_visitors_today ?? 0}
            color="blue"
          />
          <StatCard
            label="New Visitors"
            value={stats?.new_visitors_today ?? 0}
            color="green"
          />
          <StatCard
            label="Returning"
            value={stats?.returning_visitors_today ?? 0}
            color="purple"
          />
          <StatCard
            label="Active Now"
            value={stats?.active_visitors ?? 0}
            color="yellow"
          />
          <StatCard
            label="Registered"
            value={stats?.total_registered ?? 0}
            color="cyan"
          />
          <StatCard
            label="Employees"
            value={stats?.total_employees ?? 0}
            color="indigo"
          />
          <StatCard
            label="Active Convos"
            value={stats?.active_conversations ?? 0}
            color="pink"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Visitors */}
          <div className="lg:col-span-2 glass-panel p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Today's Visitors</h2>
            {recentVisitors.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <p className="text-sm">No visitors today yet</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-400">Name</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-400">Company</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-400">Time</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-400">Type</th>
                      <th className="text-left py-2 px-3 text-xs font-medium text-gray-400">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentVisitors.map((visitor) => (
                      <tr key={visitor.person_id} className="border-b border-gray-800 hover:bg-gray-800/40">
                        <td className="py-3 px-3 text-sm text-white font-medium">
                          {visitor.name}
                        </td>
                        <td className="py-3 px-3 text-sm text-gray-400">
                          {visitor.company || '—'}
                        </td>
                        <td className="py-3 px-3 text-sm text-gray-400">
                          {new Date(visitor.arrival_time).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>
                        <td className="py-3 px-3">
                          <span className={`status-badge ${
                            visitor.visit_type === 'new'
                              ? 'bg-green-600/20 text-green-400'
                              : 'bg-blue-600/20 text-blue-400'
                          }`}>
                            {visitor.visit_type === 'new' ? 'New' : 'Returning'}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <span className={`status-badge ${
                            visitor.status === 'arrived'
                              ? 'bg-yellow-600/20 text-yellow-400'
                              : visitor.status === 'departed'
                              ? 'bg-gray-600/20 text-gray-400'
                              : 'bg-green-600/20 text-green-400'
                          }`}>
                            {visitor.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* System Status */}
          <div className="glass-panel p-6">
            <h2 className="text-lg font-semibold text-white mb-4">System Status</h2>
            <div className="space-y-4">
              <ServiceStatus
                name="Database"
                active={systemStatus?.database_active ?? false}
              />
              <ServiceStatus
                name="AI (Bedrock)"
                active={systemStatus?.ai_service_active ?? false}
              />
              <ServiceStatus
                name="Text-to-Speech"
                active={systemStatus?.tts_active ?? false}
              />
              <ServiceStatus
                name="Camera"
                active={systemStatus?.camera_active ?? false}
              />
              <ServiceStatus
                name="WebSocket"
                active={isConnected}
              />

              {systemStatus && (
                <div className="pt-4 border-t border-gray-700">
                  <p className="text-xs text-gray-400">
                    Uptime: {formatUptime(systemStatus.uptime_seconds)}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Stat Card component
function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colorClasses: Record<string, string> = {
    blue: 'from-blue-600/20 to-blue-600/5 border-blue-500/20',
    green: 'from-green-600/20 to-green-600/5 border-green-500/20',
    purple: 'from-purple-600/20 to-purple-600/5 border-purple-500/20',
    yellow: 'from-yellow-600/20 to-yellow-600/5 border-yellow-500/20',
    cyan: 'from-cyan-600/20 to-cyan-600/5 border-cyan-500/20',
    indigo: 'from-indigo-600/20 to-indigo-600/5 border-indigo-500/20',
    pink: 'from-pink-600/20 to-pink-600/5 border-pink-500/20',
  }

  return (
    <div className={`rounded-xl p-4 bg-gradient-to-b border ${colorClasses[color] || colorClasses.blue}`}>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{label}</p>
    </div>
  )
}

// Service Status component
function ServiceStatus({ name, active }: { name: string; active: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-gray-300">{name}</span>
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${active ? 'bg-green-500' : 'bg-red-500'}`} />
        <span className={`text-xs ${active ? 'text-green-400' : 'text-red-400'}`}>
          {active ? 'Active' : 'Inactive'}
        </span>
      </div>
    </div>
  )
}

export default DashboardPage
