// Read-only asset inspection; writes a generated dimensions/inventory report.
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { Matrix4, Quaternion, Vector3, Box3 } from '../../frontend/node_modules/three/build/three.module.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
  e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)])
const files = walk(path.join(root, 'assets')).filter((f) => !path.basename(f).startsWith('.'))
const models = []
for (const file of files.filter((f) => f.toLowerCase().endsWith('.glb'))) {
  const bytes = fs.readFileSync(file)
  try {
    const doc = JSON.parse(bytes.subarray(20, 20 + bytes.readUInt32LE(12)).toString('utf8').trim())
    const bounds = new Box3()
    let meshes = 0
    const visit = (id, parent) => {
      const n = doc.nodes[id]
      const local = n.matrix ? new Matrix4().fromArray(n.matrix) : new Matrix4().compose(
        new Vector3(...(n.translation || [0, 0, 0])),
        new Quaternion(...(n.rotation || [0, 0, 0, 1])), new Vector3(...(n.scale || [1, 1, 1])))
      const world = parent.clone().multiply(local)
      if (n.mesh !== undefined) {
        meshes++
        for (const primitive of doc.meshes[n.mesh].primitives) {
          const a = doc.accessors[primitive.attributes.POSITION]
          if (a.min && a.max) bounds.union(new Box3(new Vector3(...a.min), new Vector3(...a.max)).applyMatrix4(world))
        }
      }
      for (const child of n.children || []) visit(child, world)
    }
    for (const id of doc.scenes[doc.scene || 0].nodes) visit(id, new Matrix4())
    const size = bounds.getSize(new Vector3())
    models.push({ path: path.relative(root, file).replaceAll('\\', '/'),
      sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
      dimensions: { width: size.x, height: size.y, depth: size.z }, meshes,
      skins: (doc.skins || []).length, animations: (doc.animations || []).length })
  } catch (error) { models.push({ path: path.relative(root, file), error: error.message }) }
}
const counts = {}
for (const file of files) { const ext = path.extname(file).toLowerCase(); counts[ext] = (counts[ext] || 0) + 1 }
const hashes = new Map()
for (const model of models) { const list = hashes.get(model.sha256) || []; list.push(model.path); hashes.set(model.sha256, list) }
const duplicates = [...hashes.values()].filter((v) => v.length > 1)
const report = { counts, models, duplicates }
fs.writeFileSync(path.join(root, 'asset-audit.json'), JSON.stringify(report, null, 2))
console.log(JSON.stringify({ counts, models: models.length, duplicates,
  inspected: models.filter((m) => /nightstand|wall_art|curtain|ceiling|dining_table/.test(m.path)) }, null, 2))
