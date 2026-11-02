import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { Armchair, DoorOpen, Hand, Layers, Magnet, MousePointer2, PanelRight, PencilRuler, Redo2, Ruler, Square, ArrowUpRight, Undo2, X, ZoomIn, ZoomOut, Maximize2, AppWindow } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { useFloorPlanEditorStore } from '../../store/useFloorPlanEditorStore.js';
import { useProjectStore } from '../../store/useProjectStore.js';
import { apiClient } from '../../services/apiClient.js';
import { clamp, clone, containsPoint, distance, polygonBounds, roomBox, round, rotatedRectangle, snapPoint, svgToWorld, uid } from '../../utils/cadGeometry.js';
import { addFurniture, alignFurniture, arrayWindows, collectionFor, deleteEntities, editDesign, getEntity, moveFurniture } from '../../utils/cadEditing.js';
import { mergeRooms, moveWall, normalizeEditorDesign, rebuildWalls, rehostOpenings, roomAtPoint, splitRoom, transformRoom } from '../../utils/roomEditing.js';
import { hostOpening, roomEdges } from '../../utils/wallOpenings.js';
import { duplicateFloor, createStairPlacement } from '../../utils/verticalCirculation.js';
import { layoutDiagnostics, layoutConflictSummary } from '../../utils/layoutDiagnostics.js';
import { validateClientDesign } from '../../utils/clientArchitecturalValidator.js';
import { CadDoorItem, CadFurnitureItem, CadWindowItem, formatDim, getRoomColor } from './CadSymbols.jsx';
import SitePlanLayer from './SitePlanLayer.jsx';
import TransformGizmo from './TransformGizmo.jsx';
import SnapGuideLayer from './SnapGuideLayer.jsx';
import MeasurementTool from './MeasurementTool.jsx';
import LayerVisibilityPanel from './LayerVisibilityPanel.jsx';
import ValidationBadgeOverlay from './ValidationBadgeOverlay.jsx';
import FloorManagerBar from './FloorManagerBar.jsx';
import FurniturePaletteDrawer from './FurniturePaletteDrawer.jsx';
import SelectionInspector from './SelectionInspector.jsx';
import StairPlacementPanel from './StairPlacementPanel.jsx';
import CadStairItem from './CadStairItem.jsx';
import './floorplan-editor.css';
const TOOLS = [['select', 'Select', MousePointer2], ['pan', 'Pan', Hand], ['room', 'Room', Square], ['wall', 'Partition', PencilRuler], ['door', 'Door', DoorOpen], ['window', 'Window', AppWindow], ['furniture', 'Furniture', Armchair], ['stair', 'Stair', ArrowUpRight], ['measure', 'Measure', Ruler]];
const SCALE = 40,
  MARGIN = 2;
const isTextInput = target => /INPUT|TEXTAREA|SELECT/.test(target?.tagName) || target?.isContentEditable;
const setPath = (object, path, value) => {
  const parts = path.split('.');
  let target = object;
  for (const key of parts.slice(0, -1)) target = target[key] ||= {};
  target[parts.at(-1)] = value;
};
export default function FloorPlanEditorContainer({
  design,
  onApproveLayout,
  isApproving = false,
  onSelectRoom,
  selectedRoomId,
  onDesignChange,
  contextKey,
  assets = [],
  interactionBlocked = false,
  onRequestSave
}) {
  const editor = useFloorPlanEditorStore(),
    project = useProjectStore();
  const {
    activeTool,
    selection,
    activeFloorIndex,
    layers,
    snap,
    gridStep,
    strict,
    ghost,
    panel
  } = editor;
  const [preview, setPreview] = useState(null),
    [guides, setGuides] = useState([]),
    [rubber, setRubber] = useState(null);
  const [camera, setCamera] = useState({
      zoom: 1,
      x: 0,
      y: 0
    }),
    [issues, setIssues] = useState([]);
  const [asset, setAsset] = useState(null),
    [aiBusy, setAiBusy] = useState(false),
    [saving, setSaving] = useState(false);
  const [stairType,setStairType]=useState('u_shaped'),[stairPreview,setStairPreview]=useState(null),[aiFeedback,setAiFeedback]=useState(null);
  const [diagnosticRequest,setDiagnosticRequest]=useState(0);
  const svgRef = useRef(null),
    rootRef = useRef(null),
    gesture = useRef(null),
    pointers = useRef(new Map()),
    previewRef = useRef(null);
  const lastDesign = useRef(design),
    lastOwn = useRef(null),
    lastContext = useRef(null);
  const manualView=useRef(false),drawingRef=useRef(null);
  const id = useId().replaceAll(':', ''),
    gridId = `cad-grid-${id}`;
  const normalized = useMemo(() => design ? normalizeEditorDesign(design) : null, [design]),
    rendered = preview || normalized;
  const floorIndex = Math.min(activeFloorIndex, Math.max(0, (rendered?.floors.length || 1) - 1)),
    floor = rendered?.floors[floorIndex];
  const primary = selection[0],
    entity = getEntity(floor, primary);
  useEffect(()=>setAiFeedback(null),[primary?.id,floor?.id]);
  const unit = (rendered?.project?.display_unit || rendered?.project?.unit) === 'ft' ? 'ft' : 'm';
  const plotW = Number(rendered?.site?.plot?.width) || 14,
    plotD = Number(rendered?.site?.plot?.depth) || 18;
  const svgW = (plotW + MARGIN * 2) * SCALE,
    svgH = (plotD + MARGIN * 2) * SCALE;
  const mapX = x => (MARGIN + Number(x || 0)) * SCALE,
    mapY = y => (MARGIN + plotD - Number(y || 0)) * SCALE;
  const width = svgW / camera.zoom,
    height = svgH / camera.zoom;
  const viewBox = `${(svgW - width) / 2 + camera.x} ${(svgH - height) / 2 + camera.y} ${width} ${height}`;
  drawingRef.current={floor,plotD,svgW,svgH};
  const fitPlan=useCallback(()=>{
    const svg=svgRef.current,d=drawingRef.current;
    if(!svg||!d?.floor?.rooms?.length)return;
    const boxes=d.floor.rooms.map(roomBox),left=Math.min(...boxes.map(b=>b.x))-.9,right=Math.max(...boxes.map(b=>b.right))+.9,bottom=Math.min(...boxes.map(b=>b.y))-.9,top=Math.max(...boxes.map(b=>b.top))+.9;
    const rect=svg.getBoundingClientRect(),base=Math.min(rect.width/d.svgW,rect.height/d.svgH);
    if(!base)return;
    const tools=rect.width>760?112:58,desired=Math.min(Math.max(80,rect.width-tools-20)/((right-left)*SCALE),Math.max(80,rect.height-72)/((top-bottom)*SCALE));
    const zoom=clamp(desired/base,.35,6),actualScale=base*zoom;
    setCamera({zoom,x:(MARGIN+(left+right)/2)*SCALE-d.svgW/2-tools/(2*actualScale),y:(MARGIN+d.plotD-(bottom+top)/2)*SCALE-d.svgH/2});
  },[]);
  useEffect(()=>{
    manualView.current=false;
    const svg=svgRef.current;
    if(!svg)return;
    const observer=new ResizeObserver(()=>{if(!manualView.current&&!gesture.current)fitPlan()});
    observer.observe(svg);fitPlan();return()=>observer.disconnect();
  },[floor?.id,contextKey,fitPlan]);
  const key = contextKey || `${project.activeProjectId || 'local'}:${project.activeVersionId || 'draft'}`;
  const editable = Boolean(onDesignChange || project.design === design),
    blocked = interactionBlocked || saving || project.loading || project.isSavingVersion || aiBusy || isApproving;
  const draftCallback = onDesignChange || project.setDraftDesign;
  const setDraft = useCallback(next => {
    const previous=useProjectStore.getState().design;
    draftCallback(next);
    const stored=useProjectStore.getState().design;
    const resolved=stored!==previous ? stored : next;
    lastOwn.current = resolved;
    lastDesign.current = resolved;
  }, [draftCallback]);
  const clearGesture = useCallback(() => {
    gesture.current = null;
    previewRef.current = null;
    pointers.current.clear();
    setPreview(null);
    setGuides([]);
    setRubber(null);
  }, []);
  useEffect(() => {
    useFloorPlanEditorStore.setState({ active: true });
    return () => useFloorPlanEditorStore.setState({ active: false });
  }, []);
  useEffect(() => {
    if (lastContext.current !== key) {
      const history = useFloorPlanEditorStore.getState();
      // Reconcile edits made in 3D while this canvas was unmounted before
      // applying any array patches left in its history.
      if (history.contextKey === key && history.historyDesign && JSON.stringify(history.historyDesign.floors) !== JSON.stringify(design?.floors)) {
        if (project.isDirty) editor.record(history.historyDesign, design, 'External design edit');
        else useFloorPlanEditorStore.setState({ past: [], future: [], historyDesign: design });
      }
      editor.resetContext(key);
      lastContext.current = key;
      lastDesign.current = design;
      lastOwn.current = null;
      clearGesture();
      setCamera({
        zoom: 1,
        x: 0,
        y: 0
      });
    } else if (design && lastDesign.current && design !== lastDesign.current) {
      const geometry = v => JSON.stringify({
        floors: v.floors,
        rooms: v.rooms,
        walls: v.walls,
        doors: v.doors,
        windows: v.windows,
        furniture: v.furniture,
        site: v.site,
        building: v.building
      });
      if (design !== lastOwn.current && project.isDirty && geometry(design) !== geometry(lastDesign.current)) editor.record(lastDesign.current, design, 'External design edit');
      if (!project.isDirty && design !== lastOwn.current) {
        if (project.isSavingVersion) {
          if (geometry(design) !== geometry(lastDesign.current)) editor.record(lastDesign.current, design, 'Saved layout normalization');
        } else useFloorPlanEditorStore.setState({ past: [], future: [], historyDesign: design });
      }
      lastDesign.current = design;
      clearGesture();
    }
  }, [design, key, clearGesture, project.isDirty]);
  useEffect(() => {
    const timer = setTimeout(() => setIssues(validateClientDesign(rendered)), 150);
    return () => clearTimeout(timer);
  }, [rendered]);
  const serverValidation=project.layoutValidation?.versionId===project.activeVersionId?project.layoutValidation:null;
  const allIssues=useMemo(()=>[...issues,...layoutDiagnostics(rendered,serverValidation?.report)],[issues,rendered,serverValidation]);
  useEffect(() => {
    if (interactionBlocked) clearGesture();
  }, [interactionBlocked, clearGesture]);
  useEffect(() => {
    if (selectedRoomId && !selection.length && floor?.rooms.some(r => r.id === selectedRoomId)) editor.select({
      type: 'room',
      id: selectedRoomId
    });
  }, [selectedRoomId]);
  useEffect(() => {
    window.addEventListener('blur', clearGesture);
    return () => window.removeEventListener('blur', clearGesture);
  }, [clearGesture]);
  const commit = (next, description, before = design) => {
    if (!editable || blocked) return false;
    if (strict) {
      const fingerprint = i => `${i.floorIndex}:${i.code}:${i.entity.id}:${i.relatedId || ''}`;
      const existing = new Set(validateClientDesign(normalizeEditorDesign(before)).filter(i => i.severity === 'error').map(fingerprint));
      const collisionCodes = new Set(['furniture-overlap','door-swing','door-approach','outside-room','blocked-shaft','room-overlap','aperture-overlap','site-boundary','jamb-clearance','shaft-wall','shaft-room','shaft-door','shaft-door-approach','opening-height','connection','unhosted','stair-furniture','stair-boundary','stair-door','stair-door-approach','stair-width','stair-tread','stair-type','stair-dimensions','stair-rotation','stair-risers','stair-rise','stair-headroom','stair-landing','stair-access','stair-access-furniture','stair-access-door']);
      const errors = validateClientDesign(next).filter(i => i.severity === 'error' && collisionCodes.has(i.code) && !existing.has(fingerprint(i)));
      if (errors.length) {
        toast.error(errors[0].message);
        return false;
      }
    }
    if (editor.record(before, next, description)) {
      setDraft(next);
      return true;
    }
    return false;
  };
  const run = (description, mutate) => {
    if (!editable || blocked) return false;
    try {
      return commit(editDesign(design, floorIndex, mutate), description);
    } catch (error) {
      toast.error(error.message);
      return false;
    }
  };
  const undo = () => {
    if (!blocked && editor.past.length) {
      clearGesture();
      setDraft(editor.undo(design));
    }
  };
  const redo = () => {
    if (!blocked && editor.future.length) {
      clearGesture();
      setDraft(editor.redo(design));
    }
  };
  const select = (type, item, additive = false, openPanel = true) => {
    const layer = layers[collectionFor(type)];
    if (layer?.locked || !layer?.visible) return;
    const group = type === 'furniture' && item.group_id ? floor.furniture.filter(i => i.group_id === item.group_id) : [];
    if (group.length && !additive) useFloorPlanEditorStore.setState({
      selection: group.map(i => ({
        type,
        id: i.id
      }))
    });else editor.select({
      type,
      id: item.id
    }, additive);
    if (type === 'room') onSelectRoom?.(item.id);
    if (openPanel) editor.setOption('panel', 'inspector');
  };
  const update = (path, value, anchor = 'sw') => run(`Edit ${primary?.type} ${path}`, (f, d) => {
    const item = getEntity(f, primary);
    if (!item || layers[collectionFor(primary.type)]?.locked || item.locked && path !== 'locked') throw new Error('Unlock the selection to edit it.');
    if (primary.type === 'room' && ['dimensions.width', 'dimensions.depth'].includes(path)) {
      const b = roomBox(item),
        next = {
          ...b
        };
      next[path.endsWith('width') ? 'width' : 'depth'] = value;
      if (anchor.includes('e')) next.x += b.width - next.width;
      if (anchor.includes('n')) next.y += b.depth - next.depth;
      transformRoom(f, item.id, next, d.building?.wall_thickness);
    } else if (['door', 'window'].includes(primary.type) && ['width', 'wall_side', 'wall_offset', 'sill_height'].includes(path)) {
      setPath(item, path, value);
      let point = item.position,
        restricted = f;
      if (path === 'wall_offset') {
        const wall = f.walls.find(w => w.id === item.wall_id),
          length = distance(wall.start, wall.end),
          t = value / length;
        point = {
          x: wall.start.x + (wall.end.x - wall.start.x) * t,
          y: wall.start.y + (wall.end.y - wall.start.y) * t
        };
        restricted = {
          ...f,
          walls: [wall]
        };
      }
      if (path === 'wall_side') {
        const room = f.rooms.find(r => r.id === (item.room_id || item.roomId)),
          edge = roomEdges(room).find(e => e.side === value);
        point = {
          x: (edge.start.x + edge.end.x) / 2,
          y: (edge.start.y + edge.end.y) / 2
        };
      }
      Object.assign(item, hostOpening(restricted, item, point));
    } else if (primary.type === 'room' && path === 'wall_thickness') {
      item.wall_thickness = value;
      f.walls.filter(w => (w.room_ids || w.connected_rooms || []).includes(item.id)).forEach(w => {
        w.thickness = value;
      });
    } else if (primary.type === 'stair' && path === 'type') {
      item.type = value;
      const sizes = {
        straight: [1.1, 5.9],
        l_shaped: [3.8, 3.8],
        u_shaped: [2.2, 3.8]
      };
      [item.dimensions.width, item.dimensions.depth] = sizes[value];
    } else if (primary.type === 'wall' && path === 'length') {
      const oldLength = distance(item.start, item.end),
        point = {
          x: item.start.x + (item.end.x - item.start.x) * value / oldLength,
          y: item.start.y + (item.end.y - item.start.y) * value / oldLength
        };
      // Change the connected perpendicular room edge to preserve closed topology.
      const ids = item.room_ids || item.connected_rooms || [],
        horizontal = Math.abs(item.end.y - item.start.y) < .001;
      for (const rid of ids) {
        const room = f.rooms.find(r => r.id === rid),
          b = roomBox(room);
        transformRoom(f, rid, horizontal ? {
          ...b,
          width: point.x - b.x
        } : {
          ...b,
          depth: point.y - b.y
        }, d.building?.wall_thickness);
      }
    } else {
      setPath(item, path, value);
      if (primary.type === 'furniture') item.client_edited_3d = true;
    }
  });
  const action = (name, value) => {
    const ok = run(name.replaceAll('-', ' '), (f, d) => {
      if (selection.some(s => layers[collectionFor(s.type)]?.locked)) throw new Error('Unlock the selected layer first.');
      const item = getEntity(f, primary);
      if (name === 'delete') return deleteEntities(f, d, selection);
      if (name.startsWith('split-')) {
        splitRoom(f, primary.id, name.endsWith('x') ? 'x' : 'y');
        return;
      }
      if (name === 'merge') {
        mergeRooms(f, selection.map(s => s.id));
        return;
      }
      if (name === 'array') return arrayWindows(f, primary.id, value);
      if (name.startsWith('align-')) return alignFurniture(f, selection.map(s => s.id), name.slice(6));
      if (name === 'group' || name === 'ungroup') {
        const groupId = name === 'group' ? uid('group') : null;
        selection.forEach(s => {
          const i = getEntity(f, s);
          if (i.locked) throw new Error('Unlock all items first.');
          i.group_id = groupId;
        });
        return;
      }
      if (!item || item.locked) throw new Error('Unlock the selection first.');
      if (name.startsWith('rotate')) item.rotation = round(((item.rotation || 0) + (name === 'rotate45' ? 45 : 90)) % 360);
      if (name === 'mirror-x') item.flip_x = !item.flip_x;
      if (name === 'mirror-y') item.flip_y = !item.flip_y;
      if (name === 'center') {
        const b = roomBox(f.rooms.find(r => r.id === item.room_id));
        item.position.x = b.x + b.width / 2;
        item.position.y = b.y + b.depth / 2;
      }
      if (name === 'snap-wall') {
        const b = roomBox(f.rooms.find(r => r.id === item.room_id)),
          footprint = polygonBounds(rotatedRectangle(item)),
          halfW = footprint.width / 2,
          halfD = footprint.depth / 2;
        const candidates = [{
          x: b.x + halfW,
          y: item.position.y
        }, {
          x: b.right - halfW,
          y: item.position.y
        }, {
          x: item.position.x,
          y: b.y + halfD
        }, {
          x: item.position.x,
          y: b.top - halfD
        }].sort((a, b) => distance(a, item.position) - distance(b, item.position));
        Object.assign(item.position, candidates[0]);
      }
      if (name === 'duplicate') {
        const copied = clone(item);
        copied.id = uid(primary.type);
        delete copied.group_id;
        copied.position.x += .3;
        copied.position.y += .3;
        f[collectionFor(primary.type)].push(copied);
      }
      if (primary.type === 'furniture') item.client_edited_3d = true;
    });
    if (ok && ['delete', 'merge'].includes(name)) editor.select(null);
  };
  const floorAction = name => {
    let nextIndex = floorIndex;
    const ok = run(`${name} floor`, (f, d) => {
      if (name === 'duplicate') {
        duplicateFloor(d, floorIndex);
        nextIndex++;
      }
      if (name === 'add' || name === 'stair-floor') {
        if (d.floors.length >= 4) throw new Error('Up to four floors are supported.');
        duplicateFloor(d, floorIndex);
        nextIndex++;
        const added = d.floors[nextIndex];
        added.name = `Floor ${nextIndex}`;
        added.furniture = [];
        added.doors = [];
        added.windows = [];
        if(name==='stair-floor')nextIndex=floorIndex;
      }
      if (name === 'delete') {
        if (d.floors.length <= 1) throw new Error('Keep at least one floor.');
        d.deleted_furniture_ids = [...new Set([...(d.deleted_furniture_ids || []), ...f.furniture.map(i => i.id)])];
        d.floors.splice(floorIndex, 1);
        nextIndex = Math.max(0, floorIndex - 1);
      }
      if (name === 'up' || name === 'down') {
        nextIndex += name === 'up' ? 1 : -1;
        [d.floors[floorIndex], d.floors[nextIndex]] = [d.floors[nextIndex], d.floors[floorIndex]];
      }
    });
    if (ok) {
      clearGesture();
      editor.setFloor(nextIndex);
    }
  };
  const projectUpdate = (path, value) => run(`Edit ${path}`, (f, d) => {
    if (path.startsWith('floor.')) {
      setPath(f, path.slice(6), value);
      if (path === 'floor.floor_height') f.rooms.forEach(r => {
        r.dimensions.height = value;
      });
    } else setPath(d, path, value);
  });
  const applyAi = async prompt => {
    if (!entity || selection.length!==1 || !collectionFor(primary?.type)) { toast('Select one element to edit with AI.'); return false; }
    if(layers[collectionFor(primary.type)]?.locked) { toast.error('Unlock the selected layer first.'); return false; }
    if (!prompt.trim() || aiBusy || !project.activeProjectId || !project.activeVersionId) {
      toast.error('Save this project before requesting an AI edit.');
      return false;
    }
    setAiBusy(true);setAiFeedback(null);
    try {
      const response = await apiClient.post(`/projects/${project.activeProjectId}/versions/${project.activeVersionId}/layout/refine`, {
        design,
        prompt,
        selection:{type:primary.type,id:entity.id,floor_id:floor.id}
      });
      const next = response.data.design;
      if (!next) throw new Error(response.data.error || 'The edit could not be applied.');
      if (useProjectStore.getState().design !== design) throw new Error('The design changed while this edit was being prepared. Apply it again to the current draft.');
      if(!commit(next,'AI: '+prompt.slice(0,100))) {setAiFeedback({error:true,message:'The edit conflicts with the plan. Check the highlighted issues.'});return false;}
      const message=response.data.report?.changes?.[0] || `${entity.name || entity.type?.replaceAll('_',' ') || primary.type} updated.`;
      setAiFeedback({message});toast.success(message,{id:'cad-ai-result'});return true;
    } catch (error) {
      const raw=error.response?.data?.error || error.message;
      const friendly=layoutDiagnostics(rendered,{critical_errors:[raw]})[0]?.message || 'Try this edit again.';
      setAiFeedback({error:true,message:friendly});
      toast.error(friendly.length <= 140 ? friendly : `${entity.name || entity.type?.replaceAll('_',' ') || primary.type}: ${friendly.slice(0,110)}…`,{id:'cad-ai-result'});
      return false;
    } finally {
      setAiBusy(false);
    }
  };
  const save = async approve => {
    if (blocked) return;
    if(!approve){onRequestSave?.();return;}
    if(project.isDirty){toast('Save changes before building 3D.',{id:'cad-save-first'});onRequestSave?.();return;}
    const errors=validateClientDesign(normalized).filter(issue=>issue.severity==='error');
    if(errors.length){setDiagnosticRequest(value=>value+1);toast.error(layoutConflictSummary(errors.length),{id:'layout-conflicts'});return;}
    setSaving(true);
    clearGesture();
    try {
      if (approve) await onApproveLayout?.();
    } finally {
      setSaving(false);
    }
  };
  const world = e => svgToWorld(svgRef.current, e.clientX, e.clientY, plotD);
  const snapped = (point, event, moving) => {
    const furniture = moving && floor.furniture.some(i => i.id === moving.id),
      bounds = furniture ? polygonBounds(rotatedRectangle(moving)) : null;
    const clearance = furniture && /bed|desk/.test(moving.category || moving.asset || '') ? .05 : 0;
    const halfW = bounds ? bounds.width / 2 + clearance : 0,
      halfD = bounds ? bounds.depth / 2 + clearance : 0;
    const targets = floor.rooms.filter(r => r.id !== moving?.id).flatMap(r => {
      const b = roomBox(r);
      return [{
        x: b.x + halfW,
        y: b.y + halfD
      }, {
        x: b.right - halfW,
        y: b.top - halfD
      }, {
        x: b.x + b.width / 2,
        y: b.y + b.depth / 2
      }];
    });
    targets.push(...floor.furniture.filter(i => i.id !== moving?.id).map(i => i.position));
    const matrix = svgRef.current.getScreenCTM(),
      tolerance = 8 / Math.max(.01, matrix.a * SCALE);
    const result = snapPoint(point, {
      enabled: snap && !event.shiftKey,
      step: gridStep,
      tolerance,
      targets
    });
    setGuides(result.guides);
    return result.point;
  };
  const startEntity = (event, type, item, handle = null) => {
    if (blocked || event.altKey || event.button !== 0 || activeTool !== 'select' || pointers.current.size > 1 || pointers.current.size === 1 && !pointers.current.has(event.pointerId)) return;
    const layer = layers[collectionFor(type)];
    if (layer?.locked || !layer?.visible) return;
    event.stopPropagation();
    rootRef.current.focus({
      preventScroll: true
    });
    const already = selection.some(s => s.type === type && s.id === item.id);
    if (!already || event.shiftKey) select(type, item, event.shiftKey, false);
    if (event.shiftKey || !editable || item.locked) { editor.setOption('panel', 'inspector'); return; }
    const selected = already ? selection : type === 'furniture' && item.group_id ? floor.furniture.filter(i => i.group_id === item.group_id).map(i => ({
      type,
      id: i.id
    })) : [{
      type,
      id: item.id
    }];
    if (selected.some(s => getEntity(floor, s)?.locked || layers[collectionFor(s.type)]?.locked)) return;
    svgRef.current.setPointerCapture(event.pointerId);
    pointers.current.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY
    });
    gesture.current = {
      kind: 'entity',
      type,
      id: item.id,
      handle,
      start: world(event),
      client: {
        x: event.clientX,
        y: event.clientY
      },
      factor: 1 / (svgRef.current.getScreenCTM().a * SCALE),
      before: design,
      selected,
      moved: false,
      pointerId: event.pointerId
    };
  };
  const placeAsset = (chosen, point) => {
    if (layers.furniture.locked || !layers.furniture.visible) {
      toast.error('Show and unlock the furniture layer first.');
      return;
    }
    let placed;
    if (run('Add furniture', f => {
      placed = addFurniture(f, chosen, point);
    })) {
      editor.select({
        type: 'furniture',
        id: placed.id
      });
      editor.setOption('panel', 'inspector');
      editor.setTool('select');
      setAsset(null);
    }
  };
  const start = event => {
    if (blocked || event.button !== 0 && event.button !== 1) return;
    rootRef.current.focus({
      preventScroll: true
    });
    svgRef.current.setPointerCapture(event.pointerId);
    pointers.current.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY
    });
    if (pointers.current.size === 2) {
      const pts = [...pointers.current.values()];
      previewRef.current = null;
      setPreview(null);
      setRubber(null);
      gesture.current = {
        kind: 'pinch',
        distance: distance(pts[0], pts[1]),
        camera: {
          ...camera
        }
      };
      return;
    }
    if (pointers.current.size > 2) return;
    const point = world(event);
    if (activeTool === 'pan' || event.button === 1 || event.altKey) {
      manualView.current=true;
      gesture.current = {
        kind: 'pan',
        x: event.clientX,
        y: event.clientY,
        camera: {
          ...camera
        },
        factor: 1 / svgRef.current.getScreenCTM().a
      };
      return;
    }
    if (activeTool === 'measure') {
      editor.setOption('measurement', editor.measurement.length === 1 ? [editor.measurement[0], point] : [point]);
      return;
    }
    if (activeTool === 'door' || activeTool === 'window') {
      const type = activeTool;
      if (layers[collectionFor(type)].locked || !layers[collectionFor(type)].visible) {
        toast.error('Show and unlock this layer first.');
        return;
      }
      const ok = run(`Add ${type}`, f => {
        const item = hostOpening(f, {
          id: uid(type),
          kind: type,
          type: type === 'door' ? 'single_swing' : 'double_casement',
          width: type === 'door' ? .85 : 1.4,
          height: type === 'door' ? 2.1 : 1.4,
          sill_height: type === 'door' ? 0 : .9,
          swing_direction: 'inward',
          hinge_side: 'left'
        }, point);
        if (distance(item.position, point) > .75) throw new Error('Tap near a wall to place an opening.');
        f[collectionFor(type)].push(item);
        editor.select({
          type,
          id: item.id
        });
        editor.setOption('panel', 'inspector');
      });
      if (ok) editor.setTool('select');
      return;
    }
    if (activeTool === 'furniture') {
      if (!asset) {
        editor.setOption('panel', 'assets');
        return;
      }
      placeAsset(asset, point);
      return;
    }
    if (activeTool === 'stair') {
      if (floorIndex === rendered.floors.length - 1) {
        editor.setOption('panel','stairs');toast('Add an upper floor first.',{id:'cad-stair-help'});
        return;
      }
      if (layers.stairs.locked || !layers.stairs.visible) {
        toast.error('Show and unlock the stairs layer first.');
        return;
      }
      let stair;
      try{stair=createStairPlacement(floor,snapped(point,event),stairType)}catch(error){toast.error(error.message,{id:'cad-stair-help'});return;}
      if (run('Add stair', f => {
        f.stairs.push(stair);
      })) {
        editor.select({
          type: 'stair',
          id: stair.id
        });
        editor.setTool('select');
        editor.setOption('panel', 'inspector');
        setStairPreview(null);toast.success('Stair placed. Upper opening aligned.',{id:'cad-stair-help'});
      }
      return;
    }
    if (activeTool === 'room' || activeTool === 'wall') {
      if (!editable || layers.rooms.locked || activeTool === 'wall' && layers.walls.locked) return;
      const p = snapped(point, event);
      gesture.current = {
        kind: activeTool,
        start: p,
        before: design
      };
      setRubber({
        start: p,
        end: p,
        kind: activeTool
      });
      return;
    }
    if (!event.shiftKey) editor.select(null);
    gesture.current = {
      kind: 'marquee',
      start: point,
      additive: event.shiftKey
    };
    setRubber({
      start: point,
      end: point,
      kind: 'marquee'
    });
  };
  const move = event => {
    if(activeTool==='stair'&&!gesture.current){try{setStairPreview(createStairPlacement(floor,world(event),stairType))}catch{setStairPreview(null)}}
    if (pointers.current.has(event.pointerId)) pointers.current.set(event.pointerId, {
      x: event.clientX,
      y: event.clientY
    });
    const g = gesture.current;
    if (!g || blocked) return;
    if (g.kind === 'pinch') {
      manualView.current=true;
      if (pointers.current.size === 2) {
        const p = [...pointers.current.values()];
        setCamera({
          ...g.camera,
          zoom: clamp(g.camera.zoom * distance(p[0], p[1]) / Math.max(g.distance, 1), .35, 6)
        });
      }
      return;
    }
    if (g.kind === 'pan') {
      setCamera({
        ...g.camera,
        x: g.camera.x - (event.clientX - g.x) * g.factor,
        y: g.camera.y - (event.clientY - g.y) * g.factor
      });
      return;
    }
    const point = g.kind === 'entity' ? {
      x: g.start.x + (event.clientX - g.client.x) * g.factor,
      y: g.start.y - (event.clientY - g.client.y) * g.factor
    } : world(event);
    if (['marquee', 'room', 'wall'].includes(g.kind)) {
      setRubber({
        start: g.start,
        end: g.kind === 'marquee' ? point : snapped(point, event),
        kind: g.kind
      });
      return;
    }
    if (g.kind !== 'entity' || distance(point, g.start) < .015 && !g.moved) return;
    g.moved = true;
    try {
      const baseFloor = normalizeEditorDesign(g.before).floors[floorIndex],
        source = getEntity(baseFloor, g),
        delta = {
          x: point.x - g.start.x,
          y: point.y - g.start.y
        };
      const next = editDesign(g.before, floorIndex, (f, d) => {
        const item = getEntity(f, g);
        if (g.type === 'door' || g.type === 'window') {
          Object.assign(item, hostOpening(f, item, point));
          return;
        }
        if (g.type === 'wall') {
          moveWall(f, g.id, snapped(point, event), d.building?.wall_thickness);
          return;
        }
        if (g.handle === 'rotate') {
          let angle = (Math.atan2(point.y - source.position.y, point.x - source.position.x) * 180 / Math.PI - 90 + 360) % 360;
          item.rotation = snap && !event.shiftKey ? Math.round(angle / 45) * 45 : round(angle);
          item.client_edited_3d = true;
          return;
        }
        if (g.handle) {
          const b = roomBox(source),
            centered = g.type === 'furniture';
          if (centered) {
            const angle = (source.rotation || 0) * Math.PI / 180,
              c = Math.cos(angle),
              s = Math.sin(angle),
              local = {
                x: delta.x * c + delta.y * s,
                y: -delta.x * s + delta.y * c
              };
            const left = g.handle.includes('w') ? -b.width / 2 + local.x : -b.width / 2,
              right = g.handle.includes('e') ? b.width / 2 + local.x : b.width / 2;
            const bottom = g.handle.includes('s') ? -b.depth / 2 + local.y : -b.depth / 2,
              top = g.handle.includes('n') ? b.depth / 2 + local.y : b.depth / 2;
            if (right - left < .05 || top - bottom < .05) return;
            const cx = (left + right) / 2,
              cy = (bottom + top) / 2;
            item.dimensions.width = round(right - left);
            item.dimensions.depth = round(top - bottom);
            item.position.x = round(source.position.x + cx * c - cy * s);
            item.position.y = round(source.position.y + cx * s + cy * c);
            item.client_edited_3d = true;
          } else {
            const p = snapped(point, event),
              nextBox = {
                ...b
              };
            if (g.handle.includes('w')) {
              nextBox.x = Math.min(p.x, b.right - 1);
              nextBox.width = b.right - nextBox.x;
            }
            if (g.handle.includes('e')) nextBox.width = Math.max(1, p.x - b.x);
            if (g.handle.includes('s')) {
              nextBox.y = Math.min(p.y, b.top - 1);
              nextBox.depth = b.top - nextBox.y;
            }
            if (g.handle.includes('n')) nextBox.depth = Math.max(1, p.y - b.y);
            if (g.type === 'room') transformRoom(f, g.id, nextBox, d.building?.wall_thickness);else {
              item.position.x = nextBox.x;
              item.position.y = nextBox.y;
              item.dimensions.width = nextBox.width;
              item.dimensions.depth = nextBox.depth;
            }
          }
          return;
        }
        const p = snapped({
            x: source.position.x + delta.x,
            y: source.position.y + delta.y
          }, event, source),
          snappedDelta = {
            x: p.x - source.position.x,
            y: p.y - source.position.y
          };
        if (g.type === 'furniture') moveFurniture(f, g.selected, snappedDelta);else if (g.type === 'room') for (const selected of g.selected.filter(s => s.type === 'room')) {
          const r = getEntity(f, selected),
            b = roomBox(r);
          transformRoom(f, r.id, {
            ...b,
            x: b.x + snappedDelta.x,
            y: b.y + snappedDelta.y
          }, d.building?.wall_thickness);
        } else Object.assign(item.position, p);
      });
      previewRef.current = next;
      setPreview(next);
    } catch (error) {
      if (!g.error) {
        g.error = error.message;
        console.warn('[CAD transform]', error.message);
      }
    }
  };
  const end = event => {
    const g = gesture.current;
    pointers.current.delete(event.pointerId);
    if (g?.kind === 'pinch') {
      if (!pointers.current.size) clearGesture();
      return;
    }
    if (!g) return;
    if (g.kind === 'entity' && g.moved && previewRef.current) commit(previewRef.current, `${g.handle ? 'Transform' : 'Move'} ${g.type}`, g.before);
    if (g.kind === 'entity') editor.setOption('panel', 'inspector');
    if (g.kind === 'marquee' && rubber) {
      const b = {
        x: Math.min(g.start.x, rubber.end.x),
        y: Math.min(g.start.y, rubber.end.y),
        right: Math.max(g.start.x, rubber.end.x),
        top: Math.max(g.start.y, rubber.end.y)
      };
      if (b.right - b.x > .1 && b.top - b.y > .1) {
        const found = [];
        for (const [type, items] of [['furniture', floor.furniture], ['room', floor.rooms]]) {
          if (!layers[collectionFor(type)].visible || layers[collectionFor(type)].locked) continue;
          for (const item of items) {
            const bounds = type === 'furniture' ? polygonBounds(rotatedRectangle(item)) : roomBox(item);
            if (containsPoint(b, {
              x: bounds.x,
              y: bounds.y
            }) && containsPoint(b, {
              x: bounds.right,
              y: bounds.top
            })) found.push({
              type,
              id: item.id
            });
          }
          if (found.length) break;
        }
        useFloorPlanEditorStore.setState({
          selection: g.additive ? [...selection, ...found.filter(s => !selection.some(a => a.id === s.id && a.type === s.type))] : found,
          panel: found.length ? 'inspector' : panel
        });
      }
    }
    if (g.kind === 'room' && rubber) {
      const x = Math.min(g.start.x, rubber.end.x),
        y = Math.min(g.start.y, rubber.end.y),
        w = Math.abs(g.start.x - rubber.end.x),
        d = Math.abs(g.start.y - rubber.end.y);
      if (w >= 1 && d >= 1) {
        const room = {
          id: uid('room'),
          name: 'New room',
          type: 'living_room',
          position: {
            x,
            y,
            z: floor.elevation || 0
          },
          dimensions: {
            width: w,
            depth: d,
            height: floor.floor_height || 3
          },
          wall_thickness: .2,
          locked: false
        };
        if (run('Add room', (f, doc) => {
          f.rooms.push(room);
          rebuildWalls(f, doc.building?.wall_thickness);
          rehostOpenings(f);
        })) {
          select('room', room);
          editor.setTool('select');
        }
      } else toast.error('Draw a room at least 1 m wide and deep.');
    }
    if (g.kind === 'wall' && rubber) {
      const room = roomAtPoint(floor, {
        x: (g.start.x + rubber.end.x) / 2,
        y: (g.start.y + rubber.end.y) / 2
      });
      if (room) {
        const b = roomBox(room),
          vertical = Math.abs(rubber.end.y - g.start.y) > Math.abs(rubber.end.x - g.start.x),
          axis = vertical ? 'x' : 'y',
          coordinate = round((g.start[axis] + rubber.end[axis]) / 2),
          spanning = vertical ? Math.min(g.start.y, rubber.end.y) <= b.y + .3 && Math.max(g.start.y, rubber.end.y) >= b.top - .3 : Math.min(g.start.x, rubber.end.x) <= b.x + .3 && Math.max(g.start.x, rubber.end.x) >= b.right - .3;
        if (!spanning) toast.error('Draw a partition across the full room, from one boundary to the opposite boundary.');else if (run('Split room with partition', f => splitRoom(f, room.id, axis, coordinate))) editor.setTool('select');
      } else toast.error('Draw a partition across an existing room.');
    }
    clearGesture();
    if (svgRef.current.hasPointerCapture(event.pointerId)) svgRef.current.releasePointerCapture(event.pointerId);
  };
  const keyboard = e => {
    if (isTextInput(e.target) || blocked) return;
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 'z') {
      e.preventDefault();
      e.shiftKey ? redo() : undo();
    } else if (mod && e.key.toLowerCase() === 'y') {
      e.preventDefault();
      redo();
    } else if (mod && e.key.toLowerCase() === 's') {
      e.preventDefault();
      save(false);
    } else if (e.key === 'Escape') {
      clearGesture();
      editor.select(null);
      editor.setTool('select');
      editor.setOption('panel', null);
      setAsset(null);
    } else if ((e.key === 'Delete' || e.key === 'Backspace') && selection.length) {
      e.preventDefault();
      action('delete');
    } else if (mod && e.key.toLowerCase() === 'd' && primary?.type === 'furniture') {
      e.preventDefault();
      action('duplicate');
    } else if (e.key === 'v') editor.setTool('select');else if (e.key === 'h') editor.setTool('pan');else if (e.key.toLowerCase() === 'g') editor.setOption('snap', !snap);
  };
  if (!rendered || !floor) return <div className="cad-editor">No floor plan available.</div>;
  const canSelect = activeTool === 'select' && !blocked,
    selected = (type, id) => selection.some(s => s.type === type && s.id === id);
  const hazardIds = new Set(issues.filter(i => i.floorIndex === floorIndex && i.severity === 'error').map(i => i.entity.id));
  const handleSize = 12 / Math.max(.25, svgRef.current?.getScreenCTM()?.a || 1);
  const dimension = (r, index) => {
    const b = roomBox(r),
      y = mapY(b.y) - 7,
      x = mapX(b.x) + 5;
    return <g key={index} fill="#a9b8cc" stroke="#64748b" strokeWidth=".8" pointerEvents="none"><path d={`M ${mapX(b.x) + 10} ${y - 8} V ${y + 3} M ${mapX(b.x) + 10} ${y - 3} H ${mapX(b.right) - 10} M ${mapX(b.right) - 10} ${y - 8} V ${y + 3}`} /><text x={mapX(b.x + b.width / 2)} y={y - 8} textAnchor="middle" stroke="none" fontSize="9">{formatDim(b.width, unit)}</text><text x={x + 6} y={mapY(b.y + b.depth / 2)} textAnchor="middle" stroke="none" fontSize="9" transform={`rotate(-90 ${x + 6} ${mapY(b.y + b.depth / 2)})`}>{formatDim(b.depth, unit)}</text></g>;
  };
  return <section ref={rootRef} className={`cad-editor ${panel ? 'cad-panel-open' : ''} ${panel&&editor.panelExpanded?'cad-panel-expanded':''}`} aria-label="2D design editor" tabIndex={0} onKeyDown={keyboard}>
    <div className="cad-header"><div><span className="cad-eyebrow">DESIGN WORKSPACE</span><strong>2D design editor</strong></div><div className="cad-header-actions"><span className={`cad-draft-status ${project.isDirty?'dirty':''}`}>{project.isSavingVersion?'Saving…':project.isDirty?'Unsaved changes':'All changes saved'}</span><button aria-label="Undo" title={editor.past.at(-1)?.description || 'Undo (Ctrl Z)'} disabled={!editor.past.length || blocked} onClick={undo}><Undo2 size={17} /></button><button aria-label="Redo" disabled={!editor.future.length || blocked} onClick={redo}><Redo2 size={17} /></button><button aria-label="Toggle properties" aria-pressed={panel === 'inspector'} onClick={() => editor.setOption('panel', panel === 'inspector' ? null : 'inspector')}><PanelRight size={17} /></button></div></div>
    <FloorManagerBar floors={rendered.floors} active={floorIndex} onSelect={index => {
      clearGesture();
      editor.setFloor(index);
    }} onAction={floorAction} ghost={ghost} onGhost={() => editor.setOption('ghost', !ghost)} />
    <div className="cad-workspace"><div className="cad-viewport">
      <div className="cad-tools" role="toolbar" aria-label="CAD tools">{TOOLS.map(([tool, label, Icon]) => <button key={tool} aria-label={label} title={label} aria-pressed={activeTool === tool} disabled={!editable && !['select', 'pan', 'measure'].includes(tool) || blocked} onClick={() => {
            clearGesture();
            editor.setTool(tool);
            if (tool === 'furniture') editor.setOption('panel', 'assets');
            if(tool==='stair')editor.setOption('panel','stairs');
          }}><Icon size={17} /><span>{label}</span></button>)}</div>
      <svg ref={svgRef} role="img" aria-label={`${floor.name || 'Floor'} editable plan`} className={`cad-canvas cad-tool-${activeTool}`} viewBox={viewBox} onPointerDown={start} onPointerMove={move} onPointerUp={end} onPointerCancel={clearGesture} onLostPointerCapture={() => {
          if (gesture.current) clearGesture();
        }} onContextMenu={e => e.preventDefault()} onDragOver={e => {
          e.preventDefault();
          e.dataTransfer.dropEffect = 'copy';
        }} onDrop={e => {
          e.preventDefault();
          try {
            placeAsset(JSON.parse(e.dataTransfer.getData('application/archigen-asset')), world(e));
          } catch {
            toast.error('Choose an asset from the furniture palette.');
          }
        }} onWheel={e => {
          if (blocked || gesture.current) return;
          manualView.current=true;
          setCamera(c => ({
            ...c,
            zoom: clamp(c.zoom * (e.deltaY < 0 ? 1.12 : 1 / 1.12), .35, 6)
          }));
        }}>
        <defs><pattern id={gridId} width={gridStep * SCALE} height={gridStep * SCALE} patternUnits="userSpaceOnUse" x={mapX(0)} y={mapY(0)}><circle cx="1" cy="1" r=".65" fill="var(--border, #292929)" /></pattern><pattern id={`hatch-${id}`} width="8" height="8" patternTransform="rotate(45)" patternUnits="userSpaceOnUse"><line x1="0" y1="0" x2="0" y2="8" stroke="#64748b" strokeWidth=".7" /></pattern></defs>
        <rect x="-10000" y="-10000" width="20000" height="20000" fill={`url(#${gridId})`} pointerEvents="none" />
        {layers.site.visible && <g pointerEvents="none"><rect x={mapX(0)} y={mapY(plotD)} width={plotW * SCALE} height={plotD * SCALE} fill="#0f172a55" stroke="#f8717188" strokeDasharray="8 5" strokeWidth="1.5" /><SitePlanLayer design={rendered} isGroundFloor={floorIndex === 0} mapX={mapX} mapY={mapY} orientation={rendered.project?.orientation || 'south'} plotW={plotW} plotD={plotD} scale={SCALE} /></g>}
        {layers.site.visible && rendered.site?.setbacks && (() => {
          const s=rendered.site.setbacks, w=plotW-Number(s.left||0)-Number(s.right||0), d=plotD-Number(s.front||0)-Number(s.back||0);
          return w>0&&d>0 ? <rect x={mapX(s.left||0)} y={mapY(plotD-Number(s.back||0))} width={w*SCALE} height={d*SCALE} fill="none" stroke="#f9731666" strokeWidth="1" strokeDasharray="4 5" pointerEvents="none"/> : null;
        })()}
        {ghost && floorIndex > 0 && <g opacity=".25" pointerEvents="none" stroke="#22d3ee" strokeDasharray="5 4">{rendered.floors[floorIndex - 1].walls.map(w => <line key={w.id} x1={mapX(w.start.x)} y1={mapY(w.start.y)} x2={mapX(w.end.x)} y2={mapY(w.end.y)} strokeWidth={(w.thickness || .2) * SCALE} />)}{[...rendered.floors[floorIndex - 1].doors, ...rendered.floors[floorIndex - 1].windows].map(o => <circle key={o.id} cx={mapX(o.position.x)} cy={mapY(o.position.y)} r="5" fill="none" />)}</g>}
        {layers.rooms.visible && floor.rooms.map(r => {
            const b = roomBox(r),
              color = getRoomColor(r.type, selected('room', r.id));
            return <g key={r.id} data-entity-id={r.id} data-entity-type="room" onPointerDown={e => startEntity(e, 'room', r)} style={{
              cursor: canSelect ? 'move' : undefined
            }}><rect x={mapX(b.x)} y={mapY(b.top)} width={b.width * SCALE} height={b.depth * SCALE} fill={color.fill} stroke={selected('room', r.id) ? '#60a5fa' : color.border} strokeWidth="1.5" />{r.type === 'garage' && <rect x={mapX(b.x)} y={mapY(b.top)} width={b.width * SCALE} height={b.depth * SCALE} fill={`url(#hatch-${id})`} opacity=".3" />}</g>;
          })}
        {layers.walls.visible && floor.walls.map(w => <g key={w.id} data-entity-id={w.id} data-entity-type="wall" onPointerDown={e => startEntity(e, 'wall', w)} style={{
            cursor: canSelect ? 'move' : undefined
          }}><line x1={mapX(w.start.x)} y1={mapY(w.start.y)} x2={mapX(w.end.x)} y2={mapY(w.end.y)} stroke={selected('wall', w.id) ? '#60a5fa' : w.type === 'exterior' ? '#7b8ca4' : '#536780'} strokeWidth={(w.thickness || .15) * SCALE} strokeLinecap="square" /><line x1={mapX(w.start.x)} y1={mapY(w.start.y)} x2={mapX(w.end.x)} y2={mapY(w.end.y)} stroke="transparent" strokeWidth={Math.max(12, (w.thickness || .15) * SCALE)} /></g>)}
        {layers.stairs.visible && <g>{floor.stair_openings.map(o => {
              const b = roomBox(o);
              return <g key={o.id} pointerEvents="none"><rect x={mapX(b.x)} y={mapY(b.top)} width={b.width * SCALE} height={b.depth * SCALE} fill={`url(#hatch-${id})`} stroke="#fbbf24" strokeDasharray="5 3" /><text x={mapX(b.x + b.width / 2)} y={mapY(b.y + b.depth / 2)} fill="#fbbf24" fontSize="10" textAnchor="middle">STAIR VOID</text></g>;
            })}{floor.stairs.map(s => {
              return <g key={s.id} data-entity-id={s.id} data-entity-type="stair" onPointerDown={e => startEntity(e, 'stair', s)}><CadStairItem stair={s} scale={SCALE} mapX={mapX} mapY={mapY} selected={selected('stair', s.id)} /></g>;
            })}</g>}
        {layers.furniture.visible && floor.furniture.map(item => {
            const b = polygonBounds(rotatedRectangle(item));
            return <g key={item.id} data-entity-id={item.id} data-entity-type="furniture" onPointerDown={e => startEntity(e, 'furniture', item)} style={{
              cursor: canSelect ? 'move' : undefined
            }}><rect x={mapX(b.x)} y={mapY(b.top)} width={b.width * SCALE} height={b.depth * SCALE} fill={hazardIds.has(item.id) ? '#f59e0b33' : 'transparent'} stroke={selected('furniture', item.id) ? '#60a5fa' : 'transparent'} strokeDasharray="4 3" /><g transform={`translate(${mapX(item.position.x)} ${mapY(item.position.y)}) rotate(${-Number(item.rotation || 0)}) scale(${item.flip_x ? -1 : 1} ${item.flip_y ? -1 : 1}) rotate(${item.rotation || 0}) translate(${-mapX(item.position.x)} ${-mapY(item.position.y)})`}><CadFurnitureItem item={item} scale={SCALE} mapX={mapX} mapY={mapY} /></g></g>;
          })}
        {['door', 'window'].map(type => layers[collectionFor(type)].visible && floor[collectionFor(type)].map(o => {
            const wall = floor.walls.find(w => w.id === o.wall_id),
              angle = wall ? Math.atan2(wall.end.y - wall.start.y, wall.end.x - wall.start.x) : ['east', 'west'].includes(o.wall_side) ? Math.PI / 2 : 0,
              dx = Math.cos(angle) * (o.width || 1) / 2,
              dy = Math.sin(angle) * (o.width || 1) / 2;
            return <g key={o.id} data-entity-id={o.id} data-entity-type={type} onPointerDown={e => startEntity(e, type, o)} style={{
              cursor: canSelect ? 'move' : undefined
            }}>{type === 'door' ? <CadDoorItem door={o} scale={SCALE} mapX={mapX} mapY={mapY} rooms={floor.rooms} /> : <CadWindowItem windowItem={o} scale={SCALE} mapX={mapX} mapY={mapY} rooms={floor.rooms} />}<line x1={mapX(o.position.x - dx)} y1={mapY(o.position.y - dy)} x2={mapX(o.position.x + dx)} y2={mapY(o.position.y + dy)} stroke={selected(type, o.id) ? '#60a5fa' : 'transparent'} strokeWidth="13" opacity={selected(type, o.id) ? .35 : 1} /></g>;
          }))}
        {layers.rooms.visible && floor.rooms.map(room => {
          const b = roomBox(room), name = String(room.name || room.type).replaceAll('_', ' ').slice(0, 28);
          const fontSize = Math.min(12 / Math.max(.2, svgRef.current?.getScreenCTM()?.a || 1), b.width * SCALE / Math.max(8, name.length * .65));
          const x = mapX(b.x + b.width / 2), y = mapY(b.top - Math.min(.7, b.depth / 2));
          return <text key={room.id} x={x} y={y} textAnchor="middle" fill="#dbeafe" stroke="#111c2e" strokeWidth="3" paintOrder="stroke" fontSize={fontSize} fontWeight="600" pointerEvents="none">{name}<tspan x={x} dy={fontSize * 1.3} fontSize={fontSize * .8} fill="#a9b8cc">{(b.width * b.depth * (unit === 'ft' ? 10.7639 : 1)).toFixed(1)} {unit}²{room.locked ? ' · Locked' : ''}</tspan></text>;
        })}
        {layers.dimensions.visible && floor.rooms.map(dimension)}
        {entity && selection.length === 1 && canSelect && layers[collectionFor(primary.type)]?.visible && !layers[collectionFor(primary.type)]?.locked && <TransformGizmo entity={entity} type={primary.type} mapX={mapX} mapY={mapY} scale={SCALE} handleSize={handleSize} onStart={(e, handle) => startEntity(e, primary.type, entity, handle)} />}
        <SnapGuideLayer guides={guides} mapX={mapX} mapY={mapY} width={plotW} depth={plotD} /><MeasurementTool points={editor.measurement} mapX={mapX} mapY={mapY} unit={unit} />
        {activeTool==='stair'&&stairPreview&&<rect x={mapX(stairPreview.position.x)} y={mapY(stairPreview.position.y+stairPreview.dimensions.depth)} width={stairPreview.dimensions.width*SCALE} height={stairPreview.dimensions.depth*SCALE} fill="var(--accent-glow)" stroke="var(--accent)" strokeWidth="2" strokeDasharray="6 3" pointerEvents="none"/>}
        {rubber && (rubber.kind === 'wall' ? <line x1={mapX(rubber.start.x)} y1={mapY(rubber.start.y)} x2={mapX(rubber.end.x)} y2={mapY(rubber.end.y)} stroke="#60a5fa" strokeWidth="4" pointerEvents="none" /> : <rect x={mapX(Math.min(rubber.start.x, rubber.end.x))} y={mapY(Math.max(rubber.start.y, rubber.end.y))} width={Math.abs(rubber.end.x - rubber.start.x) * SCALE} height={Math.abs(rubber.end.y - rubber.start.y) * SCALE} fill="#3b82f622" stroke="#60a5fa" strokeDasharray="5 3" pointerEvents="none" />)}
      </svg>
      {activeTool==='stair'&&<div className="cad-tool-hint" role="status">{rendered.floors[floorIndex+1]?'Click a clear area to place stairs.':'Add an upper floor in the stair panel first.'}</div>}
      <div className="cad-view-controls"><button aria-label="Zoom out" onClick={() => {manualView.current=true;setCamera(c => ({
            ...c,
            zoom: Math.max(.35, c.zoom / 1.2)
          }))}}><ZoomOut size={16} /></button><span>{Math.round(camera.zoom * 100)}%</span><button aria-label="Zoom in" onClick={() => {manualView.current=true;setCamera(c => ({
            ...c,
            zoom: Math.min(6, c.zoom * 1.2)
          }))}}><ZoomIn size={16} /></button><button aria-label="Fit plan" onClick={() => {manualView.current=false;fitPlan()}}><Maximize2 size={15} /></button></div>
      <ValidationBadgeOverlay issues={allIssues} autoOpenKey={serverValidation || diagnosticRequest} onRepair={()=>{
        const next=editDesign(design,floorIndex,(f,d)=>{d.floors.forEach(rehostOpenings)});
        if(commit(next,'Repair door links'))toast.success('Door links repaired. Review remaining checks.');
        else toast('Move disconnected doors onto a shared wall.');
      }} onSelect={issue => {
          clearGesture();
          editor.setFloor(issue.floorIndex);
          editor.select(issue.entity);
          editor.setOption('panel', 'inspector');
        }} />
    </div>{panel && <aside className="cad-sidepanel" aria-label={panel === 'assets' ? 'Furniture palette' : panel === 'layers' ? 'Plan layers' : panel==='stairs'?'Stair placement':'Selection properties'}><div className="cad-panel-heading"><strong>{panel === 'assets' ? 'Asset library' : panel === 'layers' ? 'Plan layers' : panel==='stairs'?'Stair placement':'Properties'}</strong><div className="cad-panel-header-actions"><button className="cad-panel-expand" aria-label={editor.panelExpanded?'Collapse panel':'Expand panel'} aria-expanded={editor.panelExpanded} onClick={()=>editor.setOption('panelExpanded',!editor.panelExpanded)}><Maximize2 size={15}/></button><button aria-label="Close panel" onClick={() => editor.setOption('panel', null)}><X size={17} /></button></div></div>{panel === 'assets' ? <FurniturePaletteDrawer assets={assets} selected={asset} onChoose={a => {
          setAsset(a);
          editor.setTool('furniture');
          editor.setOption('panel', null);
        }} /> : panel === 'layers' ? <LayerVisibilityPanel layers={layers} onChange={editor.setLayer} /> : panel==='stairs'?<StairPlacementPanel floor={floor} upper={rendered.floors[floorIndex+1]} type={stairType} onType={setStairType} onAddFloor={()=>floorAction('stair-floor')} busy={blocked}/>:<SelectionInspector key={`${primary?.type}:${primary?.id}:${floor.id}`} entity={entity} type={primary?.type} selection={selection} design={rendered} floor={floor} unit={unit} onUpdate={update} onAction={action} onProject={projectUpdate} onAiEdit={applyAi} aiFeedback={aiFeedback} onAiFocus={()=>{if(rootRef.current?.clientWidth<=540)editor.setOption('panelExpanded',true)}} busy={aiBusy || blocked} />}</aside>}</div>
    {(project.isGenerating3D || project.generation3D?.error) && <div className="cad-build-status" data-status={project.isGenerating3D ? 'running' : 'failed'} role="status">
      {project.isGenerating3D ? 'Building 3D. You can return to this version to check progress.' : project.generation3D.error}
    </div>}
    <div className="cad-statusbar"><button aria-pressed={snap} onClick={() => editor.setOption('snap', !snap)} title="Toggle snapping (G); hold Shift to bypass"><Magnet size={14} /><span>Snap</span></button><select aria-label="Grid spacing" value={gridStep} onChange={e => editor.setOption('gridStep', Number(e.target.value))}>{[.1, .25, .5, 1, .1524, .3048].map(step => <option key={step} value={step}>{step === .1524 ? '6 in' : step === .3048 ? '1 ft' : `${step} m`}</option>)}</select><button aria-label="Strict placement" aria-pressed={strict} onClick={() => editor.setOption('strict', !strict)}>{strict ? 'Strict' : 'Warnings'}</button><button aria-label="Toggle layers" aria-pressed={panel === 'layers'} onClick={() => editor.setOption('panel', panel === 'layers' ? null : 'layers')}><Layers size={14} /><span>Layers</span></button><span className="cad-status-hint">{asset ? `Tap a room to place ${asset.name}` : activeTool === 'room' ? 'Drag to draw a room' : activeTool === 'wall' ? 'Draw across a room to split it' : activeTool === 'measure' ? 'Tap two points to measure' : `${floor.rooms.length} rooms · ${unit}`}</span>{onApproveLayout && <button className="cad-approve" aria-label="Build 3D" disabled={blocked} onClick={() => save(true)}>{isApproving || saving || project.isGenerating3D ? 'Building…' : project.generation3D?.error ? 'Retry Build 3D' : 'Build 3D'}</button>}</div>
  </section>;
}
