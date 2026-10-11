/**
 * wizard-constants.js
 * Central constants & default state for the HomeWizard
 */

// ── Room types with metadata ──
export const ROOM_TYPES = [
  { id: 'master_bedroom', label: 'Master Bedroom', icon: '👑', category: 'bedroom', hasAttachedBath: true, maxCount: 2 },
  { id: 'bedroom', label: 'Bedroom', icon: '🛏️', category: 'bedroom', hasAttachedBath: true, maxCount: 6 },
  { id: 'bathroom', label: 'Bathroom', icon: '🚿', category: 'utility', maxCount: 6 },
  { id: 'kitchen', label: 'Kitchen', icon: '🍳', category: 'living', maxCount: 2 },
  { id: 'living_room', label: 'Living Room', icon: '🛋️', category: 'living', maxCount: 2 },
  { id: 'drawing_room', label: 'Drawing Room', icon: '🪑', category: 'living', maxCount: 2 },
  { id: 'dining_room', label: 'Dining Room', icon: '🍽️', category: 'living', maxCount: 2 },
  { id: 'garage', label: 'Garage', icon: '🚗', category: 'utility', maxCount: 2 },
  { id: 'balcony', label: 'Balcony', icon: '🌅', category: 'outdoor', maxCount: 4 },
  { id: 'prayer_room', label: 'Prayer Room', icon: '🕌', category: 'special', maxCount: 1 },
  { id: 'study_room', label: 'Study Room', icon: '📚', category: 'special', maxCount: 2 },
  { id: 'laundry_room', label: 'Laundry Room', icon: '🧺', category: 'utility', maxCount: 1 },
  { id: 'storage_room', label: 'Storage Room', icon: '📦', category: 'utility', maxCount: 2 },
  { id: 'servant_room', label: 'Servant Room', icon: '🏠', category: 'special', maxCount: 2 },
  { id: 'garden', label: 'Garden', icon: '🌿', category: 'outdoor', maxCount: 2 },
  { id: 'terrace', label: 'Terrace', icon: '☀️', category: 'outdoor', maxCount: 2 },
]

export const ROOM_SIZES = [
  { id: 'small', label: 'Small' },
  { id: 'medium', label: 'Medium' },
  { id: 'large', label: 'Large' },
]

export const ROOM_LOCATIONS = [
  { id: 'no_preference', label: 'No Preference' },
  { id: 'front', label: 'Front' },
  { id: 'back', label: 'Back' },
  { id: 'left', label: 'Left' },
  { id: 'right', label: 'Right' },
]

// ── Building configuration ──
export const FLOOR_OPTIONS = [
  { value: 1, label: 'Ground Floor Only' },
  { value: 2, label: 'Ground + 1 Floor' },
  { value: 3, label: 'Ground + 2 Floors' },
  { value: 4, label: 'Ground + 3 Floors' },
]

export const BUILDING_TYPES = [
  { id: 'house', label: 'House', icon: '🏠' },
  { id: 'villa', label: 'Villa', icon: '🏡' },
  { id: 'bungalow', label: 'Bungalow', icon: '🏘️' },
]

export const ORIENTATIONS = [
  { id: 'north', label: 'North', icon: '⬆️' },
  { id: 'south', label: 'South', icon: '⬇️' },
  { id: 'east', label: 'East', icon: '➡️' },
  { id: 'west', label: 'West', icon: '⬅️' },
]

export const ROAD_ACCESS = [
  { id: 'front', label: 'Front' },
  { id: 'left', label: 'Left Side' },
  { id: 'right', label: 'Right Side' },
  { id: 'front_and_side', label: 'Front & Side' },
]

export const UNITS = [
  { id: 'ft', label: 'Feet' },
  { id: 'm', label: 'Meters' },
]

// ── Architectural styles ──
export const ARCHITECTURAL_STYLES = [
  { id: 'modern', label: 'Modern', desc: 'Clean lines, open spaces, large windows' },
  { id: 'minimalist', label: 'Minimalist', desc: 'Simple forms, neutral colors, less is more' },
  { id: 'contemporary', label: 'Contemporary', desc: 'Current trends, mixed materials' },
  { id: 'traditional', label: 'Traditional', desc: 'Classic aesthetics, ornamental details' },
  { id: 'mediterranean', label: 'Mediterranean', desc: 'Warm tones, arches, terracotta' },
  { id: 'luxury', label: 'Luxury', desc: 'Premium finishes, grand proportions' },
]

export const ROOF_TYPES = [
  { id: 'flat', label: 'Flat Roof' },
  { id: 'pitched', label: 'Pitched Roof' },
]

export const EXTERIOR_COLORS = [
  { id: 'white', label: 'White', color: '#f5f5f5' },
  { id: 'cream', label: 'Cream', color: '#f5f0e1' },
  { id: 'grey', label: 'Grey', color: '#9ca3af' },
  { id: 'beige', label: 'Beige', color: '#d4c5a9' },
  { id: 'charcoal', label: 'Charcoal', color: '#374151' },
  { id: 'terracotta', label: 'Terracotta', color: '#c2703e' },
  { id: 'navy', label: 'Navy', color: '#1e3a5f' },
  { id: 'sage', label: 'Sage', color: '#87a878' },
]

export const WALL_MATERIALS = [
  { id: 'plaster', label: 'Plaster' },
  { id: 'brick', label: 'Brick' },
  { id: 'stone', label: 'Stone' },
  { id: 'wood_cladding', label: 'Wood Cladding' },
  { id: 'concrete', label: 'Concrete' },
]

export const INTERIOR_STYLES = [
  { id: 'contemporary', label: 'Contemporary' },
  { id: 'scandinavian', label: 'Scandinavian' },
  { id: 'industrial', label: 'Industrial' },
  { id: 'bohemian', label: 'Bohemian' },
  { id: 'classic', label: 'Classic' },
]

export const FLOORING_MATERIALS = [
  { id: 'hardwood', label: 'Hardwood' },
  { id: 'marble', label: 'Marble' },
  { id: 'tile', label: 'Tile' },
  { id: 'vinyl', label: 'Vinyl' },
  { id: 'carpet', label: 'Carpet' },
]

export const FURNITURE_PREFS = [
  { id: 'fully_furnished', label: 'Fully Furnished', icon: '🪑', desc: 'Complete furniture in every room' },
  { id: 'partially_furnished', label: 'Partially Furnished', icon: '🛋️', desc: 'Key pieces in main rooms' },
  { id: 'unfurnished', label: 'Unfurnished', icon: '📐', desc: 'Empty rooms, structure only' },
]

export const DESIGN_PRIORITIES = [
  { id: 'space_efficiency', label: 'Space Efficiency', icon: '📏', desc: 'Maximize usable area' },
  { id: 'aesthetics', label: 'Aesthetics', icon: '✨', desc: 'Beautiful appearance' },
  { id: 'balanced', label: 'Balanced', icon: '⚖️', desc: 'Best of both worlds' },
]

export const BUDGET_OPTIONS = [
  { id: 'economy', label: 'Economy', icon: '💰' },
  { id: 'standard', label: 'Standard', icon: '💰💰' },
  { id: 'premium', label: 'Premium', icon: '💰💰💰' },
  { id: 'custom', label: 'Custom Budget', icon: '✏️' },
]

// ── Extra features ──
export const EXTRA_FEATURES = [
  { id: 'front_garden', label: 'Front Garden', icon: '🌻' },
  { id: 'back_garden', label: 'Back Garden', icon: '🌿' },
  { id: 'boundary_wall', label: 'Boundary Wall', icon: '🧱' },
  { id: 'entrance_gate', label: 'Entrance Gate', icon: '🚪' },
  { id: 'car_parking', label: 'Car Parking', icon: '🅿️', hasConfig: true, configLabel: 'Number of vehicles', configKey: 'parkingSpaces', configDefault: 1, configMax: 4 },
  { id: 'swimming_pool', label: 'Swimming Pool', icon: '🏊' },
  { id: 'rooftop_terrace', label: 'Rooftop Terrace', icon: '🌇' },
  { id: 'balcony', label: 'Balcony', icon: '🌅' },
  { id: 'outdoor_seating', label: 'Outdoor Seating', icon: '🪑' },
  { id: 'exterior_lighting', label: 'Exterior Lighting', icon: '💡' },
  { id: 'solar_panels', label: 'Solar Panels', icon: '☀️' },
  { id: 'storage_area', label: 'Storage Area', icon: '📦' },
  { id: 'laundry_area', label: 'Laundry Area', icon: '🧺' },
  { id: 'servant_quarters', label: 'Servant Quarters', icon: '🏠' },
]

// ── Wizard steps ──
export const WIZARD_STEPS = [
  { id: 1, title: 'Plot Details', shortTitle: 'Plot', icon: '📐' },
  { id: 2, title: 'Room Configuration', shortTitle: 'Rooms', icon: '🏗️' },
  { id: 3, title: 'Design Preferences', shortTitle: 'Design', icon: '🎨' },
  { id: 4, title: 'Extra Features', shortTitle: 'Features', icon: '⭐' },
  { id: 5, title: 'Review & Generate', shortTitle: 'Review', icon: '🚀' },
]

// ── Default wizard form state ──
export const DEFAULT_WIZARD_STATE = {
  // Step 1 - Plot
  plot: {
    width: '',
    length: '',
    unit: 'ft',
    floors: 1,
    buildingType: 'house',
    orientation: 'north',
    roadAccess: 'front',
    coverage: '',
    setbacks: {
      front: '',
      rear: '',
      left: '',
      right: '',
    },
    additionalSiteRequirements: '',
  },
  // Step 2 - Rooms
  rooms: [],
  // Step 3 - Design
  design: {
    architecturalStyle: 'modern',
    roofType: 'flat',
    exteriorColor: 'white',
    wallMaterial: 'plaster',
    interiorStyle: 'contemporary',
    flooringMaterial: 'tile',
    furniture: 'fully_furnished',
    designPriority: 'balanced',
    budget: 'standard',
    customBudget: '',
    customBudgetCurrency: 'USD',
  },
  // Step 4 - Features
  features: {},
  featureConfigs: {},
  specialRequirements: '',
}

export const SPECIAL_REQUIREMENTS_MAX_LENGTH = 1000
