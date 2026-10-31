import * as THREE from 'three'

// Remove the demonstration wall and the second, open variant from this authored scene.
// Work on a clone: GLTFLoader shares its cached source with thumbnails and other openings.
export function cleanOpeningScene(scene, asset) {
  const id = String(asset.asset_id || asset.id || asset.s3_key?.split('/').pop()?.split('.')[0] || '').toLowerCase()
  if (id !== 'standard_window_01') return scene
  const clone = scene.clone(true)
  if (id === 'standard_window_01') {
    const remove = []
    clone.traverse((node) => {
      if (/^Wall(?:[._]|\d)|^(Wing[ _]\d{2}|Frame)[._]?001$/.test(node.name)) remove.push(node)
    })
    remove.forEach((node) => node.removeFromParent())
  }
  return clone
}

export function archedWindowScene() {
  const root = new THREE.Group()
  const frame = new THREE.MeshStandardMaterial({ color: '#eee9df', roughness: 0.55 })
  const glass = new THREE.MeshPhysicalMaterial({ color: '#c5e3ec', transparent: true, opacity: 0.28,
    roughness: 0.12, side: THREE.DoubleSide, depthWrite: false })
  const wall = new THREE.MeshStandardMaterial({ color: '#e2ded6', roughness: 0.95, side: THREE.DoubleSide })
  const shape = new THREE.Shape()
  shape.moveTo(-0.5, 0); shape.lineTo(0.5, 0); shape.lineTo(0.5, 0.65)
  shape.absellipse(0, 0.65, 0.5, 0.35, 0, Math.PI, false)
  shape.lineTo(-0.5, 0)
  const inner = new THREE.Path()
  inner.moveTo(-0.44, 0.06); inner.lineTo(-0.44, 0.65)
  inner.absellipse(0, 0.65, 0.44, 0.29, Math.PI, 0, true)
  inner.lineTo(0.44, 0.06); inner.closePath()
  shape.holes.push(inner)
  const rim = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: 0.16, bevelEnabled: false, curveSegments: 48 }), frame)
  rim.position.z = -0.08; rim.name = 'Arched_frame'; root.add(rim)
  const pane = new THREE.Shape(inner.getPoints(48))
  const glazing = new THREE.Mesh(new THREE.ShapeGeometry(pane), glass)
  glazing.name = 'Arched_glass'; root.add(glazing)
  // Fill the rectangular wall aperture outside the arch, leaving the glass clear.
  const infill = new THREE.Shape()
  infill.moveTo(-0.5, 1); infill.lineTo(0.5, 1); infill.lineTo(0.5, 0.65)
  infill.absellipse(0, 0.65, 0.5, 0.35, 0, Math.PI, false); infill.closePath()
  const corners = new THREE.Mesh(new THREE.ExtrudeGeometry(infill, { depth: 0.22, bevelEnabled: false, curveSegments: 48 }), wall)
  corners.position.z = -0.11; corners.name = 'Arch_wall_infill'; root.add(corners)
  return root
}
