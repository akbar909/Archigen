import * as THREE from 'three'

function pbr(color, roughness = 0.7, metalness = 0.05) {
	return new THREE.MeshStandardMaterial({ color, roughness, metalness })
}

function addBox(group, w, h, d, material, x = 0, y = 0, z = 0) {
	const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material)
	mesh.position.set(x, y, z)
	mesh.castShadow = true
	mesh.receiveShadow = true
	group.add(mesh)
	return mesh
}

function addCylinder(group, radiusTop, radiusBottom, height, material, x = 0, y = 0, z = 0, radialSegments = 12) {
	const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radiusTop, radiusBottom, height, radialSegments), material)
	mesh.position.set(x, y, z)
	mesh.castShadow = true
	mesh.receiveShadow = true
	group.add(mesh)
	return mesh
}

function addSphere(group, radius, material, x = 0, y = 0, z = 0, widthSegments = 12, heightSegments = 12) {
	const mesh = new THREE.Mesh(new THREE.SphereGeometry(radius, widthSegments, heightSegments), material)
	mesh.position.set(x, y, z)
	mesh.castShadow = true
	mesh.receiveShadow = true
	group.add(mesh)
	return mesh
}

function buildSeat(group, dims, material) {
	addBox(group, dims.w, dims.h * 0.38, dims.d, material, 0, dims.h * 0.19, 0)
}

function buildSimpleBack(group, dims, material, backScale = 0.55) {
	addBox(group, dims.w, dims.h * backScale, dims.d * 0.18, material, 0, dims.h * (0.38 + backScale / 2), -dims.d * 0.41)
}

function buildSofa(item) {
	const dims = item.dimensions || { w: 2.2, h: 0.85, d: 0.9 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#4A6FA5', item.roughness ?? 0.8, item.metalness ?? 0)
	const baseMat = pbr('#2d2d33', 0.8, 0.02)
	addBox(group, dims.w * 0.98, dims.h * 0.08, dims.d * 0.95, baseMat, 0, dims.h * 0.04, 0)
	buildSeat(group, dims, mat)
	buildSimpleBack(group, dims, mat, 0.58)
	addBox(group, dims.w * 0.08, dims.h * 0.58, dims.d * 0.92, mat, -dims.w * 0.46, dims.h * 0.29, 0)
	addBox(group, dims.w * 0.08, dims.h * 0.58, dims.d * 0.92, mat, dims.w * 0.46, dims.h * 0.29, 0)
	return group
}

function buildArmchair(item) {
	const dims = item.dimensions || { w: 1.0, h: 0.9, d: 0.95 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#8C6F5A', item.roughness ?? 0.82, item.metalness ?? 0)
	addBox(group, dims.w * 0.92, dims.h * 0.1, dims.d * 0.92, mat, 0, dims.h * 0.05, 0)
	buildSeat(group, dims, mat)
	buildSimpleBack(group, dims, mat, 0.52)
	addBox(group, dims.w * 0.12, dims.h * 0.52, dims.d * 0.9, mat, -dims.w * 0.38, dims.h * 0.26, 0)
	addBox(group, dims.w * 0.12, dims.h * 0.52, dims.d * 0.9, mat, dims.w * 0.38, dims.h * 0.26, 0)
	return group
}

function buildCoffeeTable(item) {
	const dims = item.dimensions || { w: 1.2, h: 0.45, d: 0.6 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#C8A96A', item.roughness ?? 0.35, item.metalness ?? 0.08)
	addBox(group, dims.w, Math.max(dims.h * 0.12, 0.03), dims.d, mat, 0, dims.h, 0)
	const legHeight = Math.max(dims.h * 0.88, 0.2)
	const legX = dims.w * 0.42
	const legZ = dims.d * 0.42
	;[-1, 1].forEach((sx) => {
		;[-1, 1].forEach((sz) => {
			addBox(group, 0.05, legHeight, 0.05, mat, sx * legX, legHeight / 2, sz * legZ)
		})
	})
	return group
}

function buildBed(item) {
	const dims = item.dimensions || { w: 2.0, h: 0.7, d: 1.6 }
	const group = new THREE.Group()
	const frameMat = pbr('#3D2B10', 0.65, 0.05)
	const mattressMat = pbr(item.color || '#E1D7CB', item.roughness ?? 0.95, item.metalness ?? 0)
	addBox(group, dims.w, dims.h * 0.32, dims.d, frameMat, 0, dims.h * 0.16, 0)
	addBox(group, dims.w * 0.92, dims.h * 0.28, dims.d * 0.92, mattressMat, 0, dims.h * 0.44, 0)
	addBox(group, dims.w, dims.h * 0.8, dims.d * 0.12, frameMat, 0, dims.h * 0.46, -dims.d * 0.44)
	return group
}

function buildWardrobe(item) {
	const dims = item.dimensions || { w: 1.4, h: 2.1, d: 0.6 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#7C5C3D', item.roughness ?? 0.72, item.metalness ?? 0.03)
	addBox(group, dims.w, dims.h, dims.d, mat, 0, dims.h / 2, 0)
	addBox(group, 0.02, dims.h, dims.d * 0.98, pbr('#1A1A1A', 0.35, 0.2), 0, dims.h / 2, dims.d / 2 - 0.01)
	return group
}

function buildDresser(item) {
	const dims = item.dimensions || { w: 1.2, h: 0.9, d: 0.5 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#8A6143', item.roughness ?? 0.7, item.metalness ?? 0.04)
	addBox(group, dims.w, dims.h, dims.d, mat, 0, dims.h / 2, 0)
	const drawerHeight = dims.h / 4
	for (let i = 0; i < 3; i += 1) {
		addBox(group, dims.w * 0.92, drawerHeight * 0.1, dims.d * 0.98, pbr('#5a3f2a', 0.6, 0.03), 0, drawerHeight * (i + 0.5), dims.d / 2 - 0.01)
	}
	return group
}

function buildDesk(item) {
	const dims = item.dimensions || { w: 1.4, h: 0.75, d: 0.7 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#946B3F', item.roughness ?? 0.55, item.metalness ?? 0.04)
	addBox(group, dims.w, Math.max(dims.h * 0.08, 0.03), dims.d, mat, 0, dims.h, 0)
	const legHeight = Math.max(dims.h * 0.92, 0.3)
	const legX = dims.w * 0.45
	const legZ = dims.d * 0.42
	;[-1, 1].forEach((sx) => {
		;[-1, 1].forEach((sz) => {
			addBox(group, 0.06, legHeight, 0.06, mat, sx * legX, legHeight / 2, sz * legZ)
		})
	})
	return group
}

function buildBookshelf(item) {
	const dims = item.dimensions || { w: 1.0, h: 1.8, d: 0.35 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#7B5A3B', item.roughness ?? 0.65, item.metalness ?? 0.03)
	addBox(group, dims.w, dims.h, dims.d, mat, 0, dims.h / 2, 0)
	for (let i = 1; i < 4; i += 1) {
		addBox(group, dims.w * 0.94, 0.03, dims.d * 0.96, pbr('#5a4028', 0.7, 0.02), 0, (dims.h / 4) * i, 0)
	}
	return group
}

function buildTvUnit(item) {
	const dims = item.dimensions || { w: 1.8, h: 0.5, d: 0.4 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#3D2B10', item.roughness ?? 0.6, item.metalness ?? 0.05)
	addBox(group, dims.w, dims.h, dims.d, mat, 0, dims.h / 2, 0)
	addBox(group, dims.w * 0.9, dims.h * 2.1, 0.05, pbr('#111111', 0.25, 0.85), 0, dims.h + dims.h * 0.95, 0)
	return group
}

function buildFloorLamp(item) {
	const dims = item.dimensions || { w: 0.3, h: 1.6, d: 0.3 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#B8960C', item.roughness ?? 0.35, item.metalness ?? 0.8)
	addBox(group, 0.06, dims.h * 0.82, 0.06, mat, 0, dims.h * 0.41, 0)
	addSphere(group, 0.16, pbr('#F5DEB3', 0.92, 0), 0, dims.h * 0.94, 0)
	return group
}

function buildPendantLight(item) {
	const dims = item.dimensions || { w: 0.35, h: 0.8, d: 0.35 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#D4A017', item.roughness ?? 0.3, item.metalness ?? 0.9)
	addBox(group, 0.03, Math.max(dims.h * 0.55, 0.2), 0.03, mat, 0, dims.h * 0.72, 0)
	addSphere(group, Math.max(dims.w * 0.34, 0.12), pbr('#FFF2CC', 0.9, 0), 0, dims.h * 0.32, 0)
	return group
}

function buildRug(item) {
	const dims = item.dimensions || { w: 3.0, h: 0.02, d: 2.0 }
	const group = new THREE.Group()
	addBox(group, dims.w, 0.02, dims.d, pbr(item.color || '#8B4513', item.roughness ?? 0.95, item.metalness ?? 0), 0, 0.01, 0)
	return group
}

function buildPlant(item) {
	const group = new THREE.Group()
	addCylinder(group, 0.18, 0.22, 0.35, pbr('#C47C40', 0.72, 0.08), 0, 0.18, 0, 10)
	addSphere(group, 0.3, pbr(item.color || '#2D5A27', item.roughness ?? 0.88, item.metalness ?? 0), 0.02, 0.68, 0)
	return group
}

function buildDiningTable(item) {
	const dims = item.dimensions || { w: 1.8, h: 0.75, d: 0.9 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#9B734A', item.roughness ?? 0.45, item.metalness ?? 0.03)
	addBox(group, dims.w, dims.h * 0.1, dims.d, mat, 0, dims.h, 0)
	const legHeight = Math.max(dims.h * 0.9, 0.35)
	const legX = dims.w * 0.42
	const legZ = dims.d * 0.4
	;[-1, 1].forEach((sx) => {
		;[-1, 1].forEach((sz) => {
			addBox(group, 0.06, legHeight, 0.06, mat, sx * legX, legHeight / 2, sz * legZ)
		})
	})
	return group
}

function buildDiningChair(item) {
	const dims = item.dimensions || { w: 0.45, h: 0.95, d: 0.45 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#8F6847', item.roughness ?? 0.58, item.metalness ?? 0.03)
	addBox(group, dims.w * 0.9, dims.h * 0.16, dims.d * 0.92, mat, 0, dims.h * 0.18, 0)
	addBox(group, dims.w * 0.9, dims.h * 0.48, dims.d * 0.14, mat, 0, dims.h * 0.5, -dims.d * 0.34)
	addBox(group, 0.04, dims.h * 0.8, 0.04, mat, -dims.w * 0.35, dims.h * 0.4, -dims.d * 0.35)
	addBox(group, 0.04, dims.h * 0.8, 0.04, mat, dims.w * 0.35, dims.h * 0.4, -dims.d * 0.35)
	addBox(group, 0.04, dims.h * 0.8, 0.04, mat, -dims.w * 0.35, dims.h * 0.4, dims.d * 0.35)
	addBox(group, 0.04, dims.h * 0.8, 0.04, mat, dims.w * 0.35, dims.h * 0.4, dims.d * 0.35)
	return group
}

function buildKitchenCounter(item) {
	const dims = item.dimensions || { w: 2.2, h: 0.9, d: 0.65 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#B9A68B', item.roughness ?? 0.6, item.metalness ?? 0.05)
	addBox(group, dims.w, dims.h, dims.d, mat, 0, dims.h / 2, 0)
	addBox(group, dims.w * 0.98, 0.06, dims.d * 0.98, pbr('#D6D6D6', 0.4, 0.1), 0, dims.h + 0.03, 0)
	return group
}

function buildKitchenIsland(item) {
	const dims = item.dimensions || { w: 2.0, h: 0.9, d: 1.0 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#A88F73', item.roughness ?? 0.55, item.metalness ?? 0.05)
	addBox(group, dims.w, dims.h, dims.d, mat, 0, dims.h / 2, 0)
	addBox(group, dims.w * 0.98, 0.06, dims.d * 0.98, pbr('#CFCFCF', 0.38, 0.12), 0, dims.h + 0.03, 0)
	return group
}

function buildRefrigerator(item) {
	const dims = item.dimensions || { w: 0.85, h: 2.0, d: 0.75 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#DCE3EA', item.roughness ?? 0.3, item.metalness ?? 0.18)
	addBox(group, dims.w, dims.h, dims.d, mat, 0, dims.h / 2, 0)
	addBox(group, 0.02, dims.h, dims.d * 0.96, pbr('#A8B0B8', 0.2, 0.6), 0, dims.h / 2, dims.d / 2 - 0.01)
	return group
}

function buildOven(item) {
	const dims = item.dimensions || { w: 0.75, h: 0.9, d: 0.65 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#E2E5E8', item.roughness ?? 0.35, item.metalness ?? 0.3)
	addBox(group, dims.w, dims.h, dims.d, mat, 0, dims.h / 2, 0)
	addBox(group, dims.w * 0.78, dims.h * 0.56, 0.03, pbr('#101418', 0.25, 0.85), 0, dims.h * 0.48, dims.d / 2 + 0.02)
	return group
}

function buildBathtub(item) {
	const dims = item.dimensions || { w: 1.7, h: 0.65, d: 0.8 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#E9EEF5', item.roughness ?? 0.25, item.metalness ?? 0.1)
	addBox(group, dims.w, dims.h * 0.55, dims.d, mat, 0, dims.h * 0.28, 0)
	addBox(group, dims.w * 0.92, dims.h * 0.32, dims.d * 0.86, pbr('#FFFFFF', 0.18, 0.05), 0, dims.h * 0.42, 0)
	return group
}

function buildToilet(item) {
	const dims = item.dimensions || { w: 0.45, h: 0.85, d: 0.7 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#F5F7FA', item.roughness ?? 0.25, item.metalness ?? 0.08)
	addBox(group, dims.w * 0.55, dims.h * 0.42, dims.d * 0.55, mat, 0, dims.h * 0.21, 0.05)
	addBox(group, dims.w * 0.8, dims.h * 0.32, dims.d * 0.6, mat, 0, dims.h * 0.54, -0.02)
	return group
}

function buildSink(item) {
	const dims = item.dimensions || { w: 0.6, h: 0.95, d: 0.5 }
	const group = new THREE.Group()
	const mat = pbr(item.color || '#F3F6FA', item.roughness ?? 0.3, item.metalness ?? 0.08)
	addBox(group, dims.w, dims.h * 0.5, dims.d, mat, 0, dims.h * 0.25, 0)
	addBox(group, dims.w * 0.84, 0.06, dims.d * 0.82, pbr('#D4D9DE', 0.2, 0.4), 0, dims.h * 0.53, 0)
	return group
}

function buildStaircase(item) {
	const dims = item.dimensions || { w: 1.2, h: 3.2, d: 3.8 }
	const group = new THREE.Group()
	const numSteps = 16
	const stepHeight = dims.h / numSteps
	const stepDepth = dims.d / numSteps
	const stepWidth = dims.w

	const treadMat = pbr(item.color || '#7c5335', 0.6, 0.05)
	const steelMat = pbr('#1e293b', 0.4, 0.8)
	const glassRailMat = new THREE.MeshPhysicalMaterial({
		color: '#e2e8f0',
		transparent: true,
		opacity: 0.35,
		roughness: 0.1,
		metalness: 0.1,
	})

	addBox(group, 0.18, dims.h * 0.08, dims.d * 1.05, steelMat, 0, dims.h * 0.46, 0)

	for (let i = 0; i < numSteps; i += 1) {
		const stepY = i * stepHeight + stepHeight / 2
		const stepZ = -dims.d / 2 + i * stepDepth + stepDepth / 2
		addBox(group, stepWidth, 0.06, stepDepth * 1.15, treadMat, 0, stepY, stepZ)
		addBox(group, 0.12, stepHeight * 0.7, 0.12, steelMat, 0, stepY - stepHeight * 0.35, stepZ)
	}

	addBox(group, 0.03, dims.h * 0.32, dims.d, glassRailMat, stepWidth / 2 + 0.02, dims.h * 0.55, 0)
	addBox(group, 0.05, 0.05, dims.d * 1.02, steelMat, stepWidth / 2 + 0.02, dims.h * 0.72, 0)

	return group
}

function buildPoolLounger(item) {
	const dims = item.dimensions || { w: 0.85, h: 0.45, d: 2.0 }
	const group = new THREE.Group()
	const frameMat = pbr('#1e293b', 0.5, 0.7)
	const cushionMat = pbr(item.color || '#f8fafc', 0.85, 0.0)

	addBox(group, dims.w, 0.06, dims.d, frameMat, 0, 0.15, 0)
	addBox(group, dims.w * 0.9, 0.15, 0.06, frameMat, 0, 0.075, dims.d * 0.42)
	addBox(group, dims.w * 0.9, 0.15, 0.06, frameMat, 0, 0.075, -dims.d * 0.42)
	addBox(group, dims.w * 0.94, 0.08, dims.d * 0.65, cushionMat, 0, 0.22, dims.d * 0.12)

	const backGroup = new THREE.Group()
	backGroup.position.set(0, 0.2, -dims.d * 0.22)
	backGroup.rotation.x = THREE.MathUtils.degToRad(-35)
	addBox(backGroup, dims.w * 0.94, 0.08, dims.d * 0.38, cushionMat, 0, 0, -dims.d * 0.16)
	group.add(backGroup)

	return group
}

function buildOutdoorSofa(item) {
	const dims = item.dimensions || { w: 2.6, h: 0.75, d: 1.6 }
	const group = new THREE.Group()
	const frameMat = pbr('#1e293b', 0.6, 0.3)
	const cushionMat = pbr(item.color || '#334155', 0.9, 0.0)

	addBox(group, dims.w, 0.12, dims.d, frameMat, 0, 0.06, 0)
	addBox(group, dims.w * 0.94, 0.18, dims.d * 0.6, cushionMat, 0, 0.21, 0.2)
	addBox(group, dims.w * 0.94, 0.45, 0.22, cushionMat, 0, 0.4, -dims.d * 0.36)
	addBox(group, dims.w * 0.36, 0.18, dims.d * 0.4, cushionMat, -dims.w * 0.29, 0.21, -0.2)

	return group
}

function buildPatioTable(item) {
	const dims = item.dimensions || { w: 1.2, h: 0.38, d: 0.8 }
	const group = new THREE.Group()
	const concreteMat = pbr('#475569', 0.85, 0.05)
	const woodMat = pbr('#78350f', 0.6, 0.05)

	addBox(group, dims.w, 0.08, dims.d, woodMat, 0, dims.h - 0.04, 0)
	addBox(group, dims.w * 0.8, dims.h - 0.08, dims.d * 0.75, concreteMat, 0, (dims.h - 0.08) / 2, 0)

	return group
}

const BUILDERS = {
	sofa: buildSofa,
	sofa_3seater: buildSofa,
	sofa_sectional: buildSofa,
	armchair: buildArmchair,
	coffee_table: buildCoffeeTable,
	bed: buildBed,
	king_bed: buildBed,
	queen_bed: buildBed,
	single_bed: buildBed,
	bed_single: buildBed,
	bed_double: buildBed,
	wardrobe: buildWardrobe,
	dresser: buildDresser,
	desk: buildDesk,
	bookshelf: buildBookshelf,
	tv_unit: buildTvUnit,
	tv_stand: buildTvUnit,
	floor_lamp: buildFloorLamp,
	pendant_light: buildPendantLight,
	rug: buildRug,
	plant: buildPlant,
	dining_table: buildDiningTable,
	dining_chair: buildDiningChair,
	office_chair: buildDiningChair,
	kitchen_counter: buildKitchenCounter,
	kitchen_island: buildKitchenIsland,
	refrigerator: buildRefrigerator,
	oven: buildOven,
	bathtub: buildBathtub,
	shower: buildBathtub,
	toilet: buildToilet,
	sink: buildSink,
	bathroom_vanity: buildSink,
	nightstand: buildCoffeeTable,
	staircase: buildStaircase,
	stairs: buildStaircase,
	pool_lounger: buildPoolLounger,
	outdoor_sofa: buildOutdoorSofa,
	patio_table: buildPatioTable,
}

const ASSET_PREVIEW_SIZES = {
	sofa: { dims: { w: 2.2, h: 0.85, d: 0.9 }, color: '#4A6FA5' },
	bed: { dims: { w: 2.0, h: 0.7, d: 1.8 }, color: '#8B7355' },
	table: { dims: { w: 1.6, h: 0.75, d: 0.9 }, color: '#8C6239' },
	chair: { dims: { w: 0.5, h: 0.9, d: 0.5 }, color: '#5D4037' },
	counter: { dims: { w: 2.0, h: 0.9, d: 0.65 }, color: '#475569' },
	wardrobe: { dims: { w: 1.5, h: 2.1, d: 0.6 }, color: '#7C5C3D' },
	tv: { dims: { w: 1.8, h: 0.5, d: 0.4 }, color: '#3D2B10' },
	bath: { dims: { w: 1.7, h: 0.6, d: 0.8 }, color: '#f8fafc' },
	toilet: { dims: { w: 0.5, h: 0.75, d: 0.68 }, color: '#f1f5f9' },
}

function buildCompositeFurnitureFromParts(item) {
	const group = new THREE.Group()
	const parts = item.parts || {}

	for (const [partKey, part] of Object.entries(parts)) {
		if (!part || typeof part !== 'object') continue

		const color = part.color || item.color || '#cccccc'
		const roughness = part.roughness ?? item.roughness ?? 0.7
		const metalness = part.metalness ?? item.metalness ?? 0.05
		const mat = pbr(color, roughness, metalness)

		let mesh = null
		const partType = String(part.type || '').toLowerCase()

		if (partType === 'cylinder') {
			const rt = Number(part.radius_top) || 0.2
			const rb = Number(part.radius_bottom) || 0.2
			const h = Number(part.height) || 0.5
			const segs = Number(part.radial_segments) || 16
			mesh = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, segs), mat)
		} else if (partType === 'sphere') {
			const r = Number(part.radius) || 0.3
			mesh = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 16), mat)
		} else {
			const w = Number(part.w) || Number(part.width) || 0.5
			const h = Number(part.h) || Number(part.height) || 0.5
			const d = Number(part.d) || Number(part.depth) || 0.5
			mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat)
		}

		mesh.castShadow = true
		mesh.receiveShadow = true

		const ox = Number(part.offset_x) || 0
		const oy = Number(part.offset_y) || 0
		const oz = Number(part.offset_z) || 0
		mesh.position.set(ox, oy, oz)

		if (part.rotation_x) mesh.rotation.x = THREE.MathUtils.degToRad(Number(part.rotation_x))
		if (part.rotation_y) mesh.rotation.y = THREE.MathUtils.degToRad(Number(part.rotation_y))
		if (part.rotation_z) mesh.rotation.z = THREE.MathUtils.degToRad(Number(part.rotation_z))

		group.add(mesh)
	}

	return group
}

export function buildFurniture(furnitureArray = []) {
	const group = new THREE.Group()

	for (const item of furnitureArray) {
		if (!item || typeof item !== 'object') {
			continue
		}

		let piece = null
		if (item.parts && typeof item.parts === 'object' && Object.keys(item.parts).length > 0) {
			piece = buildCompositeFurnitureFromParts(item)
		} else {
			const key = String(item.asset || item.type || item.category || '').toLowerCase()
			const baseKey = key.split('_')[0]
			const builder = BUILDERS[key] || BUILDERS[baseKey]
			if (builder) {
				piece = builder(item)
			} else {
				const preset = ASSET_PREVIEW_SIZES[key] || ASSET_PREVIEW_SIZES[baseKey]
				const dims = item.dimensions || preset?.dims || { w: 1, h: 0.8, d: 1 }
				piece = new THREE.Group()
				addBox(
					piece,
					Number(dims.w) || 1,
					Number(dims.h) || 0.8,
					Number(dims.d) || 1,
					pbr(item.color || preset?.color || '#8B7355', item.roughness ?? 0.7, item.metalness ?? 0.05),
					0,
					(Number(dims.h) || 0.8) / 2,
					0
				)
			}
		}

		if (piece) {
			const position = item.position || { x: 0, y: 0, z: 0 }
			piece.position.set(Number(position.x) || 0, Number(position.y) || 0, Number(position.z) || 0)
			piece.rotation.y = THREE.MathUtils.degToRad(Number(item.rotation_y) || 0)
			group.add(piece)
		}
	}

	return group
}

export { makeFloorTexture } from './floorTextures'
