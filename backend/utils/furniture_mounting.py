"""Reviewed mounting defaults for wall fixtures in older saved layouts."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def _fixtures():
    root=Path(__file__).resolve().parents[2]/'blender'/'metadata'
    result={}
    for path in root.glob('*.json'):
        try:
            record=json.loads(path.read_text(encoding='utf-8'))
        except (ValueError,OSError):
            continue
        if record.get('category')=='shower' and record.get('mounting',{}).get('default_height'):
            result[record['id']]=record
    return result


def mount_wall_fixture(item,room):
    record=_fixtures().get(item.get('asset_id') or item.get('model_id') or item.get('asset'))
    if not record:
        return item
    result=dict(item)
    mounting=record['mounting']
    p=room.get('position',{});d=room.get('dimensions',{})
    pos=dict(item.get('position',{}))
    x,y=float(p.get('x',0)),float(p.get('y',0))
    width,depth=float(d.get('width',3)),float(d.get('depth',3))
    aliases={'north':'front','south':'back','west':'left','east':'right'}
    side=item.get('wall_side') or aliases.get(item.get('anchor_wall')) or min([
        (abs(pos.get('x',x)-x),'left'),(abs(pos.get('x',x)-x-width),'right'),
        (abs(pos.get('y',y)-y),'back'),(abs(pos.get('y',y)-y-depth),'front')])[1]
    dimensions=dict(item.get('dimensions',{})) if item.get('wall_mounted') else {key:record[key] for key in ('width','depth','height')}
    height=min(float(item.get('mount_height',mounting['default_height'])),max(0,float(d.get('height',3))-dimensions['height']-.1))
    normals={'front':{'x':0,'y':0,'z':1},'back':{'x':0,'y':0,'z':-1},'left':{'x':1,'y':0,'z':0},'right':{'x':-1,'y':0,'z':0}}
    offset=dimensions['depth']/2+.12
    if side=='left':pos['x']=x+offset
    if side=='right':pos['x']=x+width-offset
    if side=='back':pos['y']=y+offset
    if side=='front':pos['y']=y+depth-offset
    result.update(wall_mounted=True,wall_side=side,wall_normal=normals[side],mounting=mounting,
                  mount_height=max(0,height),dimensions=dimensions,position=pos,
                  anchor_wall={'front':'north','back':'south','left':'west','right':'east'}[side],
                  rotation={'front':0,'back':180,'left':90,'right':270}[side],
                  rotation_y={'front':0,'back':180,'left':90,'right':270}[side],
                  wall_orientation_version=mounting['orientation_version'],placement_hint='wall_exact')
    return result
