import { useEffect } from 'react'
import { useThree } from '@react-three/fiber'
export default function PlacementProbe() {
  const { camera } = useThree()
  useEffect(() => { window.placementCamera = () => camera.position.toArray() }, [camera])
  return null
}
