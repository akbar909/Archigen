import test from 'node:test';
import assert from 'node:assert/strict';
import { cadFixture } from '../../tests/cad-fixture.mjs';
import { clone, parseDimension, polygonsOverlap, projectToSegment, rotatedRectangle, snapPoint, SpatialHash } from './cadGeometry.js';
import { useFloorPlanEditorStore } from '../store/useFloorPlanEditorStore.js';
import { applyPatches, createCommand } from './commandHistory.js';
import { editDesign, arrayWindows, deleteEntities } from './cadEditing.js';
import { mergeRooms, moveWall, normalizeEditorDesign, rebuildWalls, splitRoom, transformRoom } from './roomEditing.js';
import { hostOpening, doorSector } from './wallOpenings.js';
import { validateClientDesign } from './clientArchitecturalValidator.js';
import { buildSpatialGraph, inaccessibleRooms } from './spatialGraph.js';
import { duplicateFloor, synchronizeStairs, createStairPlacement } from './verticalCirculation.js';
import { layoutDiagnostics } from './layoutDiagnostics.js';
test('unit parsing accepts explicit metric, feet, inches, and rejects unsafe values', () => {
  assert.equal(parseDimension('12 ft'), 3.6576);
  assert.equal(parseDimension('2.5 m', 'ft'), 2.5);
  assert.equal(parseDimension('100 mm'), .1);
  assert.ok(Math.abs(parseDimension('6\' 2"') - 1.8796) < 1e-9);
  assert.equal(parseDimension('1', 'ft'), .3048);
  for (const v of ['NaN', 'Infinity', '4foo', '1e999', '<script>']) assert.throws(() => parseDimension(v));
});
test('SAT excludes rotated bounding-box false positives, includes exact rotated intersections', () => {
  const item = (x, y, rotation = 45) => ({
    position: {
      x,
      y
    },
    dimensions: {
      width: 4,
      depth: .3
    },
    rotation
  });
  assert.equal(polygonsOverlap(rotatedRectangle(item(0, 0)), rotatedRectangle(item(1, 1))), false);
  assert.equal(polygonsOverlap(rotatedRectangle(item(0, 0)), rotatedRectangle(item(0, 0, 135))), true);
  assert.equal(polygonsOverlap(rotatedRectangle(item(0, 0)), rotatedRectangle(item(10, 10))), false);
});
test('segment projection works on horizontal, vertical, sloped, reversed and degenerate walls', () => {
  for (const [start, end, point, expected] of [[{
    x: 0,
    y: 0
  }, {
    x: 4,
    y: 0
  }, {
    x: 2,
    y: 3
  }, {
    x: 2,
    y: 0
  }], [{
    x: 0,
    y: 0
  }, {
    x: 0,
    y: 4
  }, {
    x: 3,
    y: 2
  }, {
    x: 0,
    y: 2
  }], [{
    x: 0,
    y: 0
  }, {
    x: 4,
    y: 4
  }, {
    x: 1,
    y: 3
  }, {
    x: 2,
    y: 2
  }], [{
    x: 4,
    y: 0
  }, {
    x: 0,
    y: 0
  }, {
    x: 2,
    y: 3
  }, {
    x: 2,
    y: 0
  }], [{
    x: 1,
    y: 1
  }, {
    x: 1,
    y: 1
  }, {
    x: 2,
    y: 2
  }, {
    x: 1,
    y: 1
  }]]) {
    const actual = projectToSegment(point, start, end);
    assert.ok(Math.abs(actual.x - expected.x) < 1e-9);
    assert.ok(Math.abs(actual.y - expected.y) < 1e-9);
  }
});
test('opening hosting clamps jambs and transfers corners, maintaining room and wall semantics', () => {
  const f = cadFixture().floors[0],
    original = f.doors[0];
  const clamped = hostOpening(f, original, {
    x: 1.01,
    y: 1
  });
  assert.ok(clamped.position.x >= 1 + original.width / 2 + .099);
  const moved = hostOpening(f, original, {
    x: 1,
    y: 5
  });
  assert.equal(moved.wall_side, 'west');
  assert.equal(moved.position.x, 1);
  assert.ok(f.walls.find(w => w.id === moved.wall_id).room_ids.includes(moved.room_id));
});
test('shared wall network splits T intersections and moves connected rectangular rooms', () => {
  const d = cadFixture(),
    f = d.floors[0],
    wall = f.walls.find(w => w.room_ids.length === 2);
  assert.equal(f.walls.filter(w => w.room_ids.length === 2).length, 1);
  moveWall(f, wall.id, {
    x: 6.5,
    y: 4
  }, .2);
  assert.equal(f.rooms[0].dimensions.width, 5.5);
  assert.equal(f.rooms[1].position.x, 6.5);
  assert.equal(f.rooms[1].dimensions.width, 4.5);
  const originalArea = f.rooms.reduce((s, r) => s + r.dimensions.width * r.dimensions.depth, 0);
  splitRoom(f, 'living', 'y', 5);
  assert.equal(f.walls.filter(w => w.room_ids.length === 2).length, 3);
  assert.equal(f.rooms.reduce((s, r) => s + r.dimensions.width * r.dimensions.depth, 0), originalArea);
});
test('split and merge preserve area, inventory and remove internal doorway references', () => {
  const f = cadFixture().floors[0],
    area = f.rooms[0].dimensions.width * f.rooms[0].dimensions.depth;
  const ids = splitRoom(f, 'living', 'y', 5);
  assert.equal(f.rooms.length, 3);
  assert.equal(new Set(f.rooms.map(r => r.id)).size, 3);
  assert.ok(f.furniture.every(i => f.rooms.some(r => r.id === i.room_id)));
  const merged = mergeRooms(f, ids),
    room = f.rooms.find(r => r.id === merged);
  assert.equal(room.dimensions.width * room.dimensions.depth, area);
  assert.equal(f.rooms.length, 2);
  assert.throws(() => splitRoom(f, merged, 'x', 1.2));
  assert.throws(() => mergeRooms(f, [merged, 'missing']));
});
test('twenty heterogeneous transactions undo to byte-identical initial JSON and redo exactly', () => {
  const initial = cadFixture(),
    commands = [];
  let current = initial;
  for (let i = 0; i < 20; i++) {
    const next = editDesign(current, 0, (f, d) => {
      if (i % 4 === 0) transformRoom(f, 'living', {
        ...f.rooms[0].position,
        width: 5 + i / 100,
        depth: 8
      });
      if (i % 4 === 1) f.furniture[0].position.x += .1;
      if (i % 4 === 2) {
        const ids = splitRoom(f, 'living', 'y', 5);
        mergeRooms(f, ids);
      }
      if (i % 4 === 3) {
        f.furniture.push({
          ...clone(f.furniture[0]),
          id: `added_${i}`
        });
        deleteEntities(f, d, [{
          type: 'furniture',
          id: `added_${i}`
        }]);
      }
    });
    commands.push(createCommand(current, next, `Edit ${i}`));
    current = next;
  }
  const final = JSON.stringify(current);
  for (const command of [...commands].reverse()) current = applyPatches(current, command.inversePatches);
  assert.equal(JSON.stringify(current), JSON.stringify(initial));
  for (const command of commands) current = applyPatches(current, command.patches);
  assert.equal(JSON.stringify(current), final);
});
test('patches safely support escaped keys and refuse prototype injection', () => {
  const a = {
      'a/b': {
        'x~y': 1
      }
    },
    b = {
      'a/b': {
        'x~y': 2
      },
      new: []
    };
  assert.deepEqual(applyPatches(a, createCommand(a, b, 'x').patches), b);
  assert.throws(() => applyPatches({}, [{
    op: 'add',
    path: '/__proto__/polluted',
    value: true
  }]));
});
test('window arrays preserve original identifier and provide equal spacing', () => {
  const f = cadFixture().floors[0];
  arrayWindows(f, 'living_window', 3);
  const same = f.windows.filter(w => w.wall_id === f.windows.find(w => w.id === 'living_window').wall_id);
  assert.equal(same.length, 3);
  const offsets = same.map(w => w.wall_offset).sort((a, b) => a - b);
  assert.ok(Math.abs(offsets[2] - offsets[1] - (offsets[1] - offsets[0])) < .001);
});
test('stairs synchronize canonical connections, voids, elevations and duplicate IDs', () => {
  const d = normalizeEditorDesign(cadFixture());
  duplicateFloor(d, 0);
  assert.equal(d.floors[1].elevation, 3);
  assert.notEqual(d.floors[1].rooms[0].id, d.floors[0].rooms[0].id);
  assert.equal(d.floors[1].rooms[1].type, 'bedroom', 'ID rewrites must never change room types');
  assert.equal(d.floors[1].furniture[0].category, 'sofa', 'ID rewrites must never change asset categories');
  assert.equal(d.floors[1].furniture[0].asset, 'sofa');
  d.floors[0].stairs.push({
    id: 'stair',
    type: 'u_shaped',
    position: {
      x: 2,
      y: 2,
      z: 0
    },
    dimensions: {
      width: 2.2,
      depth: 3.8,
      height: 3
    }
  });
  synchronizeStairs(d);
  assert.equal(d.floors[1].stair_openings[0].serves_stair_id, 'stair');
  const voidId = d.floors[1].stair_openings[0].id;
  d.floors[0].stairs[0].position.x = 3;
  d.floors[0].floor_height = 3.4;
  synchronizeStairs(d);
  assert.equal(d.floors[1].elevation, 3.4);
  assert.equal(d.floors[1].stair_openings[0].position.x, 3);
  assert.equal(d.floors[1].stair_openings[0].id, voidId);
  d.floors[0].stairs = [];
  synchronizeStairs(d);
  assert.equal(d.floors[1].stair_openings.length, 0);
});
test('validation identifies collisions, swing conflicts, unreachable rooms and missing shafts', () => {
  const d = normalizeEditorDesign(cadFixture()),
    f = d.floors[0];
  assert.equal(inaccessibleRooms(f).length, 0);
  assert.ok(buildSpatialGraph(f).get('living').has('bedroom'));
  f.furniture[1] = {
    ...clone(f.furniture[0]),
    id: 'overlap'
  };
  let issues = validateClientDesign(d);
  assert.ok(issues.some(i => i.code === 'furniture-overlap'));
  f.doors = f.doors.filter(i => i.id !== 'bed_door');
  assert.equal(inaccessibleRooms(f)[0].id, 'bedroom');
  const sector = doorSector(f.doors[0]);
  assert.ok(sector.length > 10);
  duplicateFloor(d, 0);
  issues = validateClientDesign(d);
  assert.ok(issues.some(i => i.code === 'missing-stair'));
});
test('snapping honors bypass and magnetic alignment within world tolerance', () => {
  assert.deepEqual(snapPoint({
    x: 1.12,
    y: 2.11
  }, {
    enabled: false
  }).point, {
    x: 1.12,
    y: 2.11
  });
  assert.deepEqual(snapPoint({
    x: 1.12,
    y: 2.11
  }, {
    step: .25,
    targets: [{
      x: 1.15,
      y: 2.1
    }],
    tolerance: .08
  }).point, {
    x: 1.15,
    y: 2.1
  });
});

test('spatial hash includes large and negative-coordinate footprints across every occupied cell', () => {
  const spatial = new SpatialHash(2);
  spatial.insert('wide', {x:-5,y:-2,right:6,top:3});
  assert.ok(spatial.query({x:5,y:2,right:5.1,top:2.1}).has('wide'));
  assert.ok(spatial.query({x:-4,y:-1,right:-3,top:0}).has('wide'));
  assert.equal(spatial.query({x:20,y:20,right:21,top:21}).size,0);
});

test('history tracks its document, invalidates redo on branching and clears at version boundaries', () => {
  const store=useFloorPlanEditorStore;
  store.getState().resetContext('history-test-a');
  const before=cadFixture(),after=editDesign(before,0,f=>{f.furniture[0].rotation=45});
  store.getState().record(before,after,'Rotate');
  assert.deepEqual(store.getState().historyDesign,after);
  assert.deepEqual(store.getState().undo(after),before);
  assert.equal(store.getState().future.length,1);
  const branch=editDesign(before,0,f=>{f.furniture[0].rotation=90});
  store.getState().record(before,branch,'Rotate again');
  assert.equal(store.getState().future.length,0);
  store.getState().resetContext('history-test-b');
  assert.equal(store.getState().past.length,0);
  assert.equal(store.getState().historyDesign,null);
});

test('door transfer synchronizes every canonical and legacy room reference',()=>{
  const floor=cadFixture().floors[0],door=floor.doors.find(d=>d.id==='bed_door');
  const moved=hostOpening(floor,door,{x:1,y:6});
  assert.deepEqual(moved.connected_room_ids,['living']);
  assert.deepEqual(moved.connected_rooms,['living']);
  assert.equal(moved.connected_room_id,null);
  assert.equal(moved.client_edited_2d,true);
});

test('strict diagnostics catch stale plural door connections',()=>{
  const design=normalizeEditorDesign(cadFixture()),door=design.floors[0].doors[0];
  door.connected_room_id=null;door.connected_room_ids=['living','bedroom'];
  assert.ok(validateClientDesign(design).some(i=>i.code==='connection'&&i.entity.id===door.id));
});

test('stair placement centers the footprint inside a room and rejects insufficient space',()=>{
  const floor=normalizeEditorDesign(cadFixture()).floors[0];
  const stair=createStairPlacement(floor,{x:3.5,y:4},'u_shaped');
  assert.equal(stair.position.x,2.4);assert.equal(stair.position.y,2.1);
  assert.throws(()=>createStairPlacement(floor,{x:13,y:15}));
  const small=structuredClone(floor);small.rooms[0].dimensions.width=2;
  assert.throws(()=>createStairPlacement(small,{x:2,y:4}));
});

test('approval errors become short diagnostic rows with selectable entities',()=>{
  const design=cadFixture(),issues=layoutDiagnostics(design,{critical_errors:["Door 'bed_door' intends to connect ['living', 'bedroom'] but its wall 'wall_l0_part_012' connects ['living']."]});
  assert.equal(issues[0].entity.id,'bed_door');
  assert.ok(issues[0].message.length<120);assert.ok(!issues[0].message.includes('wall_l0'));
});
