import { Suspense } from 'react'
import * as THREE from 'three'
import { Environment, Html, OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Loader2, Sparkles } from 'lucide-react'

import { CharacterAvatar, CameraController } from './CharacterAvatar'
import { BlenderErrorBoundary, BlenderHouseModel, BlenderLoadingFallback } from './BlenderModel'
import RoomVolume from './RoomVolume'
import ViewerOverlay from './ViewerOverlay'
import FloorPlanVectorViewer from '../FloorPlanVectorViewer'

export default function ViewerStage({ state }) {
  const {
    containerRef,
    isFullscreen,
    isNightMode,
    viewMode,
    planSubMode,
    design,
    approveFloorPlan,
    activeProjectId,
    activeVersionId,
    isApprovingLayout,
    handleSelectRoom,
    selectedRoomId,
    glbUrl,
    viewSource,
    modelReloadKey,
    handleBlenderError,
    handleReloadSavedModel,
    setDetectedRooms,
    setDetectedDoors,
    setIsModelRendered,
    showRoof,
    activeFloorLevel,
    visibleRooms,
    visibleDoors,
    visibleWindows,
    dismissedSynthesisPrompt,
    setDismissedSynthesisPrompt,
    isGenerating3D,
    regenerate3D,
    charPos,
    charRot,
    isMoving,
    walkCycle,
    controlsRef,
    targetPos,
    targetCamPos,
    isModelRendered,
    handleModeChange,
    setViewSource,
    showCallouts,
    setShowCallouts,
    isMouseLookLocked,
    toggleMouseLook,
    setIsNightMode,
    handleResetCamera,
    toggleFullscreen,
    rooms,
    doors,
    windows,
    isApproved,
    toggleShowRoof,
    setActiveFloorLevel,
    floors,
    setPlanSubMode,
    charFloorLevel,
  } = state

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        minHeight: 0,
        borderRadius: isFullscreen ? 0 : 'var(--radius-lg)',
        overflow: 'hidden',
        background: isNightMode ? '#070a10' : '#0b0f17',
        boxShadow: '0 12px 40px rgba(0,0,0,0.5)',
      }}
    >
      {/* 2D Vector CAD Floor Plan View */}
      {viewMode === 'plan' && planSubMode === 'vector' ? (
        <div style={{ position: 'absolute', inset: 0, zIndex: 1, overflow: 'hidden' }}>
          <FloorPlanVectorViewer
            design={design}
            onApproveLayout={() => approveFloorPlan(activeProjectId, activeVersionId)}
            isApproving={isApprovingLayout}
            onSelectRoom={handleSelectRoom}
            selectedRoomId={selectedRoomId}
          />
        </div>
      ) : (
        <Canvas
          shadows
          dpr={[1, 1.75]}
          camera={{ position: [22, 22, 28], fov: 44, near: 0.1, far: 350 }}
          gl={{
            antialias: true,
            logarithmicDepthBuffer: true,
            toneMapping: THREE.ACESFilmicToneMapping,
            toneMappingExposure: 1.1,
            outputColorSpace: THREE.SRGBColorSpace,
          }}
        >
          <color attach="background" args={[isNightMode ? '#060911' : '#0a0e17']} />

          <ambientLight intensity={isNightMode ? 0.35 : 0.75} color={isNightMode ? '#1e293b' : '#f8fafc'} />
          <hemisphereLight
            intensity={isNightMode ? 0.3 : 0.6}
            groundColor="#090d16"
            color={isNightMode ? '#334155' : '#e0f2fe'}
          />

          <directionalLight
            position={[28, 42, 24]}
            intensity={isNightMode ? 0.5 : 2.0}
            color={isNightMode ? '#93c5fd' : '#fffbeb'}
            castShadow
            shadow-mapSize-width={2048}
            shadow-mapSize-height={2048}
            shadow-camera-left={-45}
            shadow-camera-right={45}
            shadow-camera-top={45}
            shadow-camera-bottom={-45}
            shadow-bias={-0.00005}
            shadow-normalBias={0.03}
          />

          {/* ── Photorealistic Architectural House Model: Cloud Blender GLB ── */}
          {glbUrl && viewSource !== 'threejs' ? (
            <BlenderErrorBoundary
              key={`${glbUrl}:${modelReloadKey}`}
              onError={handleBlenderError}
              onRetry={handleReloadSavedModel}
            >
              <Suspense fallback={<BlenderLoadingFallback onRetry={handleReloadSavedModel} />}>
                <BlenderHouseModel
                  url={glbUrl}
                  onRoomsDetected={setDetectedRooms}
                  onDoorsDetected={setDetectedDoors}
                  onLoaded={() => setIsModelRendered(true)}
                  showRoof={showRoof}
                  activeFloorLevel={activeFloorLevel}
                />
              </Suspense>
            </BlenderErrorBoundary>
          ) : (
            <group>
              {visibleRooms.map((r, idx) => (
                <RoomVolume
                  key={r.id || idx}
                  room={r}
                  viewMode={viewMode}
                  isSelected={selectedRoomId === r.id}
                  isNightMode={isNightMode}
                  furniture={r.furniture}
                  doors={visibleDoors}
                  windows={visibleWindows}
                />
              ))}
            </group>
          )}

          {!glbUrl && !dismissedSynthesisPrompt && (
            <Html center style={{ pointerEvents: 'auto', transform: 'translate3d(-50%, -70px, 0)' }}>
              <div
                style={{
                  position: 'relative',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  padding: '24px 28px',
                  background: 'rgba(18, 18, 18, 0.95)',
                  border: '1px solid rgba(16, 163, 127, 0.4)',
                  borderRadius: 20,
                  boxShadow: '0 25px 60px rgba(0,0,0,0.8), 0 0 25px rgba(16, 163, 127, 0.15)',
                  backdropFilter: 'blur(28px)',
                  width: 340,
                  color: 'white',
                  pointerEvents: 'auto',
                }}
              >
                {/* Close / Dismiss button so user can inspect scene uninterrupted */}
                <button
                  type="button"
                  onClick={() => setDismissedSynthesisPrompt(true)}
                  title="Dismiss popup"
                  style={{
                    position: 'absolute',
                    top: 10,
                    right: 12,
                    background: 'transparent',
                    border: 'none',
                    color: 'rgba(255,255,255,0.45)',
                    fontSize: '1rem',
                    cursor: 'pointer',
                    padding: 4,
                  }}
                >
                  ✕
                </button>

                {isGenerating3D ? (
                  <>
                    <div
                      style={{
                        position: 'relative',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 56,
                        height: 56,
                        marginBottom: 14,
                      }}
                    >
                      <div
                        style={{
                          position: 'absolute',
                          inset: 0,
                          borderRadius: '50%',
                          border: '2px dashed rgba(16, 163, 127, 0.5)',
                          animation: 'spin 6s linear infinite',
                        }}
                      />
                      <Loader2 size={28} color="#10a37f" style={{ animation: 'spin 1.2s linear infinite' }} />
                    </div>
                    <div style={{ fontSize: '1.02rem', fontWeight: 700, marginBottom: 6, color: '#f8fafc' }}>
                      Synthesizing 3D Model…
                    </div>
                    <div style={{ fontSize: '0.80rem', color: 'rgba(255,255,255,0.75)', lineHeight: 1.5, marginBottom: 14 }}>
                      Cloud Blender is constructing walls, applying PBR textures, and placing 3D furniture.
                    </div>
                    <div
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '4px 12px',
                        background: 'rgba(16, 163, 127, 0.15)',
                        borderRadius: 999,
                        border: '1px solid rgba(16, 163, 127, 0.3)',
                        fontSize: '0.72rem',
                        color: '#10a37f',
                        fontWeight: 600,
                      }}
                    >
                      <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: '#10a37f', animation: 'pulse 1.5s infinite' }} />
                      EC2 Headless Blender Worker
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{ fontSize: '2.2rem', marginBottom: 10 }}>🏛️</div>
                    <div style={{ fontSize: '1.02rem', fontWeight: 700, marginBottom: 6 }}>
                      {design?.layout_approved || design?.approved_at
                        ? '3D Model Pending Synthesis'
                        : 'Floor Plan Ready for 3D Synthesis'}
                    </div>
                    <div style={{ fontSize: '0.80rem', color: 'rgba(255,255,255,0.72)', lineHeight: 1.45, marginBottom: 16 }}>
                      {design?.layout_approved || design?.approved_at
                        ? 'Layout is approved. Click below to trigger or re-run the 3D model builder in Blender.'
                        : 'Review the 2D floor plan or synthesize the complete multi-floor 3D model in Blender.'}
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        if (design?.layout_approved || design?.approved_at) {
                          regenerate3D(activeProjectId, activeVersionId)
                        } else {
                          approveFloorPlan(activeProjectId, activeVersionId)
                        }
                      }}
                      disabled={isApprovingLayout || isGenerating3D}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '10px 20px',
                        background: 'linear-gradient(135deg, #10a37f 0%, #0d8a6c 100%)',
                        border: '1px solid rgba(16, 163, 127, 0.5)',
                        borderRadius: 10,
                        color: '#ffffff',
                        fontSize: '0.86rem',
                        fontWeight: 600,
                        cursor: (isApprovingLayout || isGenerating3D) ? 'not-allowed' : 'pointer',
                        opacity: (isApprovingLayout || isGenerating3D) ? 0.7 : 1,
                        boxShadow: '0 4px 16px rgba(2, 132, 199, 0.5)',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      {(isApprovingLayout || isGenerating3D) ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                      <span>{design?.layout_approved ? 'Synthesize 3D Model' : 'Approve & Synthesize 3D'}</span>
                    </button>
                  </>
                )}
              </div>
            </Html>
          )}

          {/* Walkthrough Avatar (Hidden in first-person walkthrough to avoid blocking camera) */}
          <CharacterAvatar
            position={charPos}
            rotation={charRot}
            isMoving={isMoving}
            walkCycle={walkCycle}
            isVisible={
              viewMode !== 'walkthrough'
              && (activeFloorLevel === null || activeFloorLevel === undefined || activeFloorLevel === charFloorLevel)
            }
          />

          <CameraController controlsRef={controlsRef} targetPos={targetPos} targetCamPos={targetCamPos} viewMode={viewMode} />

          <OrbitControls
            ref={controlsRef}
            enabled={viewMode !== 'walkthrough'}
            enableDamping
            dampingFactor={0.08}
            minDistance={viewMode === 'walkthrough' ? 0.1 : 2}
            maxDistance={viewMode === 'walkthrough' ? 4.5 : 95}
            maxPolarAngle={viewMode === 'plan' ? 0.05 : Math.PI / 2.05}
          />
          <Environment preset={isNightMode ? 'night' : 'city'} />
        </Canvas>
      )}

      <ViewerOverlay
        viewMode={viewMode}
        onModeChange={handleModeChange}
        viewSource={viewSource}
        onViewSourceChange={setViewSource}
        glbUrl={glbUrl}
        isModelRendered={isModelRendered}
        isGenerating3D={isGenerating3D}
        onRegenerate3D={() => regenerate3D(activeProjectId, activeVersionId)}
        showCallouts={showCallouts}
        onToggleCallouts={() => setShowCallouts(!showCallouts)}
        isMouseLookLocked={isMouseLookLocked}
        onToggleMouseLook={toggleMouseLook}
        isNightMode={isNightMode}
        onToggleNightMode={() => setIsNightMode(!isNightMode)}
        onResetCamera={handleResetCamera}
        isFullscreen={isFullscreen}
        onToggleFullscreen={toggleFullscreen}
        rooms={rooms}
        doors={doors}
        windows={windows}
        design={design}
        isApproved={isApproved}
        selectedRoomId={selectedRoomId}
        onSelectRoom={handleSelectRoom}
        showRoof={showRoof}
        onToggleRoof={toggleShowRoof}
        activeFloorLevel={activeFloorLevel}
        onChangeFloorLevel={setActiveFloorLevel}
        floors={floors}
        planSubMode={planSubMode}
        onPlanSubModeChange={setPlanSubMode}
        onApproveLayout={() => approveFloorPlan(activeProjectId, activeVersionId)}
        isApprovingLayout={isApprovingLayout}
      />
    </div>
  )
}

