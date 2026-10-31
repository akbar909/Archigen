export function buildSpatialGraph(floor) {
  const graph = new Map([['exterior', new Set()], ...(floor.rooms || []).map(r => [r.id, new Set()])]);
  for (const door of floor.doors || []) {
    const a = door.room_id || door.roomId;
    const wall = floor.walls?.find(w => w.id === door.wall_id);
    const ids = wall?.room_ids || wall?.connected_rooms || [];
    const b = door.connected_room_id || ids.find(id => id !== a) || (wall?.type === 'exterior' || door.type === 'main_entrance' ? 'exterior' : null);
    if (!graph.has(a) || !graph.has(b) || a === b) continue;
    graph.get(a).add(b);
    graph.get(b).add(a);
  }
  return graph;
}
export function inaccessibleRooms(floor) {
  const graph = buildSpatialGraph(floor),
    queue = ['exterior'],
    reached = new Set(queue);
  // Upper storeys begin at their stair landing, which connects to the entrance below.
  for (const room of floor.rooms || []) if (floor.level > 0 && /stair_lobby/.test(room.type) && floor.stair_openings?.length) {
    reached.add(room.id);
    queue.push(room.id);
  }
  for (let i = 0; i < queue.length; i++) for (const neighbor of graph.get(queue[i]) || []) if (!reached.has(neighbor)) {
    reached.add(neighbor);
    queue.push(neighbor);
  }
  return (floor.rooms || []).filter(r => !reached.has(r.id) && !['garden', 'terrace', 'balcony'].includes(r.type));
}
