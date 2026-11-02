const list = value => Array.isArray(value) ? value : []

function furnitureIds(design) {
  const ids = new Set()
  const add = items => list(items).forEach(item => { if (item?.id) ids.add(String(item.id)) })
  add(design?.furniture)
  add(design?.exterior?.assets)
  list(design?.rooms).forEach(room => add(room.furniture))
  list(design?.floors).forEach(floor => {
    add(floor.furniture)
    list(floor.rooms).forEach(room => add(room.furniture))
  })
  return ids
}

function pruneAddedEmptyCollections(value, baseline) {
  if (!value || typeof value !== 'object') return
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      const previous = item?.id ? list(baseline).find(entry => entry?.id === item.id) : baseline?.[index]
      pruneAddedEmptyCollections(item, previous)
    })
    return
  }
  for (const key of Object.keys(value)) {
    pruneAddedEmptyCollections(value[key], baseline?.[key])
    // The asset helpers lazily create these collections. Removing a newly
    // added object should also undo those empty containers, not save them.
    if (['furniture', 'assets', 'deleted_furniture_ids'].includes(key)
      && Array.isArray(value[key]) && value[key].length === 0
      && !Object.hasOwn(baseline || {}, key)) delete value[key]
    else if (key === 'exterior' && value[key] && !Array.isArray(value[key])
      && Object.keys(value[key]).length === 0 && !Object.hasOwn(baseline || {}, key)) delete value[key]
  }
}

const stableValue = value => {
  if (Array.isArray(value)) return value.map(stableValue)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.keys(value).sort().map(key => [key, stableValue(value[key])]))
}

export function reconcileDraftDesign(previous, next, persisted) {
  if (!next || !persisted) return { design: next, isDirty: next !== persisted }
  const savedIds = furnitureIds(persisted)
  const nextIds = furnitureIds(next)
  const cancelledIds = new Set([...furnitureIds(previous)].filter(id => !savedIds.has(id) && !nextIds.has(id)))
  if (cancelledIds.size) next = structuredClone(next)
  if (cancelledIds.size && Array.isArray(next.deleted_furniture_ids)) {
    // A persisted/embedded object's tombstone remains necessary. Only discard
    // tombstones for objects known to have been added and removed in this draft.
    next.deleted_furniture_ids = next.deleted_furniture_ids.filter(id => !cancelledIds.has(String(id)))
  }
  if (cancelledIds.size) pruneAddedEmptyCollections(next, persisted)
  const isDirty = JSON.stringify(stableValue(next)) !== JSON.stringify(stableValue(persisted))
  // Preserve ordinary command identities: the 2D editor uses them to
  // distinguish its undo/redo transactions from external updates.
  return { design: !isDirty && cancelledIds.size ? structuredClone(persisted) : next, isDirty }
}
