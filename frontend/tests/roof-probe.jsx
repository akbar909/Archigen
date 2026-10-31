/* eslint-disable react/prop-types */
import { useEffect } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'

export default function RoofProbe({ controlsRef, targetPos, targetCamPos, selection }) {
  const { camera, scene, gl } = useThree()
  useEffect(() => {
    window.roofWalkthroughReady = () => controlsRef.current?.enabled === false
    window.roofPrepare = (ceiling = false) => {
      const object = scene.getObjectByName('Roof_L0_focus_test')
      if (!object?.geometry) return false
      object.updateWorldMatrix(true, true)
      object.geometry.computeBoundingBox()
      const local = object.geometry.boundingBox
      const center = local.getCenter(new THREE.Vector3())
      center.y = ceiling ? local.min.y : local.max.y
      const target = object.localToWorld(center.clone())
      const normal = new THREE.Vector3(0, ceiling ? -1 : 1, 0)
        .applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(object.matrixWorld))
      const living = ceiling && window.roofRooms?.find((room) => room.id === 'living')
      if (living) {
        target.x = living.position.x + living.dimensions.width / 2
        target.z = -(living.position.y + living.dimensions.depth / 2)
      }
      const tangent = new THREE.Vector3(0, 0, 1).transformDirection(object.matrixWorld)
      const bounds = new THREE.Box3().setFromObject(object)
      const diagonal = bounds.getSize(new THREE.Vector3()).length()
      camera.position.copy(target).addScaledVector(normal, ceiling ? 1.3 : diagonal * 0.7)
        .addScaledVector(tangent, ceiling ? 0.25 : diagonal * 0.25)
      camera.lookAt(target)
      camera.updateMatrixWorld(true)
      controlsRef.current.target.copy(target)
      targetPos.current.copy(target)
      targetCamPos.current.copy(camera.position)
      window.roofReference = { target: target.toArray(), normal: normal.toArray(), bounds: { min: bounds.min.toArray(), max: bounds.max.toArray() }, ceiling, living: Boolean(living) }
      window.roofInitialPosition = camera.position.toArray()
      window.roofTrack = []
      return true
    }
    window.roofClickPoint = () => {
      const object = scene.getObjectByName('Roof_L0_focus_test')
      const local = object.geometry.boundingBox
      const hit = window.roofReference.living ? object.worldToLocal(new THREE.Vector3(...window.roofReference.target)) : local.getCenter(new THREE.Vector3())
      hit.y = window.roofReference.ceiling ? local.min.y : local.max.y
      hit.x += (local.max.x - local.min.x) * (window.roofReference.ceiling ? 0.02 : 0.15)
      hit.z -= (local.max.z - local.min.z) * (window.roofReference.ceiling ? 0.01 : 0.1)
      const projected = object.localToWorld(hit).project(camera)
      const rect = gl.domElement.getBoundingClientRect()
      return { x: rect.left + (projected.x + 1) * rect.width / 2, y: rect.top + (1 - projected.y) * rect.height / 2 }
    }
  }, [camera, scene, gl, controlsRef, targetPos, targetCamPos])
  useEffect(() => {
    window.roofSnapshot = () => {
      const reference = window.roofReference
      if (!reference) return null
      camera.updateMatrixWorld(true)
      const rect = gl.domElement.getBoundingClientRect()
      const points = []
      for (const x of [reference.bounds.min[0], reference.bounds.max[0]]) for (const y of [reference.bounds.min[1], reference.bounds.max[1]]) {
        for (const z of [reference.bounds.min[2], reference.bounds.max[2]]) {
          const point = new THREE.Vector3(x, y, z).project(camera)
          points.push({ x: rect.left + (point.x + 1) * rect.width / 2, y: rect.top + (1 - point.y) * rect.height / 2 })
        }
      }
      return { position: camera.position.toArray(), fov: camera.fov, direction: camera.getWorldDirection(new THREE.Vector3()).toArray(),
        target: controlsRef.current.target.toArray(), selectionType: selection?.type, roomId: selection?.roomId,
        selectedPrimitive: Boolean(selection?.surfaceObject), points, reference }
    }
  }, [camera, gl, controlsRef, selection])
  useFrame(() => {
    if (window.roofTrack && window.roofTrack.length < 600) window.roofTrack.push(camera.position.toArray())
  })
  return null
}
