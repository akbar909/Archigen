/* eslint-disable react/prop-types, react/no-unknown-property */
import { Component, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Bounds, Center, useGLTF } from '@react-three/drei'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { clone as cloneSkeleton } from 'three/examples/jsm/utils/SkeletonUtils.js'
import { assetYawOffset } from '../../utils/wallMount'

// Render at most two previews at once, then retain images. A canvas per card
// exhausts the browser's WebGL context limit and can kill the house renderer.
const previews = new Map()
const queue = []
let active = 0
function pump() {
  while (active < 2 && queue.length) {
    const job = queue.shift()
    if (job.cancelled) continue
    active++
    job.started = true
    job.start()
  }
}

class PreviewBoundary extends Component {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch() { this.props.onFailure() }
  render() { return this.state.failed ? null : this.props.children }
}

function ThumbnailAsset({ entry, onCapture }) {
  const { scene } = useGLTF(entry.model_path, '/draco/gltf/')
  const { gl, scene: renderScene, camera } = useThree()
  const frames = useRef(0)
  const yaw = assetYawOffset(entry)
  const pitch = Number(entry.canonical_pitch_offset_deg) || 0
  const model = useMemo(() => {
    const clone = cloneSkeleton(scene)
    clone.rotation.y += yaw * Math.PI / 180
    clone.rotation.x += pitch * Math.PI / 180
    return clone
  }, [scene, yaw, pitch])
  useFrame(() => {
    if (++frames.current !== 12) return
    gl.render(renderScene, camera)
    const image = gl.domElement.toDataURL('image/png')
    requestAnimationFrame(() => onCapture(image))
  })
  return <Bounds fit clip observe margin={1.18}><Center bottom>
    <group rotation={[0, -Math.PI / 5, 0]}><primitive object={model} /></group>
  </Center></Bounds>
}

export default function ModelThumbnail({ entry }) {
  const containerRef = useRef(null)
  const key = `${String(entry?.model_path || '').split('?')[0]}:${assetYawOffset(entry)}:${entry?.canonical_pitch_offset_deg || 0}`
  const [image, setImage] = useState(() => previews.get(key))
  const [visible, setVisible] = useState(false)
  const [granted, setGranted] = useState(false)
  const [failed, setFailed] = useState(false)
  useEffect(() => { setImage(previews.get(key)); setFailed(false) }, [key])
  const valid = /^https?:\/\//.test(entry?.model_path || '')
    && String(entry.model_path).split('?')[0].toLowerCase().endsWith('.glb')
  useEffect(() => {
    const observer = new IntersectionObserver(([record]) => setVisible(record.isIntersecting), { rootMargin: '40px' })
    if (containerRef.current) observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])
  useEffect(() => {
    if (!visible || image || failed || !valid) return undefined
    const job = { start: () => setGranted(true), started: false, cancelled: false }
    queue.push(job)
    pump()
    return () => {
      job.cancelled = true
      if (job.started) active--
      setGranted(false)
      pump()
    }
  }, [visible, image, failed, valid])
  const capture = (data) => { previews.set(key, data); setImage(data) }
  return <span ref={containerRef} className="editor-model-preview" aria-hidden="true">
    {image ? <img src={image} alt="" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
      : failed || !valid ? <span className="editor-helper-copy">Preview unavailable</span>
        : granted && <PreviewBoundary key={key} onFailure={() => setFailed(true)}>
          <Canvas orthographic dpr={1} camera={{ position: [3.2, 2.4, 3.2], zoom: 58, near: 0.01, far: 10000 }}
            gl={{ alpha: true, antialias: true, preserveDrawingBuffer: true, powerPreference: 'low-power' }}>
            <color attach="background" args={['#111821']} />
            <ambientLight intensity={1.8} />
            <directionalLight position={[4, 6, 5]} intensity={2.5} />
            <directionalLight position={[-3, 2, -2]} intensity={0.8} color="#8ed8ff" />
            <Suspense fallback={null}><ThumbnailAsset entry={entry} onCapture={capture} /></Suspense>
          </Canvas>
        </PreviewBoundary>}
  </span>
}
