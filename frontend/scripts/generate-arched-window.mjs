// Rebuild the reviewed replacement asset: node scripts/generate-arched-window.mjs
import fs from 'node:fs'
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js'
import { archedWindowScene } from '../src/utils/openingGeometry.js'

globalThis.FileReader = class {
  readAsArrayBuffer(blob) {
    blob.arrayBuffer().then((data) => { this.result = data; this.onloadend?.() })
  }
  readAsDataURL(blob) {
    blob.arrayBuffer().then((data) => {
      this.result = `data:${blob.type};base64,${Buffer.from(data).toString('base64')}`
      this.onloadend?.()
    })
  }
}
const data = Buffer.from(await new GLTFExporter().parseAsync(archedWindowScene(), { binary: true }))
for (const path of ['../public/models/', '../../blender/assets/architecture/windows/arched/']) {
  const folder = new URL(path, import.meta.url)
  fs.mkdirSync(folder, { recursive: true })
  fs.writeFileSync(new URL('arched_window_01.glb', folder), data)
}
