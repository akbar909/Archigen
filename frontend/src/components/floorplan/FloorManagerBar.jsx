import React from 'react';
import { Copy, ChevronUp, ChevronDown, Plus, Trash2 } from 'lucide-react';
export default function FloorManagerBar({
  floors,
  active,
  onSelect,
  onAction,
  ghost,
  onGhost
}) {
  return <div className="cad-floorbar"><select aria-label="Active floor" value={active} onChange={e => onSelect(Number(e.target.value))}>{floors.map((f, i) => <option key={f.id} value={i}>{f.name || (i === 0 ? 'Ground floor' : `Floor ${i}`)}</option>)}</select><button title="Add floor" aria-label="Add floor" disabled={floors.length >= 4} onClick={() => onAction('add')}><Plus size={16} /></button><button title="Duplicate floor layout" aria-label="Duplicate floor layout" disabled={floors.length >= 4} onClick={() => onAction('duplicate')}><Copy size={15} /></button><button title="Move floor down" aria-label="Move floor down" disabled={!active} onClick={() => onAction('down')}><ChevronDown size={16} /></button><button title="Move floor up" aria-label="Move floor up" disabled={active >= floors.length - 1} onClick={() => onAction('up')}><ChevronUp size={16} /></button><button title="Delete floor" aria-label="Delete floor" disabled={floors.length <= 1} onClick={() => onAction('delete')}><Trash2 size={15} /></button><button className="cad-ghost" disabled={!active} aria-pressed={ghost} onClick={onGhost}>Floor below</button></div>;
}
