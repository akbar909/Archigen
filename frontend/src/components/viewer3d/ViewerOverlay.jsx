import { useState, useRef, useEffect } from 'react'
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
  ChevronUp,
  ChevronDown,
  Check,
} from 'lucide-react'
import { getRoomMeta } from './constants'

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
  const [isRoomDrawerOpen, setIsRoomDrawerOpen] = useState(false)
  const drawerRef = useRef(null)

  // Close room drawer when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (drawerRef.current && !drawerRef.current.contains(e.target)) {
        setIsRoomDrawerOpen(false)
      }
    }
    if (isRoomDrawerOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isRoomDrawerOpen])

  // Automatically close room drawer when generating 3D or switching view modes
  useEffect(() => {
    setIsRoomDrawerOpen(false)
  }, [glbUrl, isGenerating3D, viewMode])

  const is3DReady = Boolean(glbUrl && isModelRendered && !isGenerating3D)
  const is3DLoading = Boolean(glbUrl && !isModelRendered && !isGenerating3D)
  const is2DVectorMode = viewMode === 'plan' && planSubMode === 'vector'

  // Navigation Camera Modes (3D modes only available or highlighted once 3D exists)
  const viewModes = [
    { id: 'dollhouse', icon: Home, label: 'Dollhouse 3D', requires3D: true },
    { id: 'walkthrough', icon: Footprints, label: 'Walkthrough', requires3D: true },
    { id: 'plan', icon: Grid3X3, label: 'Floor Plan', requires3D: false },
    { id: 'front', icon: Building, label: 'Front Exterior', requires3D: true },
    { id: 'back', icon: Building2, label: 'Back Exterior', requires3D: true },
  ]

  const activeRoom = rooms.find((r) => r.id === selectedRoomId)
  const currentRoomLabel = selectedRoomId === 'overview' || !selectedRoomId
    ? 'Overview'
    : (activeRoom?.name || activeRoom?.type || 'Room')

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
          zIndex: 10,
          flexWrap: 'wrap',
          maxWidth: 'calc(100% - 150px)',
          pointerEvents: 'auto',
        }}
      >
        {/* Navigation Mode Bar: Only displayed once 3D model is rendered in Three.js scene */}
        {is3DReady && (
          <div
            style={{
              display: 'flex',
              gap: 2,
              background: 'rgba(18, 18, 18, 0.92)',
              backdropFilter: 'blur(16px)',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: 999,
              padding: 3,
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              overflowX: 'auto',
              maxWidth: '100%',
            }}
          >
            {viewModes.map((mode) => {
              const IconComp = mode.icon
              const isActive = viewMode === mode.id
              return (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => onModeChange(mode.id)}
                  title={mode.label}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '5px 10px',
                    borderRadius: 999,
                    border: 'none',
                    background: isActive ? 'var(--accent)' : 'transparent',
                    color: isActive ? '#ffffff' : 'var(--text-secondary)',
                    fontSize: '0.74rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <IconComp size={13} />
                  <span>{mode.label}</span>
                </button>
              )
            })}
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
          </div>
        )}

        {/* Layer Visibility: Roof Toggle (ONLY visible once 3D model is actually rendered) */}
        {is3DReady && viewMode !== 'plan' && onToggleRoof && (
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
            {floors.map((fl, idx) => {
              const lvl = fl.level !== undefined ? fl.level : idx
              const isActive = activeFloorLevel === lvl
              const label = lvl === 0 ? 'Ground (L0)' : `Floor ${lvl} (L${lvl})`
              return (
                <button
                  key={lvl}
                  type="button"
                  onClick={() => onChangeFloorLevel(lvl)}
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

        {/* Cloud Blender 3D Model Status Indicator & Trigger */}
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
              if (!isGenerating3D && !is3DLoading && onRegenerate3D) {
                onRegenerate3D()
              }
            }}
            disabled={isGenerating3D || is3DLoading}
            title={
              is3DReady
                ? 'Photorealistic Cloud Blender 3D Model is rendered (Click to regenerate)'
                : isGenerating3D
                ? 'Blender 3D is synthesizing in cloud...'
                : is3DLoading
                ? 'Rendering 3D model into viewport...'
                : 'Click to synthesize Photorealistic Cloud Blender 3D Model!'
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
            ) : is3DReady ? (
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
                HD ✓
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
        </div>
      </div>

      {/* ── Top Right: Tools + Day/Night + Stats ── */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          zIndex: 10,
        }}
      >
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

      {/* ── Bottom Room Navigator: Responsive Lift-Up / Dropdown Menu (Only when 3D is rendered) ── */}
      {is3DReady && rooms.length > 0 && (
        <div
          ref={drawerRef}
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
