import * as THREE from 'three'

export function makeFloorTexture(pattern) {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 256
  const ctx = canvas.getContext('2d')

  ctx.fillStyle = '#b8b0a3'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  if (pattern === 'diamond_tile') {
    ctx.fillStyle = '#2A1A5E'
    ctx.fillRect(0, 0, 256, 256)
    ctx.strokeStyle = '#5A3FA0'
    ctx.lineWidth = 2
    const step = 32
    for (let x = -256; x <= 512; x += step) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x + 256, 256)
      ctx.stroke()

      ctx.beginPath()
      ctx.moveTo(x, 256)
      ctx.lineTo(x + 256, 0)
      ctx.stroke()
    }
  } else if (pattern === 'wood_planks' || pattern === 'hardwood') {
    ctx.fillStyle = '#7A4E2D'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 8; i += 1) {
      const x = i * 32
      ctx.fillStyle = i % 2 === 0 ? '#8B5E3C' : '#6F4325'
      ctx.fillRect(x, 0, 28, 256)
      ctx.fillStyle = 'rgba(255,255,255,0.06)'
      ctx.fillRect(x + 2, 0, 2, 256)
    }
  } else if (pattern === 'marble_tile' || pattern === 'marble') {
    ctx.fillStyle = '#e8e0d0'
    ctx.fillRect(0, 0, 256, 256)
    ctx.strokeStyle = 'rgba(140,130,110,0.22)'
    ctx.lineWidth = 2
    for (let i = 0; i < 10; i += 1) {
      ctx.beginPath()
      ctx.moveTo(Math.random() * 256, 0)
      for (let j = 0; j < 5; j += 1) {
        ctx.bezierCurveTo(Math.random() * 256, j * 48, Math.random() * 256, j * 48 + 24, Math.random() * 256, (j + 1) * 48)
      }
      ctx.stroke()
    }
    ctx.strokeStyle = 'rgba(255,255,255,0.4)'
    for (let i = 0; i < 4; i += 1) {
      const offset = i * 64
      ctx.strokeRect(offset, offset, 64, 64)
    }
  } else if (pattern === 'hex_tile') {
    ctx.fillStyle = '#d9e2dc'
    ctx.fillRect(0, 0, 256, 256)
    ctx.strokeStyle = '#83948a'
    ctx.lineWidth = 2
    const radius = 20
    const stepX = radius * 1.5
    const stepY = Math.sqrt(3) * radius
    for (let row = -1; row < 10; row += 1) {
      for (let col = -1; col < 10; col += 1) {
        const cx = col * stepX + (row % 2 === 0 ? 0 : stepX / 2) + 30
        const cy = row * stepY + 30
        ctx.beginPath()
        for (let i = 0; i < 6; i += 1) {
          const angle = (Math.PI / 3) * i + Math.PI / 6
          const px = cx + radius * Math.cos(angle)
          const py = cy + radius * Math.sin(angle)
          if (i === 0) {
            ctx.moveTo(px, py)
          } else {
            ctx.lineTo(px, py)
          }
        }
        ctx.closePath()
        ctx.stroke()
      }
    }
  } else if (pattern === 'checker_tile' || pattern === 'tile') {
    ctx.fillStyle = '#f4f4f0'
    ctx.fillRect(0, 0, 256, 256)
    ctx.fillStyle = '#363636'
    for (let y = 0; y < 4; y += 1) {
      for (let x = 0; x < 4; x += 1) {
        if ((x + y) % 2 === 0) {
          ctx.fillRect(x * 64, y * 64, 64, 64)
        }
      }
    }
  } else if (pattern === 'carpet') {
    ctx.fillStyle = '#6B4080'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 1800; i += 1) {
      const variation = (Math.random() - 0.5) * 30
      ctx.fillStyle = `rgba(${110 + variation},${80 + variation},${120 + variation},0.8)`
      ctx.fillRect(Math.random() * 256, Math.random() * 256, 2, 2)
    }
  } else if (pattern === 'concrete') {
    ctx.fillStyle = '#a9aeb6'
    ctx.fillRect(0, 0, 256, 256)
    for (let i = 0; i < 3200; i += 1) {
      const shade = 120 + Math.random() * 80
      ctx.fillStyle = `rgba(${shade},${shade},${shade},0.16)`
      ctx.fillRect(Math.random() * 256, Math.random() * 256, 1, 1)
    }
    ctx.strokeStyle = 'rgba(70, 70, 70, 0.16)'
    ctx.lineWidth = 2
    ctx.strokeRect(4, 4, 248, 248)
  }

  const texture = new THREE.CanvasTexture(canvas)
  texture.wrapS = THREE.RepeatWrapping
  texture.wrapT = THREE.RepeatWrapping
  texture.repeat.set(4, 4)
  texture.needsUpdate = true
  return texture
}
