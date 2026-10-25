/**
 * wizard-utils.js
 * Validation, conversion, and utility functions for the HomeWizard
 */
import {
  ROOM_TYPES,
  ARCHITECTURAL_STYLES,
  ROOF_TYPES,
  FURNITURE_PREFS,
  DESIGN_PRIORITIES,
  EXTRA_FEATURES,
  EXTERIOR_COLORS,
  WALL_MATERIALS,
  INTERIOR_STYLES,
  FLOORING_MATERIALS,
  BUILDING_TYPES,
  ORIENTATIONS,
  ROAD_ACCESS,
  FLOOR_OPTIONS,
} from './wizard-constants'

// ── Step 1 Validation ──
export function validatePlotDetails(plot) {
  const errors = {}

  const width = parseFloat(plot.width)
  const length = parseFloat(plot.length)

  if (!plot.width || isNaN(width) || width <= 0) {
    errors.width = 'Plot width must be a positive number'
  } else if (width > 1000) {
    errors.width = 'Plot width seems unrealistically large (max 1000)'
  } else if (width < 10 && plot.unit === 'ft') {
    errors.width = 'Minimum width is 10 ft'
  } else if (width < 3 && plot.unit === 'm') {
    errors.width = 'Minimum width is 3 m'
  }

  if (!plot.length || isNaN(length) || length <= 0) {
    errors.length = 'Plot length must be a positive number'
  } else if (length > 1000) {
    errors.length = 'Plot length seems unrealistically large (max 1000)'
  } else if (length < 10 && plot.unit === 'ft') {
    errors.length = 'Minimum length is 10 ft'
  } else if (length < 3 && plot.unit === 'm') {
    errors.length = 'Minimum length is 3 m'
  }

  // Validate setbacks if provided
  const setbackFields = ['front', 'rear', 'left', 'right']
  for (const field of setbackFields) {
    const val = plot.setbacks[field]
    if (val !== '' && val !== null && val !== undefined) {
      const num = parseFloat(val)
      if (isNaN(num) || num < 0) {
        errors[`setback_${field}`] = `${field.charAt(0).toUpperCase() + field.slice(1)} setback must be a non-negative number`
      }
    }
  }

  // Check buildable area if setbacks provided
  if (!errors.width && !errors.length) {
    const leftSetback = parseFloat(plot.setbacks.left) || 0
    const rightSetback = parseFloat(plot.setbacks.right) || 0
    const frontSetback = parseFloat(plot.setbacks.front) || 0
    const rearSetback = parseFloat(plot.setbacks.rear) || 0

    const buildableWidth = width - leftSetback - rightSetback
    const buildableLength = length - frontSetback - rearSetback

    if (buildableWidth <= 0) {
      errors.setback_general = 'Left + Right setbacks exceed plot width. No buildable area remains.'
    } else if (buildableLength <= 0) {
      errors.setback_general = 'Front + Rear setbacks exceed plot length. No buildable area remains.'
    }
  }

  // Coverage validation
  if (plot.coverage) {
    const cov = parseFloat(plot.coverage)
    if (isNaN(cov) || cov <= 0 || cov > 100) {
      errors.coverage = 'Coverage must be between 1% and 100%'
    }
  }

  return errors
}

// ── Step 2 Validation ──
export function validateRoomConfiguration(rooms, floors) {
  const errors = {}

  if (!rooms || rooms.length === 0) {
    errors.general = 'Please select at least one room'
    return errors
  }

  // Check floor assignments for validity
  for (const room of rooms) {
    if (room.floor !== undefined && room.floor >= floors) {
      errors[`room_${room.id}`] = `${getLabelForRoom(room.type)} is assigned to floor ${room.floor} but the building only has ${floors} floor(s)`
    }
    if (room.count <= 0) {
      errors[`room_${room.id}_count`] = `${getLabelForRoom(room.type)} must have at least 1 room`
    }
  }

  return errors
}

// ── Step 3 Validation (Design prefs are optional, minimal validation) ──
export function validateDesignPreferences(design) {
  const errors = {}
  if (design.budget === 'custom' && design.customBudget) {
    const val = parseFloat(design.customBudget)
    if (isNaN(val) || val <= 0) {
      errors.customBudget = 'Please enter a valid budget amount'
    }
  }
  return errors
}

// ── Step 4 Validation (all optional) ──
export function validateExtraFeatures() {
  return {}
}

// ── Compute plot area ──
export function computePlotArea(width, length, unit) {
  const w = parseFloat(width)
  const l = parseFloat(length)
  if (isNaN(w) || isNaN(l) || w <= 0 || l <= 0) return null
  const area = w * l
  return { area: Math.round(area * 100) / 100, unit: unit === 'm' ? 'sq m' : 'sq ft' }
}

// ── Get room label ──
export function getLabelForRoom(typeId) {
  const found = ROOM_TYPES.find((r) => r.id === typeId)
  return found ? found.label : typeId
}

// ── Get floor label ──
export function getFloorLabel(floorIndex) {
  if (floorIndex === 0) return 'Ground Floor'
  if (floorIndex === 1) return '1st Floor'
  if (floorIndex === 2) return '2nd Floor'
  if (floorIndex === 3) return '3rd Floor'
  return `Floor ${floorIndex}`
}

// ── Convert wizard state → prompt for Gemini ──
export function buildPromptFromWizard(wizardState) {
  const { plot, rooms, design, features, featureConfigs, specialRequirements } = wizardState

  const parts = []

  // Plot description
  const unitLabel = plot.unit === 'm' ? 'meters' : 'feet'
  parts.push(`Design a ${plot.buildingType} on a ${plot.width}x${plot.length} ${unitLabel} ${plot.orientation}-facing plot.`)

  // Floors
  const floorOption = FLOOR_OPTIONS.find((f) => f.value === plot.floors)
  if (floorOption) {
    // Keep this sentence machine-readable as well as friendly. The backend's
    // constraint parser understands "2 floors"; "Ground + 1 Floor" alone is
    // only a display label and previously collapsed multi-floor wizard plans
    // back to one storey.
    parts.push(`${plot.floors} floors total (${floorOption.label}).`)
  }

  // Road access
  parts.push(`Road access from ${plot.roadAccess.replace('_', ' ')}.`)

  // Setbacks
  const setbackParts = []
  if (plot.setbacks.front) setbackParts.push(`front: ${plot.setbacks.front}${plot.unit}`)
  if (plot.setbacks.rear) setbackParts.push(`rear: ${plot.setbacks.rear}${plot.unit}`)
  if (plot.setbacks.left) setbackParts.push(`left: ${plot.setbacks.left}${plot.unit}`)
  if (plot.setbacks.right) setbackParts.push(`right: ${plot.setbacks.right}${plot.unit}`)
  if (setbackParts.length > 0) parts.push(`Setbacks: ${setbackParts.join(', ')}.`)
  if (plot.coverage) parts.push(`Maximum coverage: ${plot.coverage}%.`)

  // Rooms
  if (rooms.length > 0) {
    const roomDescriptions = rooms.map((room) => {
      const label = getLabelForRoom(room.type)
      // Put the count, room type and floor next to one another so this prompt
      // remains compatible with natural-language generation outside the
      // structured wizard payload.
      let desc = `${room.count} ${label}`
      if (room.floor !== undefined && plot.floors > 1) desc += ` on ${getFloorLabel(room.floor)}`
      if (room.preferredSize) desc += ` (${room.preferredSize})`
      if (room.attachedBathroom) desc += ' with attached bathroom'
      if (room.preferredLocation && room.preferredLocation !== 'no_preference') desc += ` at ${room.preferredLocation}`
      return desc
    })
    parts.push(`Rooms: ${roomDescriptions.join(', ')}.`)
  }

  // Design preferences
  const styleMeta = ARCHITECTURAL_STYLES.find((s) => s.id === design.architecturalStyle)
  if (styleMeta) parts.push(`Architectural style: ${styleMeta.label}.`)
  parts.push(`Roof: ${design.roofType}.`)
  if (design.exteriorColor) parts.push(`Exterior color: ${design.exteriorColor}.`)
  if (design.wallMaterial) parts.push(`Wall material: ${design.wallMaterial}.`)
  if (design.interiorStyle) parts.push(`Interior style: ${design.interiorStyle}.`)
  if (design.flooringMaterial) parts.push(`Flooring: ${design.flooringMaterial}.`)

  const furnPref = FURNITURE_PREFS.find((f) => f.id === design.furniture)
  if (furnPref) parts.push(`Furniture: ${furnPref.label}.`)

  const prioPref = DESIGN_PRIORITIES.find((p) => p.id === design.designPriority)
  if (prioPref) parts.push(`Design priority: ${prioPref.label}.`)

  if (design.budget) {
    const budgetLabel = design.budget === 'custom' && design.customBudget
      ? `Custom (${design.customBudget})`
      : design.budget.charAt(0).toUpperCase() + design.budget.slice(1)
    parts.push(`Budget: ${budgetLabel}.`)
  }

  // Features
  const enabledFeatures = Object.entries(features)
    .filter(([, enabled]) => enabled)
    .map(([id]) => {
      const meta = EXTRA_FEATURES.find((f) => f.id === id)
      let label = meta ? meta.label : id
      if (featureConfigs[id]?.parkingSpaces) {
        label += ` (${featureConfigs[id].parkingSpaces} vehicles)`
      }
      return label
    })
  if (enabledFeatures.length > 0) parts.push(`Additional features: ${enabledFeatures.join(', ')}.`)

  // Special requirements
  if (specialRequirements?.trim()) {
    parts.push(`Special requirements: ${specialRequirements.trim()}.`)
  }

  return parts.join(' ')
}

// ── Determine style from wizard state for existing API ──
export function getStyleFromWizard(wizardState) {
  const style = wizardState.design.architecturalStyle
  // Map to the styles used by the existing ChatInput
  const styleMap = {
    modern: 'modern',
    minimalist: 'minimal',
    contemporary: 'modern',
    traditional: 'classic',
    mediterranean: 'coastal',
    luxury: 'modern',
  }
  return styleMap[style] || 'modern'
}
