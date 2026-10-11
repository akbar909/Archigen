import { useState, useMemo, useCallback } from 'react'
import { ROOM_TYPES, ROOM_SIZES, ROOM_LOCATIONS } from './wizard-constants'
import { getFloorLabel } from './wizard-utils'
import { Plus, Minus, ChevronDown, ChevronUp, AlertTriangle, X } from 'lucide-react'

function QuantitySelector({ value, min = 1, max = 6, onChange }) {
  return (
    <div className="flex items-center gap-1 bg-white/5 border border-white/10 rounded-lg p-0.5">
      <button
        type="button"
        className="w-5 h-5 flex items-center justify-center rounded bg-white/5 text-white/70 hover:bg-white/10 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
        onClick={() => onChange(Math.max(min, value - 1))}
        disabled={value <= min}
        aria-label="Decrease quantity"
      >
        <Minus size={11} />
      </button>
      <span className="w-5 text-center text-xs font-bold text-white tabular-nums">{value}</span>
      <button
        type="button"
        className="w-5 h-5 flex items-center justify-center rounded bg-white/5 text-white/70 hover:bg-white/10 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-colors"
        onClick={() => onChange(Math.min(max, value + 1))}
        disabled={value >= max}
        aria-label="Increase quantity"
      >
        <Plus size={11} />
      </button>
    </div>
  )
}

function RoomConfigPanel({ room, floors, onUpdate, onRemove }) {
  const [expanded, setExpanded] = useState(false)
  const meta = ROOM_TYPES.find((r) => r.id === room.type)

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] hover:border-white/15 rounded-lg transition-all overflow-hidden shadow-sm">
      <div className="flex items-center justify-between px-3 py-2 bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <span className="text-base p-1 bg-white/5 rounded-md">{meta?.icon || '🚪'}</span>
          <div>
            <span className="text-xs font-semibold text-white/90 block leading-tight">{meta?.label || room.type}</span>
            <span className="text-[10px] text-white/40">
              {room.preferredSize} • {floors > 1 ? getFloorLabel(room.floor) : 'Single Story'}
              {room.attachedBathroom ? ' • +Bath' : ''}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <QuantitySelector
            value={room.count}
            max={meta?.maxCount || 6}
            onChange={(val) => onUpdate({ ...room, count: val })}
          />
          <button
            type="button"
            className="p-1 rounded bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
            onClick={() => setExpanded(!expanded)}
            aria-label="Toggle room settings"
          >
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
          <button
            type="button"
            className="p-1 rounded bg-white/5 hover:bg-rose-500/20 text-white/40 hover:text-rose-400 transition-colors"
            onClick={() => onRemove(room.id)}
            aria-label={`Remove ${meta?.label}`}
          >
            <X size={13} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="p-3 border-t border-white/[0.06] bg-black/20 space-y-2.5">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {/* Preferred Size */}
            <div>
              <label className="block text-[10px] font-medium text-white/60 mb-1">Preferred Size</label>
              <div className="flex p-0.5 bg-white/5 border border-white/10 rounded-md gap-0.5">
                {ROOM_SIZES.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={`flex-1 py-0.5 px-1 rounded text-[10px] font-medium transition-all ${
                      room.preferredSize === s.id
                        ? 'bg-emerald-500 text-white font-semibold shadow-sm'
                        : 'text-white/60 hover:text-white'
                    }`}
                    onClick={() => onUpdate({ ...room, preferredSize: s.id })}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Location Preference */}
            <div>
              <label className="block text-[10px] font-medium text-white/60 mb-1">Location Preference</label>
              <select
                className="w-full bg-[#1c1c1c] border border-white/10 rounded-md px-2 py-1 text-[11px] text-white focus:outline-none focus:border-emerald-500/60"
                value={room.preferredLocation || 'no_preference'}
                onChange={(e) => onUpdate({ ...room, preferredLocation: e.target.value })}
              >
                {ROOM_LOCATIONS.map((l) => (
                  <option key={l.id} value={l.id} className="bg-[#171717] text-white">
                    {l.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Floor assignment */}
            {floors > 1 && (
              <div>
                <label className="block text-[10px] font-medium text-white/60 mb-1">Floor Level</label>
                <select
                  className="w-full bg-[#1c1c1c] border border-white/10 rounded-md px-2 py-1 text-[11px] text-white focus:outline-none focus:border-emerald-500/60"
                  value={room.floor ?? 0}
                  onChange={(e) => onUpdate({ ...room, floor: parseInt(e.target.value) })}
                >
                  {Array.from({ length: floors }, (_, i) => (
                    <option key={i} value={i} className="bg-[#171717] text-white">
                      {getFloorLabel(i)}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Attached bathroom */}
            {meta?.hasAttachedBath && (
              <div>
                <label className="block text-[10px] font-medium text-white/60 mb-1">Attached Ensuite</label>
                <button
                  type="button"
                  className={`w-full py-1 px-2 rounded-md border text-[11px] font-medium transition-all ${
                    room.attachedBathroom
                      ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-semibold'
                      : 'bg-white/5 border-white/10 text-white/60 hover:text-white'
                  }`}
                  onClick={() => onUpdate({ ...room, attachedBathroom: !room.attachedBathroom })}
                >
                  {room.attachedBathroom ? '✓ Attached Bathroom' : '+ Add Attached Bath'}
                </button>
              </div>
            )}
          </div>

          {/* Notes */}
          <div>
            <input
              type="text"
              className="w-full bg-white/5 border border-white/10 rounded-md px-2.5 py-1 text-xs text-white placeholder-white/20 focus:outline-none focus:border-emerald-500/60"
              placeholder="Optional room note (e.g. large garden window)..."
              value={room.notes || ''}
              onChange={(e) => onUpdate({ ...room, notes: e.target.value })}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export default function RoomConfigurationStep({ data, floors, onChange, errors }) {
  const selectedRoomIds = useMemo(() => new Set(data.map((r) => r.type)), [data])

  const toggleRoom = useCallback(
    (roomType) => {
      if (selectedRoomIds.has(roomType)) {
        onChange(data.filter((r) => r.type !== roomType))
      } else {
        onChange([
          ...data,
          {
            id: `${roomType}_${Date.now()}`,
            type: roomType,
            count: 1,
            preferredSize: 'medium',
            preferredLocation: 'no_preference',
            floor: 0,
            attachedBathroom: false,
            notes: '',
          },
        ])
      }
    },
    [data, onChange, selectedRoomIds]
  )

  const updateRoom = useCallback(
    (updatedRoom) => {
      onChange(data.map((r) => (r.id === updatedRoom.id ? updatedRoom : r)))
    },
    [data, onChange]
  )

  const removeRoom = useCallback(
    (roomId) => {
      onChange(data.filter((r) => r.id !== roomId))
    },
    [data, onChange]
  )

  const floorConflicts = useMemo(() => {
    return data.filter((room) => room.floor >= floors)
  }, [data, floors])

  return (
    <div className="w-full max-w-4xl mx-auto space-y-3">
      {errors.general && (
        <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400 font-medium">
          {errors.general}
        </div>
      )}

      {floorConflicts.length > 0 && (
        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs">
          <AlertTriangle size={15} className="flex-shrink-0" />
          <span>
            {floorConflicts.length} room(s) assigned to floors that don't exist. Please reassign.
          </span>
        </div>
      )}

      {/* Room Selection Grid */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3 sm:p-4 backdrop-blur-sm shadow-sm space-y-2.5">
        <div className="flex items-center justify-between">
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
            Available Rooms
          </h3>
          <span className="text-[11px] text-white/40">
            {data.length} selected
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
          {ROOM_TYPES.map((rt) => {
            const isSelected = selectedRoomIds.has(rt.id)
            return (
              <button
                key={rt.id}
                type="button"
                className={`py-2 px-2 rounded-lg border text-center transition-all flex flex-col items-center justify-center gap-1 cursor-pointer relative ${
                  isSelected
                    ? 'bg-emerald-500/15 border-emerald-500 text-white shadow-[0_0_10px_rgba(16,163,127,0.2)] ring-1 ring-emerald-500/50'
                    : 'bg-white/[0.03] border-white/10 text-white/70 hover:bg-white/[0.06] hover:text-white'
                }`}
                onClick={() => toggleRoom(rt.id)}
              >
                <span className="text-xl">{rt.icon}</span>
                <span className="text-[11px] font-semibold leading-tight line-clamp-1">{rt.label}</span>
                {isSelected && (
                  <span className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 text-black text-[9px] font-black flex items-center justify-center">
                    ✓
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Selected Rooms List */}
      {data.length > 0 && (
        <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3 sm:p-4 backdrop-blur-sm shadow-sm space-y-2.5">
          <div className="flex items-center justify-between">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
              Configured Rooms
            </h3>
            <span className="text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full font-bold">
              {data.reduce((sum, r) => sum + r.count, 0)} total
            </span>
          </div>

          <div className="space-y-1.5">
            {data.map((room) => (
              <RoomConfigPanel
                key={room.id}
                room={room}
                floors={floors}
                onUpdate={updateRoom}
                onRemove={removeRoom}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
