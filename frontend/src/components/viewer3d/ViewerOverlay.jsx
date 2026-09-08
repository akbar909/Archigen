import { useState } from 'react'
import {
  Footprints,
  Grid3X3,
  Home,
  Info,
  Maximize2,
  Minimize2,
  Moon,
  MousePointer,
  RotateCcw,
  Sparkles,
  Sun,
  Tag,
  Loader2,
} from 'lucide-react'
import { getRoomMeta } from './constants'

export default function ViewerOverlay({
  viewMode,
  onModeChange,
  viewSource,
  onViewSourceChange,
  glbUrl,
  isGenerating3D,
  onRegenerate3D,
  showCallouts,
  onToggleCallouts,
  isMouseLookLocked,
  onToggleMouseLook,
  isNightMode,
  onToggleNightMode,
  onResetCamera,
  isFullscreen,
  onToggleFullscreen,
  rooms = [],
  doors = [],
  windows = [],
  design,
  selectedRoomId,
  onSelectRoom,
}) {
  const [showInfoPopover, setShowInfoPopover] = useState(false)

  return (
    <>
      {/* ── Top Left: Viewport Mode Switcher & Source Toggle ── */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 14,
          display: 'flex',
          gap: 6,
          alignItems: 'center',
          zIndex: 10,
          flexWrap: 'wrap',
        }}
      >
        {/* Navigation Mode: Dollhouse / Walkthrough / Floor Plan */}
        <div
          style={{
            display: 'flex',
            gap: 4,
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 999,
            padding: 3,
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          }}
        >
          {[
            { id: 'dollhouse', icon: Home, label: 'Dollhouse 3D' },
            { id: 'walkthrough', icon: Footprints, label: 'Walkthrough' },
            { id: 'plan', icon: Grid3X3, label: 'Floor Plan' },
          ].map((mode) => {
            const IconComp = mode.icon
            const isActive = viewMode === mode.id
            return (
              <button
                key={mode.id}
                type="button"
                onClick={() => onModeChange(mode.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '5px 12px',
                  borderRadius: 999,
                  border: 'none',
                  background: isActive ? 'var(--accent)' : 'transparent',
                  color: isActive ? '#ffffff' : 'var(--text-secondary)',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <IconComp size={14} />
                <span>{mode.label}</span>
              </button>
            )
          })}
        </div>

        {/* View Mode Switcher: Cloud Blender vs CAD Interactive (Always visible) */}
        <div
          style={{
            display: 'flex',
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: 999,
            padding: 3,
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            gap: 2,
            alignItems: 'center',
          }}
        >
          {/* Blender 3D Toggle */}
          <button
            type="button"
            onClick={() => {
              if (glbUrl) {
                onViewSourceChange('blender')
              } else if (!isGenerating3D && onRegenerate3D) {
                onRegenerate3D()
              }
            }}
            disabled={isGenerating3D}
            title={
              glbUrl
                ? 'Switch to Photorealistic Cloud Blender 3D Model'
                : isGenerating3D
                ? 'Blender 3D is generating...'
                : 'Blender 3D not generated yet. Click to generate now!'
            }
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 12px',
              borderRadius: 999,
              border: 'none',
              background:
                viewSource === 'blender' && glbUrl
                  ? 'rgba(56, 189, 248, 0.25)'
                  : isGenerating3D
                  ? 'rgba(234, 179, 8, 0.15)'
                  : 'transparent',
              color:
                viewSource === 'blender' && glbUrl
                  ? '#38bdf8'
                  : isGenerating3D
                  ? '#eab308'
                  : 'var(--text-secondary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: isGenerating3D ? 'wait' : 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            {isGenerating3D ? (
              <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
            ) : (
              <Sparkles size={13} />
            )}
            <span>Blender 3D</span>
            {glbUrl ? (
              <span
                style={{
                  fontSize: '0.65rem',
                  padding: '1px 5px',
                  borderRadius: 999,
                  background: 'rgba(56, 189, 248, 0.2)',
                  color: '#38bdf8',
                  marginLeft: 2,
                }}
              >
                Ready ✓
              </span>
            ) : isGenerating3D ? (
              <span
                style={{
                  fontSize: '0.65rem',
                  padding: '1px 5px',
                  borderRadius: 999,
                  background: 'rgba(234, 179, 8, 0.2)',
                  color: '#eab308',
                  marginLeft: 2,
                }}
              >
                Building…
              </span>
            ) : (
              <span
                style={{
                  fontSize: '0.65rem',
                  padding: '1px 5px',
                  borderRadius: 999,
                  background: 'rgba(255, 255, 255, 0.08)',
                  color: 'var(--text-muted)',
                  marginLeft: 2,
                }}
              >
                Generate ⚡
              </span>
            )}
          </button>

          {/* CAD View Toggle */}
          <button
            type="button"
            onClick={() => onViewSourceChange('procedural')}
            title="Show Interactive CAD Model with Furnished Rooms & Cutaway Walls"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 12px',
              borderRadius: 999,
              border: 'none',
              background: viewSource === 'procedural' ? 'var(--accent)' : 'transparent',
              color: viewSource === 'procedural' ? '#ffffff' : 'var(--text-secondary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            <Home size={13} />
            <span>CAD View</span>
          </button>
        </div>
      </div>

      {/* ── Top Right: Stats Details + Day/Night + Tools ── */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          right: 14,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          zIndex: 10,
        }}
      >
        {/* Toggle Floating Room Tags */}
        {viewMode !== 'walkthrough' && (
          <button
            type="button"
            onClick={onToggleCallouts}
            title="Toggle Room Callout Tags"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: showCallouts ? 'rgba(16, 185, 129, 0.2)' : 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(16px)',
              border: `1px solid ${showCallouts ? '#10b981' : 'rgba(255, 255, 255, 0.12)'}`,
              borderRadius: 999,
              padding: '5px 11px',
              color: showCallouts ? '#10b981' : 'var(--text-primary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              transition: 'all 0.15s ease',
            }}
          >
            <Tag size={13} />
            <span>Tags</span>
          </button>
        )}

        {/* Mouse Look Direction Toggle Button for Walkthrough */}
        {viewMode === 'walkthrough' && (
          <button
            type="button"
            onClick={onToggleMouseLook}
            title="Toggle Mouse Look Direction (or press Ctrl key)"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: isMouseLookLocked ? 'var(--accent)' : 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(16px)',
              border: `1px solid ${isMouseLookLocked ? 'var(--accent)' : 'rgba(255, 255, 255, 0.15)'}`,
              borderRadius: 999,
              padding: '5px 12px',
              color: isMouseLookLocked ? '#ffffff' : 'var(--text-primary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              transition: 'all 0.15s ease',
            }}
          >
            <MousePointer size={14} />
            <span>{isMouseLookLocked ? 'Mouse ON (Ctrl)' : 'Mouse (Ctrl)'}</span>
          </button>
        )}

        {/* Architectural Details Info Button */}
        <div style={{ position: 'relative' }}>
          <button
            type="button"
            onClick={() => setShowInfoPopover(!showInfoPopover)}
            title="View Architectural Details"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              background: showInfoPopover ? 'var(--accent)' : 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 999,
              padding: '5px 13px',
              color: showInfoPopover ? '#ffffff' : 'var(--text-primary)',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              transition: 'all 0.15s ease',
            }}
          >
            <Info size={14} />
            <span>{rooms.length}</span>
            <span>Rooms</span>
            <span style={{ color: 'rgba(255,255,255,0.3)' }}>•</span>
            <span>{doors.length} Doors</span>
            <span style={{ color: 'rgba(255,255,255,0.3)' }}>•</span>
            <span>{windows.length} Windows</span>
            <span style={{ color: 'rgba(255,255,255,0.3)' }}>•</span>
            <span style={{ textTransform: 'capitalize', color: '#fbbf24' }}>{design?.style || 'Modern'}</span>
          </button>

          {/* Floating Details Popover Card */}
          {showInfoPopover && (
            <div
              style={{
                position: 'absolute',
                top: 38,
                right: 0,
                width: 280,
                background: 'rgba(15, 23, 42, 0.95)',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: 'var(--radius-md)',
                padding: '14px 16px',
                zIndex: 30,
                boxShadow: '0 16px 48px rgba(0,0,0,0.6)',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: 8 }}>
                <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#ffffff' }}>Design Specifications</div>
                <button
                  type="button"
                  onClick={() => setShowInfoPopover(false)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.8rem' }}
                >
                  ✕
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 10px', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Rooms</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent)' }}>{rooms.length}</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 10px', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Doors</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ffffff' }}>{doors.length}</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 10px', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Windows</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ffffff' }}>{windows.length}</div>
                </div>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 10px', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Style</div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fbbf24', textTransform: 'capitalize', marginTop: 3 }}>
                    {design?.style || 'Modern'}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 2 }}>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginBottom: 6, fontWeight: 600, textTransform: 'uppercase' }}>
                  Room Dimensions
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 120, overflowY: 'auto' }}>
                  {rooms.map((r, i) => (
                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      <span>{r.type}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{r.width}m × {r.length}m</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Night / Day Toggle */}
        <button
          type="button"
          onClick={onToggleNightMode}
          title={isNightMode ? 'Switch to Day Mode' : 'Switch to Night Glow'}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 999,
            padding: '5px 12px',
            color: isNightMode ? '#fbbf24' : 'var(--text-primary)',
            fontSize: '0.78rem',
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          }}
        >
          {isNightMode ? <Moon size={14} /> : <Sun size={14} />}
          <span>{isNightMode ? 'Night' : 'Day'}</span>
        </button>

        {/* Reset Camera Button */}
        <button
          type="button"
          onClick={onResetCamera}
          title="Reset Camera to Full View"
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '50%',
            width: 32,
            height: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-primary)',
            cursor: 'pointer',
          }}
        >
          <RotateCcw size={14} />
        </button>

        {/* Fullscreen Button */}
        <button
          type="button"
          onClick={onToggleFullscreen}
          title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '50%',
            width: 32,
            height: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-primary)',
            cursor: 'pointer',
          }}
        >
          {isFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>

      {/* ── Bottom Floating Room Navigator Strip ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 32,
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          background: 'rgba(15, 23, 42, 0.88)',
          backdropFilter: 'blur(18px)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: 999,
          padding: '4px 6px',
          maxWidth: '92%',
          overflowX: 'auto',
          zIndex: 10,
          boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
        }}
      >
        <button
          type="button"
          onClick={onResetCamera}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '5px 12px',
            borderRadius: 999,
            border: 'none',
            background: selectedRoomId === 'overview' ? 'var(--accent)' : 'rgba(255, 255, 255, 0.06)',
            color: selectedRoomId === 'overview' ? '#ffffff' : 'var(--text-secondary)',
            fontSize: '0.75rem',
            fontWeight: 600,
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            transition: 'all 0.15s ease',
          }}
        >
          <Home size={13} />
          <span>Overview</span>
        </button>

        <div style={{ width: 1, height: 16, background: 'rgba(255,255,255,0.15)', flexShrink: 0 }} />

        {rooms.map((room) => {
          const meta = getRoomMeta(room.type)
          const RoomIconComp = meta.icon
          const isSelected = selectedRoomId === room.id
          return (
            <button
              key={room.id || room.type}
              type="button"
              onClick={() => onSelectRoom(room)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '5px 11px',
                borderRadius: 999,
                border: `1px solid ${isSelected ? meta.color : 'transparent'}`,
                background: isSelected ? 'rgba(255,255,255,0.15)' : 'rgba(255, 255, 255, 0.05)',
                color: isSelected ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.15s ease',
              }}
            >
              <RoomIconComp size={13} color={isSelected ? meta.color : 'currentColor'} />
              <span>{room.type}</span>
            </button>
          )
        })}
      </div>

      {/* ── Center Crosshair for Mouse Look ── */}
      {viewMode === 'walkthrough' && isMouseLookLocked && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            pointerEvents: 'none',
            zIndex: 20,
            width: 7,
            height: 7,
            border: '2px solid rgba(255, 255, 255, 0.85)',
            borderRadius: '50%',
            boxShadow: '0 0 8px rgba(0,0,0,0.7)',
          }}
        />
      )}

      {/* ── Bottom Controls Guide ── */}
      <div
        style={{
          position: 'absolute',
          bottom: 10,
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          color: 'rgba(255, 255, 255, 0.45)',
          fontSize: '0.6875rem',
          fontWeight: 500,
          pointerEvents: 'none',
          whiteSpace: 'nowrap',
          zIndex: 10,
        }}
      >
        {viewMode === 'walkthrough' ? (
          <>
            <span><strong style={{ color: '#fbbf24' }}>[Ctrl]</strong> {isMouseLookLocked ? 'Release Mouse' : 'Enable Mouse Look'}</span>
            <span>•</span>
            <span><strong style={{ color: '#6ee7b7' }}>Mouse</strong> Look direction</span>
            <span>•</span>
            <span><strong style={{ color: '#6ee7b7' }}>WASD</strong> Walk</span>
          </>
        ) : (
          <>
            <span><strong style={{ color: 'rgba(255,255,255,0.75)' }}>WASD</strong> to walk</span>
            <span>•</span>
            <span><strong style={{ color: 'rgba(255,255,255,0.75)' }}>Left Click</strong> orbit</span>
            <span>•</span>
            <span><strong style={{ color: 'rgba(255,255,255,0.75)' }}>Right Click</strong> pan</span>
            <span>•</span>
            <span><strong style={{ color: 'rgba(255,255,255,0.75)' }}>Scroll</strong> zoom</span>
          </>
        )}
      </div>
    </>
  )
}
