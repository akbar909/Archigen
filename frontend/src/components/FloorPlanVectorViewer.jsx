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

// Convert meters to formatted display string (feet or meters)
function formatDim(meters, displayUnit = 'ft') {
  if (meters === undefined || meters === null || isNaN(meters)) return '0\''
  if (displayUnit === 'meters' || displayUnit === 'm') {
    return `${Number(meters).toFixed(1)}m`
  }
  const totalInches = Math.round(meters * 39.3701)
  const feet = Math.floor(totalInches / 12)
  const inches = totalInches % 12
  return `${feet}'-${inches}"`
}

function getRoomColor(type, isSel) {
  if (isSel) return { fill: 'rgba(59, 130, 246, 0.32)', border: '#3b82f6', text: '#93c5fd' }
  const t = String(type || '').toLowerCase()
  if (t.includes('living') || t.includes('family')) {
    return { fill: 'rgba(30, 41, 59, 0.75)', border: 'rgba(148, 163, 184, 0.4)', text: '#f1f5f9' }
  }
  if (t.includes('dining')) {
    return { fill: 'rgba(40, 45, 62, 0.75)', border: 'rgba(245, 158, 11, 0.35)', text: '#fef3c7' }
  }
  if (t.includes('bed') || t.includes('master')) {
    return { fill: 'rgba(30, 41, 59, 0.70)', border: 'rgba(148, 163, 184, 0.4)', text: '#f8fafc' }
  }
  if (t.includes('kitchen')) {
    return { fill: 'rgba(38, 48, 65, 0.75)', border: 'rgba(56, 189, 248, 0.4)', text: '#e0f2fe' }
  }
  if (t.includes('bath') || t.includes('toilet') || t.includes('powder') || t.includes('ensuite')) {
    return { fill: 'rgba(14, 116, 144, 0.22)', border: 'rgba(56, 189, 248, 0.5)', text: '#7dd3fc' }
  }
  if (t.includes('garage')) {
    return { fill: 'rgba(71, 85, 105, 0.30)', border: 'rgba(148, 163, 184, 0.45)', text: '#cbd5e1' }
  }
  if (t.includes('office') || t.includes('study')) {
    return { fill: 'rgba(35, 45, 65, 0.75)', border: 'rgba(129, 140, 248, 0.4)', text: '#e0e7ff' }
  }
  return { fill: 'rgba(30, 41, 59, 0.65)', border: 'rgba(148, 163, 184, 0.35)', text: '#f1f5f9' }
}

// Crisp Architectural CAD Furniture Symbol Component
function CadFurnitureItem({ item, scale, mapX, mapY }) {
  const cat = String(item.category || item.type || item.asset || '').toLowerCase()
  const rawX = Number(item.position?.x ?? 0)
  const rawY = Number(item.position?.y ?? item.position?.z ?? 0)
  const fw = Math.max(0.4, Number(item.dimensions?.width ?? 1.0)) * scale
  const fd = Math.max(0.4, Number(item.dimensions?.depth ?? 1.0)) * scale
  const rot = Number(item.rotation ?? item.rotation_y ?? 0)

  const cx = mapX(rawX)
  const cy = mapY(rawY)

  // 1. Bed symbol (Mattress, thick headboard, dual pillows, folded duvet line)
  if (cat.includes('bed') && !cat.includes('bedside')) {
    const isSingle = fw < 48
    return (
      <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
        {/* Mattress Base */}
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={fd} rx="3" fill="rgba(30, 41, 59, 0.85)" stroke="#64748b" strokeWidth="1.2" />
        {/* Headboard */}
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={Math.max(6, fd * 0.12)} rx="2" fill="#475569" stroke="#94a3b8" strokeWidth="1.5" />
        {/* Pillows */}
        {!isSingle ? (
          <>
            <rect x={-fw / 2 + 4} y={-fd / 2 + Math.max(8, fd * 0.15)} width={fw * 0.42} height={fd * 0.22} rx="3" fill="rgba(241, 245, 249, 0.4)" stroke="#94a3b8" strokeWidth="1" />
            <rect x={fw / 2 - 4 - fw * 0.42} y={-fd / 2 + Math.max(8, fd * 0.15)} width={fw * 0.42} height={fd * 0.22} rx="3" fill="rgba(241, 245, 249, 0.4)" stroke="#94a3b8" strokeWidth="1" />
          </>
        ) : (
          <rect x={-fw / 2 + 4} y={-fd / 2 + Math.max(6, fd * 0.15)} width={fw - 8} height={fd * 0.22} rx="3" fill="rgba(241, 245, 249, 0.4)" stroke="#94a3b8" strokeWidth="1" />
        )}
        {/* Duvet Fold Down Line */}
        <path d={`M ${-fw / 2} ${-fd / 2 + fd * 0.46} Q 0 ${-fd / 2 + fd * 0.54} ${fw / 2} ${-fd / 2 + fd * 0.46}`} fill="none" stroke="rgba(148, 163, 184, 0.6)" strokeWidth="1.2" />
      </g>
    )
  }

  // 2. Sofa / Couch / Sectional
  if (cat.includes('sofa') || cat.includes('couch')) {
    return (
      <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
        {/* Seat Base */}
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={fd} rx="4" fill="rgba(99, 102, 241, 0.2)" stroke="#6366f1" strokeWidth="1.2" />
        {/* Backrest */}
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={Math.max(6, fd * 0.28)} rx="3" fill="rgba(99, 102, 241, 0.45)" stroke="#818cf8" strokeWidth="1.2" />
        {/* Armrests */}
        <rect x={-fw / 2} y={-fd / 2} width={Math.max(5, fw * 0.13)} height={fd} rx="2" fill="rgba(99, 102, 241, 0.45)" stroke="#818cf8" strokeWidth="1" />
        <rect x={fw / 2 - Math.max(5, fw * 0.13)} y={-fd / 2} width={Math.max(5, fw * 0.13)} height={fd} rx="2" fill="rgba(99, 102, 241, 0.45)" stroke="#818cf8" strokeWidth="1" />
        {/* Cushion Dividers */}
        <line x1={-fw * 0.16} y1={-fd / 2 + fd * 0.28} x2={-fw * 0.16} y2={fd / 2} stroke="rgba(165, 180, 252, 0.45)" strokeWidth="1" />
        <line x1={fw * 0.16} y1={-fd / 2 + fd * 0.28} x2={fw * 0.16} y2={fd / 2} stroke="rgba(165, 180, 252, 0.45)" strokeWidth="1" />
      </g>
    )
  }

  // 3. Armchair / Lounge Chair
  if (cat.includes('armchair') || cat.includes('lounge_chair')) {
    return (
      <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={fd} rx="4" fill="rgba(99, 102, 241, 0.2)" stroke="#6366f1" strokeWidth="1.2" />
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={fd * 0.3} rx="3" fill="rgba(99, 102, 241, 0.45)" stroke="#818cf8" strokeWidth="1" />
        <rect x={-fw / 2} y={-fd / 2} width={fw * 0.18} height={fd} rx="2" fill="rgba(99, 102, 241, 0.45)" stroke="#818cf8" strokeWidth="1" />
        <rect x={fw / 2 - fw * 0.18} y={-fd / 2} width={fw * 0.18} height={fd} rx="2" fill="rgba(99, 102, 241, 0.45)" stroke="#818cf8" strokeWidth="1" />
      </g>
    )
  }

  // 4. Dining Table with surrounding chairs
  if (cat.includes('dining')) {
    return (
      <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={fd} rx="4" fill="rgba(245, 158, 11, 0.25)" stroke="#f59e0b" strokeWidth="1.4" />
        {/* Surrounding Chairs */}
        <rect x={-fw * 0.32} y={-fd / 2 - 8} width={fw * 0.26} height={6.5} rx="2" fill="#334155" stroke="#f59e0b" strokeWidth="0.8" />
        <rect x={fw * 0.06} y={-fd / 2 - 8} width={fw * 0.26} height={6.5} rx="2" fill="#334155" stroke="#f59e0b" strokeWidth="0.8" />
        <rect x={-fw * 0.32} y={fd / 2 + 1.5} width={fw * 0.26} height={6.5} rx="2" fill="#334155" stroke="#f59e0b" strokeWidth="0.8" />
        <rect x={fw * 0.06} y={fd / 2 + 1.5} width={fw * 0.26} height={6.5} rx="2" fill="#334155" stroke="#f59e0b" strokeWidth="0.8" />
        <rect x={-fw / 2 - 8} y={-fd * 0.18} width={6.5} height={fd * 0.36} rx="2" fill="#334155" stroke="#f59e0b" strokeWidth="0.8" />
        <rect x={fw / 2 + 1.5} y={-fd * 0.18} width={6.5} height={fd * 0.36} rx="2" fill="#334155" stroke="#f59e0b" strokeWidth="0.8" />
      </g>
    )
  }

  // 5. Toilet (Water Closet: Tank + Oval Bowl)
  if (cat.includes('toilet') || cat.includes('wc')) {
    return (
      <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
        {/* Cistern Tank */}
        <rect x={-fw * 0.44} y={-fd / 2} width={fw * 0.88} height={fd * 0.32} rx="2" fill="#1e293b" stroke="#38bdf8" strokeWidth="1.2" />
        {/* Elongated Bowl */}
        <ellipse cx={0} cy={fd * 0.12} rx={fw * 0.36} ry={fd * 0.36} fill="rgba(56, 189, 248, 0.18)" stroke="#38bdf8" strokeWidth="1.3" />
        <ellipse cx={0} cy={fd * 0.15} rx={fw * 0.24} ry={fd * 0.25} fill="none" stroke="#7dd3fc" strokeWidth="1" />
        <circle cx={0} cy={fd * 0.23} r={2.5} fill="#38bdf8" />
      </g>
    )
  }

  // 6. Sink / Vanity Basin
  if (cat.includes('sink') || cat.includes('vanity')) {
    return (
      <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
        {/* Vanity Countertop */}
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={fd} rx="2" fill="#1e293b" stroke="#38bdf8" strokeWidth="1.2" />
        {/* Oval Basin */}
        <ellipse cx={0} cy={0} rx={fw * 0.35} ry={fd * 0.32} fill="rgba(56, 189, 248, 0.18)" stroke="#38bdf8" strokeWidth="1.2" />
        <circle cx={0} cy={0} r={2} fill="#7dd3fc" />
        <circle cx={0} cy={-fd * 0.25} r={1.8} fill="#bae6fd" />
      </g>
    )
  }

  // 7. Shower / Bathtub
  if (cat.includes('shower') || cat.includes('bathtub') || cat.includes('tub')) {
    return (
      <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={fd} rx="3" fill="rgba(14, 116, 144, 0.15)" stroke="#38bdf8" strokeWidth="1.3" />
        {cat.includes('shower') ? (
          <>
            <line x1={-fw / 2} y1={-fd / 2} x2={fw / 2} y2={fd / 2} stroke="rgba(56, 189, 248, 0.35)" strokeWidth="1" strokeDasharray="3,3" />
            <circle cx={0} cy={0} r={4} fill="#0284c7" stroke="#38bdf8" strokeWidth="1" />
          </>
        ) : (
          <>
            <rect x={-fw / 2 + 4} y={-fd / 2 + 4} width={fw - 8} height={fd - 8} rx={fw * 0.22} fill="rgba(56, 189, 248, 0.22)" stroke="#7dd3fc" strokeWidth="1.2" />
            <circle cx={0} cy={fd / 2 - 9} r={2.5} fill="#38bdf8" />
          </>
        )}
      </g>
    )
  }

  // 8. Vehicle in Garage
  if (cat.includes('car') || cat.includes('vehicle')) {
    return (
      <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={fd} rx="12" fill="rgba(71, 85, 105, 0.45)" stroke="#94a3b8" strokeWidth="1.5" />
        <path d={`M ${-fw * 0.38} ${-fd * 0.16} Q 0 ${-fd * 0.25} ${fw * 0.38} ${-fd * 0.16}`} fill="none" stroke="#e2e8f0" strokeWidth="1.6" />
        <path d={`M ${-fw * 0.36} ${fd * 0.28} Q 0 ${fd * 0.35} ${fw * 0.36} ${fd * 0.28}`} fill="none" stroke="#e2e8f0" strokeWidth="1.4" />
        <rect x={-fw * 0.34} y={-fd * 0.13} width={fw * 0.68} height={fd * 0.38} rx="4" fill="rgba(30, 41, 59, 0.75)" stroke="#cbd5e1" strokeWidth="1" />
        <rect x={-fw / 2 - 3} y={-fd * 0.18} width={3.5} height={8} rx="1" fill="#cbd5e1" />
        <rect x={fw / 2 - 0.5} y={-fd * 0.18} width={3.5} height={8} rx="1" fill="#cbd5e1" />
      </g>
    )
  }

  // 9. Desk & Office Chair
  if (cat.includes('desk') || cat.includes('workstation')) {
    return (
      <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
        <rect x={-fw / 2} y={-fd / 2} width={fw} height={fd} rx="3" fill="rgba(30, 41, 59, 0.85)" stroke="#818cf8" strokeWidth="1.3" />
        <line x1={-fw * 0.35} y1={fd * 0.2} x2={fw * 0.35} y2={fd * 0.2} stroke="rgba(129, 140, 248, 0.5)" strokeWidth="1" />
        {/* Office Chair */}
        <circle cx={0} cy={fd / 2 + 8} r={6.5} fill="#1e293b" stroke="#818cf8" strokeWidth="1" />
        <path d={`M -5.5 ${fd / 2 + 12} Q 0 ${fd / 2 + 15} 5.5 ${fd / 2 + 12}`} fill="none" stroke="#818cf8" strokeWidth="1.5" />
      </g>
    )
  }

  // 10. Default / Coffee Table / Nightstand / Media Cabinet
  const isNightstand = cat.includes('nightstand') || cat.includes('bedside')
  const isCoffee = cat.includes('coffee') || cat.includes('center_table')
  const isCabinet = cat.includes('cabinet') || cat.includes('tv') || cat.includes('dresser') || cat.includes('wardrobe')

  return (
    <g transform={`translate(${cx}, ${cy}) rotate(${rot})`}>
      <rect
        x={-fw / 2}
        y={-fd / 2}
        width={fw}
        height={fd}
        rx="2"
        fill={isCoffee ? 'rgba(245, 158, 11, 0.15)' : 'rgba(51, 65, 85, 0.65)'}
        stroke={isCoffee ? '#f59e0b' : (isCabinet ? '#818cf8' : '#94a3b8')}
        strokeWidth="1.1"
      />
      {isCabinet && (
        <>
          <line x1={0} y1={-fd / 2} x2={0} y2={fd / 2} stroke="rgba(255, 255, 255, 0.2)" strokeWidth="1" />
          <circle cx={-4} cy={0} r={1.5} fill="#cbd5e1" />
          <circle cx={4} cy={0} r={1.5} fill="#cbd5e1" />
        </>
      )}
      {isNightstand && (
        <circle cx={0} cy={0} r={1.5} fill="#cbd5e1" />
      )}
    </g>
  )
}

// Crisp Architectural CAD Door with Wall Cutout & Swing Arc
function CadDoorItem({ door, scale, mapX, mapY }) {
  const rawX = Number(door.position?.x ?? 0)
  let rawY = Number(door.position?.y ?? 0)
  const rawZ = Number(door.position?.z ?? 0)
  if (rawY <= 1.5 && rawZ > 1.5) rawY = rawZ

  const dw = Math.max(0.7, Number(door.width || 0.9)) * scale
  const wallSide = String(door.wall_side || door.wall || 'south').toLowerCase()
  const isGarage = door.type === 'garage_door' || door.type === 'overhead' || door.swing === 'overhead'
  const isMain = door.type === 'main_entrance' || door.id?.includes('main')

  const cx = mapX(rawX)
  const cy = mapY(rawY)

  // Overhead Garage Roll-up Door
  if (isGarage) {
    return (
      <g>
        <rect x={cx - dw / 2} y={cy - 4} width={dw} height={8} fill="#0d1117" />
        <line x1={cx - dw / 2} y1={cy - 2} x2={cx + dw / 2} y2={cy - 2} stroke="#38bdf8" strokeWidth="2" strokeDasharray="8,4" />
        <line x1={cx - dw / 2} y1={cy + 2} x2={cx + dw / 2} y2={cy + 2} stroke="#38bdf8" strokeWidth="2" strokeDasharray="8,4" />
        <rect x={cx - dw / 2 - 2} y={cy - 5} width={4} height={10} fill="#38bdf8" />
        <rect x={cx + dw / 2 - 2} y={cy - 5} width={4} height={10} fill="#38bdf8" />
        <text x={cx} y={cy - 8} fill="#38bdf8" fontSize="8" fontWeight="bold" textAnchor="middle">GARAGE ROLL</text>
      </g>
    )
  }

  // Horizontal wall doors (south or north)
  if (wallSide.includes('south') || wallSide.includes('north') || wallSide.includes('front') || wallSide.includes('back')) {
    const isSouth = wallSide.includes('south') || wallSide.includes('front')
    const hingeX = cx - dw / 2
    const hingeY = cy
    const swingY = isSouth ? cy - dw : cy + dw
    const sweepFlag = isSouth ? 0 : 1

    return (
      <g>
        <rect x={cx - dw / 2} y={cy - 5} width={dw} height={10} fill="#0d1117" />
        <rect x={hingeX - 1.5} y={cy - 4} width={3} height={8} fill={isMain ? '#f59e0b' : '#38bdf8'} />
        <rect x={cx + dw / 2 - 1.5} y={cy - 4} width={3} height={8} fill={isMain ? '#f59e0b' : '#38bdf8'} />
        <line
          x1={hingeX}
          y1={hingeY}
          x2={hingeX}
          y2={swingY}
          stroke={isMain ? '#fbbf24' : '#38bdf8'}
          strokeWidth={isMain ? '3' : '2.2'}
        />
        <path
          d={`M ${cx + dw / 2} ${cy} A ${dw} ${dw} 0 0 ${sweepFlag} ${hingeX} ${swingY}`}
          fill="none"
          stroke={isMain ? 'rgba(251, 191, 36, 0.45)' : 'rgba(56, 189, 248, 0.45)'}
          strokeWidth="1.2"
          strokeDasharray="4,3"
        />
      </g>
    )
  }

  // Vertical wall doors (west or east)
  const isWest = wallSide.includes('west') || wallSide.includes('left')
  const hingeX = cx
  const hingeY = cy + dw / 2
  const swingX = isWest ? cx + dw : cx - dw
  const sweepFlag = isWest ? 0 : 1

  return (
    <g>
      <rect x={cx - 5} y={cy - dw / 2} width={10} height={dw} fill="#0d1117" />
      <rect x={cx - 4} y={cy - dw / 2 - 1.5} width={8} height={3} fill="#38bdf8" />
      <rect x={cx - 4} y={hingeY - 1.5} width={8} height={3} fill="#38bdf8" />
      <line
        x1={hingeX}
        y1={hingeY}
        x2={swingX}
        y2={hingeY}
        stroke="#38bdf8"
        strokeWidth="2.2"
      />
      <path
        d={`M ${cx} ${cy - dw / 2} A ${dw} ${dw} 0 0 ${sweepFlag} ${swingX} ${hingeY}`}
        fill="none"
        stroke="rgba(56, 189, 248, 0.45)"
        strokeWidth="1.2"
        strokeDasharray="4,3"
      />
    </g>
  )
}

// Crisp Architectural CAD Window with Wall Cutout & Glazing
function CadWindowItem({ windowItem, scale, mapX, mapY }) {
  const rawX = Number(windowItem.position?.x ?? 0)
  let rawY = Number(windowItem.position?.y ?? 0)
  const rawZ = Number(windowItem.position?.z ?? 0)
  if (rawY <= 1.5 && rawZ > 1.5) rawY = rawZ

  const ww = Math.max(0.8, Number(windowItem.width || 1.4)) * scale
  const wallSide = String(windowItem.wall_side || windowItem.wall || 'south').toLowerCase()
  const isHoriz = !wallSide.includes('east') && !wallSide.includes('west') && !wallSide.includes('left') && !wallSide.includes('right')

  const cx = mapX(rawX)
  const cy = mapY(rawY)

  if (isHoriz) {
    return (
      <g>
        <rect x={cx - ww / 2} y={cy - 4} width={ww} height={8} fill="#0d1117" />
        <line x1={cx - ww / 2} y1={cy - 3} x2={cx + ww / 2} y2={cy - 3} stroke="#64748b" strokeWidth="1.5" />
        <line x1={cx - ww / 2} y1={cy + 3} x2={cx + ww / 2} y2={cy + 3} stroke="#64748b" strokeWidth="1.5" />
        <line x1={cx - ww / 2} y1={cy - 1} x2={cx + ww / 2} y2={cy - 1} stroke="#38bdf8" strokeWidth="1.2" />
        <line x1={cx - ww / 2} y1={cy + 1} x2={cx + ww / 2} y2={cy + 1} stroke="#38bdf8" strokeWidth="1.2" />
        <line x1={cx - ww / 2} y1={cy - 4} x2={cx - ww / 2} y2={cy + 4} stroke="#94a3b8" strokeWidth="2" />
        <line x1={cx + ww / 2} y1={cy - 4} x2={cx + ww / 2} y2={cy + 4} stroke="#94a3b8" strokeWidth="2" />
      </g>
    )
  }

  // Vertical Wall Windows (east / west)
  return (
    <g>
      <rect x={cx - 4} y={cy - ww / 2} width={8} height={ww} fill="#0d1117" />
      <line x1={cx - 3} y1={cy - ww / 2} x2={cx - 3} y2={cy + ww / 2} stroke="#64748b" strokeWidth="1.5" />
      <line x1={cx + 3} y1={cy - ww / 2} x2={cx + 3} y2={cy + ww / 2} stroke="#64748b" strokeWidth="1.5" />
      <line x1={cx - 1} y1={cy - ww / 2} x2={cx - 1} y2={cy + ww / 2} stroke="#38bdf8" strokeWidth="1.2" />
      <line x1={cx + 1} y1={cy - ww / 2} x2={cx + 1} y2={cy + ww / 2} stroke="#38bdf8" strokeWidth="1.2" />
      <line x1={cx - 4} y1={cy - ww / 2} x2={cx + 4} y2={cy - ww / 2} stroke="#94a3b8" strokeWidth="2" />
      <line x1={cx - 4} y1={cy + ww / 2} x2={cx + 4} y2={cy + ww / 2} stroke="#94a3b8" strokeWidth="2" />
    </g>
  )
}

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
      {/* ── Top Bar: Floor Selector & Controls ── */}
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
              <span>{f.level === 0 ? 'Ground Floor' : `Floor ${f.level} (First Floor)`}</span>
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

      {/* ── Approval Gate Notice Bar (When pending user approval) ── */}
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
              <span>Building 3D Model…</span>
            ) : (
              <>
                <CheckCircle2 size={16} />
                <span>Approve & Generate 3D</span>
              </>
            )}
          </button>
        </div>
      )}

      {/* ── North Arrow Indicator (Upper Right) ── */}
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

      {/* ── Main Interactive Vector Floor Plan Canvas (SVG) ── */}
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

          {/* Driveway Connecting Road to Garage / Entrance (if present) */}
          {design?.exterior?.driveway && (
            <g>
              <rect
                x={mapX(design.exterior.driveway.position?.x || 0)}
                y={mapY((design.exterior.driveway.position?.y || 0) + (design.exterior.driveway.depth || 3.0))}
                width={(design.exterior.driveway.width || 3.8) * scale}
                height={(design.exterior.driveway.depth || 3.0) * scale}
                fill="rgba(51, 65, 85, 0.35)"
                stroke="rgba(148, 163, 184, 0.4)"
                strokeWidth="1.5"
                strokeDasharray="6,4"
              />
              <text
                x={mapX((design.exterior.driveway.position?.x || 0) + (design.exterior.driveway.width || 3.8) / 2)}
                y={mapY((design.exterior.driveway.position?.y || 0) + (design.exterior.driveway.depth || 3.0) / 2) + 4}
                fill="#94a3b8"
                fontSize="9"
                fontWeight="700"
                textAnchor="middle"
                letterSpacing="1.5"
              >
                DRIVEWAY
              </text>
            </g>
          )}

          {/* Road Frontage Indicator Banner */}
          <rect
            x={mapX(0)}
            y={mapY(0)}
            width={plotW * scale}
            height={22}
            fill="rgba(51, 65, 85, 0.45)"
            stroke="rgba(148, 163, 184, 0.35)"
          />
          <text
            x={mapX(plotW / 2)}
            y={mapY(0) + 15}
            fill="#94a3b8"
            fontSize="10"
            fontWeight="bold"
            textAnchor="middle"
            letterSpacing="2"
          >
            ROAD ACCESS ({orientation.toUpperCase()})
          </text>

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
                      {formatDim(rw, displayUnit)} × {formatDim(rd, displayUnit)}
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
