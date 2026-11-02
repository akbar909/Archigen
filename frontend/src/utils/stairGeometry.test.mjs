import test from 'node:test';
import assert from 'node:assert/strict';
import { validateClientDesign } from './clientArchitecturalValidator.js';
import { createStairPlacement, synchronizeStairs } from './verticalCirculation.js';
import { stairAccessBox, stairMetrics, stairPlanGeometry } from './stairGeometry.js';
import { doorApproachBox } from './doorClearance.js';
import { boxesOverlap, roomBox } from './cadGeometry.js';

function designFixture(stairChanges = {}) {
  const stair = { id: 'stair', type: 'u_shaped', position: { x: 2, y: 2, z: 0 }, dimensions: { width: 2.2, depth: 3.45, height: 3 }, steps: 18, risers: 18, clear_width: 1, landing_depth: 1, access_depth: 1, headroom: 2.1, ...stairChanges };
  const floors = [0, 1].map(level => ({ id: `f${level}`, level, elevation: level * 3, floor_height: 3, rooms: [{ id: `lobby${level}`, type: 'stair_lobby', position: { x: 0, y: 0, z: level * 3 }, dimensions: { width: 8, depth: 8, height: 3 } }], walls: [], doors: [], windows: [], furniture: [], stairs: level ? [] : [stair], stair_openings: level ? [{ id: 'shaft', serves_stair_id: stair.id, position: { ...stair.position, z: 3 }, dimensions: { ...stair.dimensions, height: .2 } }] : [] }));
  return { floors };
}
const stairIssues = design => validateClientDesign(design).filter(issue => /^stair-|shaft-/.test(issue.code));
const has = (design, code) => stairIssues(design).some(issue => issue.code === code);

test('an across-plot U stair preserves real going, east access and the slab clearance', () => {
  const design = designFixture({ run_axis: 'x', opening_clearance: .05, access_depth: 1.15, dimensions: { width: 3.25, depth: 2.2, height: 3 } });
  const stair = design.floors[0].stairs[0];
  assert.equal(stairMetrics(stair).tread, .25);
  assert.equal(stairMetrics(stair).clearWidth, 1);
  assert.deepEqual(stairAccessBox(stair), {x:5.25,y:2,right:6.4,top:4.2});
  assert.deepEqual(stairIssues(design), []);
  const geometry = stairPlanGeometry(stair);
  assert.equal(geometry.flights.length, 2);
  assert.ok(geometry.lines.every(line => [line.x1,line.x2].every(x=>x>=0&&x<=3.25) && [line.y1,line.y2].every(y=>y>=0&&y<=2.2)));
  synchronizeStairs(design);
  assert.equal(design.floors[1].stair_openings[0].run_axis, 'x');
  assert.equal(design.floors[1].stair_openings[0].dimensions.width, 3.3);
  assert.equal(design.floors[1].stair_openings[0].dimensions.depth, 2.25);
  assert.deepEqual(stairIssues(design), []);
  stair.dimensions.width = 3;
  assert.match(stairIssues(design).find(issue => issue.code === 'stair-tread').message, /3\.25 m width/);
});

test('a reserved U stair with a full landing and clear access passes stair checks', () => {
  const design = designFixture();
  assert.deepEqual(stairIssues(design), []);
  const metrics = stairMetrics(design.floors[0].stairs[0]);
  assert.equal(metrics.risers, 18);
  assert.ok(Math.abs(metrics.tread - 2.45 / 9) < 1e-9);
});

test('undersized straight stairs and deep U landings report their actual required run', () => {
  const straight = designFixture({ type: 'straight', clear_width: .9, landing_depth: .9, dimensions: { width: .9, depth: 1.8, height: 3 } });
  assert.ok(has(straight, 'stair-tread'));
  assert.match(stairIssues(straight).find(issue => issue.code === 'stair-tread').message, /5\.40 m/);
  const u = designFixture({ landing_depth: 1.6, dimensions: { width: 2.2, depth: 3.6, height: 3 } });
  assert.ok(has(u, 'stair-tread'), 'using a fixed 0.9 m landing would incorrectly accept this footprint');
  assert.equal(stairMetrics(u.floors[0].stairs[0]).minimumDepth, 3.85);
});

test('stair checks enforce available clear width, landing depth and both L runs', () => {
  assert.ok(has(designFixture({ dimensions: { width: 1.9, depth: 3.45, height: 3 } }), 'stair-width'));
  assert.ok(has(designFixture({ landing_depth: .9 }), 'stair-landing'));
  assert.ok(has(designFixture({ type: 'l_shaped', clear_width: 1.1, landing_depth: 1.1, dimensions: { width: 3.2, depth: 3.8, height: 3 } }), 'stair-tread'));
  assert.ok(has(designFixture({ type: 'l_shaped', clear_width: 1, landing_depth: 1.6, dimensions: { width: 3.7, depth: 3.8, height: 3 } }), 'stair-tread'), 'explicit L landing depth reduces both runs');
  assert.equal(stairMetrics({ type: 'straight', clear_width: 1.4, dimensions: { width: 1.4, depth: 6 } }).clearWidth, 1.4);
});

test('malformed riser counts, excessive rise and ignored rotations cannot pass validation', () => {
  assert.ok(has(designFixture({ steps: 17, risers: 17 }), 'stair-risers'));
  assert.ok(has(designFixture({ steps: 18, risers: 20 }), 'stair-risers'));
  const fractional = designFixture({ steps: 18.2, risers: 18.2 });
  assert.ok(has(fractional, 'stair-risers'));
  assert.equal(stairMetrics(fractional.floors[0].stairs[0]).risers, 18, 'metrics must match the renderer count even when the supplied count is rejected');
  assert.ok(has(designFixture({ rotation: 90 }), 'stair-rotation'));
  const tall = designFixture();
  tall.floors[0].floor_height = 4.2;
  assert.ok(has(tall, 'stair-rise'));
});

test('placement grows the stair footprint when a taller storey needs more risers', () => {
  for (const type of ['straight', 'l_shaped', 'u_shaped']) {
    const floor = { floor_height: 4.2, rooms: [{ id: 'lobby', position: { x: 0, y: 0 }, dimensions: { width: 12, depth: 12 } }] };
    const stair = createStairPlacement(floor, { x: 6, y: 6 }, type), metrics = stairMetrics(stair);
    assert.equal(stair.steps, 24);
    assert.ok(metrics.tread >= .25 - 1e-6, `${type} tread ${metrics.tread}`);
    assert.ok(metrics.landingDepth >= metrics.clearWidth);
  }
});

test('upper and lower approaches stay clear, and a bedroom cannot cover the void', () => {
  const design = designFixture(), stair = design.floors[0].stairs[0];
  assert.deepEqual(stairAccessBox(stair), { x: 2, y: 1, right: 4.2, top: 2 });
  for (const [index, floor] of design.floors.entries()) floor.furniture.push({ id: `chair${index}`, category: 'chair', room_id: floor.rooms[0].id, position: { x: 2.5, y: 1.5, z: floor.elevation }, dimensions: { width: .5, depth: .5, height: .8 }, rotation: 45 });
  assert.equal(stairIssues(design).filter(issue => issue.code === 'stair-access-furniture').length, 2);
  design.floors[1].rooms[0].type = 'bedroom';
  assert.ok(stairIssues(design).some(issue => issue.code === 'shaft-room' && issue.severity === 'error'));
  assert.ok(has(design, 'stair-access'));
});

test('stair doorway checks distinguish a blocked aperture from furniture side allowances', () => {
  const design = designFixture({ position: { x: 5.3, y: 2, z: 0 } }), floor = design.floors[0];
  const door = { id: 'side-door', type: 'sliding', room_id: 'lobby0', wall_id: 'east-wall', position: { x: 8, y: 1.33, z: 0 }, width: .9, height: 2.1 };
  floor.walls.push({ id: 'east-wall', type: 'exterior', start: { x: 8, y: 0 }, end: { x: 8, y: 8 }, room_ids: ['lobby0'] });
  floor.doors.push(door);
  const stairBox = roomBox(floor.stairs[0]);
  assert.ok(boxesOverlap(stairBox, doorApproachBox(door, floor.rooms[0], floor)), 'the furniture side allowance reaches past the aperture');
  assert.equal(has(design, 'stair-door-approach'), false, 'the doorway aperture itself remains clear');
  door.position.y = 1.7;
  assert.ok(has(design, 'stair-door-approach'), 'the aperture now overlaps the stair footprint');
  const upper = design.floors[1];
  upper.walls.push({ ...floor.walls[0], room_ids: ['lobby1'] });
  const upperDoor = { ...door, id: 'upper-side-door', room_id: 'lobby1', position: { x: 8, y: 1.33, z: 3 } };
  upper.doors.push(upperDoor);
  assert.equal(has(design, 'shaft-door-approach'), false);
  upperDoor.position.y = 1.7;
  assert.ok(has(design, 'shaft-door-approach'), 'the upper-floor aperture now approaches over the void');
});

test('synchronization retains the specified clear width and explicit landing', () => {
  const design = designFixture({ landing_depth: 1.2, clear_width: 1 });
  synchronizeStairs(design);
  assert.equal(design.floors[0].stairs[0].landing_depth, 1.2);
  assert.equal(design.floors[0].stairs[0].clear_width, 1);
  assert.equal(design.floors[1].stair_openings[0].source_stair_type, 'u_shaped');
  assert.equal(design.floors[1].stair_openings[0].clear_width, 1);
  assert.equal(design.floors[1].stair_openings[0].landing_depth, 1.2);
  assert.equal(design.floors[1].stair_openings[0].access_depth, 1);
  design.floors[0].stairs[0].dimensions.width = 1.9;
  synchronizeStairs(design);
  assert.equal(design.floors[0].stairs[0].clear_width, 1);
  assert.ok(has(design, 'stair-width'));
});

test('U plan symbol has two flights, an unlined landing and a returning up arrow', () => {
  const stair = designFixture().floors[0].stairs[0], { flights, lines, arrow } = stairPlanGeometry(stair);
  assert.equal(flights.length, 2);
  assert.equal(lines.length, 20);
  assert.ok(lines.every(line => line.y1 <= 2.45 + 1e-9 && line.y2 <= 2.45 + 1e-9));
  assert.ok(lines.every(line => line.x2 <= 1.02 + 1e-9 || line.x1 >= 1.18 - 1e-9), 'tread lines must not bridge the central gap');
  assert.ok(arrow.at(-1).y < arrow.at(-2).y, 'upper flight returns toward the arrival landing');
});
