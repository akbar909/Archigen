import { useState, useCallback, useRef } from 'react'
import { toast } from 'react-hot-toast'
import { WIZARD_STEPS, DEFAULT_WIZARD_STATE } from './wizard-constants'
import {
  validatePlotDetails,
  validateRoomConfiguration,
  validateDesignPreferences,
  validateExtraFeatures,
  buildPromptFromWizard,
  getStyleFromWizard,
} from './wizard-utils'

import WizardProgress from './WizardProgress'
import WizardNavigation from './WizardNavigation'
import PlotDetailsStep from './PlotDetailsStep'
import RoomConfigurationStep from './RoomConfigurationStep'
import DesignPreferencesStep from './DesignPreferencesStep'
import ExtraFeaturesStep from './ExtraFeaturesStep'
import ReviewGenerateStep from './ReviewGenerateStep'

import { Sparkles, MessageSquare } from 'lucide-react'

export default function HomeWizard({ onGenerate, loading, onClose, onSwitchToPrompt }) {
  const [currentStep, setCurrentStep] = useState(1)
  const [wizardState, setWizardState] = useState(structuredClone(DEFAULT_WIZARD_STATE))
  const [errors, setErrors] = useState({})
  const [completedSteps, setCompletedSteps] = useState([])
  const [isGenerating, setIsGenerating] = useState(false)
  const contentRef = useRef(null)

  // Scroll to top of wizard content when step changes
  const scrollToTop = useCallback(() => {
    if (contentRef.current) {
      contentRef.current.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }, [])

  // ── Step validation ──
  const validateStep = useCallback(
    (step) => {
      let stepErrors = {}
      switch (step) {
        case 1:
          stepErrors = validatePlotDetails(wizardState.plot)
          break
        case 2:
          stepErrors = validateRoomConfiguration(wizardState.rooms, wizardState.plot.floors)
          break
        case 3:
          stepErrors = validateDesignPreferences(wizardState.design)
          break
        case 4:
          stepErrors = validateExtraFeatures()
          break
        default:
          break
      }
      setErrors(stepErrors)
      return Object.keys(stepErrors).length === 0
    },
    [wizardState]
  )

  // ── Navigation ──
  const handleNext = useCallback(() => {
    if (validateStep(currentStep)) {
      setCompletedSteps((prev) =>
        prev.includes(currentStep) ? prev : [...prev, currentStep]
      )
      setCurrentStep((prev) => Math.min(prev + 1, WIZARD_STEPS.length))
      setErrors({})
      scrollToTop()
    } else {
      toast.error('Please fix the errors before continuing')
    }
  }, [currentStep, validateStep, scrollToTop])

  const handleBack = useCallback(() => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1)
      setErrors({})
      scrollToTop()
    }
  }, [currentStep, scrollToTop])

  const handleEditStep = useCallback(
    (step) => {
      setCurrentStep(step)
      setErrors({})
      scrollToTop()
    },
    [scrollToTop]
  )

  // ── Field updates ──
  const updatePlot = useCallback((newPlot) => {
    setWizardState((prev) => ({ ...prev, plot: newPlot }))
  }, [])

  const updateRooms = useCallback((newRooms) => {
    setWizardState((prev) => ({ ...prev, rooms: newRooms }))
  }, [])

  const updateDesign = useCallback((newDesign) => {
    setWizardState((prev) => ({ ...prev, design: newDesign }))
  }, [])

  const updateFeatures = useCallback(({ features, featureConfigs, specialRequirements }) => {
    setWizardState((prev) => ({
      ...prev,
      features,
      featureConfigs,
      specialRequirements,
    }))
  }, [])

  // ── Generate ──
  const handleGenerate = useCallback(async () => {
    // Validate all steps before generating
    for (let step = 1; step <= 4; step++) {
      let stepErrors = {}
      switch (step) {
        case 1:
          stepErrors = validatePlotDetails(wizardState.plot)
          break
        case 2:
          stepErrors = validateRoomConfiguration(wizardState.rooms, wizardState.plot.floors)
          break
        case 3:
          stepErrors = validateDesignPreferences(wizardState.design)
          break
        case 4:
          stepErrors = validateExtraFeatures()
          break
        default:
          break
      }
      if (Object.keys(stepErrors).length > 0) {
        setErrors(stepErrors)
        setCurrentStep(step)
        toast.error(`Please fix errors in Step ${step} before generating`)
        scrollToTop()
        return
      }
    }

    if (isGenerating) return
    setIsGenerating(true)

    try {
      const prompt = buildPromptFromWizard(wizardState)
      const style = getStyleFromWizard(wizardState)

      await onGenerate({ prompt, style, timeout: 120 })
    } catch {
      // Error handled by store
    } finally {
      setIsGenerating(false)
    }
  }, [wizardState, onGenerate, isGenerating, scrollToTop])

  const isLastStep = currentStep === WIZARD_STEPS.length
  const effectiveLoading = loading || isGenerating

  return (
    <div className="flex flex-col h-full w-full bg-[#0d0d0d] overflow-hidden text-[#ececec] select-none">
      {/* Top Header */}
      <div className="flex-shrink-0 px-4 sm:px-6 py-2 border-b border-white/[0.08] bg-[#141414]">
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shadow-sm flex-shrink-0">
              <Sparkles size={13} />
            </div>
            <h1 className="text-xs sm:text-sm font-bold text-white tracking-tight">
              AI Architectural Design Wizard
            </h1>
          </div>

          <div className="flex items-center gap-1.5">
            {onSwitchToPrompt && (
              <button
                type="button"
                onClick={onSwitchToPrompt}
                className="flex items-center gap-1 text-[11px] text-white/60 hover:text-white px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 border border-white/10 transition-colors cursor-pointer"
                title="Switch to quick prompt box"
              >
                <MessageSquare size={11} />
                <span className="hidden sm:inline">Switch to</span> Prompt Box
              </button>
            )}

            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="text-[11px] text-white/50 hover:text-white px-2 py-0.5 rounded bg-white/5 hover:bg-white/10 transition-colors cursor-pointer"
              >
                Exit Wizard
              </button>
            )}
          </div>
        </div>

        {/* Stepper progress */}
        <WizardProgress currentStep={currentStep} completedSteps={completedSteps} />
      </div>

      {/* Step Content */}
      <div
        className="flex-1 overflow-y-auto px-3 sm:px-6 py-3 select-text"
        ref={contentRef}
      >
        {currentStep === 1 && (
          <PlotDetailsStep
            data={wizardState.plot}
            onChange={updatePlot}
            errors={errors}
          />
        )}
        {currentStep === 2 && (
          <RoomConfigurationStep
            data={wizardState.rooms}
            floors={wizardState.plot.floors}
            onChange={updateRooms}
            errors={errors}
          />
        )}
        {currentStep === 3 && (
          <DesignPreferencesStep
            data={wizardState.design}
            onChange={updateDesign}
            errors={errors}
          />
        )}
        {currentStep === 4 && (
          <ExtraFeaturesStep
            features={wizardState.features}
            featureConfigs={wizardState.featureConfigs}
            specialRequirements={wizardState.specialRequirements}
            onChange={updateFeatures}
            errors={errors}
          />
        )}
        {currentStep === 5 && (
          <ReviewGenerateStep
            wizardState={wizardState}
            onEditStep={handleEditStep}
            loading={effectiveLoading}
          />
        )}
      </div>

      {/* Navigation */}
      <WizardNavigation
        currentStep={currentStep}
        totalSteps={WIZARD_STEPS.length}
        onNext={handleNext}
        onBack={handleBack}
        onGenerate={handleGenerate}
        loading={effectiveLoading}
        isLastStep={isLastStep}
      />
    </div>
  )
}
