import { rebuildWalls, rehostOpenings } from '../src/utils/roomEditing.js';
export function cadFixture() {
  const design = {
    schema_version: '3.0',
    project: {
      name: 'Courtyard house',
      unit: 'm',
      display_unit: 'm',
      style: 'modern',
      orientation: 'south'
    },
    site: {
      plot: {
        width: 14,
        depth: 16
      },
      road: {
        side: 'south',
        width: 6
      },
      setbacks: {
        front: 1,
        back: 1,
        left: 1,
        right: 1
      }
    },
    building: {
      width: 10,
      depth: 8,
      wall_thickness: .2,
      slab_thickness: .2,
      floors: 1
    },
    floors: [{
      id: 'floor_0',
      level: 0,
      name: 'Ground floor',
      elevation: 0,
      floor_height: 3,
      slab_thickness: .2,
      rooms: [{
        id: 'living',
        name: 'Living room',
        type: 'living_room',
        position: {
          x: 1,
          y: 1,
          z: 0
        },
        dimensions: {
          width: 5,
          depth: 8,
          height: 3
        }
      }, {
        id: 'bedroom',
        name: 'Bedroom',
        type: 'bedroom',
        position: {
          x: 6,
          y: 1,
          z: 0
        },
        dimensions: {
          width: 5,
          depth: 8,
          height: 3
        }
      }],
      walls: [],
      doors: [{
        id: 'main_door',
        type: 'main_entrance',
        room_id: 'living',
        position: {
          x: 3,
          y: 1,
          z: 0
        },
        width: .95,
        height: 2.1,
        swing: 'inward_left'
      }, {
        id: 'bed_door',
        type: 'single_swing',
        room_id: 'living',
        connected_room_id: 'bedroom',
        position: {
          x: 6,
          y: 3,
          z: 0
        },
        width: .85,
        height: 2.1,
        swing: 'inward_right'
      }],
      windows: [{
        id: 'living_window',
        room_id: 'living',
        type: 'double_casement',
        position: {
          x: 1,
          y: 5,
          z: .9
        },
        width: 1.4,
        height: 1.4,
        sill_height: .9
      }, {
        id: 'bed_window',
        room_id: 'bedroom',
        type: 'double_casement',
        position: {
          x: 11,
          y: 5,
          z: .9
        },
        width: 1.4,
        height: 1.4,
        sill_height: .9
      }],
      furniture: [{
        id: 'sofa',
        name: 'Sofa',
        asset: 'sofa',
        category: 'sofa',
        room_id: 'living',
        position: {
          x: 3.5,
          y: 5,
          z: 0
        },
        dimensions: {
          width: 2.2,
          depth: .9,
          height: .85
        },
        rotation: 0
      }, {
        id: 'bed',
        name: 'Bed',
        asset: 'bed',
        category: 'bed',
        room_id: 'bedroom',
        position: {
          x: 8.5,
          y: 5,
          z: 0
        },
        dimensions: {
          width: 1.8,
          depth: 2,
          height: .8
        },
        rotation: 0
      }],
      stairs: [],
      stair_openings: []
    }]
  };
  rebuildWalls(design.floors[0]);
  rehostOpenings(design.floors[0]);
  return design;
}
