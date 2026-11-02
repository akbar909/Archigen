import React from 'react';
import { stairPlanGeometry } from '../../utils/stairGeometry.js';

export default function CadStairItem({ stair, scale, mapX, mapY, selected }) {
  const { lines, flights, arrow } = stairPlanGeometry(stair);
  const x = Number(stair.position?.x || 0), y = Number(stair.position?.y || 0), w = Number(stair.dimensions?.width || 0), d = Number(stair.dimensions?.depth || 0);
  const point = p => ({ x: mapX(x + p.x), y: mapY(y + p.y) });
  const path = arrow.map((p, i) => { const q = point(p); return `${i ? 'L' : 'M'} ${q.x} ${q.y}`; }).join(' ');
  const end = arrow.at(-1), previous = arrow.at(-2);
  const angle = end && previous ? Math.atan2(end.y - previous.y, end.x - previous.x) : 0;
  const head = end ? [angle + 2.6, angle - 2.6].map(a => point({ x: end.x + .16 * Math.cos(a), y: end.y + .16 * Math.sin(a) })) : [];
  const tip = end ? point(end) : null;
  return <>
    <rect x={mapX(x)} y={mapY(y + d)} width={w * scale} height={d * scale} fill="#34465c" stroke={selected ? '#60a5fa' : '#94a3b8'} />
    {flights.map((f, index) => <rect key={`flight-${index}`} x={mapX(x + f.x)} y={mapY(y + f.y + f.depth)} width={f.width * scale} height={f.depth * scale} fill="#26354a" stroke="#64748b" strokeWidth="1" pointerEvents="none" />)}
    {lines.map((line, index) => <line key={index} x1={mapX(x + line.x1)} y1={mapY(y + line.y1)} x2={mapX(x + line.x2)} y2={mapY(y + line.y2)} stroke="#64748b" strokeWidth="1" pointerEvents="none" />)}
    <path d={path} fill="none" stroke="#e2e8f0" strokeWidth="1.5" pointerEvents="none" />
    {tip && <path d={`M ${head[0].x} ${head[0].y} L ${tip.x} ${tip.y} L ${head[1].x} ${head[1].y}`} fill="none" stroke="#e2e8f0" strokeWidth="1.5" pointerEvents="none" />}
    <text x={mapX(x + .1)} y={mapY(y + .12)} fill="#e2e8f0" fontSize="9" pointerEvents="none">UP</text>
  </>;
}
