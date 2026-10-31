import React from 'react';
import { roomBox } from '../../utils/cadGeometry.js';
export default function TransformGizmo({
  entity,
  type,
  mapX,
  mapY,
  scale,
  onStart,
  handleSize = 9
}) {
  if (!entity || !['room', 'furniture', 'stair'].includes(type)) return null;
  const b = roomBox(entity),
    centered = type === 'furniture';
  const x = mapX(centered ? b.x - b.width / 2 : b.x),
    y = mapY(centered ? b.y + b.depth / 2 : b.top),
    w = b.width * scale,
    h = b.depth * scale;
  const cx = x + w / 2,
    cy = y + h / 2,
    rotation = centered ? entity.rotation || 0 : 0;
  return <g className="cad-gizmo" transform={`rotate(${rotation} ${cx} ${cy})`}>
    <rect x={x} y={y} width={w} height={h} fill="none" stroke="#60a5fa" strokeWidth="1.5" vectorEffect="non-scaling-stroke" pointerEvents="none" />
    {!entity.locked && <>
      {['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'].map((handle, index) => {
        const coords = [[0, 0], [.5, 0], [1, 0], [1, .5], [1, 1], [.5, 1], [0, 1], [0, .5]][index];
        return <rect key={handle} data-handle={handle} aria-label={`Resize ${handle}`} x={x + w * coords[0] - handleSize / 2} y={y + h * coords[1] - handleSize / 2} width={handleSize} height={handleSize} rx={handleSize / 5} fill="#dbeafe" stroke="#2563eb" strokeWidth="1" onPointerDown={e => onStart(e, handle)} style={{
          cursor: `${handle}-resize`
        }} />;
      })}
      {centered && <><line x1={cx} y1={y} x2={cx} y2={y - handleSize * 3} stroke="#60a5fa" pointerEvents="none" /><circle data-handle="rotate" cx={cx} cy={y - handleSize * 3} r={handleSize * .65} fill="#60a5fa" stroke="#dbeafe" onPointerDown={e => onStart(e, 'rotate')} style={{
          cursor: 'crosshair'
        }} /></>}
    </>}
  </g>;
}
