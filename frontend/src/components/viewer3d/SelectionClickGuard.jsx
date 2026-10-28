/* eslint-disable react/prop-types */
import { useEffect, useRef } from 'react'
import { useThree } from '@react-three/fiber'
import { trackSelectionGestures } from '../../utils/selectionGesture'

export default function SelectionClickGuard({ isTransforming = false }) {
  const { gl } = useThree()
  const tracker = useRef(null)
  useEffect(() => {
    tracker.current = trackSelectionGestures(gl.domElement, window)
    return () => { tracker.current?.dispose(); tracker.current = null }
  }, [gl])
  useEffect(() => {
    if (isTransforming) tracker.current?.cancel()
  }, [isTransforming])
  return null
}
