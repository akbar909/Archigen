import React from 'react'
import { doorSectors } from '../../utils/wallOpenings.js'
import { distance as distance2D } from '../../utils/cadGeometry.js'

// Convert meters to formatted display string (feet or meters)
export function formatDim(meters, displayUnit = 'ft') {
  if (meters === undefined || meters === null || isNaN(meters)) return '0\''
  if (displayUnit === 'meters' || displayUnit === 'm') {
    return `${Number(meters).toFixed(1)}m`
  }
  const totalInches = Math.round(meters * 39.3701)
  const feet = Math.floor(totalInches / 12)
  const inches = totalInches % 12
  return `${feet}'-${inches}"`
}

export function getRoomColor(type, isSel) {
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
export function CadFurnitureItem({ item, scale, mapX, mapY }) {
  const cat = String(item.category || item.type || item.asset || '').toLowerCase()
  const rawX = Number(item.position?.x ?? 0)
  const rawY = Number(item.position?.y ?? item.position?.z ?? 0)
  const fw = Math.max(0.005, Number(item.dimensions?.width ?? 1.0)) * scale
  const fd = Math.max(0.005, Number(item.dimensions?.depth ?? 1.0)) * scale
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
export function CadDoorItem({ door, scale, mapX, mapY, rooms = [] }) {
  let rawX = Number(door.position?.x ?? 0)
  let rawY = Number(door.position?.y ?? 0)
  const rawZ = Number(door.position?.z ?? 0)
  if (!door.wall_id && rawY <= 1.5 && rawZ > 1.5) rawY = rawZ

  const dw = Math.max(0.05, Number(door.width || 0.9)) * scale
  const wallSide = String(door.wall_side || door.wall || 'south').toLowerCase()
  const swing = String(door.swing || 'inward_right').toLowerCase()
  const hingeOnRight = door.hinge_side ? door.hinge_side === 'right' : swing.includes('right')
  const opensOutward = door.swing_direction ? door.swing_direction === 'outward' : swing.includes('outward')
  const isGarage = door.type === 'garage_door' || door.type === 'overhead' || door.swing === 'overhead'
  const isMain = door.type === 'main_entrance' || door.id?.includes('main')

  // Room anchor lookup: snap door directly to room perimeter wall
  const targetRoom = rooms.find((r) => r.id === (door.roomId || door.room_id))
  if (targetRoom && !door.wall_id) {
    const rx = Number(targetRoom.position?.x || 0)
    const ry = Number(targetRoom.position?.y || targetRoom.position?.z || 0)
    const rw = Number(targetRoom.dimensions?.width || targetRoom.width || 4)
    const rd = Number(targetRoom.dimensions?.depth || targetRoom.length || 4)

    if (wallSide.includes('south') || wallSide.includes('front')) {
      rawY = ry
      rawX = Math.max(rx + 0.5, Math.min(rx + rw - 0.5, rawX))
    } else if (wallSide.includes('north') || wallSide.includes('back')) {
      rawY = ry + rd
      rawX = Math.max(rx + 0.5, Math.min(rx + rw - 0.5, rawX))
    } else if (wallSide.includes('west') || wallSide.includes('left')) {
      rawX = rx
      rawY = Math.max(ry + 0.5, Math.min(ry + rd - 0.5, rawY))
    } else if (wallSide.includes('east') || wallSide.includes('right')) {
      rawX = rx + rw
      rawY = Math.max(ry + 0.5, Math.min(ry + rd - 0.5, rawY))
    }
  }

  const cx = mapX(rawX)
  const cy = mapY(rawY)

  if (door.wall_id && !isGarage) {
    const vertical = ['east', 'west'].includes(wallSide), sliding = /sliding/.test(door.type || '')
    const color = isMain ? '#fbbf24' : '#38bdf8'
    return <g>
      <rect x={vertical ? cx - 5 : cx - dw / 2} y={vertical ? cy - dw / 2 : cy - 5} width={vertical ? 10 : dw} height={vertical ? dw : 10} fill="#0d1117" />
      {sliding ? <g transform={`translate(${cx} ${cy}) rotate(${vertical ? -90 : 0})`}>
        <path d={`M ${-dw / 2} -2 H 0 V 2 H ${dw / 2} M ${-dw / 2} -5 V 5 M ${dw / 2} -5 V 5`} fill="none" stroke={color} strokeWidth="2" />
        <path d={`M ${-dw / 4} -8 H ${dw / 4} l -5 -3 m 5 3 l -5 3`} fill="none" stroke={color} strokeWidth="1" />
      </g> : doorSectors({ ...door, hinge_side:door.hinge_side || (hingeOnRight ? 'right' : 'left'), swing_direction:door.swing_direction || (opensOutward ? 'outward' : 'inward') }).map((sector,index) => {
        const hinge=sector[0], closed=sector[1], opened=sector.at(-1), radius=distance2D(hinge,closed)*scale
        const cross=(closed.x-hinge.x)*(opened.y-hinge.y)-(closed.y-hinge.y)*(opened.x-hinge.x)
        return <g key={index}><line x1={mapX(hinge.x)} y1={mapY(hinge.y)} x2={mapX(opened.x)} y2={mapY(opened.y)} stroke={color} strokeWidth="2" /><path d={`M ${mapX(closed.x)} ${mapY(closed.y)} A ${radius} ${radius} 0 0 ${cross > 0 ? 0 : 1} ${mapX(opened.x)} ${mapY(opened.y)}`} fill="none" stroke={color} strokeWidth="1" strokeDasharray="4 3" opacity=".6" /></g>
      })}
    </g>
  }

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
    const hingeX = hingeOnRight ? cx + dw / 2 : cx - dw / 2
    const closedEndX = hingeOnRight ? cx - dw / 2 : cx + dw / 2
    const hingeY = cy
    const inwardDirection = isSouth ? -1 : 1
    const swingY = cy + dw * inwardDirection * (opensOutward ? -1 : 1)
    const sweepFlag = ((closedEndX - hingeX) * (swingY - hingeY)) > 0 ? 1 : 0

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
          d={`M ${closedEndX} ${cy} A ${dw} ${dw} 0 0 ${sweepFlag} ${hingeX} ${swingY}`}
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
  // Blender's canonical local +X hinge maps to architectural +Y on a
  // vertical wall, which is upward in this SVG coordinate system.
  const hingeY = hingeOnRight ? cy - dw / 2 : cy + dw / 2
  const closedEndY = hingeOnRight ? cy + dw / 2 : cy - dw / 2
  const inwardDirection = isWest ? 1 : -1
  const swingX = cx + dw * inwardDirection * (opensOutward ? -1 : 1)
  const sweepFlag = (-(closedEndY - hingeY) * (swingX - hingeX)) > 0 ? 1 : 0

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
        d={`M ${cx} ${closedEndY} A ${dw} ${dw} 0 0 ${sweepFlag} ${swingX} ${hingeY}`}
        fill="none"
        stroke="rgba(56, 189, 248, 0.45)"
        strokeWidth="1.2"
        strokeDasharray="4,3"
      />
    </g>
  )
}

// Crisp Architectural CAD Window with Wall Cutout & Glazing
export function CadWindowItem({ windowItem, scale, mapX, mapY, rooms = [] }) {
  let rawX = Number(windowItem.position?.x ?? 0)
  let rawY = Number(windowItem.position?.y ?? 0)
  const rawZ = Number(windowItem.position?.z ?? 0)
  if (!windowItem.wall_id && rawY <= 1.5 && rawZ > 1.5) rawY = rawZ

  const ww = Math.max(0.05, Number(windowItem.width || 1.4)) * scale
  const wallSide = String(windowItem.wall_side || windowItem.wall || 'south').toLowerCase()
  const isHoriz = !wallSide.includes('east') && !wallSide.includes('west') && !wallSide.includes('left') && !wallSide.includes('right')

  // Room anchor lookup: snap window directly to room exterior wall
  const targetRoom = rooms.find((r) => r.id === (windowItem.roomId || windowItem.room_id))
  if (targetRoom && !windowItem.wall_id) {
    const rx = Number(targetRoom.position?.x || 0)
    const ry = Number(targetRoom.position?.y || targetRoom.position?.z || 0)
    const rw = Number(targetRoom.dimensions?.width || targetRoom.width || 4)
    const rd = Number(targetRoom.dimensions?.depth || targetRoom.length || 4)

    if (wallSide.includes('south') || wallSide.includes('front')) {
      rawY = ry
      rawX = Math.max(rx + 0.5, Math.min(rx + rw - 0.5, rawX))
    } else if (wallSide.includes('north') || wallSide.includes('back')) {
      rawY = ry + rd
      rawX = Math.max(rx + 0.5, Math.min(rx + rw - 0.5, rawX))
    } else if (wallSide.includes('west') || wallSide.includes('left')) {
      rawX = rx
      rawY = Math.max(ry + 0.5, Math.min(ry + rd - 0.5, rawY))
    } else if (wallSide.includes('east') || wallSide.includes('right')) {
      rawX = rx + rw
      rawY = Math.max(ry + 0.5, Math.min(ry + rd - 0.5, rawY))
    }
  }

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
