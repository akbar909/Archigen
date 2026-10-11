import { useMemo } from 'react'
import {
  ARCHITECTURAL_STYLES,
  ROOF_TYPES,
  EXTERIOR_COLORS,
  WALL_MATERIALS,
  INTERIOR_STYLES,
  FLOORING_MATERIALS,
  FURNITURE_PREFS,
  DESIGN_PRIORITIES,
  BUDGET_OPTIONS,
  BUILDING_TYPES,
  ORIENTATIONS,
  ROAD_ACCESS,
  FLOOR_OPTIONS,
  EXTRA_FEATURES,
} from './wizard-constants'
import { computePlotArea, getLabelForRoom, getFloorLabel } from './wizard-utils'
import { Edit3 } from 'lucide-react'

function ReviewSection({ title, icon, onEdit, children }) {
  return (
    <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3 sm:p-3.5 backdrop-blur-sm shadow-sm space-y-2">
      <div className="flex items-center justify-between pb-1.5 border-b border-white/[0.06]">
        <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
          {icon && <span className="text-sm">{icon}</span>}
          {title}
        </span>
        <button
          type="button"
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/20 transition-all cursor-pointer"
          onClick={onEdit}
          aria-label={`Edit ${title}`}
        >
          <Edit3 size={10} />
          <span>Edit</span>
        </button>
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  )
}

function ReviewRow({ label, value }) {
  if (!value && value !== 0) return null
  return (
    <div className="flex items-center justify-between py-0.5 text-xs">
      <span className="text-white/50">{label}</span>
      <span className="text-white/90 font-semibold text-right">{value}</span>
    </div>
  )
}

export default function ReviewGenerateStep({ wizardState, onEditStep }) {
  const { plot, rooms, design, features, featureConfigs, specialRequirements } = wizardState

  const plotArea = useMemo(
    () => computePlotArea(plot.width, plot.length, plot.unit),
    [plot.width, plot.length, plot.unit]
  )

  const getLabel = (items, id) => {
    const found = items.find((i) => i.id === id || i.value === id)
    return found ? found.label : id
  }

  const enabledFeatures = useMemo(() => {
    return Object.entries(features)
      .filter(([, enabled]) => enabled)
      .map(([id]) => {
        const meta = EXTRA_FEATURES.find((f) => f.id === id)
        let label = meta ? meta.label : id
        if (featureConfigs[id]?.parkingSpaces) {
          label += ` (${featureConfigs[id].parkingSpaces} vehicles)`
        }
        return label
      })
  }, [features, featureConfigs])

  // Group rooms by floor
  const roomsByFloor = useMemo(() => {
    const groups = {}
    for (const room of rooms) {
      const floorKey = room.floor ?? 0
      if (!groups[floorKey]) groups[floorKey] = []
      groups[floorKey].push(room)
    }
    return groups
  }, [rooms])

  return (
    <div className="w-full max-w-4xl mx-auto space-y-3">
      {/* Plot & Building */}
      <ReviewSection title="Plot & Building Details" icon="📐" onEdit={() => onEditStep(1)}>
        <ReviewRow label="Plot Dimensions" value={`${plot.width} × ${plot.length} ${plot.unit}`} />
        {plotArea && <ReviewRow label="Total Plot Area" value={`${plotArea.area.toLocaleString()} ${plotArea.unit}`} />}
        <ReviewRow label="Floors" value={getLabel(FLOOR_OPTIONS, plot.floors)} />
        <ReviewRow label="Building Type" value={getLabel(BUILDING_TYPES, plot.buildingType)} />
        <ReviewRow label="Facing Direction" value={getLabel(ORIENTATIONS, plot.orientation)} />
        <ReviewRow label="Road Access" value={getLabel(ROAD_ACCESS, plot.roadAccess)} />
        {plot.coverage && <ReviewRow label="Target Coverage" value={`${plot.coverage}%`} />}
      </ReviewSection>

      {/* Rooms & Floors */}
      <ReviewSection title="Rooms & Layout Distribution" icon="🏗️" onEdit={() => onEditStep(2)}>
        {rooms.length === 0 ? (
          <p className="text-xs text-white/40 italic">No rooms selected</p>
        ) : (
          <div className="space-y-1.5">
            <ReviewRow label="Total Rooms Count" value={rooms.reduce((sum, r) => sum + r.count, 0)} />
            
            {plot.floors > 1 ? (
              Object.entries(roomsByFloor)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([floor, floorRooms]) => (
                  <div key={floor} className="p-2 bg-white/[0.02] border border-white/5 rounded-lg space-y-1">
                    <span className="text-[10px] font-semibold text-emerald-400 block">{getFloorLabel(Number(floor))}</span>
                    <div className="flex flex-wrap gap-1">
                      {floorRooms.map((room) => (
                        <span
                          key={room.id}
                          className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[11px] text-white/90 font-medium flex items-center gap-1"
                        >
                          <span className="text-emerald-400 font-bold">{room.count}×</span>
                          <span>{getLabelForRoom(room.type)}</span>
                          {room.preferredSize !== 'medium' && (
                            <span className="text-[9px] text-white/40">({room.preferredSize})</span>
                          )}
                          {room.attachedBathroom && (
                            <span className="text-[9px] text-emerald-400 font-semibold">+Bath</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                ))
            ) : (
              <div className="flex flex-wrap gap-1 pt-0.5">
                {rooms.map((room) => (
                  <span
                    key={room.id}
                    className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[11px] text-white/90 font-medium flex items-center gap-1"
                  >
                    <span className="text-emerald-400 font-bold">{room.count}×</span>
                    <span>{getLabelForRoom(room.type)}</span>
                    {room.preferredSize !== 'medium' && (
                      <span className="text-[9px] text-white/40">({room.preferredSize})</span>
                    )}
                    {room.attachedBathroom && (
                      <span className="text-[9px] text-emerald-400 font-semibold">+Bath</span>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </ReviewSection>

      {/* Design Preferences */}
      <ReviewSection title="Design & Finishes" icon="🎨" onEdit={() => onEditStep(3)}>
        <ReviewRow label="Architectural Style" value={getLabel(ARCHITECTURAL_STYLES, design.architecturalStyle)} />
        <ReviewRow label="Roof Structure" value={getLabel(ROOF_TYPES, design.roofType)} />
        <ReviewRow label="Exterior Color" value={getLabel(EXTERIOR_COLORS, design.exteriorColor)} />
        <ReviewRow label="Wall Material" value={getLabel(WALL_MATERIALS, design.wallMaterial)} />
        <ReviewRow label="Interior Style" value={getLabel(INTERIOR_STYLES, design.interiorStyle)} />
        <ReviewRow label="Flooring Material" value={getLabel(FLOORING_MATERIALS, design.flooringMaterial)} />
        <ReviewRow label="Furniture Level" value={getLabel(FURNITURE_PREFS, design.furniture)} />
        <ReviewRow label="Design Priority" value={getLabel(DESIGN_PRIORITIES, design.designPriority)} />
      </ReviewSection>

      {/* Extra Features */}
      <ReviewSection title="Amenities & Requirements" icon="⭐" onEdit={() => onEditStep(4)}>
        {enabledFeatures.length === 0 ? (
          <p className="text-xs text-white/40 italic">No extra amenities selected</p>
        ) : (
          <div className="flex flex-wrap gap-1">
            {enabledFeatures.map((f) => (
              <span
                key={f}
                className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-300 font-medium"
              >
                {f}
              </span>
            ))}
          </div>
        )}
        {specialRequirements && (
          <div className="mt-2 p-2 bg-white/[0.02] border border-white/5 rounded-lg">
            <span className="block text-[10px] font-medium text-white/40 mb-0.5">Special Requirements:</span>
            <p className="text-xs text-white/80 leading-relaxed italic">{specialRequirements}</p>
          </div>
        )}
      </ReviewSection>
    </div>
  )
}
