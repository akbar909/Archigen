import React from 'react';
export default function SnapGuideLayer({
  guides,
  mapX,
  mapY,
  width,
  depth
}) {
  return <g pointerEvents="none">{guides.map((g, i) => <line key={i} x1={mapX(g.axis === 'x' ? g.value : 0)} x2={mapX(g.axis === 'x' ? g.value : width)} y1={mapY(g.axis === 'y' ? g.value : 0)} y2={mapY(g.axis === 'y' ? g.value : depth)} stroke={g.axis === 'x' ? '#22d3ee' : '#e879f9'} strokeDasharray="5 4" strokeWidth="1" vectorEffect="non-scaling-stroke" />)}</g>;
}
