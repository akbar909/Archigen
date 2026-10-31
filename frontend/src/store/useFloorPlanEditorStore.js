import { create } from 'zustand';
import { applyPatches, createCommand } from '../utils/commandHistory.js';
const layers = () => Object.fromEntries(['rooms', 'walls', 'doors', 'windows', 'furniture', 'stairs', 'dimensions', 'site'].map(key => [key, {
  visible: true,
  locked: false
}]));
export const useFloorPlanEditorStore = create((set, get) => ({
  active: false,
  contextKey: null,
  activeTool: 'select',
  selection: [],
  activeFloorIndex: 0,
  snap: true,
  gridStep: .25,
  strict: true,
  ghost: false,
  layers: layers(),
  past: [],
  future: [],
  historyDesign: null,
  panel: null,
  panelExpanded: false,
  measurement: [],
  setTool: activeTool => set({
    activeTool,
    measurement: []
  }),
  select: (entity, additive = false) => set(state => ({
    selection: !entity ? [] : additive ? state.selection.some(e => e.type === entity.type && e.id === entity.id) ? state.selection.filter(e => e.type !== entity.type || e.id !== entity.id) : [...state.selection, entity] : [entity]
  })),
  setFloor: activeFloorIndex => set({
    activeFloorIndex,
    selection: [],
    measurement: []
  }),
  setOption: (key, value) => set({
    [key]: value
  }),
  setLayer: (key, patch) => set(state => ({
    layers: {
      ...state.layers,
      [key]: {
        ...state.layers[key],
        ...patch
      }
    }
  })),
  resetContext: contextKey => {
    if (get().contextKey !== contextKey) set({
      contextKey,
      selection: [],
      activeFloorIndex: 0,
      past: [],
      future: [],
      historyDesign: null,
      panel: null,
      panelExpanded: false,
      measurement: [],
      activeTool: 'select',
      strict: true
    });
  },
  record: (before, after, description) => {
    const command = createCommand(before, after, description);
    if (command.patches.length) set(state => ({
      past: [...state.past.slice(-99), command],
      future: [],
      historyDesign: after
    }));
    return command.patches.length > 0;
  },
  undo: design => {
    const command = get().past.at(-1);
    if (!command) return design;
    const next = applyPatches(design, command.inversePatches);
    set(state => ({
      past: state.past.slice(0, -1),
      future: [...state.future, command],
      historyDesign: next,
      selection: []
    }));
    return next;
  },
  redo: design => {
    const command = get().future.at(-1);
    if (!command) return design;
    const next = applyPatches(design, command.patches);
    set(state => ({
      future: state.future.slice(0, -1),
      past: [...state.past, command],
      historyDesign: next,
      selection: []
    }));
    return next;
  }
}));
