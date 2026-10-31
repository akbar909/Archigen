const collections = {room:'rooms',furniture:'furniture',door:'doors',window:'windows',wall:'walls',stair:'stairs'};
export const layoutConflictSummary=count=>`Review ${count} layout ${count===1?'conflict':'conflicts'} in Design checks.`;
export function layoutDiagnostics(design, report) {
  const messages = [...new Set(report?.critical_errors || report?.errors || [])];
  return messages.map(raw => {
    let found = null;
    const identifier=raw.match(/(?:Door|Opening|Furniture|Room|Stair|Floor|Slab opening)\s+'([^']+)'/i)?.[1] || raw.match(/'([^']+)'/)?.[1];
    for (const [floorIndex,floor] of (design?.floors || []).entries()) {
      for (const [type,key] of Object.entries(collections)) {
        const item = (floor[key] || []).find(e => identifier ? e.id===identifier : raw.includes(`'${e.id}'`));
        if (item && !found) found = {floorIndex,entity:{type,id:item.id},item,floor};
      }
    }
    const destination=found?.item.connected_room_id || found?.item.connected_room_ids?.find(id=>id!==(found.item.room_id||found.item.roomId));
    const name = found?.item.name || (found?.entity.type === 'door' ? `Door to ${found.floor.rooms.find(r => r.id === destination)?.name || 'room'}` : found?.entity.type || 'Layout');
    let message = raw;
    if (/intends to connect|no canonical host wall/.test(raw)) message = `${name}: place it on a shared wall between its rooms.`;
    else if (/no stair to the next storey/.test(raw)) message = 'Add a stair connecting this floor to the floor above.';
    else if (/slab opening|not aligned/.test(raw)) message = 'Align the stair with its upper-floor opening.';
    else if (/blocks the stair/.test(raw)) message = 'Move furniture out of the stair area.';
    else if (/require more wall length/.test(raw)) message = 'Openings need more room on this wall. Reduce their widths or move one.';
    if (message === raw) for (const floor of design?.floors || []) for (const key of Object.values(collections)) for (const item of floor[key] || []) message = message.replaceAll(`'${item.id}'`, item.name || key.slice(0,-1));
    return {code:'server-conflict',severity:'error',floorIndex:found?.floorIndex || 0,entity:found?.entity || {type:'floor',id:design?.floors?.[0]?.id},message:message.length>200?message.slice(0,197)+'…':message,details:raw};
  });
}
