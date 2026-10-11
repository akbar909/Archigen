import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'

export default function WizardNavigation({ currentStep, totalSteps, onNext, onBack, onGenerate, loading, isLastStep }) {
  return (
    <div className="flex items-center justify-between px-4 sm:px-6 py-2 border-t border-white/[0.08] bg-[#121212]/95 backdrop-blur-md flex-shrink-0">
      <button
        type="button"
        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium
          text-white/60 bg-white/5 border border-white/[0.08]
          hover:bg-white/10 hover:text-white hover:border-white/15
          disabled:opacity-20 disabled:cursor-not-allowed
          transition-all cursor-pointer"
        onClick={onBack}
        disabled={currentStep === 1}
        aria-label="Go back"
      >
        <ChevronLeft size={14} />
        <span className="hidden sm:inline">Back</span>
      </button>

      <span className="text-[11px] text-white/30 font-medium">
        Step {currentStep} of {totalSteps}
      </span>

      {isLastStep ? (
        <button
          type="button"
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold
            bg-gradient-to-r from-emerald-600 to-emerald-500 text-white
            hover:from-emerald-500 hover:to-emerald-400
            disabled:opacity-50 disabled:cursor-not-allowed
            shadow-[0_0_15px_rgba(16,163,127,0.3)]
            transition-all active:scale-[0.98] cursor-pointer"
          onClick={onGenerate}
          disabled={loading}
          aria-label="Generate My House"
        >
          {loading ? (
            <>
              <Loader2 size={13} className="animate-spin" />
              <span>Generating…</span>
            </>
          ) : (
            <>
              <span>🏠</span>
              <span>Generate My House</span>
            </>
          )}
        </button>
      ) : (
        <button
          type="button"
          className="flex items-center gap-1 px-4 py-1.5 rounded-lg text-xs font-semibold
            bg-emerald-500/15 text-emerald-400 border border-emerald-500/30
            hover:bg-emerald-500/25 hover:border-emerald-500/50
            transition-all active:scale-[0.98] cursor-pointer"
          onClick={onNext}
          aria-label="Next step"
        >
          <span>Next</span>
          <ChevronRight size={14} />
        </button>
      )}
    </div>
  )
}
