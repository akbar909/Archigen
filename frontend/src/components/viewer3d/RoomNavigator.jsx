import { useEffect, useRef, useState } from 'react'
import { Check, ChevronDown, ChevronUp, Home } from 'lucide-react'

import { getRoomMeta } from './constants'

export default function RoomNavigator({
  is3DReady,
  rooms,
  selectedRoomId,
  onSelectRoom,
  onResetCamera,
  resetKey,
}) {
  const [isRoomDrawerOpen, setIsRoomDrawerOpen] = useState(false)
  const drawerRef = useRef(null)

  useEffect(() => {
    function handleClickOutside(event) {
      if (drawerRef.current && !drawerRef.current.contains(event.target)) {
        setIsRoomDrawerOpen(false)
      }
    }
    if (isRoomDrawerOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isRoomDrawerOpen])

  useEffect(() => setIsRoomDrawerOpen(false), [resetKey])

  const activeRoom = rooms.find((room) => room.id === selectedRoomId)
  const currentRoomLabel = selectedRoomId === 'overview' || !selectedRoomId
    ? 'Overview'
    : (activeRoom?.name || activeRoom?.type || 'Room')

  return (
    <>
      {/* ── Bottom Room Navigator: Responsive Lift-Up / Dropdown Menu (Only when 3D is rendered) ── */}
      {is3DReady && rooms.length > 0 && (
        <div
          ref={drawerRef}
          className="room-navigator"
          style={{
            position: 'absolute',
            bottom: 30,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 15,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            pointerEvents: 'auto',
          }}
        >
          {/* Lift-Up Popup List (Appears Above the Button) */}
          {isRoomDrawerOpen && (
            <div
              style={{
                position: 'absolute',
                bottom: '100%',
                marginBottom: 8,
                background: 'rgba(18, 18, 18, 0.96)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: 16,
                padding: '8px',
                boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
                width: 240,
                maxHeight: '260px',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                gap: 4,
                zIndex: 25,
                animation: 'fadeUp 0.15s ease-out',
              }}
            >
              <div
                style={{
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--text-muted)',
                  padding: '4px 8px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span>Navigate Rooms</span>
                <span style={{ color: 'var(--accent)' }}>{rooms.length} total</span>
              </div>

              {/* Overview Button */}
              <button
                type="button"
                onClick={() => {
                  onResetCamera()
                  setIsRoomDrawerOpen(false)
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '7px 10px',
                  borderRadius: 8,
                  border: 'none',
                  background: selectedRoomId === 'overview' ? 'var(--accent)' : 'rgba(255, 255, 255, 0.04)',
                  color: selectedRoomId === 'overview' ? '#ffffff' : 'var(--text-primary)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'background 0.12s ease',
                  textAlign: 'left',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                  <Home size={14} />
                  <span>Entire House (Overview)</span>
                </div>
                {selectedRoomId === 'overview' && <Check size={14} />}
              </button>

              <div style={{ height: 1, background: 'rgba(255,255,255,0.08)', margin: '2px 4px' }} />

              {/* Individual Rooms */}
              {rooms.map((room) => {
                const meta = getRoomMeta(room.type)
                const RoomIconComp = meta.icon
                const isSelected = selectedRoomId === room.id
                return (
                  <button
                    key={room.id || room.type}
                    type="button"
                    onClick={() => {
                      onSelectRoom(room)
                      setIsRoomDrawerOpen(false)
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '7px 10px',
                      borderRadius: 8,
                      border: 'none',
                      background: isSelected ? 'rgba(16, 163, 127, 0.18)' : 'transparent',
                      color: isSelected ? '#10a37f' : 'var(--text-secondary)',
                      fontSize: '0.76rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'background 0.12s ease',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
                      <RoomIconComp size={13} color={isSelected ? '#10a37f' : meta.color || 'currentColor'} />
                      <span>{room.name || room.type}</span>
                    </div>
                    {isSelected && <Check size={13} color="#10a37f" />}
                  </button>
                )
              })}
            </div>
          )}

          {/* Trigger Pill Button */}
          <button
            type="button"
            onClick={() => setIsRoomDrawerOpen(!isRoomDrawerOpen)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'rgba(18, 18, 18, 0.92)',
              backdropFilter: 'blur(18px)',
              border: `1px solid ${isRoomDrawerOpen ? 'var(--accent)' : 'rgba(255, 255, 255, 0.15)'}`,
              borderRadius: 999,
              padding: '6px 14px',
              color: '#ffffff',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 30px rgba(0,0,0,0.5)',
              transition: 'all 0.15s ease',
            }}
          >
            <Home size={13} color="var(--accent)" />
            <span>Room: <strong style={{ color: 'var(--accent)' }}>{currentRoomLabel}</strong></span>
            {isRoomDrawerOpen ? <ChevronDown size={14} color="var(--text-muted)" /> : <ChevronUp size={14} color="var(--text-muted)" />}
          </button>
        </div>
      )}
    </>
  )
}


