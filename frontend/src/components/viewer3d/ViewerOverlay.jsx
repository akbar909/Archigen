import { useEffect, useRef, useState } from 'react'
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
  Loader2,
  Building,
  Building2,
  Eye,
  EyeOff,
  ChevronDown,
} from 'lucide-react'

import RoomNavigator from './RoomNavigator'

export default function ViewerOverlay({
  viewMode,
  onModeChange,
  viewSource,
  onViewSourceChange,
  glbUrl,
  isModelRendered = false,
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
  isApproved = false,
  selectedRoomId,
  onSelectRoom,
  showRoof = true,
  onToggleRoof,
  activeFloorLevel = 0,
  onChangeFloorLevel,
  floors = [],
  planSubMode = 'vector',
  onPlanSubModeChange,
  onApproveLayout,
  isApprovingLayout = false,
}) {
  const [showInfoPopover, setShowInfoPopover] = useState(false)

  const is2DVectorMode = viewMode === 'plan' && planSubMode === 'vector'
  const is3DReady = Boolean(glbUrl && isModelRendered && !isGenerating3D)
  // The Canvas is not mounted in vector-plan mode. In that mode an existing
  // GLB is ready to open, not stuck in a false loading state.
  const is3DLoading = Boolean(glbUrl && !isModelRendered && !isGenerating3D && !is2DVectorMode)

  // Navigation Camera Modes (3D modes only available or highlighted once 3D exists)
  const viewModes = [
    { id: 'dollhouse', icon: Home, label: 'Dollhouse 3D', requires3D: true },
    { id: 'walkthrough', icon: Footprints, label: 'Walkthrough', requires3D: true },
    { id: 'plan', icon: Grid3X3, label: 'Floor Plan', requires3D: false },
    { id: 'front', icon: Building, label: 'Front Exterior', requires3D: true },
    { id: 'back', icon: Building2, label: 'Back Exterior', requires3D: true },
    { id: 'roof', icon: Eye, label: 'Roof View', requires3D: true },
  ]


  const [isViewMenuOpen, setIsViewMenuOpen] = useState(false)
  const viewMenuRef = useRef(null)

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (viewMenuRef.current && !viewMenuRef.current.contains(event.target)) {
        setIsViewMenuOpen(false)
      }
    }
    if (isViewMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isViewMenuOpen])

  const currentModeObj = viewModes.find((m) => m.id === viewMode) || viewModes[0]
  const CurrentIcon = currentModeObj.icon

  return (
    <>
      {/* ── Top Left Controls: Responsive Navigation & Layer Bar ── */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          left: 12,
          display: 'flex',
          gap: 6,
          alignItems: 'center',
          zIndex: 20,
          pointerEvents: 'auto',
        }}
      >
        {/* Compact View Mode Dropdown */}
        {is3DReady && (
          <div ref={viewMenuRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => setIsViewMenuOpen((prev) => !prev)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'rgba(18, 18, 18, 0.92)',
                backdropFilter: 'blur(16px)',
                border: isViewMenuOpen ? '1px solid var(--accent)' : '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: 999,
                padding: '5px 12px',
                color: '#ffffff',
                fontSize: '0.78rem',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                transition: 'all 0.15s ease',
              }}
            >
              <CurrentIcon size={14} className="text-emerald-400" />
              <span>{currentModeObj.label}</span>
              <ChevronDown
                size={13}
                style={{
                  transition: 'transform 0.2s ease',
                  transform: isViewMenuOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                  color: 'var(--text-muted)',
                }}
              />
            </button>

            {/* Dropdown Menu Options */}
            {isViewMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: 'calc(100% + 6px)',
                  left: 0,
                  minWidth: 175,
                  background: 'rgba(18, 18, 18, 0.96)',
                  backdropFilter: 'blur(20px)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: 14,
                  padding: 4,
                  boxShadow: '0 16px 40px rgba(0,0,0,0.5), 0 0 15px rgba(0,0,0,0.3)',
                  zIndex: 50,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                }}
              >
                {viewModes.map((mode) => {
                  const IconComp = mode.icon
                  const isActive = viewMode === mode.id
                  return (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => {
                        onModeChange(mode.id)
                        setIsViewMenuOpen(false)
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '7px 10px',
                        borderRadius: 9,
                        border: 'none',
                        background: isActive ? 'rgba(16, 163, 127, 0.2)' : 'transparent',
                        color: isActive ? '#34d399' : 'rgba(255, 255, 255, 0.85)',
                        fontSize: '0.76rem',
                        fontWeight: isActive ? 600 : 500,
                        cursor: 'pointer',
                        textAlign: 'left',
                        transition: 'all 0.12s ease',
                        width: '100%',
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive) e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)'
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive) e.currentTarget.style.background = 'transparent'
                      }}
                    >
                      <IconComp size={14} style={{ color: isActive ? '#34d399' : 'var(--text-muted)' }} />
                      <span>{mode.label}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Plan Mode Sub-Toggle: 2D CAD Blueprint vs 3D Top-Down */}
        {viewMode === 'plan' && onPlanSubModeChange && (
          <div
            style={{
              display: 'flex',
              gap: 2,
              background: 'rgba(18, 18, 18, 0.92)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(16, 163, 127, 0.3)',
              borderRadius: 999,
              padding: 2,
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            }}
          >
            <button
              type="button"
              onClick={() => onPlanSubModeChange('vector')}
              style={{
                padding: '4px 9px',
                borderRadius: 999,
                border: 'none',
                background: planSubMode === 'vector' ? '#10a37f' : 'transparent',
                color: planSubMode === 'vector' ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              📐 2D CAD Plan
            </button>
            {is3DReady && (
              <button
                type="button"
                onClick={() => onPlanSubModeChange('3d')}
                style={{
                  padding: '4px 9px',
                  borderRadius: 999,
                  border: 'none',
                  background: planSubMode === '3d' ? '#10a37f' : 'transparent',
                  color: planSubMode === '3d' ? '#ffffff' : 'var(--text-secondary)',
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                🏛️ 3D Top-Down
              </button>
            )}
          </div>
        )}

        {/* Layer Visibility: Roof Toggle (Visible in all 3D modes including 3D Top-Down Floor Plan) */}
        {is3DReady && !is2DVectorMode && onToggleRoof && (
          <button
            type="button"
            onClick={onToggleRoof}
            title={showRoof ? 'Click to hide roof and inspect upper floor interior' : 'Click to show roof structure'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '5px 11px',
              borderRadius: 999,
              border: `1px solid ${showRoof ? 'rgba(255, 255, 255, 0.15)' : 'rgba(234, 179, 8, 0.5)'}`,
              background: showRoof ? 'rgba(18, 18, 18, 0.88)' : 'rgba(234, 179, 8, 0.2)',
              color: showRoof ? 'var(--text-secondary)' : '#fbbf24',
              fontSize: '0.74rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              backdropFilter: 'blur(16px)',
              whiteSpace: 'nowrap',
            }}
          >
            {showRoof ? <Eye size={13} /> : <EyeOff size={13} />}
            <span>{showRoof ? 'Roof: ON' : 'Roof: OFF'}</span>
          </button>
        )}

        {/* Multi-floor Selector (in 3D mode when >1 floor and 3D is rendered) */}
        {!is2DVectorMode && is3DReady && floors.length > 1 && onChangeFloorLevel && (
          <div
            style={{
              display: 'flex',
              gap: 2,
              background: 'rgba(18, 18, 18, 0.88)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 999,
              padding: 2,
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            }}
          >
            <button
              key="all"
              type="button"
              onClick={() => onChangeFloorLevel(null)}
              style={{
                padding: '4px 9px',
                borderRadius: 999,
                border: 'none',
                background: activeFloorLevel === null || activeFloorLevel === undefined ? 'var(--accent)' : 'transparent',
                color: activeFloorLevel === null || activeFloorLevel === undefined ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              All
            </button>
            {floors.map((fl, idx) => {
              const lvl = fl.level !== undefined ? fl.level : idx
              const isActive = activeFloorLevel === lvl
              const label = lvl === 0 ? 'Ground (L0)' : `Floor ${lvl} (L${lvl})`
              return (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => onChangeFloorLevel(isActive ? null : lvl)}
                  style={{
                    padding: '4px 9px',
                    borderRadius: 999,
                    border: 'none',
                    background: isActive ? 'var(--accent)' : 'transparent',
                    color: isActive ? '#ffffff' : 'var(--text-secondary)',
                    fontSize: '0.72rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {label}
                </button>
              )
            })}
          </div>
        )}

      </div>

      {/* ── Top Right: Blender 3D Status + Day/Night + Tools ── */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          zIndex: 10,
        }}
      >
        {/* Saved cloud model opens directly; regeneration is a separate action. */}
        {isApproved && (
          <div
            style={{
              display: 'flex',
              background: 'rgba(18, 18, 18, 0.88)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: 999,
              padding: 3,
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              alignItems: 'center',
            }}
          >
            <button
              type="button"
              onClick={() => {
                if (isGenerating3D || is3DLoading) return
                if (glbUrl) {
                  onViewSourceChange?.('blender')
                  onModeChange?.('dollhouse')
                } else if (onRegenerate3D) {
                  onRegenerate3D()
                }
              }}
              disabled={isGenerating3D || is3DLoading}
              title={
                is3DReady
                  ? 'Open the saved cloud Blender model'
                  : isGenerating3D
                  ? 'Blender 3D is synthesizing in cloud...'
                  : is3DLoading
                  ? 'Rendering 3D model into viewport...'
                  : glbUrl
                  ? 'Open the previously generated cloud model'
                  : 'Generate a new Blender 3D model'
              }
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 5,
                padding: '5px 12px',
                borderRadius: 999,
                border: 'none',
                background: is3DReady
                  ? 'rgba(16, 163, 127, 0.18)'
                  : (isGenerating3D || is3DLoading)
                  ? 'rgba(234, 179, 8, 0.2)'
                  : 'rgba(16, 163, 127, 0.35)',
                color: is3DReady
                  ? '#10a37f'
                  : (isGenerating3D || is3DLoading)
                  ? '#eab308'
                  : '#ffffff',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: (isGenerating3D || is3DLoading) ? 'wait' : 'pointer',
                transition: 'all 0.15s ease',
                whiteSpace: 'nowrap',
              }}
            >
              {isGenerating3D || is3DLoading ? (
                <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <Sparkles size={13} />
              )}
              <span>Blender 3D</span>
              {isGenerating3D ? (
                <span
                  style={{
                    fontSize: '0.65rem',
                    padding: '1px 5px',
                    borderRadius: 999,
                    background: 'rgba(234, 179, 8, 0.3)',
                    color: '#eab308',
                    marginLeft: 2,
                  }}
                >
                  Rendering…
                </span>
              ) : is3DLoading ? (
                <span
                  style={{
                    fontSize: '0.65rem',
                    padding: '1px 5px',
                    borderRadius: 999,
                    background: 'rgba(16, 163, 127, 0.25)',
                    color: '#10a37f',
                    marginLeft: 2,
                  }}
                >
                  Loading 3D…
                </span>
              ) : glbUrl ? (
                <span
                  style={{
                    fontSize: '0.65rem',
                    padding: '1px 5px',
                    borderRadius: 999,
                    background: 'rgba(16, 163, 127, 0.25)',
                    color: '#10a37f',
                    marginLeft: 2,
                  }}
                >
                  {is3DReady ? 'HD ✓' : 'View'}
                </span>
              ) : (
                <span
                  style={{
                    fontSize: '0.65rem',
                    padding: '1px 5px',
                    borderRadius: 999,
                    background: '#10a37f',
                    color: '#ffffff',
                    marginLeft: 2,
                  }}
                >
                  Generate ⚡
                </span>
              )}
            </button>
            {glbUrl && is3DReady && onRegenerate3D && (
              <button
                type="button"
                onClick={() => {
                  if (window.confirm('Regenerate this model from the approved layout? This can take several minutes.')) {
                    onRegenerate3D()
                  }
                }}
                title="Regenerate the Blender model"
                aria-label="Regenerate the Blender model"
                style={{
                  display: 'grid',
                  placeItems: 'center',
                  width: 28,
                  height: 28,
                  border: 'none',
                  borderRadius: '50%',
                  background: 'transparent',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                }}
              >
                <RotateCcw size={13} />
              </button>
            )}
          </div>
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
              gap: 5,
              background: isMouseLookLocked ? 'var(--accent)' : 'rgba(18, 18, 18, 0.88)',
              backdropFilter: 'blur(16px)',
              border: `1px solid ${isMouseLookLocked ? 'var(--accent)' : 'rgba(255, 255, 255, 0.15)'}`,
              borderRadius: 999,
              padding: '5px 11px',
              color: isMouseLookLocked ? '#ffffff' : 'var(--text-primary)',
              fontSize: '0.74rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              transition: 'all 0.15s ease',
              whiteSpace: 'nowrap',
            }}
          >
            <MousePointer size={13} />
            <span>{isMouseLookLocked ? 'Mouse ON' : 'Mouse'}</span>
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
              gap: 5,
              background: showInfoPopover ? 'var(--accent)' : 'rgba(18, 18, 18, 0.88)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 999,
              padding: '5px 10px',
              color: showInfoPopover ? '#ffffff' : 'var(--text-primary)',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              transition: 'all 0.15s ease',
            }}
          >
            <Info size={13} />
          </button>

          {/* Floating Details Popover Card */}
          {showInfoPopover && (
            <div
              style={{
                position: 'absolute',
                top: 36,
                right: 0,
                width: 270,
                background: 'rgba(18, 18, 18, 0.96)',
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

        {/* Night / Day Toggle: Only shown in 3D modes */}
        {!is2DVectorMode && (
          <button
            type="button"
            onClick={onToggleNightMode}
            title={isNightMode ? 'Switch to Day Mode' : 'Switch to Night Glow'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: 'rgba(18, 18, 18, 0.88)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: 999,
              padding: '5px 11px',
              color: isNightMode ? '#fbbf24' : 'var(--text-primary)',
              fontSize: '0.74rem',
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
            }}
          >
            {isNightMode ? <Moon size={13} /> : <Sun size={13} />}
            <span>{isNightMode ? 'Night' : 'Day'}</span>
          </button>
        )}

        {/* Reset Camera Button */}
        <button
          type="button"
          onClick={onResetCamera}
          title="Reset Camera to Full View"
          style={{
            background: 'rgba(18, 18, 18, 0.88)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '50%',
            width: 30,
            height: 30,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-primary)',
            cursor: 'pointer',
          }}
        >
          <RotateCcw size={13} />
        </button>

        {/* Fullscreen Button */}
        <button
          type="button"
          onClick={onToggleFullscreen}
          title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
          style={{
            background: 'rgba(18, 18, 18, 0.88)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: '50%',
            width: 30,
            height: 30,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-primary)',
            cursor: 'pointer',
          }}
        >
          {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
        </button>
      </div>

      <RoomNavigator
        is3DReady={is3DReady}
        rooms={rooms}
        selectedRoomId={selectedRoomId}
        onSelectRoom={onSelectRoom}
        onResetCamera={onResetCamera}
        resetKey={`${glbUrl}:${isGenerating3D}:${viewMode}`}
      />

      {/* ── Center Crosshair for Mouse Look in Walkthrough ── */}
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

      {/* ── Bottom Controls Guide (Desktop only, minimal footprint - Only when 3D is rendered) ── */}
      {is3DReady && (
        <div
          className="desktop-only"
          style={{
            position: 'absolute',
            bottom: 8,
            left: '50%',
            transform: 'translateX(-50%)',
            alignItems: 'center',
            gap: 8,
            color: 'rgba(255, 255, 255, 0.40)',
            fontSize: '0.65rem',
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
              <span><strong style={{ color: 'rgba(255,255,255,0.70)' }}>WASD</strong> move</span>
              <span>•</span>
              <span><strong style={{ color: 'rgba(255,255,255,0.70)' }}>Left Click</strong> orbit</span>
              <span>•</span>
              <span><strong style={{ color: 'rgba(255,255,255,0.70)' }}>Right Click</strong> pan</span>
              <span>•</span>
              <span><strong style={{ color: 'rgba(255,255,255,0.70)' }}>Scroll</strong> zoom</span>
            </>
          )}
        </div>
      )}
    </>
  )
}
