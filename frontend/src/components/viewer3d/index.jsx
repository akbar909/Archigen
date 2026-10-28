/* eslint-disable react/prop-types */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { toast } from 'react-hot-toast'

import { useProjectStore } from '../../store'
import { BlenderHouseModel } from './BlenderModel'
import { getCachedModelUrl } from '../../utils/modelCache'
import { fetchUploadedAssetCatalog, refreshUploadedAsset } from '../../services'
import { canApplyAccentColor, objectDimensions } from '../../utils/assetModel'
import { applySurfaceTexture, surfaceFaceKey } from '../../utils/sceneEditing'
import { adjustAssetPlacement, createAssetPlacement, placementCameraView, placementRoom } from '../../utils/assetPlacement'
import { wallMountNormal, wallMountRotation } from '../../utils/wallMount'
import ViewerStage from './ViewerStage'
import { createNavigationModel, moveWithCollisions, normalizeNavigationDoors, WALK_SPEED, LOOK_SENSITIVITY } from '../../utils/navigation'
import {
  clampFurniturePosition,
  alignWallFurniture,
  clampMountHeight,
  ceilingMountedPosition,
  addFurnitureToRoom,
  addExteriorAsset,
  findFurnitureById,
  findRoomById,
  normalizeDegrees,
  removeFurnitureById,
  updateFurnitureById,
  updateRoomById,
  updateWallById,
} from '../../utils/designEditing'
import {
  modelIdentity,
  objectFloorLevel,
  roomPlacement,
} from './viewerUtils'


async function applyTextureToObject(object, asset, repeat = 2, onCatalogAssetRefreshed, faceNormal = null) {
  const url = asset?.url || asset?.thumbnail_url
  if (!object || !url || asset?.kind !== 'texture') return null
  try {
    const count = await applySurfaceTexture(object, url, repeat, faceNormal)
    return count > 0 ? asset : null
  } catch (firstError) {
    try {
      const fresh = await refreshUploadedAsset(asset.s3_key)
      const freshUrl = fresh?.url || fresh?.thumbnail_url
      if (!freshUrl) throw firstError
      delete object.userData.__requestedFinishUrl
      delete object.userData.__appliedFinishUrl
      const count = await applySurfaceTexture(object, `${freshUrl}${freshUrl.includes('?') ? '&' : '?'}refresh=${Date.now()}`, repeat, faceNormal)
      if (!count) return null
      onCatalogAssetRefreshed?.(fresh)
      return fresh
    } catch (retryError) {
      console.warn('[Viewer3D] Texture apply failed after catalog refresh:', retryError)
      toast.error('Texture could not be loaded from storage. Please try again in a moment.')
      return null
    }
  }
}


// ── Main Professional Viewer3D Component ─────────────────────────────
export default function Viewer3D({ design }) {
  const {
    regenerate3D,
    reloadSaved3D,
    isGenerating3D,
    activeProjectId,
    activeVersionId,
    showRoof,
    toggleShowRoof,
    activeFloorLevel,
    setActiveFloorLevel,
    approveFloorPlan,
    isApprovingLayout,
    setDraftDesign,
    isDirty,
  } = useProjectStore()

  const rawGlbUrl = design?.glb_url || design?.model_url || null
  const [effectiveGlbUrl, setEffectiveGlbUrl] = useState(rawGlbUrl)
  const [uploadedAssets, setUploadedAssets] = useState([])
  const replaceUploadedAsset = useCallback((fresh) => {
    if (!fresh?.s3_key) return
    setUploadedAssets((current) => current.map((asset) => asset.s3_key === fresh.s3_key ? fresh : asset))
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchUploadedAssetCatalog()
      .then((data) => {
        if (!cancelled) setUploadedAssets(Array.isArray(data?.assets) ? data.assets : [])
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  // Check IndexedDB local cache first for instant model retrieval
  useEffect(() => {
    let isCancelled = false
    if (!rawGlbUrl) {
      setEffectiveGlbUrl(null)
      return
    }

    getCachedModelUrl(rawGlbUrl)
      .then((cachedBlobUrl) => {
        if (!isCancelled) {
          if (cachedBlobUrl) {
            setEffectiveGlbUrl(cachedBlobUrl)
          } else {
            setEffectiveGlbUrl(rawGlbUrl)
          }
        }
      })
      .catch(() => {
        if (!isCancelled) setEffectiveGlbUrl(rawGlbUrl)
      })

    return () => {
      isCancelled = true
    }
  }, [rawGlbUrl])

  const glbUrl = effectiveGlbUrl
  // Exclusively use Cloud Blender 3D photorealistic model
  const [viewSource, setViewSource] = useState('blender')
  const [isModelRendered, setIsModelRendered] = useState(false)
  const [modelReloadKey, setModelReloadKey] = useState(0)

  // Reset rendered flag whenever glbUrl changes or 3D is being re-synthesized
  useEffect(() => {
    setIsModelRendered(false)
  }, [glbUrl, isGenerating3D])

  const wasGeneratingRef = useRef(false)
  useEffect(() => {
    if (isGenerating3D) {
      wasGeneratingRef.current = true
    }
  }, [isGenerating3D])

  useEffect(() => {
    if (isModelRendered && wasGeneratingRef.current) {
      wasGeneratingRef.current = false
      setViewMode('dollhouse')
    }
  }, [isModelRendered])

  const handleBlenderError = (err) => {
    console.warn('[Viewer3D] Model load error:', err)
    setIsModelRendered(false)
  }

  const handleReloadSavedModel = async () => {
    BlenderHouseModel.clear(glbUrl)
    setIsModelRendered(false)
    setModelReloadKey((value) => value + 1)
    await reloadSaved3D(activeVersionId)
  }

  const isApproved = Boolean(design?.layout_approved || design?.approved_at)
  const [viewMode, setViewMode] = useState(() => (glbUrl && isApproved ? 'dollhouse' : 'plan'))
  const [planSubMode, setPlanSubMode] = useState('vector')
  const previousModelIdentityRef = useRef(null)

  // A version with a saved cloud model should open that model directly. Use
  // the path (not the temporary signature) to avoid treating URL refreshes as
  // different models.
  useEffect(() => {
    const identity = modelIdentity(glbUrl)
    if (identity && isApproved && identity !== previousModelIdentityRef.current) {
      setViewSource('blender')
      // A newly saved GLB should not pull someone out of the bedroom they are
      // editing. Keep walkthrough active; otherwise use the overview entry.
      setViewMode((current) => (current === 'walkthrough' ? current : 'dollhouse'))
      setPlanSubMode('3d')
    }
    previousModelIdentityRef.current = identity
  }, [activeVersionId, glbUrl, isApproved])

  // Always route unapproved designs to 2D CAD floor plan for user review & approval
  useEffect(() => {
    if (!isApproved) {
      setViewMode('plan')
      setPlanSubMode('vector')
    }
  }, [activeVersionId, isApproved])
  const [isNightMode, setIsNightMode] = useState(false)
  const [selectedRoomId, setSelectedRoomId] = useState('overview')
  const [dismissedSynthesisPrompt, setDismissedSynthesisPrompt] = useState(false)
  const [isEditing3D, setIsEditing3D] = useState(false)
  const [selectedEntity, setSelectedEntity] = useState(null)
  const [pendingPlacement, setPendingPlacement] = useState(null)
  const [roomTransition, setRoomTransition] = useState(null)
  const placementSequence = useRef(0)
  const committedPlacements = useRef(new Set())
  const libraryFloorChange = useRef(null)
  const onPlacementStatus = useCallback((id, status) => {
    setPendingPlacement((current) => current?.item.id === id ? { ...current, status } : current)
  }, [])
  const onRoomTransitionComplete = useCallback((id) => {
    setRoomTransition((current) => current?.id === id ? null : current)
  }, [])
  const cancelPlacement = useCallback(() => setPendingPlacement(null), [])
  useEffect(() => {
    if (!isEditing3D || selectedEntity?.type !== 'library') setPendingPlacement(null)
  }, [isEditing3D, selectedEntity?.type])
  useEffect(() => {
    setPendingPlacement(null)
    setRoomTransition(null)
  }, [activeProjectId, activeVersionId])
  const hiddenBlenderFurnitureIds = useMemo(() => (
    Array.isArray(design?.deleted_furniture_ids) ? design.deleted_furniture_ids : []
  ), [design?.deleted_furniture_ids])
  const [transformMode, setTransformMode] = useState('translate')
  const [isTransforming, setIsTransforming] = useState(false)
  const [transformRevision, setTransformRevision] = useState(0)

  const [isFullscreen, setIsFullscreen] = useState(false)
  const [showCallouts, setShowCallouts] = useState(true)

  const containerRef = useRef(null)
  const controlsRef = useRef(null)
  const targetPos = useRef(new THREE.Vector3(0, 1.0, 0))
  const targetCamPos = useRef(new THREE.Vector3(22, 22, 28))

  const rooms = useMemo(() => (Array.isArray(design?.rooms) ? design.rooms : []), [design?.rooms])
  const doors = useMemo(() => (Array.isArray(design?.doors) ? design.doors : []), [design?.doors])
  const windows = useMemo(() => (Array.isArray(design?.windows) ? design.windows : []), [design?.windows])
  const visibleRooms = useMemo(
    () => activeFloorLevel === null || activeFloorLevel === undefined
      ? rooms
      : rooms.filter((room) => objectFloorLevel(room) === activeFloorLevel),
    [rooms, activeFloorLevel],
  )
  const visibleDoors = useMemo(
    () => activeFloorLevel === null || activeFloorLevel === undefined
      ? doors
      : doors.filter((door) => objectFloorLevel(door) === activeFloorLevel),
    [doors, activeFloorLevel],
  )
  const visibleWindows = useMemo(
    () => activeFloorLevel === null || activeFloorLevel === undefined
      ? windows
      : windows.filter((window) => objectFloorLevel(window) === activeFloorLevel),
    [windows, activeFloorLevel],
  )
  const isExteriorAccessWalkable = useMemo(() => {
    const exterior = design?.exterior || {}
    const path = exterior.entrance_path || {}
    const start = path.start || {}
    const end = path.end || {}
    const ax = Number(start.x)
    const az = Number(start.y)
    const bx = Number(end.x)
    const bz = Number(end.y)
    const pathWidth = Math.max(0.8, Number(path.width) || 1.2)
    const driveway = exterior.driveway || {}
    const driveX = Number(driveway.position?.x)
    const driveZ = Number(driveway.position?.y)
    const driveWidth = Number(driveway.width)
    const driveDepth = Number(driveway.depth)

    return (x, z, pad = 0.15) => {
      z *= viewSource === 'blender' ? -1 : 1
      if ([ax, az, bx, bz].every(Number.isFinite)) {
        const vx = bx - ax
        const vz = bz - az
        const lengthSq = vx * vx + vz * vz
        const amount = lengthSq > 0
          ? Math.max(0, Math.min(1, ((x - ax) * vx + (z - az) * vz) / lengthSq))
          : 0
        const nearestX = ax + amount * vx
        const nearestZ = az + amount * vz
        if (Math.hypot(x - nearestX, z - nearestZ) <= pathWidth / 2 + pad) return true
      }
      return (
        [driveX, driveZ, driveWidth, driveDepth].every(Number.isFinite)
        && x >= driveX - pad && x <= driveX + driveWidth + pad
        && z >= driveZ - pad && z <= driveZ + driveDepth + pad
      )
    }
  }, [design?.exterior, viewSource])
  const floors = useMemo(() => {
    if (Array.isArray(design?.floors) && design.floors.length > 0) {
      return design.floors
    }
    return [{ id: 'ground_floor', level: 0, rooms }]
  }, [design?.floors, rooms])

  const selectedFurniture = useMemo(
    () => selectedEntity?.type === 'furniture'
      ? findFurnitureById(design, selectedEntity.id)
      : null,
    [design, selectedEntity],
  )
  const [detectedRooms, setDetectedRooms] = useState([])
  const [detectedDoors, setDetectedDoors] = useState([])
  const selectedEditRoom = useMemo(() => {
    const room = findRoomById(design, selectedEntity?.roomId)
    if (room) {
      return {
        ...placementRoom(room, detectedRooms),
        openings: [...doors, ...windows],
      }
    }
    if (selectedEntity?.roomId !== 'exterior_ground') return null
    const plot = design?.site?.plot || {}
    return {
      id: 'exterior_ground',
      name: 'Exterior Ground',
      position: { x: 0, y: 0, z: 0 },
      dimensions: {
        width: Number(plot.width) || 30,
        depth: Number(plot.depth) || 30,
        height: 3,
      },
    }
  }, [design, selectedEntity?.roomId, doors, windows, detectedRooms])

  useEffect(() => {
    setSelectedEntity(null)
    setIsEditing3D(false)
    setIsTransforming(false)
  }, [activeVersionId])

  useEffect(() => {
    const expected = libraryFloorChange.current
    libraryFloorChange.current = null
    setSelectedEntity((current) => expected?.level === activeFloorLevel && current?.type === 'library'
      && current.roomId === expected.roomId ? current : null)
    setIsTransforming(false)
  }, [activeFloorLevel])

  useEffect(() => {
    if (!isEditing3D) return
    if (!glbUrl || viewSource !== 'blender' || (viewMode === 'plan' && planSubMode === 'vector')) {
      setIsEditing3D(false)
      setSelectedEntity(null)
      setIsTransforming(false)
    }
  }, [glbUrl, isEditing3D, planSubMode, viewMode, viewSource])

  useEffect(() => {
    if (selectedEntity?.type === 'furniture' && !selectedFurniture) {
      setSelectedEntity(null)
    }
  }, [selectedEntity?.type, selectedFurniture])

  const handleSelectEntity = useCallback((entity) => {
    if (pendingPlacement || roomTransition) return
    setSelectedEntity(entity)
    setTransformMode('translate')
  }, [pendingPlacement, roomTransition])

  const handleSelectionObjectReady = useCallback((entity) => {
    setSelectedEntity((current) => {
      if (!current || current.type !== entity.type || current.id !== entity.id) return current
      if (current.object === entity.object) return current
      return { ...current, ...entity }
    })
  }, [])

  const toggleEditing3D = () => {
    setIsEditing3D((current) => {
      const next = !current
      if (next) {
        if (!glbUrl) return false
        if (document.pointerLockElement) document.exitPointerLock?.()
        keysRef.current = { w: false, a: false, s: false, d: false }
        setViewSource('blender')
        setDismissedSynthesisPrompt(true)
      } else {
        const camera = controlsRef.current?.object
        if (camera) {
          const direction = camera.getWorldDirection(new THREE.Vector3())
          yawRef.current = Math.atan2(direction.x, -direction.z)
          pitchRef.current = Math.asin(THREE.MathUtils.clamp(direction.y, -1, 1))
          targetCamPos.current.copy(camera.position)
        }
        setSelectedEntity(null)
        setIsTransforming(false)
      }
      return next
    })
  }

  const updateSelectedFurniture = (patchOrUpdater) => {
    if (!selectedFurniture?.id) return
    const assetInfo = selectedEntity?.object?.userData?.asset_info
    setDraftDesign((draft) => updateFurnitureById(draft, selectedFurniture.id, (item) => ({
      ...(assetInfo || {}),
      ...(typeof patchOrUpdater === 'function' ? patchOrUpdater(item) : patchOrUpdater),
    })))
  }

  const blenderObjectDraftTransform = (object, furniture = selectedFurniture, room = selectedEditRoom) => {
    if (!object || !furniture || !room) return null
    object.updateWorldMatrix(true, false)
    const worldPosition = object.getWorldPosition(new THREE.Vector3())
    const worldQuaternion = object.getWorldQuaternion(new THREE.Quaternion())
    const worldEuler = new THREE.Euler().setFromQuaternion(worldQuaternion, 'YXZ')
    const dimensions = objectDimensions(object)
    const elevation = furniture.ceiling_mounted
      ? ceilingMountedPosition({ ...furniture, dimensions }, room).z
      : Number(room.position?.z) || 0
    const wallMounted = furniture.wall_mounted === true
    const mountHeight = clampMountHeight({ ...furniture, dimensions }, room, worldPosition.y - elevation)
    const rotation = normalizeDegrees(-THREE.MathUtils.radToDeg(worldEuler.y))
    const facing = wallMounted ? wallMountRotation(furniture.wall_side, furniture.wall_normal, rotation) : rotation
    const position = clampFurniturePosition(
      { ...furniture, dimensions, rotation: facing, mount_height: mountHeight },
      room,
      {
        x: worldPosition.x,
        y: -worldPosition.z,
        z: elevation,
      },
    )
    // Apply the same constrained transform to the visible object immediately.
    // Previously the saved metadata was clamped while the gizmo stayed beyond
    // the wall until a later render.
    object.position.set(position.x, wallMounted ? elevation + mountHeight : elevation, -position.y)
    if (wallMounted) {
      object.rotation.y = -THREE.MathUtils.degToRad(facing)
    }
    return {
      position,
      dimensions,
      rotation: facing,
      rotation_y: facing,
      client_edited_3d: true,
      placement_hint: 'user_exact',
      ...(wallMounted ? { mount_height: mountHeight } : {}),
    }
  }

  const nudgeSelectedFurniture = (deltaX, deltaZ, deltaHeight = 0) => {
    if (!selectedFurniture || !selectedEditRoom) return
    if (selectedEntity?.source === 'blender' && selectedEntity.object) {
      selectedEntity.object.position.x += deltaX
      selectedEntity.object.position.z -= deltaZ
      selectedEntity.object.position.y += deltaHeight
      const transform = blenderObjectDraftTransform(selectedEntity.object)
      if (transform) updateSelectedFurniture(transform)
      setTransformRevision((rev) => rev + 1)
      return
    }
    const current = selectedFurniture.position || {}
    const nextPosition = clampFurniturePosition(selectedFurniture, selectedEditRoom, {
      x: (Number(current.x) || 0) + deltaX,
      y: (Number(current.y) || 0) + deltaZ,
      z: Number(current.z) || Number(selectedEditRoom.position?.z) || 0,
    })
    updateSelectedFurniture({ position: nextPosition,
      ...(selectedFurniture.wall_mounted ? { mount_height: clampMountHeight(selectedFurniture, selectedEditRoom,
        (Number(selectedFurniture.mount_height) || 0) + deltaHeight) } : {}),
    })
    setTransformRevision((rev) => rev + 1)
  }

  const rotateSelectedFurniture = (degrees) => {
    if (!selectedFurniture) return
    if (selectedFurniture.wall_mounted || selectedFurniture.ceiling_mounted) return
    if (selectedEntity?.source === 'blender' && selectedEntity.object) {
      selectedEntity.object.rotation.y -= THREE.MathUtils.degToRad(degrees)
      const transform = blenderObjectDraftTransform(selectedEntity.object)
      if (transform) updateSelectedFurniture(transform)
      return
    }
    const rotation = normalizeDegrees(
      (Number(selectedFurniture.rotation ?? selectedFurniture.rotation_y) || 0) + degrees,
    )
    const position = clampFurniturePosition(
      { ...selectedFurniture, rotation },
      selectedEditRoom,
      selectedFurniture.position || {},
    )
    updateSelectedFurniture({ rotation, rotation_y: rotation, position })
  }

  const swapSelectedFurniture = (catalogItem) => {
    if (!selectedFurniture || !catalogItem) return
    const dimensions = { ...catalogItem.dimensions }
    const currentTransform = selectedEntity?.source === 'blender'
      ? blenderObjectDraftTransform(selectedEntity.object)
      : null
    const position = clampFurniturePosition(
      { ...selectedFurniture, dimensions },
      selectedEditRoom,
      currentTransform?.position || selectedFurniture.position || {},
    )
    updateSelectedFurniture({
      ...(currentTransform || {}),
      asset: catalogItem.asset,
      asset_id: catalogItem.asset_id || catalogItem.id,
      model_id: catalogItem.id,
      model_path: catalogItem.model_path || null,
      s3_key: catalogItem.s3_key || null,
      canonical_yaw_offset_deg: catalogItem.canonical_yaw_offset_deg || 0,
      canonical_pitch_offset_deg: catalogItem.canonical_pitch_offset_deg || 0,
      mounting: catalogItem.mounting,
      wall_orientation_version: catalogItem.mounting?.orientation_version || 0,
      name: catalogItem.name,
      category: catalogItem.category || selectedFurniture.category,
      asset_group: catalogItem.group,
      suppressed_furniture_ids: catalogItem.is_assembly
        ? editableFurniture.filter((item) => item.id !== selectedFurniture.id && String(item.room_id || item.roomId) === String(selectedEntity.roomId)
          && /chair/.test(String(item.category || item.asset))).map((item) => item.id)
        : [],
      dimensions,
      color: catalogItem.color || selectedFurniture.color,
      position,
      client_edited_3d: true,
    })
  }

  const duplicateSelectedFurniture = () => {
    if (!selectedFurniture || !selectedEditRoom) return
    const currentTransform = selectedEntity?.source === 'blender' && selectedEntity.object
      ? blenderObjectDraftTransform(selectedEntity.object)
      : null
    const basePos = currentTransform?.position || selectedFurniture.position || {}
    const baseDims = currentTransform?.dimensions || selectedFurniture.dimensions || { width: 0.6, depth: 0.6, height: 0.6 }
    const offset = Math.max(0.6, (Number(baseDims.width) || 0.6) + 0.25)

    let nextPos = clampFurniturePosition(
      { ...selectedFurniture, dimensions: baseDims },
      selectedEditRoom,
      {
        x: (Number(basePos.x) || 0) + offset,
        y: Number(basePos.y) || 0,
        z: Number(basePos.z) || Number(selectedEditRoom.position?.z) || 0,
      },
    )
    if (Math.abs(nextPos.x - (Number(basePos.x) || 0)) < 0.05) {
      nextPos = clampFurniturePosition(
        { ...selectedFurniture, dimensions: baseDims },
        selectedEditRoom,
        {
          x: (Number(basePos.x) || 0) - offset,
          y: Number(basePos.y) || 0,
          z: Number(basePos.z) || Number(selectedEditRoom.position?.z) || 0,
        },
      )
    }
    if (Math.abs(nextPos.x - (Number(basePos.x) || 0)) < 0.05) {
      nextPos = clampFurniturePosition(
        { ...selectedFurniture, dimensions: baseDims },
        selectedEditRoom,
        {
          x: Number(basePos.x) || 0,
          y: (Number(basePos.y) || 0) + offset,
          z: Number(basePos.z) || Number(selectedEditRoom.position?.z) || 0,
        },
      )
    }

    const newId = `${selectedFurniture.category || selectedFurniture.asset || 'furniture'}_${selectedEditRoom.id}_${Date.now()}`
    const duplicatedItem = {
      ...selectedFurniture,
      ...(currentTransform || {}),
      id: newId,
      name: selectedFurniture.name ? `${selectedFurniture.name} (Copy)` : 'Duplicate Furniture',
      position: nextPos,
      dimensions: { ...baseDims },
      rotation: currentTransform?.rotation ?? selectedFurniture.rotation ?? 0,
      rotation_y: currentTransform?.rotation_y ?? selectedFurniture.rotation_y ?? 0,
      client_edited_3d: true,
      placement_hint: 'user_exact',
    }

    setDraftDesign((draft) => addFurnitureToRoom(draft, selectedEditRoom.id, duplicatedItem))
    setSelectedEntity({
      type: 'furniture',
      id: newId,
      roomId: selectedEditRoom.id,
      object: null,
      source: 'blender',
    })
    toast.success(`Added another ${String(selectedFurniture.name || selectedFurniture.category || 'item').replaceAll('_', ' ')}`)
  }

  const addModelAsNewFurniture = (catalogItem) => {
    if (!selectedEditRoom || !catalogItem?.model_path) return
    if (selectedEntity?.type === 'library') {
      if (roomTransition) return
      const item = createAssetPlacement(catalogItem, selectedEditRoom, `placement_${++placementSequence.current}`)
      if (item) setPendingPlacement({ asset: catalogItem, item, roomId: selectedEditRoom.id, status: 'loading' })
      return
    }
    if (catalogItem.group === 'ceiling_asset') { addSelectedWallDecor(catalogItem); return }
    const currentTransform = selectedEntity?.source === 'blender' && selectedEntity.object
      ? blenderObjectDraftTransform(selectedEntity.object)
      : null
    const basePos = currentTransform?.position || selectedFurniture?.position || {
      x: (Number(selectedEditRoom.position?.x) || 0) + (Number(selectedEditRoom.dimensions?.width) || 3) / 2,
      y: (Number(selectedEditRoom.position?.y) || 0) + (Number(selectedEditRoom.dimensions?.depth) || 3) / 2,
      z: Number(selectedEditRoom.position?.z) || 0,
    }
    const dims = { ...catalogItem.dimensions }
    const offset = selectedEntity?.type === 'library' ? 0 : Math.max(0.6, (Number(dims.width) || 0.6) + 0.25)
    let nextPos = clampFurniturePosition(
      { dimensions: dims },
      selectedEditRoom,
      {
        x: (Number(basePos.x) || 0) + offset,
        y: Number(basePos.y) || 0,
        z: Number(basePos.z) || Number(selectedEditRoom.position?.z) || 0,
      },
    )
    if (Math.abs(nextPos.x - (Number(basePos.x) || 0)) < 0.05) {
      nextPos = clampFurniturePosition(
        { dimensions: dims },
        selectedEditRoom,
        {
          x: (Number(basePos.x) || 0) - offset,
          y: Number(basePos.y) || 0,
          z: Number(basePos.z) || Number(selectedEditRoom.position?.z) || 0,
        },
      )
    }

    const newId = `${catalogItem.id || catalogItem.category || 'furniture'}_${selectedEditRoom.id}_${Date.now()}`
    const item = {
      id: newId,
      name: catalogItem.name,
      category: catalogItem.category || selectedFurniture?.category || 'bedside_table',
      asset: catalogItem.asset || catalogItem.category || selectedFurniture?.asset || 'bedside_table',
      asset_id: catalogItem.asset_id || catalogItem.id,
      model_id: catalogItem.id,
      model_path: catalogItem.model_path || null,
      s3_key: catalogItem.s3_key || null,
      canonical_yaw_offset_deg: catalogItem.canonical_yaw_offset_deg || 0,
      canonical_pitch_offset_deg: catalogItem.canonical_pitch_offset_deg || 0,
      room_id: selectedEditRoom.id,
      position: nextPos,
      rotation: 0,
      rotation_y: 0,
      dimensions: dims,
      color: catalogItem.color,
      client_edited_3d: true,
      placement_hint: 'user_exact',
    }

    setDraftDesign((draft) => addFurnitureToRoom(draft, selectedEditRoom.id, item))
    setSelectedEntity({
      type: 'furniture',
      id: newId,
      roomId: selectedEditRoom.id,
      object: null,
      source: 'blender',
    })
    toast.success(`Added ${catalogItem.name} to room`)
  }

  const confirmPlacement = () => {
    const pending = pendingPlacement
    if (!pending || pending.status !== 'ready' || roomTransition
      || selectedEntity?.type !== 'library' || pending.roomId !== selectedEntity.roomId
      || pending.roomId !== selectedRoomId || committedPlacements.current.has(pending.item.id)) return
    committedPlacements.current.add(pending.item.id)
    const id = `${pending.asset.id}_${pending.roomId}_${Date.now()}_${++placementSequence.current}`
    const item = { ...pending.item, id, position: { ...pending.item.position }, dimensions: { ...pending.item.dimensions } }
    setDraftDesign((draft) => addFurnitureToRoom(draft, pending.roomId, item))
    setPendingPlacement(null)
    setSelectedEntity({ type: 'furniture', id, roomId: pending.roomId, object: null, source: 'blender' })
    toast.success(`Placed ${pending.asset.name} in ${selectedEditRoom?.name || 'the selected room'}`)
  }

  const adjustPlacement = (dx, dy, rotation = 0) => {
    if (!selectedEditRoom || roomTransition) return
    setPendingPlacement((current) => current?.roomId === selectedEditRoom.id
      ? { ...current, item: adjustAssetPlacement(current.item, selectedEditRoom, dx, dy, rotation) } : current)
  }

  const resizeSelectedFurniture = (factor) => {
    if (!selectedFurniture || !selectedEditRoom || !Number.isFinite(factor)) return
    const currentTransform = selectedEntity?.source === 'blender' && selectedEntity.object
      ? blenderObjectDraftTransform(selectedEntity.object) : null
    const currentDimensions = selectedEntity?.object ? objectDimensions(selectedEntity.object) : selectedFurniture.dimensions || { width: 1, depth: 1, height: 1 }
    const roomDims = selectedEditRoom.dimensions || {}
    const angle = (Number(selectedFurniture.rotation) || 0) * Math.PI / 180
    const footprintWidth = Math.abs(Math.cos(angle)) * currentDimensions.width + Math.abs(Math.sin(angle)) * currentDimensions.depth
    const footprintDepth = Math.abs(Math.sin(angle)) * currentDimensions.width + Math.abs(Math.cos(angle)) * currentDimensions.depth
    factor = Math.min(factor, (Number(roomDims.width) - 0.3) / footprintWidth,
      (Number(roomDims.depth) - 0.3) / footprintDepth, (Number(roomDims.height) - 0.2) / currentDimensions.height)
    if (!Number.isFinite(factor) || factor <= 0) return
    const dimensions = Object.fromEntries(Object.entries(currentDimensions)
      .map(([key, value]) => [key, Math.max(0.02, Number(value) * factor)]))
    const position = clampFurniturePosition({ ...selectedFurniture, ...(currentTransform || {}), dimensions }, selectedEditRoom, currentTransform?.position || selectedFurniture.position || {})
    if (selectedEntity?.object && !selectedFurniture.model_path && !selectedEntity.object.userData?.asset_info) {
      selectedEntity.object.scale.multiplyScalar(factor)
      selectedEntity.object.position.set(position.x, Number(position.z) || 0, -position.y)
    }
    updateSelectedFurniture({ ...(currentTransform || {}), dimensions, position, client_edited_3d: true })
  }

  const constrainGizmoTransform = () => {
    if (selectedEntity?.source === 'blender' && selectedEntity.object) blenderObjectDraftTransform(selectedEntity.object)
  }

  const deleteSelectedFurniture = () => {
    if (!selectedFurniture?.id) return
    const label = selectedFurniture.name || selectedFurniture.category || selectedFurniture.asset || 'this furniture item'
    if (!window.confirm(`Delete ${String(label).replaceAll('_', ' ')} from the design?`)) return
    if (selectedEntity?.source === 'blender' && selectedEntity.object) {
      selectedEntity.object.visible = false
    }
    setDraftDesign((draft) => removeFurnitureById(draft, selectedFurniture.id))
    setSelectedEntity(null)
  }

  const setSelectedFurnitureColor = (color) => {
    if (!selectedFurniture || !color || !canApplyAccentColor(selectedEntity?.object)) return
    if (selectedEntity?.source === 'blender' && selectedEntity.object) {
      selectedEntity.object.traverse((child) => {
        if (!child.isMesh || !child.material) return
        const materials = Array.isArray(child.material) ? child.material : [child.material]
        materials.forEach((material) => material.color?.set(color))
      })
    }
    const transform = selectedEntity?.source === 'blender'
      ? blenderObjectDraftTransform(selectedEntity.object)
      : null
    updateSelectedFurniture({ ...(transform || {}), color })
  }

  const setSelectedFloorFinish = async (finish) => {
    if (!selectedEditRoom || !finish) return
    if (finish.kind === 'model' && finish.model_path) {
      const roomPosition = selectedEditRoom.position || {}
      const roomDimensions = selectedEditRoom.dimensions || {}
      const hit = selectedEntity?.hitPoint || {}
      const id = `${finish.id}_${selectedEditRoom.id}_${Date.now()}`
      const item = {
        id,
        name: finish.name,
        category: finish.category || 'rug',
        asset: finish.category || 'rug',
        asset_id: finish.asset_id || finish.id,
        model_id: finish.id,
        model_path: finish.model_path,
        s3_key: finish.s3_key,
        room_id: selectedEditRoom.id,
        position: {
          x: Number(hit.x) || (Number(roomPosition.x) || 0) + (Number(roomDimensions.width) || 1) / 2,
          y: Number.isFinite(Number(hit.z)) ? -Number(hit.z) : (Number(roomPosition.y) || 0) + (Number(roomDimensions.depth) || 1) / 2,
          z: Number(roomPosition.z) || 0,
        },
        rotation: 0,
        dimensions: { ...finish.dimensions },
        client_edited_3d: true,
        placement_hint: 'user_exact',
      }
      setDraftDesign((draft) => addFurnitureToRoom(draft, selectedEditRoom.id, item))
      setSelectedEntity({ type: 'furniture', id, roomId: selectedEditRoom.id, object: null, source: 'blender' })
      return
    }
    finish = await applyTextureToObject(selectedEntity?.object, finish, 2.5, replaceUploadedAsset)
    if (!finish) return
    setDraftDesign((draft) => updateRoomById(draft, selectedEditRoom.id, (room) => {
      room.materials = {
        ...(room.materials || {}),
        floor: {
          pattern: finish.id,
          color: finish.color,
          roughness: finish.roughness,
          asset_id: finish.asset_id || finish.id,
          s3_key: finish.s3_key,
          texture_url: finish.url,
        },
      }
      room.pbr_material = {
        ...(room.pbr_material || {}),
        floor: {
          ...(room.pbr_material?.floor || {}),
          pattern: finish.id,
          color: finish.color,
          roughness: finish.roughness,
          asset_id: finish.asset_id || finish.id,
          s3_key: finish.s3_key,
          texture_url: finish.url,
        },
      }
    }))
  }

  const setSelectedWallFinish = async (finish) => {
    if (!finish || !selectedEntity?.wallId) return
    const normal = selectedEntity.surfaceNormal
    if (!normal) { toast.error('Please select the room-facing side of the wall.'); return }
    const face = surfaceFaceKey(normal)
    finish = await applyTextureToObject(selectedEntity.object, finish, 1.8, replaceUploadedAsset, normal)
    if (!finish) return
    setDraftDesign((draft) => {
      draft.wall_face_overrides = { ...(draft.wall_face_overrides || {}), [selectedEntity.wallId]: {
        ...(draft.wall_face_overrides?.[selectedEntity.wallId] || {}), [face]: {
        pattern: finish.id, asset_id: finish.asset_id || finish.id,
        s3_key: finish.s3_key, texture_url: finish.url, normal,
      } } }
      return draft
    })
    setDraftDesign((draft) => updateWallById(draft, selectedEntity.wallId, (wall) => {
      wall.material_overrides = { ...(wall.material_overrides || {}), [face]: {
        pattern: finish.id,
        asset_id: finish.asset_id || finish.id,
        s3_key: finish.s3_key,
        texture_url: finish.url,
        normal,
      } }
    }))
    if (!selectedEditRoom || !selectedEntity?.wallSide) return
    setDraftDesign((draft) => updateRoomById(draft, selectedEditRoom.id, (room) => {
      const pattern = finish.pattern || finish.id
      room.materials = {
        ...(room.materials || {}),
        accent_wall: {
          pattern,
          color: finish.color,
          side: selectedEntity.wallSide,
          asset_id: finish.asset_id || finish.id,
          s3_key: finish.s3_key,
          texture_url: finish.url,
        },
      }
      room.pbr_material = {
        ...(room.pbr_material || {}),
        accent_wall: {
          pattern,
          color: finish.color,
          side: selectedEntity.wallSide,
          asset_id: finish.asset_id || finish.id,
          s3_key: finish.s3_key,
          texture_url: finish.url,
        },
      }
    }))
  }

  const setSelectedGroundFinish = async (finish) => {
    if (!finish) return
    if (finish.kind === 'model' && finish.model_path) {
      const hit = selectedEntity?.hitPoint || {}
      const id = `${finish.id}_ground_${Date.now()}`
      const item = {
        id,
        name: finish.name,
        category: finish.category || 'outdoor',
        asset: finish.category || 'outdoor',
        asset_id: finish.asset_id || finish.id,
        model_id: finish.id,
        model_path: finish.model_path,
        s3_key: finish.s3_key,
        room_id: 'exterior_ground',
        position: { x: Number(hit.x) || 0, y: Number.isFinite(Number(hit.z)) ? -Number(hit.z) : 0, z: 0 },
        rotation: 0,
        dimensions: { ...finish.dimensions },
        client_edited_3d: true,
        placement_hint: 'user_exact',
      }
      setDraftDesign((draft) => addExteriorAsset(draft, item))
      setSelectedEntity({ type: 'furniture', id, roomId: 'exterior_ground', object: null, source: 'blender' })
      return
    }
    if (finish.kind !== 'texture') return
    finish = await applyTextureToObject(selectedEntity?.object, finish, 3.5, replaceUploadedAsset)
    if (!finish) return
    setDraftDesign((draft) => {
      draft.exterior = {
        ...(draft.exterior || {}),
        ground_finish: {
          pattern: finish.id,
          asset_id: finish.asset_id || finish.id,
          s3_key: finish.s3_key,
          texture_url: finish.url,
        },
      }
      return draft
    })
  }

  const addSelectedWallDecor = (decor) => {
    if (!selectedEditRoom || !decor) return
    setTransformMode('translate')
    if (decor.group === 'ceiling_asset') {
      if (!['ceiling', 'library'].includes(selectedEntity?.type)) return
      const p = selectedEditRoom.position || {}
      const d = selectedEditRoom.dimensions || {}
      const id = `${decor.id}_${selectedEditRoom.id}_${Date.now()}`
      const height = Number(decor.dimensions?.height) || 0.6
      const item = {
        id, name: decor.name, category: decor.category, asset: decor.category,
        asset_id: decor.id, model_id: decor.id, model_path: decor.model_path,
        s3_key: decor.s3_key, room_id: selectedEditRoom.id, asset_group: decor.group,
        canonical_yaw_offset_deg: decor.canonical_yaw_offset_deg || 0,
        canonical_pitch_offset_deg: decor.canonical_pitch_offset_deg || 0,
        ceiling_mounted: true, client_edited_3d: true, placement_hint: 'user_exact',
        dimensions: { ...decor.dimensions }, rotation: 0,
        position: {
          x: selectedEntity.hitPoint?.x ?? (Number(p.x) || 0) + (Number(d.width) || 4) / 2,
          y: selectedEntity.hitPoint?.z !== undefined ? -selectedEntity.hitPoint.z : (Number(p.y) || 0) + (Number(d.depth) || 4) / 2,
          z: (Number(p.z) || 0) + (Number(d.height) || 3) - height - 0.06,
        },
      }
      setDraftDesign((draft) => addFurnitureToRoom(draft, selectedEditRoom.id, item))
      setSelectedEntity({ type: 'furniture', id, roomId: selectedEditRoom.id, object: null, source: 'blender' })
      return
    }
    if (!selectedEntity?.wallSide) return
    const roomPosition = selectedEditRoom.position || {}
    const roomDimensions = selectedEditRoom.dimensions || {}
    const roomX = Number(roomPosition.x) || 0
    const roomY = Number(roomPosition.y) || 0
    const elevation = Number(roomPosition.z) || 0
    const width = Number(roomDimensions.width ?? selectedEditRoom.width) || 1
    const depth = Number(roomDimensions.depth ?? selectedEditRoom.length) || 1
    const side = selectedEntity.wallSide
    const offset = 0.12 + (Number(decor.dimensions?.depth) || 0.08) / 2
    const hitPoint = selectedEntity.hitPoint || {}
    const hitX = Number(hitPoint.x)
    const hitY = Number(hitPoint.y)
    const hitZ = Number(hitPoint.z)
    const decorWidth = Number(decor.dimensions?.width) || 0.8
    const decorHeight = Number(decor.dimensions?.height) || 0.8
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value))
    const horizontalPadding = decorWidth / 2 + 0.08
    const desiredX = Number.isFinite(hitX) ? hitX : roomX + width / 2
    const desiredY = Number.isFinite(hitZ) ? -hitZ : roomY + depth / 2
    const usesX = side === 'front' || side === 'back'
    const minimum = (usesX ? roomX : roomY) + horizontalPadding
    const maximum = (usesX ? roomX + width : roomY + depth) - horizontalPadding
    let safeCoordinate = clamp(usesX ? desiredX : desiredY, minimum, maximum)
    const openings = (decor.group === 'curtain' ? [] : [...doors, ...windows]).filter((opening) => (
      String(opening?.wall_id || '') === String(selectedEntity.wallId || '')
      || (
        String(opening?.room_id || opening?.roomId || '') === String(selectedEditRoom.id)
        && String(opening?.wall_side || '').toLowerCase() === String(side).toLowerCase()
      )
    ))
    openings.forEach((opening) => {
      const center = usesX ? Number(opening?.position?.x) : Number(opening?.position?.y)
      if (!Number.isFinite(center)) return
      const clearance = (Number(opening.width) || 0.9) / 2 + decorWidth / 2 + 0.12
      if (Math.abs(safeCoordinate - center) >= clearance) return
      const before = center - clearance
      const after = center + clearance
      const candidates = [before, after].filter((value) => value >= minimum && value <= maximum)
      if (candidates.length > 0) {
        safeCoordinate = candidates.sort((a, b) => Math.abs(a - safeCoordinate) - Math.abs(b - safeCoordinate))[0]
      }
    })
    const placement = {
      front: { x: safeCoordinate, y: roomY + depth - offset, rotation: 0, anchorWall: 'south' },
      back: { x: safeCoordinate, y: roomY + offset, rotation: 180, anchorWall: 'north' },
      left: { x: roomX + offset, y: safeCoordinate, rotation: 270, anchorWall: 'west' },
      right: { x: roomX + width - offset, y: safeCoordinate, rotation: 90, anchorWall: 'east' },
    }[side]
    if (!placement) return
    const id = `${decor.id}_${selectedEditRoom.id}_${Date.now()}`
    const item = {
      id,
      name: decor.name,
      category: decor.id,
      asset: decor.id,
      asset_id: decor.asset_id || decor.id,
      model_id: decor.id,
      model_path: decor.model_path,
      s3_key: decor.s3_key,
      canonical_yaw_offset_deg: decor.canonical_yaw_offset_deg || 0,
      canonical_pitch_offset_deg: decor.canonical_pitch_offset_deg || 0,
      mounting: decor.mounting,
      wall_orientation_version: decor.mounting?.orientation_version || 0,
      asset_group: decor.group,
      room_id: selectedEditRoom.id,
      position: { x: placement.x, y: placement.y, z: elevation },
      rotation: wallMountRotation(side, selectedEntity.surfaceNormal, placement.rotation),
      rotation_y: wallMountRotation(side, selectedEntity.surfaceNormal, placement.rotation),
      dimensions: { ...decor.dimensions },
      color: decor.color,
      wall_mounted: true,
      client_edited_3d: true,
      mount_height: Number.isFinite(hitY)
        ? clamp(hitY - elevation - decorHeight / 2, 0.2, Math.max(0.2, (Number(roomDimensions.height) || 3) - decorHeight - 0.15))
        : 1.25,
      placement_hint: 'wall_exact',
      anchor_wall: placement.anchorWall,
      wall_side: side,
      wall_normal: wallMountNormal(side, selectedEntity.surfaceNormal),
      wall_anchor: Number.isFinite(hitX) && Number.isFinite(hitZ) ? { x: hitX, y: -hitZ } : null,
      wall_id: selectedEntity.wallId || `${selectedEditRoom.id}:${side}`,
    }
    item.position = clampFurniturePosition(item, selectedEditRoom, item.position)
    setDraftDesign((draft) => addFurnitureToRoom(draft, selectedEditRoom.id, item))
    setSelectedEntity({ type: 'furniture', id, roomId: selectedEditRoom.id, object: null, source: 'blender' })
  }

  const commitGizmoTransform = () => {
    const object = selectedEntity?.object
    if (!object || !selectedFurniture || !selectedEditRoom) return
    setTransformRevision((rev) => rev + 1)
    if (selectedEntity.source === 'blender') {
      const transform = blenderObjectDraftTransform(object)
      if (transform) updateSelectedFurniture(transform)
      return
    }
    const roomPosition = selectedEditRoom.position || {}
    const roomDimensions = selectedEditRoom.dimensions || {}
    const roomWidth = Number(roomDimensions.width ?? selectedEditRoom.width) || 1
    const roomDepth = Number(roomDimensions.depth ?? selectedEditRoom.length) || 1
    const centerX = (Number(roomPosition.x) || 0) + roomWidth / 2
    const centerZ = (Number(roomPosition.y) || 0) + roomDepth / 2
    const elevation = Number(roomPosition.z) || 0
    const rotation = normalizeDegrees(-THREE.MathUtils.radToDeg(object.rotation.y))
    const isWallMounted = selectedFurniture.wall_mounted === true
    const nextPosition = clampFurniturePosition(
      { ...selectedFurniture, rotation },
      selectedEditRoom,
      {
        x: centerX + object.position.x,
        y: centerZ + object.position.z,
        z: isWallMounted ? elevation : elevation + Math.max(0, object.position.y),
      },
    )
    updateSelectedFurniture({
      position: nextPosition,
      rotation,
      rotation_y: rotation,
      ...(isWallMounted ? { mount_height: Math.max(0, object.position.y) } : {}),
    })
  }

  // Real 3D detected room floor slabs and doors from loaded GLB

  const editableFurniture = useMemo(() => {
    const unique = new Map()
    const add = (items) => {
      if (!Array.isArray(items)) return
      items.forEach((item) => {
        if (item?.id && !unique.has(item.id)) unique.set(item.id, item)
      })
    }
    design?.floors?.forEach((floor) => add(floor?.furniture))
    add(design?.furniture)
    design?.rooms?.forEach((room) => add(room?.furniture))
    add(design?.exterior?.assets)
    const urlByKey = new Map(uploadedAssets.map((asset) => [asset.s3_key, asset.model_path]))
    const deleted = new Set(hiddenBlenderFurnitureIds.map(String))
    return [...unique.values()].filter((item) => !deleted.has(String(item.id))).map((item) => (
      item?.s3_key && urlByKey.get(item.s3_key)
        ? { ...item, model_path: urlByKey.get(item.s3_key),
          canonical_yaw_offset_deg: uploadedAssets.find((a) => a.s3_key === item.s3_key)?.canonical_yaw_offset_deg || 0,
          canonical_pitch_offset_deg: uploadedAssets.find((a) => a.s3_key === item.s3_key)?.canonical_pitch_offset_deg || 0,
          mounting: uploadedAssets.find((a) => a.s3_key === item.s3_key)?.mounting }
        : item
    )).map((item) => {
      const room = findRoomById(design, item.room_id || item.roomId)
      if (item.wall_mounted) return alignWallFurniture(item, room,
        uploadedAssets.find((asset) => asset.s3_key === item.s3_key || asset.id === item.asset_id || asset.id === item.model_id))
      return item.ceiling_mounted && room ? { ...item, position: ceilingMountedPosition(item, room) } : item
    })
  }, [design, uploadedAssets, hiddenBlenderFurnitureIds])

  // Helper to get true 3D room position and bounds (from real GLB meshes if available)
  const getRoom3DPosition = useCallback((room) => {
    const floorHeight = Number(design?.building?.floor_height ?? design?.house?.floorHeight) || 3
    return roomPlacement(room, detectedRooms, floorHeight, viewSource === 'blender' ? -1 : 1)
  }, [detectedRooms, design?.building?.floor_height, design?.house?.floorHeight, viewSource])

  // Pre-cached navigation rooms for instant collision detection without per-frame recomputation
  const navigationRooms = useMemo(() => {
    const floorHeight = Number(design?.building?.floor_height ?? design?.house?.floorHeight) || 3
    return rooms.map((room) => roomPlacement(room, detectedRooms, floorHeight, viewSource === 'blender' ? -1 : 1))
  }, [rooms, detectedRooms, design?.building?.floor_height, design?.house?.floorHeight, viewSource])

  // When real GLB 3D rooms are detected, re-sync character position to active selected room
  useEffect(() => {
    if (detectedRooms.length > 0 && selectedRoomId && selectedRoomId !== 'overview') {
      const room = rooms.find((r) => r.id === selectedRoomId)
      if (room) {
        const pos = getRoom3DPosition(room)
        setCharPos({ x: pos.x, y: pos.y + 0.1, z: pos.z })
        setCharFloorLevel(pos.level)
      }
    }
  }, [detectedRooms, selectedRoomId, rooms, getRoom3DPosition])

  // Collect all doors across design (GLB 3D doors + top-level + per-room) for doorway passage detection
  const allDoors = useMemo(() => {
    return normalizeNavigationDoors({ doors, detected: detectedDoors, rooms,
      zSign: viewSource === 'blender' ? -1 : 1,
      floorHeight: Number(design?.building?.floor_height) || 3 })
  }, [doors, rooms, detectedDoors, viewSource, design?.building?.floor_height])

  const navigationModel = useMemo(() => {
    const floorWalls = (design?.floors || []).flatMap((floor) => (floor.walls || []).map((wall) => ({
      ...wall, floor_level: wall.floor_level ?? floor.level ?? 0,
    })))
    return createNavigationModel({ rooms: navigationRooms, doors: allDoors,
      walls: floorWalls.length ? floorWalls : design?.walls || [],
      zSign: viewSource === 'blender' ? -1 : 1,
      wallThickness: Number(design?.building?.wall_thickness) || 0.2,
      exteriorAccess: isExteriorAccessWalkable })
  }, [navigationRooms, allDoors, design?.floors, design?.walls, design?.building?.wall_thickness, isExteriorAccessWalkable, viewSource])

  // House bounding box for initial & overview framing
  const houseBounds = useMemo(() => {
    if (rooms.length === 0 && detectedRooms.length === 0) {
      return { cx: 0, cz: 0, w: 24, l: 24, maxDim: 22, maxZ: 6 }
    }
    let minX = Infinity, maxX = -Infinity, minZ = Infinity, maxZ = -Infinity

    if (detectedRooms.length > 0) {
      detectedRooms.forEach((d) => {
        const hw = d.size.x / 2
        const hl = d.size.z / 2
        minX = Math.min(minX, d.center.x - hw)
        maxX = Math.max(maxX, d.center.x + hw)
        minZ = Math.min(minZ, d.center.z - hl)
        maxZ = Math.max(maxZ, d.center.z + hl)
      })
    } else {
      rooms.forEach((r) => {
        const pos = getRoom3DPosition(r)
        const rx = pos.x
        const rz = pos.z
        const rw = pos.w / 2
        const rl = pos.l / 2
        minX = Math.min(minX, rx - rw)
        maxX = Math.max(maxX, rx + rw)
        minZ = Math.min(minZ, rz - rl)
        maxZ = Math.max(maxZ, rz + rl)
      })
    }

    const w = maxX - minX
    const l = maxZ - minZ
    const cx = (minX + maxX) / 2
    const cz = (minZ + maxZ) / 2
    const maxDim = Math.max(w, l + 12, 24)
    return { cx, cz, w, l, maxDim, minX, maxX, minZ, maxZ }
  }, [rooms, detectedRooms, getRoom3DPosition])

  // Find active room bounds
  const currentRoom = useMemo(() => {
    return rooms.find((r) => r.id === selectedRoomId) || rooms[0] || null
  }, [rooms, selectedRoomId])

  // Character movement state
  const [charPos, setCharPos] = useState({ x: 0, y: 0.1, z: 0 })
  const charPosRef = useRef({ x: 0, y: 0.1, z: 0 })
  const [charFloorLevel, setCharFloorLevel] = useState(0)
  const [charRot, setCharRot] = useState(0)
  const [isMoving, setIsMoving] = useState(false)
  const [walkCycle, setWalkCycle] = useState(0)
  const keysRef = useRef({ w: false, a: false, s: false, d: false })

  // Mouse look state & angles
  const [isMouseLookLocked, setIsMouseLookLocked] = useState(false)
  const isMouseLockedRef = useRef(false)
  const yawRef = useRef(0)
  const pitchRef = useRef(0)
  const eyeHeightRef = useRef(1.65)
  const initializedLayoutRef = useRef(null)
  const framingLayoutKey = useMemo(() => JSON.stringify({
    model: modelIdentity(glbUrl),
    rooms: rooms.map((room) => [room.id, room.position || room.bounds, room.dimensions || room.bounds]),
    detected: detectedRooms.map((room) => [room.roomId, room.center, room.size]),
  }), [glbUrl, rooms, detectedRooms])

  // Toggle pointer lock for mouse look
  const toggleMouseLook = useCallback(() => {
    if (viewMode !== 'walkthrough' || isEditing3D) return
    if (!document.pointerLockElement) {
      containerRef.current?.requestPointerLock?.()
    } else {
      document.exitPointerLock?.()
    }
  }, [viewMode, isEditing3D])

  // Pointer lock change listener
  useEffect(() => {
    const handlePointerLockChange = () => {
      const isLocked = document.pointerLockElement === containerRef.current
      setIsMouseLookLocked(isLocked)
      isMouseLockedRef.current = isLocked
      if (controlsRef.current) {
        controlsRef.current.enableRotate = !isLocked
        if (isLocked) {
          const direction = controlsRef.current.object.getWorldDirection(new THREE.Vector3())
          yawRef.current = Math.atan2(direction.x, -direction.z)
          pitchRef.current = Math.asin(THREE.MathUtils.clamp(direction.y, -1, 1))
        }
      }
    }
    document.addEventListener('pointerlockchange', handlePointerLockChange)
    return () => document.removeEventListener('pointerlockchange', handlePointerLockChange)
  }, [])

  // Mouse move handler for look direction
  useEffect(() => {
    const onMouseMove = (e) => {
      if (!isMouseLockedRef.current || viewMode !== 'walkthrough' || isEditing3D) return

      const sensitivity = LOOK_SENSITIVITY
      yawRef.current += e.movementX * sensitivity
      pitchRef.current -= e.movementY * sensitivity

      const maxPitch = 1.35
      pitchRef.current = Math.max(-maxPitch, Math.min(maxPitch, pitchRef.current))

      if (controlsRef.current?.object) {
        const cam = controlsRef.current.object
        cam.position.y = eyeHeightRef.current
        const cosPitch = Math.cos(pitchRef.current)
        const sinPitch = Math.sin(pitchRef.current)
        const cosYaw = Math.cos(yawRef.current)
        const sinYaw = Math.sin(yawRef.current)

        const lookDir = new THREE.Vector3(
          sinYaw * cosPitch,
          sinPitch,
          -cosYaw * cosPitch
        )

        const lookTarget = cam.position.clone().add(lookDir.multiplyScalar(2.0))
        cam.lookAt(lookTarget)
        controlsRef.current.target.copy(lookTarget)
        targetPos.current.copy(lookTarget)
        targetCamPos.current.copy(cam.position)
      }
    }

    window.addEventListener('mousemove', onMouseMove)
    return () => window.removeEventListener('mousemove', onMouseMove)
  }, [isEditing3D, viewMode, toggleMouseLook])

  // Initialize and auto-frame complete house
  useEffect(() => {
    if (initializedLayoutRef.current === framingLayoutKey) return
    initializedLayoutRef.current = framingLayoutKey
    if (viewMode === 'walkthrough') return
    if (rooms.length > 0) {
      const first = rooms[0]
      const firstPosition = getRoom3DPosition(first)
      setCharPos({ x: firstPosition.x, y: firstPosition.y + 0.1, z: firstPosition.z })
      charPosRef.current = { x: firstPosition.x, y: firstPosition.y + 0.1, z: firstPosition.z }
      setCharFloorLevel(firstPosition.level)
      setSelectedRoomId('overview')

      const { cx, cz, maxDim } = houseBounds
      targetPos.current.set(cx, 1.0, cz + 2.0)
      targetCamPos.current.set(cx + maxDim * 0.95, maxDim * 1.05, cz + maxDim * 1.15)
    }
  }, [framingLayoutKey, rooms, houseBounds, getRoom3DPosition, viewMode])

  // Keyboard navigation & Ctrl key for mouse toggle
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.target?.closest?.('input, textarea, select, [contenteditable="true"]')) return
      if (e.key === 'Control') {
        if (isEditing3D) return
        e.preventDefault()
        toggleMouseLook()
        return
      }

      const k = e.key.toLowerCase()
      if (['w', 'arrowup'].includes(k)) keysRef.current.w = true
      if (['s', 'arrowdown'].includes(k)) keysRef.current.s = true
      if (['a', 'arrowleft'].includes(k)) keysRef.current.a = true
      if (['d', 'arrowright'].includes(k)) keysRef.current.d = true
    }
    const onKeyUp = (e) => {
      const k = e.key.toLowerCase()
      if (['w', 'arrowup'].includes(k)) keysRef.current.w = false
      if (['s', 'arrowdown'].includes(k)) keysRef.current.s = false
      if (['a', 'arrowleft'].includes(k)) keysRef.current.a = false
      if (['d', 'arrowright'].includes(k)) keysRef.current.d = false
    }
    const onBlur = () => { keysRef.current = { w: false, a: false, s: false, d: false } }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    window.addEventListener('blur', onBlur)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
      window.removeEventListener('blur', onBlur)
    }
  }, [isEditing3D, viewMode, toggleMouseLook])

  // High-performance movement loop with delta time, wall sliding, and zero React re-renders in walkthrough
  useEffect(() => {
    let animId
    let lastTime = performance.now()
    let isMovingLocal = false

    const update = () => {
      const now = performance.now()
      const delta = Math.min((now - lastTime) / 1000, 0.08)
      lastTime = now

      const { w, a, s, d } = keysRef.current
      const hasInput = !isEditing3D && (w || s || a || d)

      if (hasInput) {
        if (!isMovingLocal) {
          isMovingLocal = true
          setIsMoving(true)
        }

        if (viewMode === 'walkthrough' && controlsRef.current?.object) {
          const cam = controlsRef.current.object
          const speed = WALK_SPEED * delta

          const forward = new THREE.Vector3()
          cam.getWorldDirection(forward)
          forward.y = 0
          forward.normalize()

          const right = new THREE.Vector3().crossVectors(forward, new THREE.Vector3(0, 1, 0)).normalize()

          const move = new THREE.Vector3(0, 0, 0)
          if (w) move.add(forward)
          if (s) move.sub(forward)
          if (d) move.add(right)
          if (a) move.sub(right)

          if (move.lengthSq() > 0) {
            move.normalize().multiplyScalar(speed)

            const curCamX = cam.position.x
            const curCamZ = cam.position.z
            const { x: finalX, z: finalZ } = moveWithCollisions(navigationModel, curCamX, curCamZ, move.x, move.z, charFloorLevel)

            if (finalX !== curCamX || finalZ !== curCamZ) {
              const dx = finalX - curCamX
              const dz = finalZ - curCamZ
              cam.position.x = finalX
              cam.position.z = finalZ
              cam.position.y = eyeHeightRef.current
              controlsRef.current.target.x += dx
              controlsRef.current.target.z += dz
              targetCamPos.current.copy(cam.position)
              targetPos.current.copy(controlsRef.current.target)

              charPosRef.current.x = finalX
              charPosRef.current.y = eyeHeightRef.current - 1.55
              charPosRef.current.z = finalZ
            }
          }
        } else {
          // 3rd-person avatar movement (only when avatar is visible in dollhouse / topdown)
          const speed = WALK_SPEED * delta
          setWalkCycle((c) => c + delta * 8.5)

          let moveX = 0
          let moveZ = 0
          if (w) moveZ -= speed
          if (s) moveZ += speed
          if (a) moveX -= speed
          if (d) moveX += speed

          if (moveX !== 0 || moveZ !== 0) {
            const targetRot = Math.atan2(moveX, moveZ) + Math.PI
            setCharRot(targetRot)

            setCharPos((prev) => {
              const length = Math.hypot(moveX, moveZ)
              const { x: nextX, z: nextZ } = moveWithCollisions(navigationModel, prev.x, prev.z,
                moveX / length * speed, moveZ / length * speed, charFloorLevel)
              if (nextX !== prev.x || nextZ !== prev.z) {
                targetPos.current.set(nextX, prev.y + 1.0, nextZ)
                charPosRef.current = { x: nextX, y: prev.y, z: nextZ }
                return { x: nextX, y: prev.y, z: nextZ }
              }
              return prev
            })
          }
        }
      } else {
        if (isMovingLocal) {
          isMovingLocal = false
          setIsMoving(false)
          // Sync charPos to React state once on movement stop so avatar is accurate
          setCharPos({ ...charPosRef.current })
        }
      }

      animId = requestAnimationFrame(update)
    }

    animId = requestAnimationFrame(update)
    return () => cancelAnimationFrame(animId)
  }, [navigationModel, viewMode, charFloorLevel, isEditing3D])

  // Select room camera jump (jumps directly into the true 3D room center)
  const handleSelectRoom = (room) => {
    if (isEditing3D && selectedEntity?.type === 'library') { openAssetLibrary(room.id); return }
    setSelectedRoomId(room.id)
    const pos = getRoom3DPosition(room)
    const rx = pos.x
    const ry = pos.y
    const rz = pos.z
    setActiveFloorLevel(pos.level)
    setCharFloorLevel(pos.level)
    const p = { x: rx, y: ry + 0.1, z: rz }
    charPosRef.current = p
    setCharPos(p)

    if (viewMode === 'walkthrough') {
      yawRef.current = 0
      pitchRef.current = 0
      targetCamPos.current.set(rx, ry + 1.65, rz + 0.2)
      targetPos.current.set(rx, ry + 1.6, rz - 2.0)
      eyeHeightRef.current = ry + 1.65
      if (controlsRef.current) {
        controlsRef.current.object.position.set(rx, ry + 1.65, rz + 0.2)
        controlsRef.current.target.set(rx, ry + 1.6, rz - 2.0)
        controlsRef.current.update()
      }
    } else if (viewMode === 'plan') {
      targetPos.current.set(rx, ry, rz)
      targetCamPos.current.set(rx, ry + 22, rz + 0.01)
    } else {
      targetPos.current.set(rx, ry + 1.0, rz)
      targetCamPos.current.set(rx + 8, ry + 9, rz + 9)
    }
  }

  const openAssetLibrary = (requestedRoomId) => {
    const camera = controlsRef.current?.object
    const cameraRoom = camera && navigationRooms.find((entry) => entry.level === charFloorLevel
      && Math.abs(camera.position.x - entry.x) < entry.w / 2
      && Math.abs(camera.position.z - entry.z) < entry.l / 2)
    const room = rooms.find((entry) => String(entry.id) === String(requestedRoomId || cameraRoom?.id || selectedRoomId)) || rooms[0]
    if (!room) return
    const normalized = placementRoom(room, detectedRooms)
    const pos = getRoom3DPosition(room)
    setPendingPlacement(null)
    setIsTransforming(false)
    setSelectedRoomId(room.id)
    setSelectedEntity({ type: 'library', id: `library:${room.id}`, roomId: room.id })
    libraryFloorChange.current = { level: pos.level, roomId: room.id }
    setActiveFloorLevel(pos.level)
    setCharFloorLevel(pos.level)
    setViewMode('walkthrough')
    keysRef.current = { w: false, a: false, s: false, d: false }
    const view = placementCameraView(normalized)
    eyeHeightRef.current = view.position[1]
    charPosRef.current = { x: view.position[0], y: view.position[1] - 1.55, z: view.position[2] }
    setCharPos({ ...charPosRef.current })
    setRoomTransition({ id: ++placementSequence.current, roomId: room.id, ...view })
  }

  // View mode switcher
  const handleModeChange = (mode) => {
    if (mode !== 'walkthrough' && document.pointerLockElement) {
      document.exitPointerLock?.()
    }
    setViewMode(mode)
    const { cx, cz, maxDim } = houseBounds

    if (mode === 'plan') {
      targetPos.current.set(cx, 0, cz + 2.0)
      targetCamPos.current.set(cx, maxDim * 1.8, cz + 2.01)
      if (controlsRef.current) {
        controlsRef.current.maxDistance = 120
      }
    } else if (mode === 'dollhouse') {
      targetPos.current.set(cx, 1.0, cz + 2.0)
      targetCamPos.current.set(cx + maxDim * 0.95, maxDim * 1.05, cz + maxDim * 1.15)
      if (controlsRef.current) {
        controlsRef.current.minDistance = 2
        controlsRef.current.maxDistance = 95
      }
    } else if (mode === 'front') {
      targetPos.current.set(cx, maxDim * 0.18, cz)
      targetCamPos.current.set(cx, maxDim * 0.35, cz + maxDim * 1.1)
      if (controlsRef.current) {
        controlsRef.current.minDistance = 2
        controlsRef.current.maxDistance = 120
      }
    } else if (mode === 'back') {
      targetPos.current.set(cx, maxDim * 0.18, cz)
      targetCamPos.current.set(cx, maxDim * 0.35, cz - maxDim * 1.1)
      if (controlsRef.current) {
        controlsRef.current.minDistance = 2
        controlsRef.current.maxDistance = 120
      }
    } else if (mode === 'roof') {
      targetPos.current.set(cx, maxDim * 0.12, cz)
      targetCamPos.current.set(cx + maxDim * 0.45, maxDim * 1.45, cz + maxDim * 0.55)
      if (controlsRef.current) {
        controlsRef.current.minDistance = 2
        controlsRef.current.maxDistance = 140
      }
    } else if (mode === 'walkthrough') {
      yawRef.current = 0
      pitchRef.current = 0
      const cur = currentRoom || rooms[0]
      const pos = getRoom3DPosition(cur)
      const rx = pos.x
      const ry = pos.y
      const rz = pos.z
      const p = { x: rx, y: ry + 0.1, z: rz }
      charPosRef.current = p
      setCharPos(p)

      targetCamPos.current.set(rx, ry + 1.65, rz + 0.2)
      targetPos.current.set(rx, ry + 1.6, rz - 2.0)
      eyeHeightRef.current = ry + 1.65

      if (controlsRef.current) {
        controlsRef.current.object.position.set(rx, ry + 1.65, rz + 0.2)
        controlsRef.current.target.set(rx, ry + 1.6, rz - 2.0)
        controlsRef.current.minDistance = 0.1
        controlsRef.current.maxDistance = 6.0
        controlsRef.current.update()
      }
    }
  }

  // Fullscreen handler
  const toggleFullscreen = () => {
    if (!containerRef.current) return
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {})
      setIsFullscreen(true)
    } else {
      document.exitFullscreen().catch(() => {})
      setIsFullscreen(false)
    }
  }

  // Reset Camera to complete house view
  const handleResetCamera = () => {
    setSelectedRoomId('overview')
    handleModeChange(viewMode)
  }

  return (
    <ViewerStage
      state={{
        containerRef, isFullscreen, isNightMode, viewMode, planSubMode, design,
        approveFloorPlan, activeProjectId, activeVersionId, isApprovingLayout,
        handleSelectRoom, selectedRoomId, glbUrl, viewSource, modelReloadKey,
        handleBlenderError, handleReloadSavedModel, setDetectedRooms, setDetectedDoors,
        setIsModelRendered, showRoof, activeFloorLevel, visibleRooms, visibleDoors,
        visibleWindows, dismissedSynthesisPrompt, setDismissedSynthesisPrompt,
        isGenerating3D, regenerate3D, charPos, charRot, isMoving, walkCycle,
        controlsRef, targetPos, targetCamPos, isModelRendered, handleModeChange,
        setViewSource, showCallouts, setShowCallouts, isMouseLookLocked,
        toggleMouseLook, setIsNightMode, handleResetCamera, toggleFullscreen,
        rooms, doors, windows, isApproved, toggleShowRoof, setActiveFloorLevel,
        floors, setPlanSubMode, charFloorLevel,
        isEditing3D, toggleEditing3D, selectedEntity, setSelectedEntity,
        handleSelectEntity, handleSelectionObjectReady, selectedFurniture,
        selectedEditRoom, transformMode, setTransformMode, isTransforming,
        setIsTransforming, transformRevision, commitGizmoTransform, nudgeSelectedFurniture,
        constrainGizmoTransform, resizeSelectedFurniture,
        rotateSelectedFurniture, swapSelectedFurniture, duplicateSelectedFurniture,
        addModelAsNewFurniture, deleteSelectedFurniture,
        pendingPlacement, cancelPlacement, confirmPlacement, onPlacementStatus,
        roomTransition, onRoomTransitionComplete, openAssetLibrary,
        adjustPlacement,
        setSelectedFloorFinish, setSelectedWallFinish,
        setSelectedGroundFinish, uploadedAssets,
        isDirty,
        navigationModel,
        setSelectedFurnitureColor, editableFurniture, hiddenBlenderFurnitureIds,
        addSelectedWallDecor,
      }}
    />
  )
}
