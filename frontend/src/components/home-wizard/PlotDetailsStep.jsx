import { useMemo } from 'react'
import {
  FLOOR_OPTIONS,
  BUILDING_TYPES,
  ORIENTATIONS,
  ROAD_ACCESS,
  UNITS,
} from './wizard-constants'
import { computePlotArea } from './wizard-utils'
import { Ruler, Building2, Compass, Route } from 'lucide-react'

export default function PlotDetailsStep({ data, onChange, errors }) {
  const plotArea = useMemo(
    () => computePlotArea(data.width, data.length, data.unit),
    [data.width, data.length, data.unit]
  )

  const updateField = (field, value) => {
    onChange({ ...data, [field]: value })
  }

  const updateSetback = (field, value) => {
    onChange({
      ...data,
      setbacks: { ...data.setbacks, [field]: value },
    })
  }

  return (
    <div className="w-full max-w-4xl mx-auto space-y-3">
      {/* Plot Dimensions */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3.5 sm:p-4 backdrop-blur-sm shadow-sm space-y-2.5">
        <div className="flex items-center justify-between">
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
            <Ruler size={13} />
            Plot Dimensions
          </h3>
          {plotArea && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-500/10 border border-emerald-500/25 rounded-md text-emerald-300 text-[11px]">
              <span>📏 Total Area:</span>
              <strong className="text-white font-semibold">{plotArea.area.toLocaleString()} {plotArea.unit}</strong>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-12 gap-2.5 items-end">
          <div className="sm:col-span-5">
            <label className="block text-[11px] font-medium text-white/70 mb-1" htmlFor="plot-width">
              Width <span className="text-rose-400">*</span>
            </label>
            <input
              id="plot-width"
              type="number"
              className={`w-full bg-white/[0.05] border rounded-lg px-3 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none transition-all ${
                errors.width
                  ? 'border-rose-500/80 focus:ring-1 focus:ring-rose-500'
                  : 'border-white/10 focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/30'
              }`}
              placeholder={data.unit === 'ft' ? 'e.g. 40' : 'e.g. 12'}
              value={data.width}
              onChange={(e) => updateField('width', e.target.value)}
              min="0"
              step="any"
            />
            {errors.width && <span className="text-[10px] text-rose-400 mt-0.5 block font-medium">{errors.width}</span>}
          </div>

          <div className="sm:col-span-5">
            <label className="block text-[11px] font-medium text-white/70 mb-1" htmlFor="plot-length">
              Length <span className="text-rose-400">*</span>
            </label>
            <input
              id="plot-length"
              type="number"
              className={`w-full bg-white/[0.05] border rounded-lg px-3 py-1.5 text-xs text-white placeholder-white/20 focus:outline-none transition-all ${
                errors.length
                  ? 'border-rose-500/80 focus:ring-1 focus:ring-rose-500'
                  : 'border-white/10 focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/30'
              }`}
              placeholder={data.unit === 'ft' ? 'e.g. 60' : 'e.g. 18'}
              value={data.length}
              onChange={(e) => updateField('length', e.target.value)}
              min="0"
              step="any"
            />
            {errors.length && <span className="text-[10px] text-rose-400 mt-0.5 block font-medium">{errors.length}</span>}
          </div>

          <div className="sm:col-span-2">
            <label className="block text-[11px] font-medium text-white/70 mb-1" htmlFor="plot-unit">
              Unit
            </label>
            <div className="flex p-0.5 bg-white/[0.05] border border-white/10 rounded-lg gap-0.5 h-[32px] items-center">
              {UNITS.map((u) => (
                <button
                  key={u.id}
                  type="button"
                  className={`flex-1 h-full rounded-md text-[11px] font-semibold transition-all ${
                    data.unit === u.id
                      ? 'bg-emerald-500 text-white shadow-sm'
                      : 'text-white/60 hover:text-white hover:bg-white/5'
                  }`}
                  onClick={() => updateField('unit', u.id)}
                >
                  {u.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Building Configuration */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3.5 sm:p-4 backdrop-blur-sm shadow-sm space-y-3">
        <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
          <Building2 size={13} />
          Building Configuration
        </h3>

        {/* Floors */}
        <div>
          <label className="block text-[11px] font-medium text-white/70 mb-1.5">
            Number of Floors <span className="text-rose-400">*</span>
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {FLOOR_OPTIONS.map((opt) => {
              const isSelected = data.floors === opt.value
              return (
                <button
                  key={opt.value}
                  type="button"
                  className={`py-2 px-2.5 rounded-lg border text-center transition-all flex items-center justify-center gap-2 cursor-pointer ${
                    isSelected
                      ? 'bg-emerald-500/15 border-emerald-500 text-white shadow-[0_0_10px_rgba(16,163,127,0.2)] ring-1 ring-emerald-500/50'
                      : 'bg-white/[0.03] border-white/10 text-white/70 hover:bg-white/[0.06] hover:text-white'
                  }`}
                  onClick={() => updateField('floors', opt.value)}
                >
                  <span className="text-base">🏢</span>
                  <span className="text-xs font-semibold">{opt.label}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Building Type */}
        <div>
          <label className="block text-[11px] font-medium text-white/70 mb-1.5">
            Building Type <span className="text-rose-400">*</span>
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {BUILDING_TYPES.map((bt) => {
              const isSelected = data.buildingType === bt.id
              return (
                <button
                  key={bt.id}
                  type="button"
                  className={`py-2 px-3 rounded-lg border text-center transition-all flex items-center justify-center gap-2 cursor-pointer ${
                    isSelected
                      ? 'bg-emerald-500/15 border-emerald-500 text-white shadow-[0_0_10px_rgba(16,163,127,0.2)] ring-1 ring-emerald-500/50'
                      : 'bg-white/[0.03] border-white/10 text-white/70 hover:bg-white/[0.06] hover:text-white'
                  }`}
                  onClick={() => updateField('buildingType', bt.id)}
                >
                  <span className="text-lg">{bt.icon}</span>
                  <span className="text-xs font-semibold">{bt.label}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Facing and Road Access */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-0.5">
          {/* Facing */}
          <div>
            <label className="block text-[11px] font-medium text-white/70 mb-1.5 flex items-center gap-1">
              <Compass size={12} className="text-emerald-400" />
              Plot Facing <span className="text-rose-400">*</span>
            </label>
            <div className="grid grid-cols-4 gap-1.5">
              {ORIENTATIONS.map((o) => {
                const isSelected = data.orientation === o.id
                return (
                  <button
                    key={o.id}
                    type="button"
                    className={`py-1.5 px-1 rounded-lg border text-center transition-all flex flex-col items-center justify-center gap-0.5 ${
                      isSelected
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-semibold ring-1 ring-emerald-500/50'
                        : 'bg-white/[0.03] border-white/10 text-white/60 hover:bg-white/[0.06] hover:text-white'
                    }`}
                    onClick={() => updateField('orientation', o.id)}
                  >
                    <span className="text-xs">{o.icon}</span>
                    <span className="text-[10px] font-medium leading-tight">{o.label}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Road Access */}
          <div>
            <label className="block text-[11px] font-medium text-white/70 mb-1.5 flex items-center gap-1">
              <Route size={12} className="text-emerald-400" />
              Road Access <span className="text-rose-400">*</span>
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              {ROAD_ACCESS.map((ra) => {
                const isSelected = data.roadAccess === ra.id
                return (
                  <button
                    key={ra.id}
                    type="button"
                    className={`py-2 px-2.5 rounded-lg border text-center transition-all flex items-center justify-center gap-1.5 ${
                      isSelected
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-semibold ring-1 ring-emerald-500/50'
                        : 'bg-white/[0.03] border-white/10 text-white/60 hover:bg-white/[0.06] hover:text-white'
                    }`}
                    onClick={() => updateField('roadAccess', ra.id)}
                  >
                    <span className="text-xs font-medium">{ra.label}</span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Optional Setbacks & Site Details */}
      <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-3.5 sm:p-4 backdrop-blur-sm space-y-2.5">
        <div className="flex items-center justify-between">
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-white/50">
            Setbacks & Extra Site Parameters
          </h3>
          <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-full bg-white/10 text-white/40">
            Optional
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-12 gap-2.5 items-center">
          <div className="sm:col-span-4">
            <label className="block text-[10px] font-medium text-white/60 mb-0.5" htmlFor="plot-coverage">
              Max Coverage (%)
            </label>
            <input
              id="plot-coverage"
              type="number"
              className="w-full bg-white/[0.05] border border-white/10 rounded-lg px-2.5 py-1 text-xs text-white placeholder-white/20 focus:outline-none focus:border-emerald-500/60"
              placeholder="e.g. 60"
              value={data.coverage}
              onChange={(e) => updateField('coverage', e.target.value)}
              min="1"
              max="100"
            />
          </div>

          <div className="sm:col-span-8">
            <label className="block text-[10px] font-medium text-white/60 mb-0.5">
              Setbacks ({data.unit})
            </label>
            <div className="grid grid-cols-4 gap-1.5">
              {['front', 'rear', 'left', 'right'].map((side) => (
                <div key={side}>
                  <input
                    id={`setback-${side}`}
                    type="number"
                    className="w-full bg-white/[0.05] border border-white/10 rounded-lg px-2 py-1 text-xs text-white placeholder-white/20 focus:outline-none focus:border-emerald-500/60"
                    placeholder={side}
                    value={data.setbacks[side]}
                    onChange={(e) => updateSetback(side, e.target.value)}
                    min="0"
                    step="any"
                  />
                </div>
              ))}
            </div>
          </div>
        </div>

        {errors.setback_general && (
          <div className="p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-[11px] text-rose-400">
            {errors.setback_general}
          </div>
        )}
      </div>
    </div>
  )
}
