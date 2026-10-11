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
} from './wizard-constants'

export default function DesignPreferencesStep({ data, onChange, errors }) {
  const updateField = (field, value) => {
    onChange({ ...data, [field]: value })
  }

  return (
    <div className="w-full max-w-4xl mx-auto space-y-3">
      {/* Architectural Style */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3.5 sm:p-4 backdrop-blur-sm shadow-sm space-y-2.5">
        <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
          Architectural Style <span className="text-rose-400">*</span>
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {ARCHITECTURAL_STYLES.map((style) => {
            const isSelected = data.architecturalStyle === style.id
            return (
              <button
                key={style.id}
                type="button"
                className={`p-2.5 rounded-lg border text-left transition-all flex flex-col justify-between cursor-pointer ${
                  isSelected
                    ? 'bg-emerald-500/15 border-emerald-500 text-white shadow-[0_0_10px_rgba(16,163,127,0.2)] ring-1 ring-emerald-500/50'
                    : 'bg-white/[0.03] border-white/10 text-white/70 hover:bg-white/[0.06] hover:text-white'
                }`}
                onClick={() => updateField('architecturalStyle', style.id)}
              >
                <div>
                  <span className="text-xs font-semibold text-white block mb-0.5">{style.label}</span>
                  <span className="text-[10px] text-white/50 leading-tight block line-clamp-2">{style.desc}</span>
                </div>
                {isSelected && (
                  <span className="mt-1.5 text-[10px] font-bold text-emerald-400">
                    ✓ Selected
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Exterior Design */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3.5 sm:p-4 backdrop-blur-sm shadow-sm space-y-3">
        <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
          Exterior Finishes & Envelope
        </h3>

        {/* Color Palette */}
        <div>
          <label className="block text-[10px] font-medium text-white/70 mb-1.5">
            Color Scheme
          </label>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-1.5">
            {EXTERIOR_COLORS.map((c) => {
              const isSelected = data.exteriorColor === c.id
              return (
                <button
                  key={c.id}
                  type="button"
                  className={`py-1.5 px-2 rounded-lg border transition-all flex items-center gap-1.5 text-center cursor-pointer ${
                    isSelected
                      ? 'bg-emerald-500/15 border-emerald-500 text-white ring-1 ring-emerald-500/50'
                      : 'bg-white/[0.03] border-white/10 text-white/70 hover:bg-white/[0.06]'
                  }`}
                  onClick={() => updateField('exteriorColor', c.id)}
                >
                  <span
                    className="w-4 h-4 rounded-full border border-white/20 flex-shrink-0"
                    style={{ backgroundColor: c.color }}
                  />
                  <span className="text-[10px] font-medium truncate">{c.label}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Wall Material & Roof Type */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-0.5">
          {/* Wall Material */}
          <div>
            <label className="block text-[10px] font-medium text-white/70 mb-1.5">Wall Material</label>
            <div className="grid grid-cols-3 gap-1.5">
              {WALL_MATERIALS.map((m) => {
                const isSelected = data.wallMaterial === m.id
                return (
                  <button
                    key={m.id}
                    type="button"
                    className={`py-1.5 px-2 rounded-md border text-center transition-all text-[11px] font-medium ${
                      isSelected
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-semibold'
                        : 'bg-white/[0.03] border-white/10 text-white/60 hover:bg-white/[0.06] hover:text-white'
                    }`}
                    onClick={() => updateField('wallMaterial', m.id)}
                  >
                    {m.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Roof Type */}
          <div>
            <label className="block text-[10px] font-medium text-white/70 mb-1.5">Roof Structure</label>
            <div className="grid grid-cols-3 gap-1.5">
              {ROOF_TYPES.map((r) => {
                const isSelected = data.roofType === r.id
                return (
                  <button
                    key={r.id}
                    type="button"
                    className={`py-1.5 px-2 rounded-md border text-center transition-all text-[11px] font-medium ${
                      isSelected
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-semibold'
                        : 'bg-white/[0.03] border-white/10 text-white/60 hover:bg-white/[0.06] hover:text-white'
                    }`}
                    onClick={() => updateField('roofType', r.id)}
                  >
                    {r.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Interior & Flooring */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3.5 sm:p-4 backdrop-blur-sm shadow-sm space-y-2.5">
        <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
          Interior Finishes
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Interior Style */}
          <div>
            <label className="block text-[10px] font-medium text-white/70 mb-1.5">Interior Decor Style</label>
            <div className="grid grid-cols-3 gap-1.5">
              {INTERIOR_STYLES.map((s) => {
                const isSelected = data.interiorStyle === s.id
                return (
                  <button
                    key={s.id}
                    type="button"
                    className={`py-1.5 px-2 rounded-md border text-center transition-all text-[11px] font-medium ${
                      isSelected
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-semibold'
                        : 'bg-white/[0.03] border-white/10 text-white/60 hover:bg-white/[0.06] hover:text-white'
                    }`}
                    onClick={() => updateField('interiorStyle', s.id)}
                  >
                    {s.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Flooring Material */}
          <div>
            <label className="block text-[10px] font-medium text-white/70 mb-1.5">Primary Flooring</label>
            <div className="grid grid-cols-3 gap-1.5">
              {FLOORING_MATERIALS.map((f) => {
                const isSelected = data.flooringMaterial === f.id
                return (
                  <button
                    key={f.id}
                    type="button"
                    className={`py-1.5 px-2 rounded-md border text-center transition-all text-[11px] font-medium ${
                      isSelected
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-300 font-semibold'
                        : 'bg-white/[0.03] border-white/10 text-white/60 hover:bg-white/[0.06] hover:text-white'
                    }`}
                    onClick={() => updateField('flooringMaterial', f.id)}
                  >
                    {f.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Furniture & Design Priorities */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Furniture */}
        <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3 sm:p-3.5 backdrop-blur-sm shadow-sm space-y-2">
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
            Furniture Level
          </h3>
          <div className="space-y-1.5">
            {FURNITURE_PREFS.map((f) => {
              const isSelected = data.furniture === f.id
              return (
                <button
                  key={f.id}
                  type="button"
                  className={`w-full py-1.5 px-2.5 rounded-lg border text-left transition-all flex items-center gap-2 cursor-pointer ${
                    isSelected
                      ? 'bg-emerald-500/15 border-emerald-500 text-white ring-1 ring-emerald-500/50'
                      : 'bg-white/[0.03] border-white/10 text-white/70 hover:bg-white/[0.06]'
                  }`}
                  onClick={() => updateField('furniture', f.id)}
                >
                  <span className="text-base">{f.icon}</span>
                  <div>
                    <span className="text-xs font-semibold text-white block leading-tight">{f.label}</span>
                    <span className="text-[10px] text-white/40 block">{f.desc}</span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* Design Priority */}
        <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3 sm:p-3.5 backdrop-blur-sm shadow-sm space-y-2">
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
            Design Priority
          </h3>
          <div className="space-y-1.5">
            {DESIGN_PRIORITIES.map((p) => {
              const isSelected = data.designPriority === p.id
              return (
                <button
                  key={p.id}
                  type="button"
                  className={`w-full py-1.5 px-2.5 rounded-lg border text-left transition-all flex items-center gap-2 cursor-pointer ${
                    isSelected
                      ? 'bg-emerald-500/15 border-emerald-500 text-white ring-1 ring-emerald-500/50'
                      : 'bg-white/[0.03] border-white/10 text-white/70 hover:bg-white/[0.06]'
                  }`}
                  onClick={() => updateField('designPriority', p.id)}
                >
                  <span className="text-base">{p.icon}</span>
                  <div>
                    <span className="text-xs font-semibold text-white block leading-tight">{p.label}</span>
                    <span className="text-[10px] text-white/40 block">{p.desc}</span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
