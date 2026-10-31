import React, { useEffect, useRef, useState } from 'react';
import { Copy, Lock, RotateCw, Trash2, Unlock } from 'lucide-react';
import { parseDimension } from '../../utils/cadGeometry.js';
import { formatDim } from './CadSymbols.jsx';
import { MIN_ROOM_DIMENSIONS } from '../../utils/clientArchitecturalValidator.js';
function Field({
  label,
  value,
  onCommit,
  unit,
  min = -Infinity,
  max = Infinity,
  numeric = true,
  disabled = false
}) {
  const display = numeric ? Number(Number(value || 0) * (unit === 'ft' ? 1 / .3048 : 1)).toFixed(2) : value || '';
  const [draft, setDraft] = useState(display),
    [error, setError] = useState('');
  const cancelCommit = useRef(false);
  useEffect(() => {
    setDraft(display);
    setError('');
  }, [display]);
  const commit = () => {
    if (cancelCommit.current) { cancelCommit.current = false; return; }
    if (draft === display) return;
    try {
      const resolved = numeric ? unit ? parseDimension(draft, unit) : Number(draft) : draft.trim();
      if (numeric && (!Number.isFinite(resolved) || resolved < min || resolved > max)) throw new Error(`Enter a value from ${min} to ${max}${unit ? ' m internally' : ''}.`);
      if (resolved !== value && onCommit(resolved) === false) setDraft(display);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };
  return <label className="cad-field"><span>{label}{unit && <small>{unit}</small>}</span><input aria-label={label} disabled={disabled} value={draft} onChange={e => setDraft(e.target.value)} onBlur={commit} onKeyDown={e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        e.currentTarget.blur();
      }
      if (e.key === 'Escape') {
        cancelCommit.current = true;
        setDraft(display);
        e.currentTarget.blur();
      }
    }} inputMode={numeric ? 'decimal' : 'text'} aria-invalid={Boolean(error)} />{error && <small className="cad-field-error">{error}</small>}</label>;
}
function Choice({
  label,
  value,
  options,
  onChange,
  disabled
}) {
  return <label className="cad-field"><span>{label}</span><select aria-label={label} value={value || ''} disabled={disabled} onChange={e => onChange(e.target.value)}>{options.map(option => <option key={typeof option === 'string' ? option : option.value} value={typeof option === 'string' ? option : option.value}>{typeof option === 'string' ? option.replaceAll('_', ' ') : option.label}</option>)}</select></label>;
}
export default function SelectionInspector({
  entity,
  type,
  selection,
  design,
  floor,
  unit,
  onUpdate,
  onAction,
  onProject,
  onAiEdit,
  aiFeedback,
  onAiFocus,
  busy
}) {
  const [anchor, setAnchor] = useState('sw'),
    [arrayCount, setArrayCount] = useState(3),
    [prompt, setPrompt] = useState('');
  const locked = Boolean(entity?.locked),
    change = (path, value) => onUpdate(path, value, anchor);
  const field = (label, path, value, min, max, isLength = true) => <Field key={path} label={label} value={value} unit={isLength ? unit : null} min={min} max={max} disabled={locked} onCommit={v => change(path, v)} />;
  const ai = <form className="cad-ai" onSubmit={async e => {
    e.preventDefault();
    if (await onAiEdit(prompt)) setPrompt('');
  }}><label htmlFor="cad-ai-prompt">Edit with AI</label><div className="cad-ai-target">{entity?.name || type?.replaceAll('_',' ')}<small>{floor.name || `Floor ${floor.level}`}</small></div><textarea id="cad-ai-prompt" placeholder={type==='room'?'Make this room wider…':type==='furniture'?'Rotate it 45 degrees, or move it left…':'Describe a change to this selection…'} value={prompt} maxLength={1500} disabled={busy || locked} onFocus={onAiFocus} onChange={e => setPrompt(e.target.value)} /><button disabled={busy || locked || !prompt.trim()} type="submit">{busy ? 'Applying…' : 'Apply edit'}</button>{aiFeedback&&<p className={aiFeedback.error?'cad-ai-error':'cad-ai-success'} role="status">{aiFeedback.message}</p>}<small>Uses this selection. Undo with Ctrl / ⌘ Z.</small></form>;
  if (!entity || type === 'floor') return <div className="cad-inspector-content">
    <div className="cad-eyebrow">PROJECT</div><h3>{design.project?.name || 'Floor plan'}</h3>
    <p>Select an element to edit its properties. Shift-click or draw a selection box to select multiple elements.</p>
    <Choice label="Display units" value={unit} options={['m', 'ft']} onChange={value => onProject('project.display_unit', value)} />
    <Field label="Floor name" value={floor.name || (floor.level === 0 ? 'Ground floor' : `Floor ${floor.level}`)} numeric={false} onCommit={v => onProject('floor.name', v || 'Floor')} />
    <Field label="Floor height" value={floor.floor_height || 3} unit={unit} min={2.2} max={5} onCommit={v => onProject('floor.floor_height', v)} />
    <Field label="Slab thickness" value={floor.slab_thickness || .2} unit={unit} min={.1} max={.4} onCommit={v => onProject('floor.slab_thickness', v)} />
    <div className="cad-stat"><span>Floor area</span><strong>{(floor.rooms.reduce((sum, r) => sum + r.dimensions.width * r.dimensions.depth, 0) * (unit === 'ft' ? 10.7639 : 1)).toFixed(1)} {unit}²</strong></div>
    <div className="cad-stat"><span>Floor elevation</span><strong>{formatDim(floor.elevation, unit)}</strong></div>
    <details className="cad-site-settings"><summary>Site & setbacks</summary>
      <div className="cad-field-grid"><Field label="Plot width" value={design.site?.plot?.width || 14} unit={unit} min={5} max={500} onCommit={v => onProject('site.plot.width',v)} /><Field label="Plot depth" value={design.site?.plot?.depth || 18} unit={unit} min={5} max={500} onCommit={v => onProject('site.plot.depth',v)} /></div>
      {['front','back','left','right'].map(side => <Field key={side} label={`${side[0].toUpperCase()+side.slice(1)} setback`} value={design.site?.setbacks?.[side] || 0} unit={unit} min={0} max={50} onCommit={v => onProject(`site.setbacks.${side}`,v)} />)}
    </details>
    <p>Drag room edges to resize. Drag a wall to move its connected room edges. Hold Shift to bypass snapping.</p><p className="cad-ai-empty">Select one room, furniture item or opening to edit it with AI.</p>
  </div>;
  if (selection.length > 1) return <div className="cad-inspector-content"><div className="cad-eyebrow">MULTIPLE SELECTION</div><h3>{selection.length} elements</h3><div className="cad-action-grid">{selection.every(s => s.type === 'room') && selection.length === 2 && <button onClick={() => onAction('merge')}>Merge rooms</button>}{selection.every(s => s.type === 'furniture') && <>{['left', 'center', 'right', 'distribute'].map(a => <button key={a} onClick={() => onAction(`align-${a}`)}>{a === 'distribute' ? 'Distribute' : `Align ${a}`}</button>)}<button onClick={() => onAction('group')}>Group</button><button onClick={() => onAction('ungroup')}>Ungroup</button></>}<button onClick={() => onAction('delete')}><Trash2 size={14} />Delete selected</button></div></div>;
  return <div className="cad-inspector-content"><div className="cad-eyebrow">{type?.toUpperCase()}</div><div className="cad-selection-title"><h3>{entity.name || entity.type?.replaceAll('_', ' ') || type}</h3><button aria-label={locked ? 'Unlock selection' : 'Lock selection'} aria-pressed={locked} onClick={() => onUpdate('locked', !locked)}>{locked ? <Lock size={16} /> : <Unlock size={16} />}</button></div>
    {locked && <p>This element is locked. Unlock it to edit.</p>}
    {ai}
    {type === 'room' && <>
      <Field label="Room name" value={entity.name} numeric={false} disabled={locked} onCommit={v => change('name', v)} />
      <Choice label="Room type" value={entity.type} options={[...new Set([entity.type, ...Object.keys(MIN_ROOM_DIMENSIONS)])]} disabled={locked} onChange={v => change('type', v)} />
      <Choice label="Resize anchor" value={anchor} options={[{
        value: 'sw',
        label: 'South-west'
      }, {
        value: 'nw',
        label: 'North-west'
      }, {
        value: 'ne',
        label: 'North-east'
      }, {
        value: 'se',
        label: 'South-east'
      }]} onChange={setAnchor} />
      <div className="cad-field-grid">{field('Width', 'dimensions.width', entity.dimensions.width, 1, 100)}{field('Depth', 'dimensions.depth', entity.dimensions.depth, 1, 100)}{field('Height', 'dimensions.height', entity.dimensions.height, 2, 5)}{field('Wall thickness', 'wall_thickness', entity.wall_thickness || .2, .1, .5)}</div>
      <div className="cad-stat"><span>Area</span><strong>{(entity.dimensions.width * entity.dimensions.depth * (unit === 'ft' ? 10.7639 : 1)).toFixed(2)} {unit}²</strong></div>
      <div className="cad-action-grid"><button disabled={locked} onClick={() => onAction('split-x')}>Split left / right</button><button disabled={locked} onClick={() => onAction('split-y')}>Split front / back</button></div>
      <p>Use the wall tool to draw a partition at a chosen position. Shift-select a neighboring room to merge.</p>
    </>}
    {(type === 'door' || type === 'window') && <>
      <Choice label="Opening type" value={entity.type || (type === 'door' ? 'single_swing' : 'double_casement')} options={type === 'door' ? [...new Set([entity.type || 'single_swing', 'single_swing', 'double', 'sliding', 'main_entrance'])] : [...new Set([entity.type || 'double_casement', 'double_casement', 'fixed', 'sliding'])]} disabled={locked} onChange={v => change('type', v)} />
      <div className="cad-field-grid">{field('Width', 'width', entity.width, .3, 6)}{field('Height', 'height', entity.height, .2, 4)}{field('Wall offset', 'wall_offset', entity.wall_offset ?? entity.offset ?? 0, 0, 100)}{type === 'window' && field('Sill height', 'sill_height', entity.sill_height ?? .9, 0, 4)}</div>
      <Choice label="Wall side" value={entity.wall_side || 'south'} options={['south', 'north', 'west', 'east']} disabled={locked} onChange={v => change('wall_side', v)} />
      {type === 'door' ? <>
        <Choice label="Width preset" value="" options={[{
          value: '',
          label: 'Choose a preset'
        }, {
          value: '.95',
          label: 'Entrance · 950 mm'
        }, {
          value: '.85',
          label: 'Interior · 850 mm'
        }, {
          value: '.75',
          label: 'Bathroom · 750 mm'
        }]} disabled={locked} onChange={v => v && change('width', Number(v))} />
        <div className="cad-action-grid"><button disabled={locked} onClick={() => change('swing_direction', entity.swing_direction === 'outward' ? 'inward' : 'outward')}>Swing: {entity.swing_direction || 'inward'}</button><button disabled={locked} onClick={() => change('hinge_side', entity.hinge_side === 'right' ? 'left' : 'right')}>Hinge: {entity.hinge_side || 'left'}</button></div>
        <p>{floor.rooms.find(r => r.id === entity.room_id)?.name || entity.room_id} → {floor.rooms.find(r => r.id === entity.connected_room_id)?.name || entity.connected_room_id || 'Exterior'}</p>
      </> : <><Field label="Array count" value={arrayCount} min={2} max={12} onCommit={v => setArrayCount(Math.round(v))} /><button disabled={locked} onClick={() => onAction('array', arrayCount)}>Create equally spaced windows</button></>}
    </>}
    {type === 'furniture' && <>
      <p>{entity.category?.replaceAll('_', ' ')} · {entity.asset_id || entity.asset}</p>
      <div className="cad-field-grid">{field('Width', 'dimensions.width', entity.dimensions.width, .05, 20)}{field('Depth', 'dimensions.depth', entity.dimensions.depth, .05, 20)}{field('Height', 'dimensions.height', entity.dimensions.height, .05, 5)}{field('Rotation', 'rotation', entity.rotation || 0, -3600, 3600, false)}</div>
      <div className="cad-action-grid"><button disabled={locked} onClick={() => onAction('rotate45')}><RotateCw size={14} />45°</button><button disabled={locked} onClick={() => onAction('rotate90')}><RotateCw size={14} />90°</button><button disabled={locked} onClick={() => onAction('mirror-x')}>Mirror X</button><button disabled={locked} onClick={() => onAction('mirror-y')}>Mirror Y</button><button disabled={locked} onClick={() => onAction('center')}>Center in room</button><button disabled={locked} onClick={() => onAction('snap-wall')}>Snap to wall</button><button disabled={locked} onClick={() => onAction('duplicate')}><Copy size={14} />Duplicate</button></div>
    </>}
    {type === 'wall' && <>
      {field('Length', 'length', Math.hypot(entity.end.x - entity.start.x, entity.end.y - entity.start.y), .2, 100)}{field('Thickness', 'thickness', entity.thickness || .2, .1, .5)}
      <Choice label="Wall type" value={entity.type} options={['interior', 'exterior']} disabled={locked} onChange={v => change('type', v)} /><label className="cad-check"><input type="checkbox" checked={Boolean(entity.load_bearing)} disabled={locked} onChange={e => change('load_bearing', e.target.checked)} />Load bearing</label><p>Move a wall in the plan to adjust its connected rooms. Remove partitions by merging rooms.</p>
    </>}
    {type === 'stair' && <>
      <Choice label="Stair type" value={entity.type || 'u_shaped'} options={['straight', 'l_shaped', 'u_shaped']} disabled={locked} onChange={v => change('type', v)} />
      <div className="cad-field-grid">{field('Width', 'dimensions.width', entity.dimensions.width, .9, 10)}{field('Depth', 'dimensions.depth', entity.dimensions.depth, 2, 15)}</div><p>{entity.risers || entity.steps || 18} risers · {formatDim((floor.floor_height || 3) / (entity.risers || entity.steps || 18), unit)} rise</p><p>Upper-floor opening follows the stair automatically.</p>
    </>}
    {type !== 'wall' && <button className="cad-danger" disabled={locked} onClick={() => onAction('delete')}><Trash2 size={14} />Delete {type}</button>}
  </div>;
}
