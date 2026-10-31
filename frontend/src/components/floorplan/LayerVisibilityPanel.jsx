import React from 'react';
import { Eye, EyeOff, Lock, Unlock } from 'lucide-react';
export default function LayerVisibilityPanel({
  layers,
  onChange
}) {
  return <div className="cad-layers">{Object.entries(layers).map(([key, layer]) => <div key={key}><span>{key}</span><button aria-label={`${layer.visible ? 'Hide' : 'Show'} ${key}`} aria-pressed={layer.visible} onClick={() => onChange(key, {
        visible: !layer.visible
      })}>{layer.visible ? <Eye size={16} /> : <EyeOff size={16} />}</button><button aria-label={`${layer.locked ? 'Unlock' : 'Lock'} ${key}`} aria-pressed={layer.locked} onClick={() => onChange(key, {
        locked: !layer.locked
      })}>{layer.locked ? <Lock size={16} /> : <Unlock size={16} />}</button></div>)}</div>;
}
