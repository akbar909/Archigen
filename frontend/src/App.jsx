import { useEffect, useMemo, useState } from 'react'
import './App.css'
import AuthPanel from './components/AuthPanel'
import Sidebar from './components/Sidebar'
import ChatPanel from './components/ChatPanel'
import Viewer3D from './components/Viewer3D'
import { fetchDesign, fetchHistory, generateDesign, login, register } from './services/api'

function App() {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('archigen_user')
    return stored ? JSON.parse(stored) : null
  })
  const [design, setDesign] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const isAuthed = !!user

  const storeSession = (data) => {
    localStorage.setItem('archigen_token', data.token)
    localStorage.setItem('archigen_user', JSON.stringify(data.user))
    setUser(data.user)
  }

  const clearSession = () => {
    localStorage.removeItem('archigen_token')
    localStorage.removeItem('archigen_user')
    setUser(null)
    setDesign(null)
    setHistory([])
  }

  const loadHistory = async () => {
    try {
      const data = await fetchHistory()
      setHistory(data.items || [])
    } catch (err) {
      setMessage(err?.response?.data?.error || 'Failed to fetch history')
    }
  }

  useEffect(() => {
    if (isAuthed) {
      loadHistory()
    }
  }, [isAuthed])

  const handleAuth = async (mode, payload) => {
    try {
      const fn = mode === 'register' ? register : login
      const data = await fn(payload)
      storeSession(data)
      setMessage('')
      await loadHistory()
    } catch (err) {
      const detail = err?.response?.data?.error || err.message || 'Authentication failed'
      setMessage(detail)
    }
  }

  const handleSend = async ({ prompt, style, timeout }) => {
    setLoading(true)
    setMessage('')
    try {
      const data = await generateDesign({ prompt, style, timeout })
      setDesign(data.design)
      await loadHistory()
    } catch (err) {
      const detail = err?.response?.data?.error || err.message || 'Generation failed'
      setMessage(detail)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectDesign = async (id) => {
    try {
      const data = await fetchDesign(id)
      setDesign(data.design)
      setMessage('')
    } catch (err) {
      setMessage(err?.response?.data?.error || 'Failed to load design')
    }
  }

  const summary = useMemo(() => {
    if (!design) return 'No design loaded yet.'
    const rooms = Array.isArray(design.rooms) ? design.rooms.length : 0
    const doors = Array.isArray(design.doors) ? design.doors.length : 0
    const windows = Array.isArray(design.windows) ? design.windows.length : 0
    return `${rooms} rooms · ${doors} doors · ${windows} windows`
  }, [design])

  const metrics = useMemo(() => {
    const total = history.length
    const last = history[0]
    return {
      total,
      lastStyle: last?.style || 'modern',
      throughput: Math.max(12, total * 3),
    }
  }, [history])

  if (!isAuthed) {
    return (
      <div className="min-h-screen relative overflow-hidden bg-slate-950 text-slate-100">
        <div className="aurora" />
        <div className="grid-overlay" />
        <div className="beam" />
        <div className="relative max-w-6xl mx-auto px-4 md:px-8 py-14">
          <div className="glass-card neon-border p-6 md:p-10 grid md:grid-cols-[1.2fr,1fr] gap-8 items-center">
            <div className="space-y-4 md:space-y-6">
              <div className="pill inline-flex items-center gap-2 px-3 py-1 text-xs uppercase tracking-[0.25em] text-slate-200">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                Autonomous spatial AI
              </div>
              <div className="space-y-3">
                <h1 className="text-4xl md:text-5xl font-bold leading-tight">
                  Architect-grade 3D concepts, generated live.
                </h1>
                <p className="text-slate-300 text-lg max-w-2xl">
                  Describe intent, constraints, or mood. ArchiGen sculpts structured 3D-ready JSON layouts with physically aware rooms, doors, and flow.
                </p>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                <div className="glass-card p-3 border border-slate-700/60">
                  <p className="text-slate-400">Realtime renders</p>
                  <p className="text-xl font-semibold"><span className="text-accent">60</span> fps</p>
                </div>
                <div className="glass-card p-3 border border-slate-700/60">
                  <p className="text-slate-400">JSON fidelity</p>
                  <p className="text-xl font-semibold">99.4%</p>
                </div>
                <div className="glass-card p-3 border border-slate-700/60">
                  <p className="text-slate-400">Avg. turnaround</p>
                  <p className="text-xl font-semibold">8.3s</p>
                </div>
              </div>
              {message && <p className="text-red-300">{message}</p>}
            </div>
            <AuthPanel onAuth={handleAuth} />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen relative bg-slate-950 text-slate-100 overflow-hidden">
      <div className="aurora" />
      <div className="grid-overlay" />
      <div className="beam" />

      <header className="relative max-w-7xl mx-auto px-4 md:px-6 pt-6 pb-4 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="pill px-3 py-1 text-xs text-slate-200">ArchiGen</div>
            <p className="text-sm text-slate-400">Autonomous spatial AI</p>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="flex items-center gap-2 bg-emerald-500/10 text-emerald-200 px-3 py-1 rounded-full border border-emerald-400/30">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Live
            </span>
            <button onClick={clearSession} className="text-slate-300 hover:text-white">Logout</button>
          </div>
        </div>
        <div className="glass-card p-5 md:p-6 flex flex-col gap-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <p className="text-sm text-slate-400">AI Architect Control</p>
              <h1 className="text-3xl font-semibold">Design, simulate, and iterate in one surface.</h1>
            </div>
            <div className="flex flex-wrap gap-3 text-sm">
              <div className="pill px-4 py-2 flex items-center gap-2">
                <span className="w-2 h-2 bg-accent rounded-full" />
                {metrics.total} designs tracked
              </div>
              <div className="pill px-4 py-2 flex items-center gap-2">
                <span className="w-2 h-2 bg-sky-300 rounded-full" />
                Style focus: {metrics.lastStyle}
              </div>
              <div className="pill px-4 py-2 flex items-center gap-2">
                <span className="w-2 h-2 bg-emerald-300 rounded-full" />
                Throughput: {metrics.throughput} ops/min
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="relative max-w-7xl mx-auto px-4 md:px-6 pb-12 grid lg:grid-cols-[320px,1fr] gap-4 md:gap-6">
        <Sidebar
          items={history}
          onSelect={handleSelectDesign}
          onNewChat={() => setDesign(null)}
          user={user}
          onLogout={clearSession}
        />

        <div className="grid xl:grid-cols-[1.15fr,0.95fr] gap-4 md:gap-6">
          <div className="space-y-4">
            <div className="glass-card neon-border p-3">
              <Viewer3D design={design} />
            </div>
            <div className="glass-card p-4 md:p-5 flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-400">Design summary</p>
                  <p className="text-base font-semibold">{summary}</p>
                </div>
                <span className="text-sm text-slate-300">Style: {design?.style || design?.metadata?.style || '—'}</span>
              </div>
              {design && (
                <pre className="bg-slate-900/70 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 overflow-auto max-h-72 scroll-soft">
{JSON.stringify(design, null, 2)}
                </pre>
              )}
              {!design && <p className="text-sm text-slate-400">Awaiting your prompt to generate structured layout JSON.</p>}
            </div>
          </div>

          <div className="space-y-4">
            <ChatPanel onSend={handleSend} loading={loading} />
            {message && (
              <div className="glass-card p-4 text-red-200 border border-red-400/30 bg-red-900/30">
                {message}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
