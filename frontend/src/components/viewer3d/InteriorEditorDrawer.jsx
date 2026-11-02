/* eslint-disable react/prop-types */
import { useEffect, useRef, useState } from 'react'
import {
  Box,
  ChevronDown,
  ChevronUp,
  Copy,
  Move,
  Paintbrush,
  RotateCcw,
  RotateCw,
  Trash2,
  X,
  Image,
  Layers3,
  Loader2,
} from 'lucide-react'

import { fetchUploadedAssetCatalog } from '../../services'
import { furnitureCategory } from '../../utils/designEditing'
import { isAssetRecommendedForRoom } from '../../utils/roomAssetLibrary'
import { assetSurface, compatibleOpening, tabletopSupports } from '../../utils/assetCompatibility'
import ModelThumbnail from './ModelThumbnail'

const FURNITURE_COLORS = ['#4A6FA5', '#668475', '#9b5f4b', '#8B7355', '#3f4650', '#d9d4ca']

function SectionTitle({ icon, children }) {
  return <h3 className="interior-editor-section-title">{icon}{children}</h3>
}

export default function InteriorEditorDrawer({
  selection,
  furniture,
  room,
  rooms = [],
  onLibraryRoomChange,
  canAccentColor = false,
  pendingPlacement,
  onCancelPlacement,
  onConfirmPlacement,
  onAdjustPlacement,
  onPlacementWallChange,
  onMountWallChange,
  transformMode,
  onTransformModeChange,
  onClose,
  onNudge,
  onRotate,
  onResize,
  onSwapModel,
  onSwapOpening,
  onDuplicate,
  onAddModelAsNew,
  onColorChange,
  onDelete,
  onFloorFinish,
  onGroundFinish,
  onWallFinish,
  onAddWallDecor,
  canFinalize3D,
  onFinalize3D,
}) {
  const [assets, setAssets] = useState([])
  const [catalogState, setCatalogState] = useState('loading')
  const [wallTab, setWallTab] = useState('finish')
  const [collapsed, setCollapsed] = useState(false)
  const [filtersExpanded, setFiltersExpanded] = useState(false)
  const [modelActionTab, setModelActionTab] = useState('swap')
  const [libraryCategory, setLibraryCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [placementSurface, setPlacementSurface] = useState('floor')
  const [supportId, setSupportId] = useState('')
  const [libraryScope, setLibraryScope] = useState('room')
  const confirmation = useRef(null)
  const placementId = pendingPlacement?.item.id
  useEffect(() => {
    if (placementId) confirmation.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [placementId])

  useEffect(() => {
    let cancelled = false
    setCatalogState('loading')
    fetchUploadedAssetCatalog()
      .then((data) => {
        if (cancelled) return
        setAssets(Array.isArray(data?.assets) ? data.assets : [])
        setCatalogState('ready')
      })
      .catch(() => {
        if (!cancelled) setCatalogState('error')
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => setWallTab(['window', 'door'].includes(selection?.type) ? 'opening' : 'finish'), [selection?.id, selection?.type])
  useEffect(() => setModelActionTab('swap'), [selection?.id])
  useEffect(() => {
    setLibraryCategory('all')
    setPlacementSurface('floor')
    setSupportId('')
    setLibraryScope('room')
    setSearch('')
  }, [selection?.roomId])

  if (!selection) return null
  const isFurniture = selection.type === 'furniture'
  const isFloor = selection.type === 'floor'
  const isGround = selection.type === 'ground'
  const category = isFurniture ? furnitureCategory(furniture) : ''
  const variants = furniture?.wall_mounted && category !== 'shower'
    ? assets.filter((entry) => furniture.asset_group ? entry.group === furniture.asset_group : entry.group === 'wall_decor' || entry.group === 'wall_panel')
    : furniture?.ceiling_mounted
      ? assets.filter((entry) => entry.group === 'ceiling_asset')
    : furniture?.room_id === 'exterior_ground'
      ? assets.filter((entry) => entry.group === 'ground_decor')
      : assets.filter((entry) => entry.group === 'furniture' && entry.category === category)
  const floorFinishes = assets.filter((entry) => entry.group === (isGround ? 'ground_finish' : 'floor_finish'))
  const floorModels = assets.filter((entry) => entry.group === 'floor_overlay')
  const groundModels = assets.filter((entry) => entry.group === 'ground_decor')
  const wallFinishes = assets.filter((entry) => entry.group === 'wall_finish')
  const wallPanels = assets.filter((entry) => entry.group === 'wall_panel')
  const wallDecor = assets.filter((entry) => entry.group === 'wall_decor')
  const curtains = assets.filter((entry) => entry.group === 'curtain')
  const ceilingAssets = assets.filter((entry) => entry.group === 'ceiling_asset')
  const roofAssets = assets.filter((entry) => entry.group === 'roof_asset')
  const library = assets.filter((entry) => ['furniture', 'floor_overlay', 'ceiling_asset'].includes(entry.group) && entry.model_path)
  const libraryRoom = String(room?.id) === String(selection.roomId) ? room : rooms.find((entry) => String(entry.id) === String(selection.roomId))
  const supports = tabletopSupports(libraryRoom)
  const surfaceLibrary = library.filter((entry) => assetSurface(entry) === placementSurface)
  const roomLibrary = libraryScope === 'all' ? surfaceLibrary : surfaceLibrary.filter((entry) => isAssetRecommendedForRoom(entry, libraryRoom))
  const categories = [...new Set(roomLibrary.map((entry) => entry.category || entry.group))].sort()
  const libraryItems = roomLibrary.filter((entry) => (libraryCategory === 'all' || (entry.category || entry.group) === libraryCategory)
    && entry.name.toLowerCase().includes(search.toLowerCase()))
  const position = furniture?.position || {}
  const rotation = Number(furniture?.rotation ?? furniture?.rotation_y) || 0
  const title = isFurniture
    ? String(furniture?.name || furniture?.category || furniture?.asset || 'Furniture').replaceAll('_', ' ')
    : isFloor || isGround
      ? isGround ? 'Exterior ground' : `${room?.name || room?.type || 'Room'} floor`
      : selection.type === 'library' ? 'Add uploaded assets'
      : selection.exterior ? 'Boundary wall'
      : selection.type === 'roof' ? 'Exterior roof'
      : selection.type === 'ceiling' ? 'Interior ceiling'
        : `${room?.name || room?.type || 'Room'} ${['window', 'door'].includes(selection.type) ? selection.type : selection.wallSide || 'wall'}`

  const catalogStatus = catalogState === 'loading'
    ? <p className="editor-empty-copy"><Loader2 size={14} className="animate-spin" /> Loading your uploaded assets…</p>
    : catalogState === 'error'
      ? <p className="editor-empty-copy">Your uploaded asset catalog could not be loaded.</p>
      : null

  const textureGrid = (items, onSelect) => items.length > 0 ? (
    <div className="editor-texture-grid">
      {items.map((entry) => (
        <button type="button" key={entry.s3_key} onClick={() => onSelect(entry)} title={entry.name}>
          <img src={entry.thumbnail_url || entry.url} alt="" loading="lazy" />
          <strong>{entry.name}</strong>
        </button>
      ))}
    </div>
  ) : catalogStatus || <p className="editor-empty-copy">No uploaded assets are available for this surface.</p>

  const modelGrid = (items, onSelect) => items.length > 0 ? (
    <div className="editor-model-grid">
      {items.map((entry) => (
        <button type="button" key={entry.s3_key} onClick={() => onSelect(entry)} title={entry.name}>
          <ModelThumbnail entry={entry} />
          <span>{entry.name}</span>
          <small>Uploaded 3D model</small>
        </button>
      ))}
    </div>
  ) : catalogStatus || <p className="editor-empty-copy">No uploaded 3D assets are available here.</p>

  return (
    <aside className={`interior-editor-drawer ${collapsed ? 'sheet-collapsed' : ''}`} aria-label="3D interior editor">
      <button type="button" className="editor-sheet-handle mobile-only" aria-expanded={!collapsed}
        aria-label={collapsed ? 'Expand editor' : 'Minimize editor'} onClick={() => setCollapsed((value) => !value)}>
        <span />{collapsed ? 'Expand editor' : 'Minimize'}
      </button>
      <div className="interior-editor-header">
        <div>
          <span className="interior-editor-kicker">3D EDITOR</span>
          <h2>{title}</h2>
          <p>{isFurniture ? `ID: ${furniture?.id || 'unknown'}` : selection.type === 'library' ? 'Choose a room and an uploaded model.' : 'Surface finish customization'}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close editor"><X size={18} /></button>
      </div>

      <div className="interior-editor-body scroll-soft">
        {selection.type === 'library' && <section className="interior-editor-section editor-library-section">
          <label className="editor-library-field">Place in room
            <select value={selection.roomId || ''} onChange={(event) => onLibraryRoomChange?.(event.target.value)}>
              {rooms.map((entry) => <option key={entry.id} value={entry.id}>{entry.name || entry.type || entry.id}</option>)}
            </select>
          </label>
          <button type="button" className="editor-filter-toggle mobile-only" aria-expanded={filtersExpanded}
            onClick={() => setFiltersExpanded((value) => !value)}>{filtersExpanded ? 'Hide filters' : 'Filters & placement options'}<ChevronDown size={16} /></button>
          <div className={`editor-library-filters ${filtersExpanded ? 'expanded' : ''}`}>
          <div className="editor-segmented-control editor-library-scope" aria-label="Asset library scope">
            <button type="button" className={libraryScope === 'room' ? 'active' : ''} aria-pressed={libraryScope === 'room'}
              onClick={() => { setLibraryScope('room'); setLibraryCategory('all'); onCancelPlacement?.() }}>For this room</button>
            <button type="button" className={libraryScope === 'all' ? 'active' : ''} aria-pressed={libraryScope === 'all'}
              onClick={() => { setLibraryScope('all'); setLibraryCategory('all'); onCancelPlacement?.() }}>All uploaded assets</button>
          </div>
          <label className="editor-library-field">Place on
            <select value={placementSurface} onChange={(event) => {
              setPlacementSurface(event.target.value); setLibraryCategory('all'); setSupportId(''); onCancelPlacement?.()
            }}>
              <option value="floor">Floor</option><option value="ceiling">Ceiling</option><option value="tabletop">Tabletop</option>
            </select>
          </label>
          {placementSurface === 'tabletop' && <label className="editor-library-field">Table or desk
            <select value={supports.some((entry) => entry.id === supportId) ? supportId : ''}
              onChange={(event) => { setSupportId(event.target.value); onCancelPlacement?.() }}>
              <option value="">Choose a table</option>
              {supports.map((entry) => <option key={entry.id} value={entry.id}>{entry.name || entry.category}</option>)}
            </select>
            {!supports.length && <span>Add a table, desk or nightstand to this room first.</span>}
          </label>}
          <label className="editor-library-field">Category
            <select value={libraryCategory} onChange={(event) => setLibraryCategory(event.target.value)}>
              <option value="all">All categories</option>
              {categories.map((entry) => <option key={entry} value={entry}>{entry.replaceAll('_', ' ')}</option>)}
            </select>
          </label>
          </div>
          <label className="editor-library-field">Search assets
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search your uploaded models" />
          </label>
          <p className="editor-helper-copy">{libraryScope === 'room' ? `Recommended for ${libraryRoom?.name || libraryRoom?.type || 'this room'}. ` : 'Showing your full uploaded library. '}Ceiling fixtures mount overhead. Select a wall or window for panels, décor or curtains.</p>
          {pendingPlacement && <div ref={confirmation} className="editor-placement-confirm" role="group" aria-label="Confirm asset placement">
            <strong>Preview: {pendingPlacement.asset.name}</strong>
            <p>{pendingPlacement.status === 'loading' ? 'Loading 3D preview…' : pendingPlacement.status === 'error'
              ? 'Preview could not load. Choose another model or cancel.' : `Place in ${libraryRoom?.name || libraryRoom?.type || 'this room'}? Nothing is saved until you confirm.`}</p>
            {pendingPlacement.item.wall_mounted && <label className="editor-library-field">Mount on wall
              <select aria-label="Preview mounting wall" value={pendingPlacement.item.wall_side} onChange={event=>onPlacementWallChange?.(event.target.value)}>
                <option value="right">Right wall</option><option value="left">Left wall</option><option value="front">North wall</option><option value="back">South wall</option>
              </select>
            </label>}
            {pendingPlacement.status === 'ready' && !pendingPlacement.item.support_id && <div className="editor-inline-actions" aria-label="Adjust placement preview">
              <button type="button" onClick={() => onAdjustPlacement?.(-0.25, 0)}>−X</button>
              <button type="button" onClick={() => onAdjustPlacement?.(0.25, 0)}>+X</button>
              {!pendingPlacement.item.wall_mounted && <button type="button" onClick={() => onAdjustPlacement?.(0, 0, 90)}>Rotate 90°</button>}
              <button type="button" onClick={() => onAdjustPlacement?.(0, -0.25)}>−Z</button>
              <button type="button" onClick={() => onAdjustPlacement?.(0, 0.25)}>+Z</button>
            </div>}
            <div className="editor-placement-buttons">
              <button type="button" onClick={onCancelPlacement}>Cancel</button>
              <button type="button" disabled={pendingPlacement.status !== 'ready'} onClick={onConfirmPlacement}>Place here</button>
            </div>
          </div>}
          {libraryItems.length > 0 || catalogState !== 'ready' ? modelGrid(libraryItems, (entry) => onAddModelAsNew(entry, supportId))
            : <p className="editor-empty-copy">No matching uploaded assets. Try another category or All uploaded assets.</p>}
        </section>}
        {isFurniture && furniture && (
          <>
            <section className="interior-editor-section">
              <SectionTitle icon={<Move size={15} />}>Transform</SectionTitle>
              <div className="editor-segmented-control">
                <button
                  type="button"
                  className={transformMode === 'translate' ? 'active' : ''}
                  onClick={() => onTransformModeChange('translate')}
                >
                  Move
                </button>
                <button
                  type="button"
                  className={transformMode === 'rotate' ? 'active' : ''}
                  disabled={Boolean(furniture.wall_mounted)}
                  onClick={() => onTransformModeChange('rotate')}
                >
                  Rotate
                </button>
              </div>

              <div className="editor-position-readout">
                <span>X <strong>{Number(position.x || 0).toFixed(2)}m</strong></span>
                <span>Z <strong>{Number(position.y || 0).toFixed(2)}m</strong></span>
                <span>R <strong>{Math.round(rotation)}°</strong></span>
              </div>

              <div className="editor-nudge-grid" aria-label="Fine position controls">
                <span />
                <button type="button" onClick={() => onNudge(0, -0.1)} title="Move toward back"><ChevronUp size={17} /></button>
                <span />
                <button type="button" onClick={() => onNudge(-0.1, 0)} title="Move left">−X</button>
                <span className="editor-nudge-center">0.1m</span>
                <button type="button" onClick={() => onNudge(0.1, 0)} title="Move right">+X</button>
                <span />
                <button type="button" onClick={() => onNudge(0, 0.1)} title="Move toward front"><ChevronDown size={17} /></button>
                <span />
              </div>

              {furniture.wall_mounted && (
                <>
                  {category==='shower' && <label className="editor-library-field">Mount on wall
                    <select aria-label="Shower mounting wall" value={furniture.wall_side || 'right'} onChange={event=>onMountWallChange?.(event.target.value)}>
                      <option value="right">Right wall</option><option value="left">Left wall</option><option value="front">North wall</option><option value="back">South wall</option>
                    </select>
                  </label>}
                  <p className="editor-helper-copy">Faces away from the selected wall surface. Move along the wall or adjust the height below.</p>
                  <p className="editor-helper-copy">Height above floor: {Number(furniture.mount_height || 0).toFixed(2)}m</p>
                  <div className="editor-inline-actions" aria-label="Height controls">
                    <button type="button" onClick={() => onNudge(0, 0, 0.1)}><ChevronUp size={16} /> Up 0.1m</button>
                    <button type="button" onClick={() => onNudge(0, 0, -0.1)}><ChevronDown size={16} /> Down 0.1m</button>
                  </div>
                </>
              )}

              <div className="editor-inline-actions">
                <button type="button" onClick={() => onRotate(-15)}><RotateCcw size={14} /> −15°</button>
                <button type="button" onClick={() => onRotate(15)}><RotateCw size={14} /> +15°</button>
                <button type="button" onClick={() => onRotate(90)}><RotateCw size={14} /> 90°</button>
              </div>
              <p className="editor-helper-copy">Resize proportionally</p>
              <div className="editor-inline-actions">
                <button type="button" onClick={() => onResize(0.9)}>Smaller −10%</button>
                <button type="button" onClick={() => onResize(1.1)}>Larger +10%</button>
              </div>
              <p className="editor-helper-copy">{Number(furniture.dimensions?.width || 0).toFixed(2)}m wide × {Number(furniture.dimensions?.depth || 0).toFixed(2)}m deep × {Number(furniture.dimensions?.height || 0).toFixed(2)}m high</p>

              {onDuplicate && !furniture.wall_mounted && !furniture.ceiling_mounted && (
                <div className="editor-inline-actions" style={{ marginTop: 12 }}>
                  <button
                    type="button"
                    onClick={onDuplicate}
                    title="Duplicate this item in the room"
                    style={{ width: '100%', justifyContent: 'center', gap: 6 }}
                  >
                    <Copy size={14} /> Add another / Duplicate {category ? category.replaceAll('_', ' ') : 'furniture'}
                  </button>
                </div>
              )}
            </section>

            <section className="interior-editor-section">
              <SectionTitle icon={<Box size={15} />}>
                {category ? `${category.replaceAll('_', ' ')} models` : 'Furniture models'}
              </SectionTitle>
              {variants.length > 0 && !furniture.wall_mounted && !furniture.ceiling_mounted && (
                <div className="editor-segmented-control" style={{ marginBottom: 10 }}>
                  <button
                    type="button"
                    className={modelActionTab === 'swap' ? 'active' : ''}
                    onClick={() => setModelActionTab('swap')}
                  >
                    Swap model
                  </button>
                  <button
                    type="button"
                    className={modelActionTab === 'add' ? 'active' : ''}
                    onClick={() => setModelActionTab('add')}
                  >
                    + Add as new
                  </button>
                </div>
              )}
              {variants.length > 0 && (
                <p className="editor-helper-copy" style={{ marginBottom: 10 }}>
                  {modelActionTab === 'add'
                    ? `Adds an additional ${category ? category.replaceAll('_', ' ') : 'item'} to ${room?.name || 'the room'}.`
                    : `Replaces current ${category ? category.replaceAll('_', ' ') : 'item'} with the selected model.`}
                </p>
              )}
              {variants.length > 0 ? (
                <div className="editor-model-grid">
                  {variants.map((entry) => {
                    const isActive = modelActionTab === 'swap' && (furniture.model_id || furniture.asset_id) === entry.id
                    return (
                      <button
                        type="button"
                        key={entry.s3_key}
                        className={isActive ? 'active' : ''}
                        onClick={() => {
                          if (modelActionTab === 'add') {
                            onAddModelAsNew?.(entry)
                          } else {
                            onSwapModel(entry)
                          }
                        }}
                        title={modelActionTab === 'add' ? `Add ${entry.name} to room` : `Swap with ${entry.name}`}
                      >
                        <ModelThumbnail entry={entry} />
                        <span>{entry.name}</span>
                        <small>{modelActionTab === 'add' ? '+ Add to room' : '3D model'}</small>
                      </button>
                    )
                  })}
                </div>
              ) : (
                catalogStatus || <p className="editor-empty-copy">No uploaded {category.replaceAll('_', ' ')} models were found.</p>
              )}
            </section>

            {canAccentColor && <section className="interior-editor-section">
              <SectionTitle icon={<Paintbrush size={15} />}>Accent color</SectionTitle>
              <div className="editor-color-row">
                {FURNITURE_COLORS.map((color) => (
                  <button
                    key={color}
                    type="button"
                    className={String(furniture.color || '').toLowerCase() === color.toLowerCase() ? 'active' : ''}
                    style={{ '--swatch': color }}
                    onClick={() => onColorChange(color)}
                    aria-label={`Set furniture color ${color}`}
                  />
                ))}
              </div>
            </section>}

            <section className="interior-editor-danger">
              <button type="button" onClick={onDelete}><Trash2 size={15} /> Delete furniture</button>
            </section>
          </>
        )}

        {(isFloor || isGround) && (
          <>
            <section className="interior-editor-section">
              <SectionTitle icon={<Image size={15} />}>{isGround ? 'Ground textures' : 'Floor textures'}</SectionTitle>
              {textureGrid(floorFinishes, isGround ? onGroundFinish : onFloorFinish)}
            </section>
            {isFloor && floorModels.length > 0 && (
              <section className="interior-editor-section">
                <SectionTitle icon={<Layers3 size={15} />}>Rugs and floor assets</SectionTitle>
                {modelGrid(floorModels, onFloorFinish)}
              </section>
            )}
            {isGround && groundModels.length > 0 && (
              <section className="interior-editor-section">
                <SectionTitle icon={<Layers3 size={15} />}>Outdoor 3D assets</SectionTitle>
                {modelGrid(groundModels, onGroundFinish)}
              </section>
            )}
          </>
        )}

        {['wall', 'window', 'door'].includes(selection.type) && (
          <>
            <section className="interior-editor-section">
              {selection.type === 'window' && <div className="editor-surface-tabs" role="tablist" aria-label="Window editing options">
                <button type="button" role="tab" aria-selected={wallTab === 'opening'} className={wallTab === 'opening' ? 'active' : ''} onClick={() => setWallTab('opening')}>Windows</button>
                <button type="button" role="tab" aria-selected={wallTab === 'curtain'} className={wallTab === 'curtain' ? 'active' : ''} onClick={() => setWallTab('curtain')}>Curtains &amp; Blinds</button>
              </div>}
              {wallTab === 'opening' && <>
                <SectionTitle icon={<Layers3 size={15} />}>{selection.type === 'door' ? 'Compatible doors and gates' : 'Window models'}</SectionTitle>
                {selection.opening ? <>
                  <p className="editor-helper-copy">Fits the existing {selection.opening.width.toFixed(2)} m × {selection.opening.height.toFixed(2)} m opening. Width and height stay fixed; model proportions may change.</p>
                  {modelGrid(assets.filter((entry) => compatibleOpening(entry, selection.opening, room)), onSwapOpening)}
                  <div className="editor-inline-actions" style={{ marginTop: 12 }}>
                    <button type="button" onClick={() => onSwapOpening(null)}>Restore original {selection.type}</button>
                  </div>
                </> : <p className="editor-helper-copy">This object could not be matched to a saved wall opening. Update the Blender worker scripts, sync them into the worker, then regenerate this version.</p>}
              </>}
              {selection.type === 'wall' && <div className="editor-surface-tabs" role="tablist" aria-label="Wall editing options">
                <button type="button" className={wallTab === 'finish' ? 'active' : ''} onClick={() => setWallTab('finish')}>Finishes</button>
                <button type="button" className={wallTab === 'panel' ? 'active' : ''} onClick={() => setWallTab('panel')}>Panels</button>
                <button type="button" className={wallTab === 'decor' ? 'active' : ''} onClick={() => setWallTab('decor')}>Décor</button>
                {!selection.exterior && <button type="button" className={wallTab === 'curtain' ? 'active' : ''} onClick={() => setWallTab('curtain')}>Curtains</button>}
              </div>}
              {wallTab === 'curtain' && <>
              <SectionTitle icon={<Layers3 size={15} />}>Curtains and blinds</SectionTitle>
              {selection.type === 'window' && <p className="editor-helper-copy">Fits inside the selected window wall.</p>}
              {modelGrid(curtains, onAddWallDecor)}
              </>}
              {wallTab === 'finish' && (
                <>
                  <SectionTitle icon={<Paintbrush size={15} />}>Wall finishes</SectionTitle>
                  <p className="editor-helper-copy">Applies only to this side of the selected wall.</p>
                  {textureGrid(wallFinishes, onWallFinish)}
                </>
              )}
              {wallTab === 'panel' && (
                <>
                  <SectionTitle icon={<Layers3 size={15} />}>Wall panels</SectionTitle>
                  {modelGrid(wallPanels, onAddWallDecor)}
                </>
              )}
              {wallTab === 'decor' && (
                <>
                  <SectionTitle icon={<Box size={15} />}>Wall décor and lights</SectionTitle>
                  <p className="editor-helper-copy">Snaps the uploaded model to the selected wall.</p>
                  {modelGrid(wallDecor, onAddWallDecor)}
                </>
              )}
            </section>
          </>
        )}

        {selection.type==='wall' && !selection.exterior && /bath/.test(`${room?.type} ${room?.name}`.toLowerCase()) && <section className="interior-editor-section">
          <SectionTitle icon={<Box size={15}/>}>Shower fixtures</SectionTitle>
          <p className="editor-helper-copy">Places the fixture on this selected wall.</p>
          {modelGrid(assets.filter(entry=>entry.category==='shower' && entry.mounting?.surface==='wall'),onAddModelAsNew)}
        </section>}
        {(selection.type === 'roof' || selection.type === 'ceiling') && (
          <section className="interior-editor-section">
            <SectionTitle icon={<Layers3 size={15} />}>{selection.type === 'roof' ? 'Exterior roof assets' : 'Ceiling fixtures'}</SectionTitle>
            {selection.type === 'roof' && <p className="editor-helper-copy">Fans and hanging lamps belong to the interior ceiling. Select its underside inside a room, or add them through Add assets.</p>}
            {modelGrid(selection.type === 'roof' ? roofAssets : ceilingAssets, onAddWallDecor)}
          </section>
        )}

        <section className="interior-editor-finalize">
          <button type="button" onClick={onFinalize3D} disabled={!canFinalize3D}>
            <Layers3 size={15} /> Finalize Blender GLB
          </button>
          <small>{canFinalize3D ? 'Optionally merge saved layers into one export.' : 'Save your layered edits before finalizing.'}</small>
        </section>
      </div>
    </aside>
  )
}
