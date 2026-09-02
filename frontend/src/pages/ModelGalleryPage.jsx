/* eslint-disable react/prop-types, react/no-unknown-property */
import { Component, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { ContactShadows, Environment, OrbitControls, useGLTF } from '@react-three/drei'
import * as THREE from 'three'

const MODELS = [
  ['bathroom', 'bathtub_001.glb'], ['bathroom', 'sink_001.glb'], ['bathroom', 'toilet_001.glb'],
  ['bedroom', 'bedside_table_001.glb'], ['bedroom', 'bed_02.glb'], ['bedroom', 'desk_001.glb'], ['bedroom', 'ArmChair_01.glb'], ['bedroom', 'GothicBed_01.glb'], ['bedroom', 'modren_wooden_cabinet_01.glb'],
  ['dining_room', 'dining_chair_001.glb'], ['dining_room', 'dining_table_001.glb'], ['dining_room', 'sideboard_001.glb'],
  ['kitchen', 'cabinet_001.glb'], ['kitchen', 'kitchen_island_001.glb'], ['kitchen', 'refrigerator_001.glb'], ['kitchen', 'sink_001.glb'], ['kitchen', 'vintage_microwave_1.glb'],
  ['living_room', 'floor_lamp.glb'], ['living_room', 'ArmChair_01.glb'], ['living_room', 'CoffeeTable_01.glb'], ['living_room', 'modren_wooden_cabinet_01.glb'],
].map(([category, file]) => ({
  category,
  file,
  name: file.replace('.glb', '').replaceAll('_', ' '),
  url: `/models/${category}__${file}`,
}))

function PreviewModel({ url }) {
  const { scene } = useGLTF(url)
  const { model, scale } = useMemo(() => {
    const model = scene.clone(true)
    const bounds = new THREE.Box3().setFromObject(model)
    const size = bounds.getSize(new THREE.Vector3())
    const center = bounds.getCenter(new THREE.Vector3())
    const largestDimension = Math.max(size.x, size.y, size.z, 0.01)

    model.position.set(-center.x, -bounds.min.y, -center.z)
    return { model, scale: 2.4 / largestDimension }
  }, [scene])

  return <primitive object={model} scale={scale} />
}

function PreviewCanvas({ model, resetKey }) {
  return (
    <Canvas key={resetKey} camera={{ position: [2.8, 1.8, 2.8], fov: 42 }} dpr={[1, 1.5]}>
      <color attach="background" args={['#171b1d']} />
      <ambientLight intensity={1.4} />
      <directionalLight position={[3, 5, 4]} intensity={3} castShadow />
      <Suspense fallback={null}>
        <PreviewModel url={model.url} />
        <Environment preset="studio" />
        <ContactShadows position={[0, 0, 0]} opacity={0.45} scale={4} blur={2.5} far={3} />
      </Suspense>
      <OrbitControls makeDefault enableDamping minDistance={1.5} maxDistance={8} />
    </Canvas>
  )
}

function LazyPreview({ model, resetKey }) {
  const previewRef = useRef(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const element = previewRef.current
    if (!element) return undefined

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting)
      },
      { rootMargin: '60px', threshold: 0.05 }
    )

    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return (
    <div ref={previewRef} className="model-preview-stage">
      {isVisible ? (
        <PreviewCanvas model={model} resetKey={resetKey} />
      ) : (
        <div className="model-loading">Scroll to load preview</div>
      )}
    </div>
  )
}

class ModelErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) return <div className="model-error">Could not load this file</div>
    return this.props.children
  }
}

export default function ModelGalleryPage() {
  const [filter, setFilter] = useState('all')
  const [resetKey, setResetKey] = useState(0)
  const categories = ['all', ...new Set(MODELS.map((model) => model.category))]
  const visibleModels = filter === 'all' ? MODELS : MODELS.filter((model) => model.category === filter)

  return (
    <main className="model-gallery">
      <header className="gallery-header">
        <div>
          <p className="gallery-kicker">ArchGen / asset laboratory</p>
          <h1>Model test gallery</h1>
          <p className="gallery-description">Inspect every browser-ready furniture asset before adding it to a generated house.</p>
        </div>
        <div className="gallery-count">
          <strong>{visibleModels.length}</strong>
          <span>of {MODELS.length} models</span>
        </div>
      </header>

      <nav className="gallery-filters" aria-label="Filter models by room">
        {categories.map((category) => (
          <button
            key={category}
            type="button"
            className={filter === category ? 'gallery-filter active' : 'gallery-filter'}
            onClick={() => setFilter(category)}
          >
            {category === 'all' ? 'All models' : category.replaceAll('_', ' ')}
          </button>
        ))}
        <button type="button" className="gallery-reset" onClick={() => setResetKey((value) => value + 1)}>
          Reset views
        </button>
      </nav>

      <section className="model-grid">
        {visibleModels.map((model) => (
          <article className="model-card" key={model.url}>
            <div className="model-preview">
              <ModelErrorBoundary>
                <Suspense fallback={<div className="model-loading">Loading model...</div>}>
                  <LazyPreview model={model} resetKey={resetKey} />
                </Suspense>
              </ModelErrorBoundary>
            </div>
            <div className="model-card-footer">
              <div>
                <h2>{model.name}</h2>
                <p>{model.category.replaceAll('_', ' ')}</p>
              </div>
              <a href={model.url} download title={`Download ${model.name}`}>
                GLB
              </a>
            </div>
          </article>
        ))}
      </section>
    </main>
  )
}
