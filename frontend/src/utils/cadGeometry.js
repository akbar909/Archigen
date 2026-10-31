// Architectural coordinates are always metres; +Y points north, +Z is elevation.
export const EPS = 1e-6;
export const clone = value => value == null ? value : JSON.parse(JSON.stringify(value));
export const uid = (prefix = 'entity') => `${prefix}_${globalThis.crypto?.randomUUID?.() || `${Date.now()}_${Math.random().toString(36).slice(2)}`}`;
export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
export const round = v => Math.round(v * 10000) / 10000;
export const distance = (a, b) => Math.hypot(b.x - a.x, b.y - a.y);
export function roomBox(room) {
  const x = Number(room.position?.x) || 0,
    y = Number(room.position?.y) || 0;
  const width = Number(room.dimensions?.width ?? room.width) || 1,
    depth = Number(room.dimensions?.depth ?? room.length) || 1;
  return {
    x,
    y,
    width,
    depth,
    right: x + width,
    top: y + depth
  };
}
export const containsPoint = (b, p, margin = 0) => p.x >= b.x + margin - EPS && p.x <= b.right - margin + EPS && p.y >= b.y + margin - EPS && p.y <= b.top - margin + EPS;
export const boxesOverlap = (a, b, gap = 0) => a.x < b.right + gap - EPS && a.right > b.x - gap + EPS && a.y < b.top + gap - EPS && a.top > b.y - gap + EPS;
export function rotatedRectangle(item, padding = 0) {
  const w = Number(item.dimensions?.width) / 2 + padding,
    d = Number(item.dimensions?.depth) / 2 + padding;
  // Blender's positive yaw maps to clockwise on the architectural XY plane.
  const angle = -(Number(item.rotation) || 0) * Math.PI / 180,
    c = Math.cos(angle),
    s = Math.sin(angle);
  return [[-w, -d], [w, -d], [w, d], [-w, d]].map(([x, y]) => ({
    x: item.position.x + x * c - y * s,
    y: item.position.y + x * s + y * c
  }));
}
export function polygonBounds(points) {
  const x = Math.min(...points.map(p => p.x)),
    y = Math.min(...points.map(p => p.y));
  const right = Math.max(...points.map(p => p.x)),
    top = Math.max(...points.map(p => p.y));
  return {
    x,
    y,
    right,
    top,
    width: right - x,
    depth: top - y
  };
}
export function polygonsOverlap(a, b) {
  if (!boxesOverlap(polygonBounds(a), polygonBounds(b))) return false;
  for (const poly of [a, b]) for (let i = 0; i < poly.length; i++) {
    const p = poly[i],
      q = poly[(i + 1) % poly.length],
      axis = {
        x: -(q.y - p.y),
        y: q.x - p.x
      };
    if (Math.hypot(axis.x, axis.y) < EPS) continue;
    const pa = a.map(v => v.x * axis.x + v.y * axis.y),
      pb = b.map(v => v.x * axis.x + v.y * axis.y);
    if (Math.max(...pa) <= Math.min(...pb) + EPS || Math.max(...pb) <= Math.min(...pa) + EPS) return false;
  }
  return true;
}
export function projectToSegment(point, start, end) {
  const dx = end.x - start.x,
    dy = end.y - start.y,
    length = Math.hypot(dx, dy);
  const t = length < EPS ? 0 : clamp(((point.x - start.x) * dx + (point.y - start.y) * dy) / (length * length), 0, 1);
  const position = {
    x: start.x + t * dx,
    y: start.y + t * dy
  };
  return {
    ...position,
    t,
    length,
    distance: distance(point, position)
  };
}
export function parseDimension(raw, unit = 'm') {
  const text = String(raw).trim().toLowerCase();
  const imperial = text.match(/^(-?\d+(?:\.\d+)?)\s*'\s*(?:(\d+(?:\.\d+)?)\s*(?:"|in)?)?$/);
  if (imperial) return Number(imperial[1]) * .3048 + Number(imperial[2] || 0) * .0254;
  const match = text.match(/^(-?\d+(?:\.\d+)?)\s*(m|meters?|metres?|cm|mm|ft|feet|foot|in|inches|\")?$/);
  if (!match) throw new Error('Enter a dimension such as 3.65 m, 12 ft, or 6\' 2".');
  const suffix = match[2] || unit;
  return round(Number(match[1]) * (/^(ft|feet|foot)$/.test(suffix) ? .3048 : /^(in|inches|")$/.test(suffix) ? .0254 : suffix === 'cm' ? .01 : suffix === 'mm' ? .001 : 1));
}
export function snapPoint(point, {
  enabled = true,
  step = .25,
  tolerance = .15,
  targets = []
} = {}) {
  if (!enabled) return {
    point,
    guides: []
  };
  const result = {
      x: round(Math.round(point.x / step) * step),
      y: round(Math.round(point.y / step) * step)
    },
    guides = [];
  for (const axis of ['x', 'y']) {
    let best = tolerance;
    for (const target of targets) if (Math.abs(point[axis] - target[axis]) < best) {
      best = Math.abs(point[axis] - target[axis]);
      result[axis] = target[axis];
    }
    if (best < tolerance) guides.push({
      axis,
      value: result[axis]
    });
  }
  return {
    point: result,
    guides
  };
}
export function svgToWorld(svg, clientX, clientY, plotDepth, scale = 40, margin = 2) {
  const matrix = svg.getScreenCTM();
  if (!matrix) return {
    x: 0,
    y: 0
  };
  const p = new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse());
  return {
    x: p.x / scale - margin,
    y: plotDepth + margin - p.y / scale
  };
}

// Broad-phase lookup for crowded plans. Each rectangle occupies every cell it
// crosses, so long or rotated footprints cannot disappear at cell boundaries.
export class SpatialHash {
  constructor(cellSize = 2) { this.cellSize = cellSize; this.cells = new Map(); }
  keys(bounds) {
    const keys = [];
    for (let x = Math.floor(bounds.x / this.cellSize); x <= Math.floor(bounds.right / this.cellSize); x++) {
      for (let y = Math.floor(bounds.y / this.cellSize); y <= Math.floor(bounds.top / this.cellSize); y++) keys.push(`${x}:${y}`);
    }
    return keys;
  }
  insert(id, bounds) {
    for (const key of this.keys(bounds)) {
      if (!this.cells.has(key)) this.cells.set(key, new Set());
      this.cells.get(key).add(id);
    }
  }
  query(bounds) { return new Set(this.keys(bounds).flatMap(key => [...(this.cells.get(key) || [])])); }
}
