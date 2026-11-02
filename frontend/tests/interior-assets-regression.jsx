import React from 'react'
import { createRoot } from 'react-dom/client'
import * as THREE from 'three'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import Viewer3D from '../src/components/viewer3d'
import { useProjectStore } from '../src/store'
import { apiClient, setUnauthorizedHandler } from '../src/services/apiClient'
import '../src/index.css'

apiClient.defaults.baseURL='/api';setUnauthorizedHandler(()=>{})
const room={id:'bedroom',name:'Bedroom',type:'bedroom',position:{x:0,y:0,z:0},dimensions:{width:4,depth:4,height:3}}
const bath={id:'bathroom',name:'Bathroom',type:'bathroom',position:{x:4,y:0,z:0},dimensions:{width:3,depth:4,height:3}}
const bed={id:'compact_bed',name:'Compact bed',asset_id:'single_bed_01',category:'bed',room_id:room.id,
  position:{x:3.3,y:2,z:0},dimensions:{width:.9,depth:1.8,height:.8},rotation:0}
const shower={id:'shower',name:'Shower',asset_id:'shower_set_02',category:'shower',room_id:bath.id,
  position:{x:6.4,y:2,z:0},dimensions:{width:1,depth:1,height:2.1},rotation:0,anchor_wall:'east'}
const wardrobe={id:'wardrobe',name:'Wardrobe',asset_id:'wardrobe_modern_01',category:'wardrobe',room_id:room.id,
  position:{x:.6,y:2,z:0},dimensions:{width:1.56,depth:.65,height:2.06},rotation:90}
const scene=new THREE.Scene()
for(const [item,color] of [[bed,'#ccc'],[shower,'#aaa'],[wardrobe,'#b98']]) {
  const root=new THREE.Group();root.name='Furniture_'+item.id
  root.userData={archgen_instance_id:item.id,archgen_id:item.asset_id,archgen_room_id:item.room_id}
  root.position.set(item.position.x,0,-item.position.y);root.rotation.y=item.rotation*Math.PI/180
  const mesh=new THREE.Mesh(new THREE.BoxGeometry(item.dimensions.width,item.dimensions.height,item.dimensions.depth),new THREE.MeshStandardMaterial({color}))
  mesh.position.y=item.dimensions.height/2;root.add(mesh);scene.add(root)
}
const wall=new THREE.Mesh(new THREE.BoxGeometry(.15,3,4),new THREE.MeshStandardMaterial({color:'#eee'}));wall.position.set(0,1.5,-2);wall.name='Wall_fixture';scene.add(wall)
const floor=new THREE.Mesh(new THREE.BoxGeometry(7,.15,4),new THREE.MeshStandardMaterial({color:'#888'}));floor.position.set(3.5,-.075,-2);scene.add(floor)
const buffer=await new GLTFExporter().parseAsync(scene,{binary:true})
const design={rooms:[room,bath],furniture:[bed,shower,wardrobe],floors:[{id:'ground_floor',level:0,rooms:[room,bath],furniture:[bed,shower,wardrobe]}],
  site:{plot:{width:7,depth:4}},layout_approved:true,glb_url:URL.createObjectURL(new Blob([buffer],{type:'model/gltf-binary'}))}
useProjectStore.setState({design,persistedDesign:structuredClone(design),activeProjectId:'fixture',activeVersionId:'fixture_v1',isDirty:false})
window.fixtureDesign=()=>structuredClone(useProjectStore.getState().design)
window.fixtureDirty=()=>useProjectStore.getState().isDirty
window.fixtureCheckpoint=()=>{useProjectStore.setState({persistedDesign:structuredClone(useProjectStore.getState().design),isDirty:false});return true}
window.confirm=()=>true
function App(){const current=useProjectStore(state=>state.design);return <div style={{width:'100vw',height:'100vh'}}><Viewer3D design={current}/></div>}
createRoot(document.getElementById('root')).render(<App/> )
