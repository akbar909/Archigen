import React, { useMemo, useState, useRef } from 'react'
import {
  Compass,
  Layers,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  CheckCircle2,
  Sparkles,
  Eye,
  EyeOff,
  Maximize2,
  Ruler,
  Armchair,
} from 'lucide-react'
import { CadDoorItem, CadFurnitureItem, CadWindowItem, formatDim, getRoomColor } from './floorplan/CadSymbols'
import SitePlanLayer from './floorplan/SitePlanLayer'

export default function FloorPlanVectorViewer({
  design,
  onApproveLayout,
  isApproving = false,
  onSelectRoom,
  selectedRoomId = null,
}) {
  const [activeFloorIdx, setActiveFloorIdx] = useState(0)
  const [zoom, setZoom] = useState(1.0)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [showDimensions, setShowDimensions] = useState(true)
  const [showFurniture, setShowFurniture] = useState(true)
  const [isDragging, setIsDragging] = useState(false)
  const dragStart = useRef({ x: 0, y: 0 })

  // Extract structured floors or construct fallback from top-level rooms
  const floors = useMemo(() => {
    if (Array.isArray(design?.floors) && design.floors.length > 0) {
      return design.floors
    }
    const rooms = Array.isArray(design?.rooms) ? design.rooms : []
    return [
      {
        id: 'ground_floor',
        level: 0,
        elevation: 0,
        floor_height: 3.0,
        rooms: rooms,
        walls: Array.isArray(design?.walls) ? design.walls : [],
        doors: Array.isArray(design?.doors) ? design.doors : [],
        windows: Array.isArray(design?.windows) ? design.windows : [],
        furniture: Array.isArray(design?.furniture) ? design.furniture : [],
        stairs: [],
      },
    ]
  }, [design])

  const activeFloor = floors[activeFloorIdx] || floors[0] || {}
  const rooms = activeFloor.rooms || []
  const walls = activeFloor.walls || design?.walls || []
  const doors = activeFloor.doors || []
  const windows = activeFloor.windows || []
  const furniture = activeFloor.furniture || []
  const stairs = activeFloor.stairs || []
  const isGroundFloor = Number(activeFloor.level || 0) === 0
  const floorNames = ['Ground Floor', 'First Floor', 'Second Floor', 'Third Floor']

  // Unit & Orientation settings
  const displayUnit = design?.project?.display_unit || design?.project?.unit || 'ft'
  const orientation = design?.project?.orientation || design?.site?.orientation || 'south'

  // Calculate SVG ViewBox based on plot & building
  const site = design?.site || {}
  const plot = site.plot || {}
  const plotW = Number(plot.width) || 14.0
  const plotD = Number(plot.depth) || 18.0

  // Margins in meters
  const margin = 2.0
  const totalSvgW = plotW + margin * 2
  const totalSvgD = plotD + margin * 2

  // SVG viewBox
  const viewBox = `0 0 ${totalSvgW * 40} ${totalSvgD * 40}`
  const scale = 40 // 40 SVG units per meter

  // Helper coordinate mappers
  const mapX = (x) => (margin + Number(x || 0)) * scale
  const mapY = (y) => (margin + (plotD - Number(y || 0))) * scale

  // North arrow rotation angle
  const northRotation = {
    north: 0,
    east: 90,
    south: 180,
    west: 270,
  }[orientation] || 180

  const handleMouseDown = (e) => {
    if (e.button !== 0) return
    setIsDragging(true)
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }
  }

  const handleMouseMove = (e) => {
    if (!isDragging) return
    setPan({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    })
  }

  const handleMouseUp = () => setIsDragging(false)

  const isApproved = Boolean(design?.layout_approved || design?.approved_at)

  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        background: '#0a0e17',
        color: '#e6edf3',
        overflow: 'hidden',
        userSelect: 'none',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Ã¢â€â‚¬Ã¢â€â‚¬ Top Bar: Floor Selector & Controls Ã¢â€â‚¬Ã¢â€â‚¬ */}
      <div
        style={{
          position: 'absolute',
          top: 56,
          left: 14,
          right: 14,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          zIndex: 10,
          pointerEvents: 'none',
          flexWrap: 'wrap',
          gap: 10,
        }}
      >
        {/* Floor Level Switcher */}
        <div
          style={{
            display: 'flex',
            gap: 4,
            background: 'rgba(15, 23, 42, 0.92)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: 999,
            padding: 4,
            pointerEvents: 'auto',
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          }}
        >
          {floors.map((f, idx) => (
            <button
              key={f.id || idx}
              type="button"
              onClick={() => setActiveFloorIdx(idx)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 14px',
                borderRadius: 999,
                border: 'none',
                background: activeFloorIdx === idx ? 'var(--accent, #3b82f6)' : 'transparent',
                color: activeFloorIdx === idx ? '#ffffff' : '#94a3b8',
                fontSize: '0.80rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <Layers size={13} />
              <span>{f.level === 0 ? 'Ground Floor' : `Floor ${f.level} (${floorNames[f.level] || `Level ${f.level}`})`}</span>
            </button>
          ))}
        </div>

        {/* View Options & Zoom */}
        <div
          style={{
            display: 'flex',
            gap: 6,
            background: 'rgba(15, 23, 42, 0.92)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: 999,
            padding: 4,
            pointerEvents: 'auto',
            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
          }}
        >
          <button
            type="button"
            onClick={() => setShowDimensions(!showDimensions)}
            title="Toggle Dimensions"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '6px 10px',
              borderRadius: 999,
              border: 'none',
              background: showDimensions ? 'rgba(59, 130, 246, 0.25)' : 'transparent',
              color: showDimensions ? '#60a5fa' : '#94a3b8',
              cursor: 'pointer',
              fontSize: '0.75rem',
            }}
          >
            <Ruler size={14} />
            <span>Dims</span>
          </button>

          <button
            type="button"
            onClick={() => setShowFurniture(!showFurniture)}
            title="Toggle Furniture"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              padding: '6px 10px',
              borderRadius: 999,
              border: 'none',
              background: showFurniture ? 'rgba(59, 130, 246, 0.25)' : 'transparent',
              color: showFurniture ? '#60a5fa' : '#94a3b8',
              cursor: 'pointer',
              fontSize: '0.75rem',
            }}
          >
            <Armchair size={14} />
            <span>Furniture</span>
          </button>

          <div style={{ width: 1, height: 18, background: 'rgba(255,255,255,0.15)', alignSelf: 'center' }} />

          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(2.5, z + 0.15))}
            style={{ background: 'transparent', border: 'none', color: '#cbd5e1', padding: '6px 8px', cursor: 'pointer' }}
            title="Zoom In"
          >
            <ZoomIn size={14} />
          </button>

          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.6, z - 0.15))}
            style={{ background: 'transparent', border: 'none', color: '#cbd5e1', padding: '6px 8px', cursor: 'pointer' }}
            title="Zoom Out"
          >
            <ZoomOut size={14} />
          </button>

          <button
            type="button"
            onClick={() => {
              setZoom(1.0)
              setPan({ x: 0, y: 0 })
            }}
            style={{ background: 'transparent', border: 'none', color: '#cbd5e1', padding: '6px 8px', cursor: 'pointer' }}
            title="Reset View"
          >
            <RotateCcw size={14} />
          </button>
        </div>
      </div>

      {/* Ã¢â€â‚¬Ã¢â€â‚¬ Approval Gate Notice Bar (When pending user approval) Ã¢â€â‚¬Ã¢â€â‚¬ */}
      {!isApproved && (
        <div
          style={{
            position: 'absolute',
            bottom: 20,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 25,
            background: 'rgba(15, 23, 42, 0.95)',
            border: '1px solid rgba(59, 130, 246, 0.45)',
            backdropFilter: 'blur(20px)',
            borderRadius: 14,
            padding: '12px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            boxShadow: '0 12px 40px rgba(0,0,0,0.65)',
            maxWidth: '90%',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.86rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#3b82f6', display: 'inline-block' }} />
              2D Floor Plan Ready for Review
            </span>
            <span style={{ fontSize: '0.74rem', color: '#94a3b8' }}>
              Inspect dimensions, room zoning, and doors. Click to approve and build high-detail 3D model.
            </span>
          </div>

          <button
            type="button"
            onClick={onApproveLayout}
            disabled={isApproving}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 18px',
              borderRadius: 8,
              border: 'none',
              background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
              color: '#ffffff',
              fontSize: '0.82rem',
              fontWeight: 700,
              cursor: isApproving ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 14px rgba(37, 99, 235, 0.4)',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
          >
            {isApproving ? (
              <span>Building 3D ModelÃ¢â‚¬Â¦</span>
            ) : (
              <>
                <CheckCircle2 size={16} />
                <span>Approve & Generate 3D</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* Ã¢â€â‚¬Ã¢â€â‚¬ North Arrow Indicator (Upper Right) Ã¢â€â‚¬Ã¢â€â‚¬ */}
      <div
        style={{
          position: 'absolute',
          top: 110,
          right: 24,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          zIndex: 15,
          opacity: 0.9,
          pointerEvents: 'none',
        }}
      >
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: '50%',
            background: 'rgba(15, 23, 42, 0.90)',
            border: '1px solid rgba(255, 255, 255, 0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transform: `rotate(${northRotation}deg)`,
            transition: 'transform 0.4s ease',
            boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
          }}
        >
          <Compass size={22} color="#f43f5e" />
        </div>
        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: '#f43f5e', marginTop: 2 }}>N</span>
      </div>

      {/* Ã¢â€â‚¬Ã¢â€â‚¬ Main Interactive Vector Floor Plan Canvas (SVG) Ã¢â€â‚¬Ã¢â€â‚¬ */}
      <div
        style={{
          flex: 1,
          width: '100%',
          height: '100%',
          cursor: isDragging ? 'grabbing' : 'grab',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        onMouseDown={handleMouseDown}
      >
        <svg
          viewBox={viewBox}
          style={{
            width: '100%',
            height: '100%',
            maxHeight: '92vh',
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: 'center center',
            transition: isDragging ? 'none' : 'transform 0.1s ease-out',
          }}
        >
          <defs>
            {/* Fine architectural CAD grid */}
            <pattern id="cadGrid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
            </pattern>
            {/* Diagonal Hatch pattern */}
            <pattern id="garageHatch" width="10" height="10" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="10" stroke="rgba(255,255,255,0.06)" strokeWidth="1.2" />
            </pattern>
          </defs>

          {/* Background Grid */}
          <rect width="100%" height="100%" fill="url(#cadGrid)" />

          {/* Plot Boundary (Dashed red line) */}
          <rect
            x={mapX(0)}
            y={mapY(plotD)}
            width={plotW * scale}
            height={plotD * scale}
            fill="rgba(15, 23, 42, 0.40)"
            stroke="rgba(244, 63, 94, 0.45)"
            strokeWidth="2"
            strokeDasharray="8,6"
          />

          <SitePlanLayer
            design={design}
            isGroundFloor={isGroundFloor}
            mapX={mapX}
            mapY={mapY}
            orientation={orientation}
            plotW={plotW}
            scale={scale}
          />

          {/* Rooms Rendering: Floor fills and Space Badges */}
          {rooms.map((r, idx) => {
            const rx = Number(r.position?.x || 0)
            const ry = Number(r.position?.y || r.position?.z || 0)
            const rw = Number(r.dimensions?.width || r.width || 4)
            const rd = Number(r.dimensions?.depth || r.length || 4)
            const isSel = selectedRoomId === r.id

            const svgX = mapX(rx)
            const svgY = mapY(ry + rd)
            const svgW = rw * scale
            const svgD = rd * scale

            const styling = getRoomColor(r.type || r.name, isSel)
            const isGarage = String(r.type || '').toLowerCase().includes('garage')

            return (
              <g key={r.id || idx} onClick={() => onSelectRoom && onSelectRoom(r.id)} style={{ cursor: 'pointer' }}>
                {/* Room Floor Fill */}
                <rect
                  x={svgX}
                  y={svgY}
                  width={svgW}
                  height={svgD}
                  fill={isGarage ? 'url(#garageHatch)' : styling.fill}
                  stroke={styling.border}
                  strokeWidth={isSel ? 2.5 : 1}
                />
                {isGarage && (
                  <rect
                    x={svgX}
                    y={svgY}
                    width={svgW}
                    height={svgD}
                    fill="rgba(51, 65, 85, 0.2)"
                  />
                )}

                {/* Room Name */}
                <text
                  x={svgX + svgW / 2}
                  y={svgY + svgD / 2 - (showDimensions ? 7 : 0)}
                  fill={isSel ? '#60a5fa' : styling.text}
                  fontSize="11.5"
                  fontWeight="700"
                  textAnchor="middle"
                  letterSpacing="0.5"
                >
                  {(r.name || r.type || `Room ${idx + 1}`).toUpperCase()}
                </text>

                {/* Dimension & Area Pill Tag */}
                {showDimensions && (
                  <g>
                    <rect
                      x={svgX + svgW / 2 - 40}
                      y={svgY + svgD / 2 + 4}
                      width={80}
                      height={16}
                      rx="4"
                      fill="rgba(15, 23, 42, 0.85)"
                      stroke="rgba(255, 255, 255, 0.12)"
                      strokeWidth="0.8"
                    />
                    <text
                      x={svgX + svgW / 2}
                      y={svgY + svgD / 2 + 15}
                      fill="#cbd5e1"
                      fontSize="9"
                      fontWeight="600"
                      textAnchor="middle"
                    >
                      {formatDim(rw, displayUnit)} Ãƒâ€” {formatDim(rd, displayUnit)}
                    </text>
                  </g>
                )}
              </g>
            )
          })}

          {/* Shared Wall Network */}
          {walls.length > 0 ? (
            walls.map((w, idx) => {
              const isExt = w.type === 'exterior'
              const x1 = mapX(w.start?.x ?? 0)
              const y1 = mapY(w.start?.y ?? 0)
              const x2 = mapX(w.end?.x ?? 0)
              const y2 = mapY(w.end?.y ?? 0)
              const strokeWidth = isExt ? 6.5 : 4.0

              return (
                <g key={w.id || idx}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={isExt ? '#0f172a' : '#1e293b'}
                    strokeWidth={strokeWidth}
                    strokeLinecap="square"
                  />
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={isExt ? '#475569' : '#64748b'}
                    strokeWidth={isExt ? 1.8 : 1.2}
                    strokeLinecap="square"
                  />
                </g>
              )
            })
          ) : (
            /* Fallback wall outline per room */
            rooms.map((r, idx) => {
              const rx = Number(r.position?.x || 0)
              const ry = Number(r.position?.y || r.position?.z || 0)
              const rw = Number(r.dimensions?.width || r.width || 4)
              const rd = Number(r.dimensions?.depth || r.length || 4)
              return (
                <rect
                  key={r.id || idx}
                  x={mapX(rx)}
                  y={mapY(ry + rd)}
                  width={rw * scale}
                  height={rd * scale}
                  fill="none"
                  stroke="#1e293b"
                  strokeWidth="6"
                />
              )
            })
          )}

          {/* Doors with Wall Cutouts & CAD Swing Arcs */}
          {doors.map((d, idx) => (
            <CadDoorItem
              key={d.id || idx}
              door={d}
              scale={scale}
              mapX={mapX}
              mapY={mapY}
              rooms={rooms}
            />
          ))}

          {/* Windows with Cutouts & Double Glazing Lines */}
          {windows.map((w, idx) => (
            <CadWindowItem
              key={w.id || idx}
              windowItem={w}
              scale={scale}
              mapX={mapX}
              mapY={mapY}
              rooms={rooms}
            />
          ))}

          {/* Staircase Steps Indicator */}
          {stairs.map((s, idx) => {
            const sx = Number(s.position?.x || 0)
            const sy = Number(s.position?.y || 0)
            const sw = Number(s.dimensions?.width || 1.1)
            const sd = Number(s.dimensions?.depth || 2.8)
            const svgX = mapX(sx)
            const svgY = mapY(sy + sd)
            const svgW = sw * scale
            const svgD = sd * scale
            const stepsCount = 14

            return (
              <g key={s.id || idx}>
                <rect
                  x={svgX}
                  y={svgY}
                  width={svgW}
                  height={svgD}
                  fill="rgba(15, 23, 42, 0.92)"
                  stroke="#f59e0b"
                  strokeWidth="1.5"
                />
                {Array.from({ length: stepsCount }).map((_, stepI) => (
                  <line
                    key={stepI}
                    x1={svgX}
                    y1={svgY + (stepI * svgD) / stepsCount}
                    x2={svgX + svgW}
                    y2={svgY + (stepI * svgD) / stepsCount}
                    stroke="rgba(245, 158, 11, 0.45)"
                    strokeWidth="1"
                  />
                ))}
                {/* Directional Flow Arrow */}
                <line
                  x1={svgX + svgW / 2}
                  y1={svgY + svgD - 6}
                  x2={svgX + svgW / 2}
                  y2={svgY + 8}
                  stroke="#f59e0b"
                  strokeWidth="1.5"
                />
                <polygon
                  points={`${svgX + svgW / 2 - 4},${svgY + 12} ${svgX + svgW / 2 + 4},${svgY + 12} ${svgX + svgW / 2},${svgY + 4}`}
                  fill="#f59e0b"
                />
                <text
                  x={svgX + svgW / 2}
                  y={svgY + svgD / 2}
                  fill="#f59e0b"
                  fontSize="8.5"
                  fontWeight="bold"
                  textAnchor="middle"
                >
                  UP
                </text>
              </g>
            )
          })}

          {/* Architectural CAD Furniture Symbols */}
          {showFurniture &&
            furniture.map((f, idx) => (
              <CadFurnitureItem
                key={f.id || idx}
                item={f}
                scale={scale}
                mapX={mapX}
                mapY={mapY}
              />
            ))}
        </svg>
      </div>
    </div>
  )
}
