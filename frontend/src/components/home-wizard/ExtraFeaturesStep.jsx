import { EXTRA_FEATURES, SPECIAL_REQUIREMENTS_MAX_LENGTH } from './wizard-constants'
import { Plus, Minus } from 'lucide-react'

export default function ExtraFeaturesStep({
  features,
  featureConfigs,
  specialRequirements,
  onChange,
}) {
  const toggleFeature = (featureId) => {
    const newFeatures = { ...features, [featureId]: !features[featureId] }
    onChange({ features: newFeatures, featureConfigs, specialRequirements })
  }

  const updateFeatureConfig = (featureId, key, value) => {
    const newConfigs = {
      ...featureConfigs,
      [featureId]: { ...(featureConfigs[featureId] || {}), [key]: value },
    }
    onChange({ features, featureConfigs: newConfigs, specialRequirements })
  }

  const updateSpecialRequirements = (value) => {
    if (value.length <= SPECIAL_REQUIREMENTS_MAX_LENGTH) {
      onChange({ features, featureConfigs, specialRequirements: value })
    }
  }

  return (
    <div className="w-full max-w-4xl mx-auto space-y-3">
      {/* Selectable Features */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3.5 sm:p-4 backdrop-blur-sm shadow-sm space-y-2.5">
        <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
          Select Amenities & Features
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {EXTRA_FEATURES.map((feat) => {
            const isEnabled = !!features[feat.id]
            return (
              <div key={feat.id} className="flex flex-col gap-1">
                <button
                  type="button"
                  className={`py-2 px-2.5 rounded-lg border text-center transition-all flex flex-col items-center justify-center gap-1 cursor-pointer relative ${
                    isEnabled
                      ? 'bg-emerald-500/15 border-emerald-500 text-white shadow-[0_0_10px_rgba(16,163,127,0.2)] ring-1 ring-emerald-500/50'
                      : 'bg-white/[0.03] border-white/10 text-white/70 hover:bg-white/[0.06] hover:text-white'
                  }`}
                  onClick={() => toggleFeature(feat.id)}
                >
                  <span className="text-xl">{feat.icon}</span>
                  <span className="text-[11px] font-semibold leading-tight line-clamp-1">{feat.label}</span>
                  {isEnabled && (
                    <span className="absolute top-1 right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 text-black text-[9px] font-black flex items-center justify-center">
                      ✓
                    </span>
                  )}
                </button>

                {isEnabled && feat.hasConfig && (
                  <div className="flex items-center justify-between px-2 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-md text-[11px]">
                    <span className="text-emerald-300 font-medium text-[10px]">{feat.configLabel}</span>
                    <div className="flex items-center gap-0.5 bg-white/5 rounded p-0.5">
                      <button
                        type="button"
                        className="w-4 h-4 flex items-center justify-center rounded bg-white/5 hover:bg-white/15 text-white/70"
                        onClick={() => {
                          const cur = featureConfigs[feat.id]?.[feat.configKey] || feat.configDefault
                          updateFeatureConfig(feat.id, feat.configKey, Math.max(1, cur - 1))
                        }}
                      >
                        <Minus size={9} />
                      </button>
                      <span className="w-4 text-center text-[10px] font-bold text-white tabular-nums">
                        {featureConfigs[feat.id]?.[feat.configKey] || feat.configDefault}
                      </span>
                      <button
                        type="button"
                        className="w-4 h-4 flex items-center justify-center rounded bg-white/5 hover:bg-white/15 text-white/70"
                        onClick={() => {
                          const cur = featureConfigs[feat.id]?.[feat.configKey] || feat.configDefault
                          updateFeatureConfig(feat.id, feat.configKey, Math.min(feat.configMax, cur + 1))
                        }}
                      >
                        <Plus size={9} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Special Requirements */}
      <div className="bg-white/[0.03] border border-white/[0.08] rounded-xl p-3.5 sm:p-4 backdrop-blur-sm shadow-sm space-y-2">
        <h3 className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
          Custom Architectural Requirements (Optional)
        </h3>

        <div className="relative">
          <textarea
            className="w-full bg-white/[0.05] border border-white/10 rounded-lg px-3 py-2 text-xs text-white placeholder-white/20 focus:outline-none focus:border-emerald-500/60 transition-all resize-none"
            placeholder="e.g. Master bedroom facing garden, high ceilings in lounge, wheelchair ramp at entrance..."
            value={specialRequirements}
            onChange={(e) => updateSpecialRequirements(e.target.value)}
            rows={2}
            maxLength={SPECIAL_REQUIREMENTS_MAX_LENGTH}
          />
          <div className="flex justify-end pt-0.5">
            <span className="text-[10px] text-white/40">
              {specialRequirements.length} / {SPECIAL_REQUIREMENTS_MAX_LENGTH}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
