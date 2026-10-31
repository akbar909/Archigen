/* eslint-disable react/prop-types, react/no-unknown-property */
import { Suspense, useEffect, useMemo, useRef } from 'react'
import { useGLTF } from '@react-three/drei'
import * as THREE from 'three'

import { buildFurniture } from '../../utils/furnitureBuilder'
import { furnitureDimensions } from '../../utils/designEditing'
import { prepareAssetModel } from '../../utils/assetModel'
import { isSelectionClick } from '../../utils/selectionGesture'

const DRACO_DECODER_PATH = '/draco/gltf/'

function normalizedBuilderItem(item) {
  const dimensions = furnitureDimensions(item)
  return {
    ...item,
    position: { x: 0, y: 0, z: 0 },
    rotation: 0,
    rotation_y: 0,
    dimensions: {
      w: dimensions.width,
      d: dimensions.depth,
      h: dimensions.height,
    },
  }
}

function ProceduralFurniture({ item }) {
  const object = useMemo(
    () => buildFurniture([normalizedBuilderItem(item)]),
    [item],
  )
  return <primitive object={object} />
}

function WallDecorPreview({ item }) {
  const dimensions = furnitureDimensions(item)
  const type = String(item.category || item.asset || '').toLowerCase()
  const color = item.color || '#b56b4e'

  if (type.includes('sconce')) {
    return (
      <group>
        <mesh position={[0, dimensions.height * 0.45, 0]} castShadow>
          <cylinderGeometry args={[dimensions.width * 0.32, dimensions.width * 0.42, dimensions.depth, 20]} />
          <meshStandardMaterial color="#d6b46d" metalness={0.65} roughness={0.28} />
        </mesh>
        <mesh position={[0, dimensions.height * 0.75, dimensions.depth * 0.55]} castShadow>
          <sphereGeometry args={[dimensions.width * 0.34, 20, 12]} />
          <meshStandardMaterial color="#fff1bf" emissive="#fbbf24" emissiveIntensity={0.35} roughness={0.25} />
        </mesh>
      </group>
    )
  }

  const isMirror = type.includes('mirror')
  return (
    <group>
      <mesh position={[0, dimensions.height / 2, 0]} castShadow>
        <boxGeometry args={[dimensions.width, dimensions.height, dimensions.depth]} />
        <meshStandardMaterial color={isMirror ? '#8f7d63' : '#4a3428'} metalness={isMirror ? 0.55 : 0.1} roughness={0.35} />
      </mesh>
      <mesh position={[0, dimensions.height / 2, dimensions.depth / 2 + 0.004]}>
        <planeGeometry args={[dimensions.width * 0.88, dimensions.height * 0.86]} />
        <meshStandardMaterial
          color={isMirror ? '#c8d8df' : color}
          metalness={isMirror ? 0.82 : 0.05}
          roughness={isMirror ? 0.12 : 0.62}
        />
      </mesh>
    </group>
  )
}

function CatalogModel({ item }) {
  const { scene } = useGLTF(item.model_path, DRACO_DECODER_PATH)
  const normalized = useMemo(() => {
    return prepareAssetModel(scene, item)
  }, [scene, item])

  return (
    <group scale={normalized.scale}>
      <primitive object={normalized.object} />
    </group>
  )
}

export default function EditableFurniture({
  item,
  room,
  isSelected,
  editingEnabled,
  onSelect,
  onObjectReady,
}) {
  const rootRef = useRef(null)
  const position = item.position || { x: 0, y: 0, z: 0 }
  const rotation = THREE.MathUtils.degToRad(Number(item.rotation_y) || 0)

  useEffect(() => {
    if (isSelected && rootRef.current) onObjectReady?.(rootRef.current)
  }, [isSelected, item, onObjectReady])

  return (
    <group
      ref={rootRef}
      position={[Number(position.x) || 0, Number(position.y) || 0, Number(position.z) || 0]}
      rotation={[0, rotation, 0]}
      scale={[item.flip_x ? -1 : 1, 1, item.flip_y ? -1 : 1]}
      userData={{
        isSelectable: true,
        entityType: 'furniture',
        entityId: item.id,
        roomId: room.id,
        category: item.category || item.asset || item.type,
        modelId: item.model_id || item.asset_id || item.asset,
      }}
      onClick={(event) => {
        if (!editingEnabled || !isSelectionClick(event)) return
        event.stopPropagation()
        onSelect?.({
          type: 'furniture',
          id: item.id,
          roomId: room.id,
          object: event.eventObject,
        })
      }}
    >
      {item.wall_mounted && !item.model_path ? (
        <WallDecorPreview item={item} />
      ) : item.model_path ? (
        <Suspense fallback={<ProceduralFurniture item={item} />}>
          <CatalogModel item={item} />
        </Suspense>
      ) : (
        <ProceduralFurniture item={item} />
      )}
    </group>
  )
}
