import { createServer } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawn } from 'node:child_process'
import assert from 'node:assert/strict'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const assets = path.resolve(frontend, '../blender/assets')
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'archigen-editor-browser-'))
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
const server = await createServer({ root: frontend, configFile: false, plugins: [react(), {
  name: 'editor-test-assets', enforce: 'pre',
  transform(code, id) {
    if (!id.replaceAll('\\', '/').endsWith('/components/viewer3d/ViewerStage.jsx')) return null
    // Keep the production viewer/controller in the integration test; only skip
    // the external HDRI download and expose the rendered camera for assertions.
    return `import PlacementProbe from '/tests/placement-probe.jsx';\n${code}`
      .replace('<Environment preset={isNightMode ? \'night\' : \'city\'} />', '<ambientLight intensity={0.5} />')
      .replace('<SelectionClickGuard isTransforming={isTransforming} />', '<><SelectionClickGuard isTransforming={isTransforming} /><PlacementProbe /></>')
  },
  configureServer(instance) {
    instance.middlewares.use((request, response, next) => {
      if (request.url.startsWith('/api/assets/catalog')) {
        response.setHeader('Content-Type', 'application/json')
        response.end(JSON.stringify({ assets: [
          { id: 'ceiling_fan_02', name: 'Ceiling fan', kind: 'model', group: 'ceiling_asset', category: 'ceiling_light', s3_key: 'assets/architecture/ceilings/fans/ceiling_fan_02.glb' },
          { id: 'ceiling_lamp_02', name: 'Ceiling lamp', kind: 'model', group: 'ceiling_asset', category: 'ceiling_light', s3_key: 'assets/architecture/ceilings/designs/ceiling_lamp_02.glb' },
          { id: 'toilet_01', name: 'Uploaded Toilet', kind: 'model', group: 'furniture', category: 'toilet', s3_key: 'assets/toilet.glb', model_path: '/asset-test/toilet.glb' },
          { id: 'cabinet_01', name: 'Uploaded Cabinet', kind: 'model', group: 'furniture', category: 'kitchen_cabinet', s3_key: 'assets/cabinet.glb', model_path: '/asset-test/cabinet.glb' },
          { id: 'single_bed_01', name: 'Uploaded Bed', kind: 'model', group: 'furniture', category: 'bed', s3_key: 'assets/furniture/bedroom/beds/single_bed_01.glb',
            model_path: 'http://127.0.0.1:5189/asset-test/furniture/bedroom/beds/single_bed_01.glb', dimensions: { width: 1, depth: 2, height: 1 } },
        ] }))
        return
      }
      if (!request.url.startsWith('/asset-test/')) return next()
      const file = path.resolve(assets, decodeURIComponent(request.url.slice('/asset-test/'.length).split('?')[0]))
      if (!file.startsWith(assets + path.sep) || !fs.existsSync(file)) { response.statusCode = 404; response.end(); return }
      response.setHeader('Content-Type', file.endsWith('.glb') ? 'model/gltf-binary' : 'image/jpeg')
      fs.createReadStream(file).pipe(response)
    })
  },
}], server: { host: '127.0.0.1', port: 5189, strictPort: true } })
let browser
let socket
try {
  await server.listen()
  browser = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', ['--headless=new', '--remote-debugging-port=0',
    `--user-data-dir=${temp}`, '--no-first-run', '--no-default-browser-check', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', 'about:blank'],
  { windowsHide: true, stdio: 'ignore' })
  const portFile = path.join(temp, 'DevToolsActivePort')
  for (let i = 0; i < 150 && !fs.existsSync(portFile); i++) await wait(100)
  const [port, endpoint] = fs.readFileSync(portFile, 'utf8').trim().split(/\r?\n/)
  socket = new WebSocket(`ws://127.0.0.1:${port}${endpoint}`)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let sequence = 0
  const pending = new Map()
  const errors = []
  socket.onmessage = ({ data }) => {
    const result = JSON.parse(data)
    if (result.method === 'Runtime.exceptionThrown') errors.push(result.params.exceptionDetails.exception?.description || result.params.exceptionDetails.text)
    if (result.method === 'Runtime.consoleAPICalled' && result.params.type === 'error') errors.push(result.params.args.map((a) => a.description || a.value).join(' '))
    if (pending.has(result.id)) {
      const { resolve, reject } = pending.get(result.id)
      pending.delete(result.id)
      result.error ? reject(result.error) : resolve(result.result)
    }
  }
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++sequence
    pending.set(id, { resolve, reject })
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }))
  })
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' })
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true })
  const evaluate = async (expression) => (await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }, sessionId)).result.value
  await send('Runtime.enable', {}, sessionId)
  await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 800, deviceScaleFactor: 1, mobile: false }, sessionId)
  await send('Page.navigate', { url: 'http://127.0.0.1:5189/tests/editor-regression.html' }, sessionId)
  let report
  for (let i = 0; i < 180; i++) { report = await evaluate('window.editorResults'); if (report) break; await wait(200) }
  const debug = report ? null : await evaluate('({ url: location.href, body: document.body.innerHTML.slice(0, 1000), resources: performance.getEntriesByType("resource").slice(-10).map(e => e.name) })')
  assert.ok(report && !report.error, JSON.stringify({ report, errors, debug }))
  assert.equal(report.textures.length, 9)
  assert.ok(report.textures.every((entry) => entry.loaded && entry.uv && entry.count === 1))
  assert.ok(report.selectionVisible, JSON.stringify(report))
  assert.deepEqual(report.position, [0, 1.65, 4])
  const actions = await evaluate("Array.from(document.querySelectorAll('.viewer-editor-actions button')).map(b => { const s = getComputedStyle(b), r = b.getBoundingClientRect(); return { color: s.color, font: s.fontSize, height: r.height, top: r.top }; })")
  assert.deepEqual(actions[0], actions[1], 'editor actions share green styling and baseline')
  assert.equal(actions[0].color, 'rgb(110, 231, 183)')
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Up 0.1m')).click()")
  await wait(150)
  assert.equal(await evaluate('window.editorHeight'), 1.1)
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Down 0.1m')).click()")
  await wait(150)
  assert.equal(await evaluate('window.editorHeight'), 1)
  await evaluate("window.editorSelectSurface('floor')")
  await wait(150)
  const floorMenu = await evaluate("document.querySelector('.interior-editor-drawer').textContent")
  assert.ok(floorMenu.includes('Floor textures'))
  assert.ok(!floorMenu.includes('Ceiling fan') && !floorMenu.includes('Room ceiling assets'))
  await evaluate("window.editorSelectSurface('roof')")
  await wait(150)
  assert.ok(!(await evaluate("document.querySelector('.interior-editor-drawer').textContent.includes('Ceiling fan')")))
  assert.ok(await evaluate("document.querySelector('.interior-editor-drawer').textContent.includes('Exterior roof')"))
  await evaluate("window.editorSelectSurface('ceiling')")
  await wait(150)
  assert.ok(await evaluate("document.querySelector('.interior-editor-drawer').textContent.includes('Ceiling fan')"))
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.title === 'Ceiling fan').click()")
  assert.equal(await evaluate('window.editorAddedCeilingAsset'), 'ceiling_fan_02')
  await evaluate("window.editorSelectSurface('library')")
  await wait(150)
  assert.ok(!(await evaluate("document.querySelector('.interior-editor-drawer').textContent.includes('Uploaded Toilet')")))
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'All uploaded assets').click()")
  await wait(100)
  assert.ok(await evaluate("document.querySelector('.interior-editor-drawer').textContent.includes('Uploaded Toilet')"))
  await evaluate("(() => { const s = document.querySelector('select'); s.value = 'bathroom'; s.dispatchEvent(new Event('change', { bubbles: true })); })()")
  await wait(100)
  assert.ok(!(await evaluate("document.querySelector('.interior-editor-drawer').textContent.includes('Uploaded Cabinet')")))
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.title === 'Uploaded Toilet').click()")
  assert.deepEqual(await evaluate('window.editorAddedAsset'), { id: 'toilet_01', roomId: 'bathroom' })
  const libraryScreenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
  fs.writeFileSync(path.join(temp, 'asset-library-desktop.png'), Buffer.from(libraryScreenshot.data, 'base64'))
  await evaluate("window.editorSelectSurface('furniture')")
  await wait(150)
  assert.ok(!(await evaluate("document.querySelector('.interior-editor-drawer').textContent.includes('Accent color')")))
  await evaluate('window.editorSetTintable(true)')
  await wait(100)
  assert.ok(await evaluate("document.querySelector('.interior-editor-drawer').textContent.includes('Accent color')"))
  await evaluate('window.editorSetTintable(false)')
  // A completed click selects, but neither the down event nor a long hold does.
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: 350, y: 300, button: 'left', buttons: 1, clickCount: 1 }, sessionId)
  assert.equal(await evaluate('window.editorSceneSelectionCount || 0'), 0)
  await wait(60)
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: 350, y: 300, button: 'left', buttons: 0, clickCount: 1 }, sessionId)
  assert.equal(await evaluate('window.editorSceneSelectionCount || 0'), 1)
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: 350, y: 300, button: 'left', buttons: 1, clickCount: 1 }, sessionId)
  await wait(500)
  assert.equal(await evaluate('window.editorSceneSelectionCount || 0'), 1)
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: 350, y: 300, button: 'left', buttons: 0, clickCount: 1 }, sessionId)
  assert.equal(await evaluate('window.editorSceneSelectionCount || 0'), 1)
  const cameraBefore = await evaluate('window.editorCameraState()')
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: 350, y: 300, button: 'left', buttons: 1, clickCount: 1 }, sessionId)
  await wait(150)
  assert.deepEqual((await evaluate('window.editorCameraState()')).direction, cameraBefore.direction)
  for (let i = 1; i <= 30; i++) {
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 350 + i * 8, y: 300, button: 'left', buttons: 1 }, sessionId)
  }
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: 590, y: 300, button: 'left', buttons: 0, clickCount: 1 }, sessionId)
  await wait(250)
  const cameraAfter = await evaluate('window.editorCameraState()')
  assert.equal(await evaluate('window.editorSceneSelectionCount || 0'), 1)
  assert.deepEqual(cameraAfter.position, cameraBefore.position)
  const dot = cameraBefore.direction.reduce((sum, value, i) => sum + value * cameraAfter.direction[i], 0)
  const dragAngle = Math.acos(Math.max(-1, Math.min(1, dot)))
  assert.ok(dragAngle > 0.3 && dragAngle < 0.6, `Unexpected drag rotation: ${dragAngle}`)
  await evaluate('window.editorSetTransforming(true)')
  await wait(50)
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: 350, y: 300, button: 'left', buttons: 1, clickCount: 1 }, sessionId)
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 550, y: 300, button: 'left', buttons: 1 }, sessionId)
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: 550, y: 300, button: 'left', buttons: 0, clickCount: 1 }, sessionId)
  assert.deepEqual((await evaluate('window.editorCameraState()')).direction, cameraAfter.direction)
  await evaluate('window.editorSetTransforming(false)')
  const screenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
  const screenshotPath = path.join(temp, 'editor-desktop.png')
  fs.writeFileSync(screenshotPath, Buffer.from(screenshot.data, 'base64'))
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: false }, sessionId)
  await send('Page.navigate', { url: 'http://127.0.0.1:5189/tests/editor-regression.html?mobile=1' }, sessionId)
  let mobile
  for (let i = 0; i < 180; i++) { mobile = await evaluate('window.editorResults'); if (mobile) break; await wait(200) }
  assert.ok(mobile?.selectionVisible && !mobile.error, JSON.stringify(mobile))
  await evaluate("window.editorSelectSurface('library')")
  await wait(200)
  const libraryBounds = await evaluate("(() => { const r = document.querySelector('.interior-editor-drawer').getBoundingClientRect(); return { left: r.left, right: r.right, bottom: r.bottom }; })()")
  assert.ok(libraryBounds.left >= 0 && libraryBounds.right <= 390 && libraryBounds.bottom <= 844)
  const mobileScreenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
  fs.writeFileSync(path.join(temp, 'editor-mobile.png'), Buffer.from(mobileScreenshot.data, 'base64'))
  await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 800, deviceScaleFactor: 1, mobile: false }, sessionId)
  await send('Page.navigate', { url: 'http://127.0.0.1:5189/tests/placement-regression.html' }, sessionId)
  const until = async (expression) => {
    for (let i = 0; i < 150; i++) { if (await evaluate(expression)) return; await wait(200) }
    throw new Error(`Timed out: ${expression}`)
  }
  await until("!!document.querySelector('.viewer-edit-toggle') && !!window.placementCamera")
  await evaluate("document.querySelector('.viewer-edit-toggle').click()")
  await until("!!document.querySelector('.viewer-add-assets')")
  await evaluate("document.querySelector('.viewer-add-assets').click()")
  await until("!!document.querySelector('.interior-editor-drawer select') && !document.querySelector('.placement-room-transition')")
  const selectDestination = async (id) => {
    await evaluate(`(() => { const s = document.querySelector('select'); s.value = '${id}'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`)
    await until(`document.querySelector('select')?.value === '${id}' && !document.querySelector('.placement-room-transition')`)
  }
  await selectDestination('kitchen')
  const kitchenCamera = await evaluate('window.placementCamera()')
  assert.ok(kitchenCamera[0] > 0 && kitchenCamera[0] < 4)
  const beforePlacement = await evaluate('window.placementDesign()')
  await selectDestination('bedroom')
  const bedroomCamera = await evaluate('window.placementCamera()')
  assert.ok(bedroomCamera[0] > 6 && bedroomCamera[0] < 10 && bedroomCamera[2] < 0 && bedroomCamera[2] > -4)
  assert.deepEqual(await evaluate('window.placementDesign()'), beforePlacement, 'room transitions never mutate the house')
  const previewBed = async () => {
    await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.title === 'Uploaded Bed').click()")
    await until("Array.from(document.querySelectorAll('button')).some(b => b.textContent === 'Place here' && !b.disabled)")
  }
  await previewBed()
  assert.deepEqual(await evaluate('window.placementDesign()'), beforePlacement, 'preview is not saved')
  const previewScreenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
  fs.writeFileSync(path.join(temp, 'placement-preview.png'), Buffer.from(previewScreenshot.data, 'base64'))
  await evaluate("Array.from(document.querySelectorAll('.editor-placement-buttons button')).find(b => b.textContent === 'Cancel').click()")
  await wait(100)
  assert.deepEqual(await evaluate('window.placementDesign()'), beforePlacement, 'cancel leaves all existing assets unchanged')
  await previewBed()
  await evaluate("(() => { const b = Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Place here'); b.click(); b.click(); })()")
  await until('window.placementDesign().furniture.length === 2')
  const committed = await evaluate('window.placementDesign()')
  assert.equal(committed.furniture.filter((item) => item.model_id === 'single_bed_01').length, 1)
  assert.equal(committed.furniture[1].room_id, 'bedroom')
  assert.deepEqual(committed.furniture[0], beforePlacement.furniture[0])
  await evaluate("document.querySelector('.viewer-add-assets').click()")
  await until("!document.querySelector('.placement-room-transition') && !!document.querySelector('select')")
  await selectDestination('upper_bedroom')
  const upstairsCamera = await evaluate('window.placementCamera()')
  assert.ok(upstairsCamera[1] > 3.4 && upstairsCamera[1] < 6.8 && upstairsCamera[2] < -6)
  await previewBed()
  await selectDestination('kitchen')
  assert.ok(!(await evaluate("!!document.querySelector('.editor-placement-confirm')")), 'changing rooms discards the pending preview')
  assert.deepEqual(await evaluate('window.placementDesign()'), committed)
  assert.equal(errors.length, 0, JSON.stringify(errors))
  console.log(JSON.stringify({ ...report, heightButtons: 'passed', surfaceMenus: 'passed',
    dragAngleDegrees: dragAngle * 180 / Math.PI, dragPosition: cameraAfter.position,
    gizmoDragDoesNotTurnCamera: true, mobileSelectionVisible: mobile.selectionVisible,
    placementRoomCameraPreviewCancelConfirmAndUpperFloor: 'passed', screenshotPath }, null, 2))
} finally {
  socket?.close()
  browser?.kill()
  await server.close()
}
