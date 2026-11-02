// Project stair geometry shared by placement, the CAD symbol and design checks.
// `steps` counts the risers/treads emitted by the Blender staircase builder.
export const STAIR_TYPES = ['u_shaped', 'straight', 'l_shaped'];
export const MIN_STAIR_TREAD = .25;
export const MAX_STAIR_RISER = .19;
export const STAIR_GAP = .16;
const finite = (value, fallback) => value == null ? fallback : Number(value);

export function defaultStairRisers(rise = 3) {
  return Math.max(16, Math.ceil(Number(rise) / .175 / 2 - 1e-9) * 2);
}

export function stairMetrics(stair, rise = stair.dimensions?.height ?? 3) {
  const type = stair.type || stair.configuration || 'u_shaped';
  const width = Number(stair.dimensions?.width), depth = Number(stair.dimensions?.depth);
  const acrossPlot = stair.run_axis === 'x', localWidth = acrossPlot ? depth : width, localDepth = acrossPlot ? width : depth;
  const requestedRisers = finite(stair.steps ?? stair.risers, defaultStairRisers(rise));
  const risers = Number.isFinite(requestedRisers) ? Math.ceil(Math.max(16, Math.trunc(requestedRisers)) / 2) * 2 : NaN;
  const availableWidth = type === 'u_shaped' ? (localWidth - STAIR_GAP) / 2 : type === 'l_shaped' ? Math.min(localWidth, localDepth) : localWidth;
  const requestedClearWidth = finite(stair.clear_width, type === 'u_shaped' ? availableWidth : Math.min(localWidth, 1.1));
  const clearWidth = Math.min(availableWidth, requestedClearWidth);
  const landingDepth = finite(stair.landing_depth, Math.max(.9, requestedClearWidth));
  const flightRisers = type === 'straight' ? risers : risers / 2;
  const runs = type === 'l_shaped' ? [localDepth - landingDepth, localWidth - landingDepth] : [localDepth - landingDepth];
  const tread = Math.min(...runs) / flightRisers;
  const minimumRun = landingDepth + flightRisers * MIN_STAIR_TREAD;
  const minimumAcross = type === 'u_shaped' ? 2 * requestedClearWidth + STAIR_GAP : type === 'l_shaped' ? minimumRun : requestedClearWidth;
  const minimumDepth = acrossPlot ? minimumAcross : minimumRun;
  const minimumWidth = acrossPlot ? minimumRun : minimumAcross;
  return { type, width, depth, localWidth, localDepth, acrossPlot, risers, requestedRisers, flightRisers, clearWidth, requestedClearWidth, availableWidth, landingDepth, runs, tread, riserHeight: Number(rise) / risers, minimumDepth, minimumWidth };
}

export function stairAccessBox(stair, destination = false) {
  const m = stairMetrics(stair), p = stair.position || {}, x = Number(p.x || 0), y = Number(p.y || 0), d = Math.max(m.clearWidth, finite(stair.access_depth, m.clearWidth));
  if (m.acrossPlot) return { x: x + m.width, y, right: x + m.width + d, top: y + m.depth };
  if (destination && m.type === 'straight') return { x, y: y + m.depth, right: x + m.width, top: y + m.depth + d };
  if (destination && m.type === 'l_shaped') return { x: x + m.width, y: y + m.depth - m.clearWidth, right: x + m.width + d, top: y + m.depth };
  return { x, y: y - d, right: x + (m.type === 'l_shaped' ? m.clearWidth : m.width), top: y };
}

export function stairPlanGeometry(stair) {
  if (stair.run_axis === 'x') {
    const width = Number(stair.dimensions?.width);
    const local = stairPlanGeometry({ ...stair, run_axis: 'y', dimensions: { ...stair.dimensions, width: stair.dimensions.depth, depth: stair.dimensions.width } });
    return {
      lines: local.lines.map(l => ({ x1: width-l.y1, y1: l.x1, x2: width-l.y2, y2: l.x2 })),
      flights: local.flights.map(f => ({ x: width-f.y-f.depth, y: f.x, width: f.depth, depth: f.width })),
      arrow: local.arrow.map(p => ({ x: width-p.y, y: p.x })),
    };
  }
  const m = stairMetrics(stair), lines = [], flights = [], w = m.width, d = m.depth, c = m.clearWidth;
  if (![w, d, c, m.tread, m.risers].every(Number.isFinite) || m.risers > 200 || m.tread <= 0) return { lines, flights, arrow: [] };
  const line = (x1, y1, x2, y2) => lines.push({ x1, y1, x2, y2 });
  const flight = (x, y, width, depth) => flights.push({ x, y, width, depth });
  if (m.type === 'straight') {
    const run = d - m.landingDepth;
    flight(0, 0, w, run);
    for (let i = 0; i <= m.risers; i++) line(0, run * i / m.risers, w, run * i / m.risers);
    return { lines, flights, arrow: [{ x: w / 2, y: .2 }, { x: w / 2, y: d - .2 }] };
  }
  if (m.type === 'l_shaped') {
    const runY = d - m.landingDepth, runX = w - m.landingDepth;
    flight(0, 0, c, runY); flight(m.landingDepth, d - c, runX, c);
    for (let i = 0; i <= m.flightRisers; i++) {
      line(0, runY * i / m.flightRisers, c, runY * i / m.flightRisers);
      line(m.landingDepth + runX * i / m.flightRisers, d - c, m.landingDepth + runX * i / m.flightRisers, d);
    }
    return { lines, flights, arrow: [{ x: c / 2, y: .2 }, { x: c / 2, y: d - c / 2 }, { x: w - .2, y: d - c / 2 }] };
  }
  const run = d - m.landingDepth, fw = (w - STAIR_GAP) / 2;
  flight(0, 0, fw, run); flight(fw + STAIR_GAP, 0, fw, run);
  for (let i = 0; i <= m.flightRisers; i++) {
    const y = run * i / m.flightRisers;
    line(0, y, fw, y); line(fw + STAIR_GAP, y, w, y);
  }
  return { lines, flights, arrow: [{ x: fw / 2, y: .2 }, { x: fw / 2, y: run + m.landingDepth / 2 }, { x: w - fw / 2, y: run + m.landingDepth / 2 }, { x: w - fw / 2, y: .2 }] };
}
