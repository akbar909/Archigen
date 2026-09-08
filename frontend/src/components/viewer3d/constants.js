import * as THREE from 'three'
import {
  Bath,
  Bed,
  Briefcase,
  DoorOpen,
  Home,
  Sofa,
  UtensilsCrossed,
} from 'lucide-react'

// ── Room Type Theme Mapping ──────────────────────────────────────────
export const ROOM_THEMES = {
  living: { color: '#eab308', icon: Sofa, label: 'Living Room' },
  bed: { color: '#3b82f6', icon: Bed, label: 'Bedroom' },
  bath: { color: '#06b6d4', icon: Bath, label: 'Bathroom' },
  wash: { color: '#06b6d4', icon: Bath, label: 'Washroom' },
  kitchen: { color: '#f97316', icon: UtensilsCrossed, label: 'Kitchen' },
  dining: { color: '#a855f7', icon: UtensilsCrossed, label: 'Dining Room' },
  office: { color: '#6366f1', icon: Briefcase, label: 'Office' },
  hall: { color: '#8b5cf6', icon: DoorOpen, label: 'Hallway' },
  default: { color: '#94a3b8', icon: Home, label: 'Room' },
}

export function getRoomMeta(type = '') {
  const t = String(type).toLowerCase()
  for (const [key, meta] of Object.entries(ROOM_THEMES)) {
    if (t.includes(key)) return meta
  }
  return ROOM_THEMES.default
}

// ── Wall Surface Texture Generator ───────────────────────────────────
export function makeSurfaceTexture(pattern = 'plain', kind = 'wall') {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = 256
  const ctx = canvas.getContext('2d')

  if (pattern === 'brick') {
    ctx.fillStyle = kind === 'ceiling' ? '#efece4' : '#8b3a3a'
    ctx.fillRect(0, 0, 256, 256)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)'
    ctx.lineWidth = 2.5
    for (let y = 0; y < 16; y += 1) {
      const offset = y % 2 === 0 ? 0 : 16
      for (let x = -1; x < 9; x += 1) {
        ctx.strokeRect(x * 32 + offset, y * 16, 32, 16)
      }
    }
  } else if (pattern === 'wood_panel') {
    ctx.fillStyle = '#6b4728'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 8; i += 1) {
      ctx.fillStyle = i % 2 === 0 ? '#79512f' : '#613e21'
      ctx.fillRect(i * 32, 0, 30, 256)
    }
  } else if (pattern === 'concrete') {
    ctx.fillStyle = '#94a3b8'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 2000; i += 1) {
      const s = 140 + Math.random() * 50
      ctx.fillStyle = `rgba(${s},${s},${s},0.15)`
      ctx.fillRect(Math.random() * 256, Math.random() * 256, 1, 1)
    }
  } else {
    ctx.fillStyle = kind === 'ceiling' ? '#fafafa' : '#f4f4f0'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 800; i += 1) {
      const s = 235 + Math.random() * 20
      ctx.fillStyle = `rgba(${s},${s},${s},0.08)`
      ctx.fillRect(Math.random() * 256, Math.random() * 256, 1, 1)
    }
  }

  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(2, 2)
  texture.needsUpdate = true
  return texture
}
