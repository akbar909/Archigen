import React from 'react'

export default function SitePlanLayer({
  design,
  isGroundFloor,
  mapX,
  mapY,
  orientation,
  plotW,
  plotD = Number(design?.site?.plot?.depth || 0),
  scale,
}) {
  if (!isGroundFloor) return null
  const roadSide = design?.site?.road?.side || orientation || 'south'
  const verticalRoad = roadSide === 'east' || roadSide === 'west'
  const roadX = roadSide === 'east' ? mapX(plotW) : roadSide === 'west' ? mapX(0) - 22 : mapX(0)
  const roadY = roadSide === 'north' ? mapY(plotD) - 22 : verticalRoad ? mapY(plotD) : mapY(0)
  const roadWidth = verticalRoad ? 22 : plotW * scale
  const roadHeight = verticalRoad ? plotD * scale : 22
  const roadLabelX = roadX + roadWidth / 2
  const roadLabelY = roadY + roadHeight / 2
  return (
    <>
          {/* A continuous pedestrian route from the plot gate to the real
              wall-hosted main entrance door. */}
          {isGroundFloor && design?.exterior?.entrance_path?.enabled !== false && design?.exterior?.entrance_path && (() => {
            const path = design.exterior.entrance_path
            const start = path.start || {}
            const end = path.end || {}
            const pathWidth = Math.max(0.8, Number(path.width || 1.2)) * scale
            return (
              <g data-testid="main-entrance-path">
                <line
                  x1={mapX(Number(start.x || 0))}
                  y1={mapY(Number(start.y || 0))}
                  x2={mapX(Number(end.x || 0))}
                  y2={mapY(Number(end.y || 0))}
                  stroke="rgba(148, 163, 184, 0.28)"
                  strokeWidth={pathWidth}
                  strokeLinecap="butt"
                />
                <line
                  x1={mapX(Number(start.x || 0))}
                  y1={mapY(Number(start.y || 0))}
                  x2={mapX(Number(end.x || 0))}
                  y2={mapY(Number(end.y || 0))}
                  stroke="rgba(226, 232, 240, 0.55)"
                  strokeWidth="1.5"
                  strokeDasharray="6,5"
                />
              </g>
            )
          })()}

          {/* Main vehicle entrance gate on the front plot boundary */}
          {isGroundFloor && design?.exterior?.gate?.enabled !== false && design?.exterior?.gate && (() => {
            const gate = design.exterior.gate
            const gateX = Number(gate.position?.x ?? design.exterior.driveway?.position?.x ?? 0)
            const gateY = Number(gate.position?.y ?? 0)
            const gateWidth = Number(gate.width ?? design.exterior.driveway?.width ?? 3.6)
            const vertical = gate.axis === 'y' || ['east', 'west'].includes(gate.side || roadSide)
            const endX = gateX + (vertical ? 0 : gateWidth)
            const endY = gateY + (vertical ? gateWidth : 0)
            const centerX = mapX((gateX + endX) / 2)
            const canvasY = mapY((gateY + endY) / 2)
            return (
              <g data-testid="main-entrance-gate">
                <line
                  x1={mapX(gateX)}
                  y1={mapY(gateY)}
                  x2={mapX(endX)}
                  y2={mapY(endY)}
                  stroke="#22d3ee"
                  strokeWidth="7"
                  strokeLinecap="square"
                />
                <line
                  x1={centerX - (vertical ? 5 : 0)}
                  y1={canvasY - (vertical ? 0 : 5)}
                  x2={centerX + (vertical ? 5 : 0)}
                  y2={canvasY + (vertical ? 0 : 5)}
                  stroke="#082f49"
                  strokeWidth="2"
                />
                <circle cx={mapX(gateX)} cy={mapY(gateY)} r="4" fill="#67e8f9" />
                <circle cx={mapX(endX)} cy={mapY(endY)} r="4" fill="#67e8f9" />
                <text
                  x={centerX}
                  y={canvasY - 9}
                  fill="#67e8f9"
                  fontSize="8"
                  fontWeight="800"
                  textAnchor="middle"
                  letterSpacing="1"
                  transform={vertical ? `rotate(-90 ${centerX} ${canvasY})` : undefined}
                >
                  MAIN GATE
                </text>
              </g>
            )
          })()}

          {/* Driveway Connecting Road to Garage / Entrance (if present) */}
          {isGroundFloor && design?.exterior?.driveway?.enabled !== false && design?.exterior?.driveway && (
            <g>
              <rect
                x={mapX(design.exterior.driveway.position?.x || 0)}
                y={mapY((design.exterior.driveway.position?.y || 0) + (design.exterior.driveway.depth || 3.0))}
                width={(design.exterior.driveway.width || 3.8) * scale}
                height={(design.exterior.driveway.depth || 3.0) * scale}
                fill="rgba(51, 65, 85, 0.35)"
                stroke="rgba(148, 163, 184, 0.4)"
                strokeWidth="1.5"
                strokeDasharray="6,4"
              />
              <text
                x={mapX((design.exterior.driveway.position?.x || 0) + (design.exterior.driveway.width || 3.8) / 2)}
                y={mapY((design.exterior.driveway.position?.y || 0) + (design.exterior.driveway.depth || 3.0) / 2) + 4}
                fill="#94a3b8"
                fontSize="9"
                fontWeight="700"
                textAnchor="middle"
                letterSpacing="1.5"
              >
                DRIVEWAY
              </text>
            </g>
          )}

          {/* Road Frontage Indicator Banner */}
          {isGroundFloor && (
            <g>
              <rect
                x={roadX}
                y={roadY}
                width={roadWidth}
                height={roadHeight}
                fill="rgba(51, 65, 85, 0.45)"
                stroke="rgba(148, 163, 184, 0.35)"
              />
              <text
                x={roadLabelX}
                y={roadLabelY + 4}
                fill="#94a3b8"
                fontSize="10"
                fontWeight="bold"
                textAnchor="middle"
                letterSpacing="2"
                transform={verticalRoad ? `rotate(-90 ${roadLabelX} ${roadLabelY})` : undefined}
              >
                ROAD ACCESS ({roadSide.toUpperCase()})
              </text>
            </g>
          )}
    </>
  )
}
