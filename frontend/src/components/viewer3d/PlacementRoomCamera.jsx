/* eslint-disable react/prop-types */
import { useEffect } from 'react'
import { useThree } from '@react-three/fiber'

// Fade between rooms rather than flying the walkthrough camera through walls.
// While transitioning, the stage suspends collision correction and other cameras.
export default function PlacementRoomCamera({ request, controlsRef, targetPos, targetCamPos, onComplete }) {
  const { camera } = useThree()
  useEffect(() => {
    if (!request) return undefined
    const move = setTimeout(() => {
      camera.clearViewOffset()
      camera.position.fromArray(request.position)
      camera.lookAt(...request.target)
      camera.updateProjectionMatrix()
      if (controlsRef.current) {
        controlsRef.current.target.fromArray(request.target)
      }
      targetCamPos.current.copy(camera.position)
      targetPos.current.fromArray(request.target)
    }, 170)
    const finish = setTimeout(() => onComplete(request.id), 430)
    return () => { clearTimeout(move); clearTimeout(finish) }
  }, [request, camera, controlsRef, targetPos, targetCamPos, onComplete])
  return null
}
