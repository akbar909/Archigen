import { AppWindow, DoorOpen, Layers, Sparkles } from 'lucide-react'

export default function StatsRow({ design }) {
  if (!design) return null

  const rooms = Array.isArray(design.rooms) ? design.rooms.length : 0
  const doors = Array.isArray(design.doors) ? design.doors.length : 0
  const windows = Array.isArray(design.windows) ? design.windows.length : 0
  const style = design?.style || design?.metadata?.style || 'Modern'

  return (
    <div className="stats-pill-bar fade-up">
      <div className="stat-pill">
        <span className="stat-pill-icon"><Layers size={14} /></span>
        <span className="stat-pill-num">{rooms}</span>
        <span className="stat-pill-text">Rooms</span>
      </div>
      <div className="stat-pill-divider" />
      <div className="stat-pill">
        <span className="stat-pill-icon"><DoorOpen size={14} /></span>
        <span className="stat-pill-num">{doors}</span>
        <span className="stat-pill-text">Doors</span>
      </div>
      <div className="stat-pill-divider" />
      <div className="stat-pill">
        <span className="stat-pill-icon"><AppWindow size={14} /></span>
        <span className="stat-pill-num">{windows}</span>
        <span className="stat-pill-text">Windows</span>
      </div>
      <div className="stat-pill-divider" />
      <div className="stat-pill">
        <span className="stat-pill-icon"><Sparkles size={14} /></span>
        <span className="stat-pill-text" style={{ textTransform: 'capitalize' }}>{style} Style</span>
      </div>
    </div>
  )
}
