import React from 'react';
import { distance } from '../../utils/cadGeometry.js';
import { formatDim } from './CadSymbols.jsx';
export default function MeasurementTool({
  points,
  mapX,
  mapY,
  unit
}) {
  if (points.length < 2) return null;
  const [a, b] = points;
  return <g pointerEvents="none" stroke="#fbbf24"><line x1={mapX(a.x)} y1={mapY(a.y)} x2={mapX(b.x)} y2={mapY(b.y)} strokeWidth="2" vectorEffect="non-scaling-stroke" />{points.map((p, i) => <circle key={i} cx={mapX(p.x)} cy={mapY(p.y)} r="4" fill="#fbbf24" />)}<text x={mapX((a.x + b.x) / 2)} y={mapY((a.y + b.y) / 2) - 10} textAnchor="middle" stroke="#0a0e17" strokeWidth="4" paintOrder="stroke" fill="#fbbf24" fontSize="14">{formatDim(distance(a, b), unit)}</text></g>;
}
