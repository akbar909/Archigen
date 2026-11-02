import { useEffect } from 'react'
import { useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { findEditableSurface } from '../src/utils/sceneEditing'
export default function PlacementProbe({ onSelect, onModeChange }) {
  const { camera, scene } = useThree()
  useEffect(() => {
    window.placementCamera = () => camera.position.toArray()
    window.setPlacementCamera = (position) => camera.position.fromArray(position)
    window.setTestViewMode = onModeChange
  }, [camera, onModeChange])
  useEffect(() => {
    window.fixtureSelect = (id) => {
      let object=null
      scene.traverse(node=>{if((node.userData?.entityId===id || node.userData?.archgen_instance_id===id)&&node.visible)object=node})
      if(!object || !onSelect)return false
      const item=window.fixtureDesign?.().furniture?.find(item=>item.id===id)
      onSelect({type:'furniture',id,roomId:item?.room_id || (id==='shower'?'bathroom':'bedroom'),object,source:'blender'})
      return true
    }
    window.fixtureBounds = (id) => {
      let object=null
      scene.traverse(node=>{if(node.userData?.entityId===id && node.visible)object=node})
      if(!object)return null
      const box=new THREE.Box3().setFromObject(object,true)
      return {min:box.min.toArray(),max:box.max.toArray()}
    }
    window.fixtureWindow = () => {
      onSelect({type:'window',id:'window',roomId:'bedroom',wallSide:'left',hitPoint:{x:.075,y:1.8,z:-2},
        surfaceNormal:{x:-1,y:0,z:0},opening:{id:'window',type:'window',position:[0,1.4,-2],width:1.4,height:1.2},source:'blender'})
      return true
    }
    window.fixtureBathroomWall = side => {
      onSelect({type:'wall',id:`bathroom_${side}`,wallId:`bathroom_${side}`,roomId:'bathroom',wallSide:side,
        hitPoint:{x:side==='right'?6.925:4.075,y:1.8,z:-2},surfaceNormal:{x:side==='right'?-1:1,y:0,z:0},source:'blender'})
      return true
    }
    window.fixtureWardrobeFront = () => {
      let root=null
      scene.traverse(node=>{if(node.userData?.entityId==='wardrobe'&&node.visible)root=node})
      if(!root)return null
      const handles=[],body=[]
      root.traverse(mesh=>{
        if(!mesh.isMesh)return
        const target=mesh.material?.name?.startsWith('Material.007')?handles:body
        const attr=mesh.geometry.attributes.position
        for(let index=0;index<attr.count;index++)target.push(new THREE.Vector3().fromBufferAttribute(attr,index).applyMatrix4(mesh.matrixWorld).x)
      })
      return {handleMin:Math.min(...handles),bodyMax:Math.max(...body)}
    }
    window.selectExteriorTestSurface = (name) => {
      const object = scene.getObjectByName(name)
      if (!object || !onSelect) return false
      const surface = findEditableSurface(object, scene)
      if (!surface) return false
      const box = new THREE.Box3().setFromObject(object)
      onSelect({ ...surface, source: 'blender', roomId: 'exterior_ground', wallId: surface.type === 'wall' ? surface.id : null,
        hitPoint: surface.type === 'wall' ? { x: -0.075, y: 1, z: -3 } : { x: -5, y: -0.22, z: 4 },
        surfaceNormal: surface.type === 'wall' ? { x: -1, y: 0, z: 0 } : { x: 0, y: 1, z: 0 },
        boundaryBounds: surface.exterior ? { minX: box.min.x, maxX: box.max.x, minY: -box.max.z, maxY: -box.min.z, base: box.min.y, height: box.max.y - box.min.y } : null })
      return true
    }
  }, [scene, onSelect])
  return null
}
