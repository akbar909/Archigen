import { useEffect } from 'react'
import { useThree } from '@react-three/fiber'
import * as THREE from 'three'
export default function MobileProbe() {
  const { camera } = useThree()
  useEffect(() => { window.mobileCamera = () => ({ position: camera.position.toArray(), direction: camera.getWorldDirection(new THREE.Vector3()).toArray(), fov: camera.fov, near: camera.near }) }, [camera])
  return null
}
