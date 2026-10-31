const ROOM_CATEGORIES = [
  [/kitchen/, /kitchen|cabinet|island|bar_stool|refrigerator|fridge|oven|stove|cooker|microwave|dishwasher|sink|dining/],
  [/bath|washroom|toilet|powder/, /bath|toilet|shower|vanity|storage|^sink$|^cabinet$/],
  [/dining/, /dining|bar_stool|sideboard|cabinet|console/],
  [/bed|guest|nursery/, /bed|nightstand|wardrobe|dresser|vanity|armchair|side_table|desk|bookshelf|storage|mirror|clock/],
  [/living|drawing|lounge|family/, /sofa|armchair|coffee_table|side_table|tv_unit|bookshelf|console|cabinet|storage/],
  [/office|study|work/, /desk|office_chair|bookshelf|cabinet|storage|armchair|side_table/],
  [/garage|parking/, /vehicle|car|storage|cabinet|workbench/],
  [/prayer|puja|meditation/, /rug|carpet|bookshelf|storage|bench/],
  [/hall|corridor|entrance|foyer/, /console|side_table|bench|storage|cabinet/],
]

// Recommendations only: the full uploaded library remains available in every
// room. Never infer upload availability or invent an asset from a room type.
export function isAssetRecommendedForRoom(asset, room) {
  const roomName = `${room?.type || ''} ${room?.name || ''}`.toLowerCase().replaceAll('_', ' ')
  if (/bath|washroom|toilet|powder/.test(roomName) && asset.group === 'ceiling_asset') {
    return /ceiling_lamp|ceiling_light|recessed|flush|bath/i.test(`${asset.id || ''} ${asset.name || ''}`) && !/chandelier|fan|pendant/i.test(`${asset.id || ''} ${asset.name || ''}`)
  }
  if (asset.group === 'ceiling_asset' || asset.group === 'floor_overlay' || asset.category === 'floor_lamp') return true
  if (asset.category === 'table_clock') return !/bath|garage|parking/.test(roomName)
  const rule = ROOM_CATEGORIES.find(([pattern]) => pattern.test(roomName))
  if (!rule) return true
  return rule[1].test(String(asset.category || '').toLowerCase())
}
