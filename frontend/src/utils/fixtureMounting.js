import { alignWallFurniture, clampMountHeight } from './designEditing.js'
import { interiorWallMountNormal } from './wallMount.js'

export function mountWallFixture(item, room, asset, placement = {}) {
  const mounting = asset?.mounting || item.mounting
  if (!room || mounting?.surface !== 'wall' || !mounting.default_height ||
    !/shower/.test([item.category,item.asset_id,item.model_id,asset?.category].join(' '))) return item
  const p = room.position || {}, d = room.dimensions || {}, pos = item.position || {}
  const oldFloorFixture = !item.wall_mounted
  const aliases = { north:'front',south:'back',west:'left',east:'right' }
  const side = placement.wallSide || item.wall_side || aliases[item.anchor_wall] || [
    [Math.abs(pos.x-(Number(p.x)||0)),'left'],
    [Math.abs(pos.x-(Number(p.x)||0)-(Number(d.width)||3)),'right'],
    [Math.abs(pos.y-(Number(p.y)||0)),'back'],
    [Math.abs(pos.y-(Number(p.y)||0)-(Number(d.depth)||3)),'front'],
  ].sort((a,b)=>a[0]-b[0])[0][1]
  const changingWall = placement.wallSide && placement.wallSide !== item.wall_side
  const next = { ...item, mounting, wall_mounted:true, wall_side:side,
    anchor_wall:{front:'north',back:'south',left:'west',right:'east'}[side],
    ...(changingWall ? {wall_anchor:null,wall_normal:interiorWallMountNormal(side),wall_id:null} : {}),
    dimensions:oldFloorFixture && asset?.dimensions ? {...asset.dimensions} : item.dimensions,
    wall_orientation_version:oldFloorFixture ? mounting.orientation_version : item.wall_orientation_version,
    mount_height:item.mount_height ?? mounting.default_height,
    placement_hint:'wall_exact' }
  if (placement.hitPoint) next.position={...pos,x:placement.hitPoint.x,y:-placement.hitPoint.z}
  if (placement.surfaceNormal) next.wall_normal=interiorWallMountNormal(side,placement.surfaceNormal)
  if (placement.hitPoint && placement.wallSide) next.wall_anchor={x:placement.hitPoint.x,y:-placement.hitPoint.z}
  if (placement.wallId) next.wall_id=placement.wallId
  next.mount_height = clampMountHeight(next, room, next.mount_height)
  return alignWallFurniture(next,room,asset)
}
