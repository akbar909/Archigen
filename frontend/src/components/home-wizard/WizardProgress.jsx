import { WIZARD_STEPS } from './wizard-constants'
import { Check } from 'lucide-react'

export default function WizardProgress({ currentStep, completedSteps }) {
  return (
    <div className="w-full">
      {/* Desktop stepper */}
      <div className="hidden md:flex items-center justify-between gap-1 py-1">
        {WIZARD_STEPS.map((step, idx) => {
          const isActive = currentStep === step.id
          const isCompleted = completedSteps.includes(step.id)
          const isPast = step.id < currentStep

          return (
            <div key={step.id} className="flex items-center flex-1 last:flex-none">
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <div
                  className={`
                    w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold
                    transition-all duration-300 border
                    ${isActive
                      ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-[0_0_10px_rgba(16,163,127,0.3)]'
                      : isCompleted || isPast
                        ? 'bg-emerald-500 border-emerald-500 text-black font-black'
                        : 'bg-white/5 border-white/10 text-white/40'
                    }
                  `}
                >
                  {isCompleted || isPast ? (
                    <Check size={11} strokeWidth={3.5} />
                  ) : (
                    <span>{step.id}</span>
                  )}
                </div>
                <span
                  className={`
                    text-[11px] font-medium hidden lg:inline whitespace-nowrap
                    ${isActive ? 'text-emerald-400 font-semibold' : isPast ? 'text-white/60' : 'text-white/30'}
                  `}
                >
                  {step.title}
                </span>
              </div>
              {idx < WIZARD_STEPS.length - 1 && (
                <div
                  className={`
                    flex-1 h-[1.5px] mx-2 rounded-full transition-colors duration-300
                    ${isPast ? 'bg-emerald-500/50' : 'bg-white/10'}
                  `}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* Mobile stepper */}
      <div className="flex md:hidden flex-col gap-1.5 py-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="text-sm">{WIZARD_STEPS[currentStep - 1]?.icon}</span>
            <span className="text-xs font-semibold text-white/90">
              {WIZARD_STEPS[currentStep - 1]?.title}
            </span>
          </div>
          <span className="text-[10px] font-medium text-white/40 bg-white/5 px-2 py-0.5 rounded-full">
            Step {currentStep} of {WIZARD_STEPS.length}
          </span>
        </div>
        <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-full transition-all duration-300"
            style={{ width: `${(currentStep / WIZARD_STEPS.length) * 100}%` }}
          />
        </div>
      </div>
    </div>
  )
}
