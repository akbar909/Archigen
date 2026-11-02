import React from 'react';
import { ArrowUp, Plus } from 'lucide-react';
import { stairPlacementDimensions } from '../../utils/verticalCirculation.js';
export const STAIR_PRESETS = {u_shaped:{label:'U-shaped',width:2.2,depth:3.8},straight:{label:'Straight',width:1.1,depth:5.9},l_shaped:{label:'L-shaped',width:3.8,depth:3.8}};
export default function StairPlacementPanel({floor, upper, type, onType, onAddFloor, busy}) {
  const preset=stairPlacementDimensions(type, floor.floor_height || 3);
  return <div className="cad-inspector-content cad-stair-setup">
    <div className="cad-eyebrow">CONNECT FLOORS</div><h3>Place a staircase</h3>
    <p>Place stairs on the lower floor. The opening on the floor above follows automatically.</p>
    <label className="cad-field"><span>Stair shape</span><select aria-label="Stair shape" value={type} onChange={e=>onType(e.target.value)}>{Object.entries(STAIR_PRESETS).map(([key,value])=><option key={key} value={key}>{value.label}</option>)}</select></label>
    <div className="cad-stair-route"><span>{floor.name || `Floor ${floor.level}`}</span><ArrowUp size={16}/><strong>{upper?.name || (upper ? `Floor ${upper.level}` : 'Upper floor needed')}</strong></div>
    {upper ? <><p className="cad-placement-instruction">Click or tap a clear area on the plan to place it.</p><p>Space needed: {preset.width} × {preset.depth} m. Keep both floors clear of furniture and crossing walls.</p></> : <><p>Add an upper floor, then place the stair here.</p><button className="cad-primary" disabled={busy} onClick={onAddFloor}><Plus size={15}/>Add upper floor</button></>}
  </div>;
}
