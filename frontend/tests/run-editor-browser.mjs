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
    return `import RoofProbe from '/tests/roof-probe.jsx'; import PlacementProbe from '/tests/placement-probe.jsx';\n${code}`
      .replace('<Environment preset={isNightMode ? \'night\' : \'city\'} />', '<ambientLight intensity={0.5} />')
      .replace('<SelectionClickGuard isTransforming={isTransforming} />', '<><SelectionClickGuard isTransforming={isTransforming} /><RoofProbe controlsRef={controlsRef} targetPos={targetPos} targetCamPos={targetCamPos} selection={selectedEntity} /><PlacementProbe onSelect={handleSelectEntity} onModeChange={handleModeChange} /></>')
  },
  configureServer(instance) {
    instance.middlewares.use((request, response, next) => {
      if (request.url.startsWith('/api/assets/catalog')) {
        response.setHeader('Content-Type', 'application/json')
        response.end(JSON.stringify({ assets: [
          { id: 'outdoor_urn', name: 'Outdoor urn', kind: 'model', group: 'ground_decor', category: 'outdoor',
            s3_key: 'assets/furniture/outdoor/planters/garden_urn_01.glb', model_path: '/asset-test/furniture/outdoor/planters/garden_urn_01.glb', dimensions: { width: 0.5, depth: 0.5, height: 0.8 } },
          { id: 'wall_panel', name: 'Boundary panel', kind: 'model', group: 'wall_panel', category: 'wall_panel',
            s3_key: 'assets/architecture/walls/designs/wall_panel_01.glb', model_path: '/asset-test/architecture/walls/designs/wall_panel_01.glb', dimensions: { width: 0.8, depth: 0.1, height: 1 } },
          { id: 'plaster_wall_diff_2k', name: 'Plaster finish', kind: 'texture', group: 'wall_finish',
            s3_key: 'assets/textures/walls/plaster_wall_diff_2k.jpg', url: '/asset-test/textures/walls/plaster_wall_diff_2k.jpg' },
          { id: 'clock_01', name: 'Clock 01', kind: 'model', group: 'furniture', category: 'table_clock', mounting: { surface: 'tabletop' },
            s3_key: 'assets/decorations/clocks/clock_01.glb', model_path: '/asset-test/decorations/clocks/clock_01.glb', dimensions: { width: 0.18, depth: 0.12, height: 0.22 } },
          { id: 'test_window', name: 'Uploaded Window', kind: 'model', group: 'window', s3_key: 'assets/windows/window_standard_02.glb', model_path: '/asset-test/windows/window_standard_02.glb', canonical_yaw_offset_deg: 90 },
          { id: 'test_gate', name: 'Uploaded Gate', kind: 'model', group: 'door', s3_key: 'assets/architecture/doors/exterior/Gate.glb', model_path: '/asset-test/architecture/doors/exterior/Gate.glb', canonical_pitch_offset_deg: 180 },
          { id: 'test_blind', name: 'Uploaded Blind', kind: 'model', group: 'curtain', s3_key: 'assets/decorations/curtains_blinds/window_blinds_low_poly_01.glb' },
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
  await evaluate("window.editorSelectSurface('window')")
  await wait(200)
  assert.ok(await evaluate("!!document.querySelector('button[title=\"Uploaded Window\"]')"))
  assert.ok(!(await evaluate("!!document.querySelector('button[title=\"Uploaded Blind\"]') || !!document.querySelector('button[title=\"Uploaded Gate\"]')")))
  await evaluate("document.querySelector('button[title=\"Uploaded Window\"]').click()")
  assert.equal(await evaluate('window.editorOpening'), 'test_window')
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Curtains & Blinds').click()")
  await wait(100)
  assert.ok(await evaluate("!!document.querySelector('button[title=\"Uploaded Blind\"]')"))
  assert.ok(!(await evaluate("!!document.querySelector('button[title=\"Uploaded Window\"]')")))
  await evaluate("window.editorSelectSurface('door')")
  await wait(200)
  assert.ok(await evaluate("!!document.querySelector('button[title=\"Uploaded Gate\"]')"))
  assert.ok(!(await evaluate("!!document.querySelector('button[title=\"Uploaded Window\"]') || !!document.querySelector('button[title=\"Uploaded Blind\"]')")))
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Restore original door').click()")
  assert.equal(await evaluate('window.editorOpening'), 'original')
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
  for (const [width, height] of [[320, 568], [844, 390], [768, 1024]]) {
    await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false }, sessionId)
    await evaluate('window.scrollTo(0, 0)')
    await wait(300)
    await evaluate("document.querySelector('.interior-editor-drawer').style.animation = 'none'")
    const responsiveDrawer = await evaluate("(() => { const drawer = document.querySelector('.interior-editor-drawer'); const r = drawer.getBoundingClientRect(); return { left: r.left, right: r.right, bottom: r.bottom, viewportWidth: innerWidth, viewportHeight: innerHeight, scrollWidth: drawer.scrollWidth, clientWidth: drawer.clientWidth }; })()")
    assert.ok(responsiveDrawer.left >= -0.5 && responsiveDrawer.right <= responsiveDrawer.viewportWidth + 0.5
      && responsiveDrawer.bottom <= responsiveDrawer.viewportHeight + 0.5 && responsiveDrawer.scrollWidth <= responsiveDrawer.clientWidth,
    `drawer fits ${width}x${height}: ${JSON.stringify(responsiveDrawer)}`)
  }
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: false }, sessionId)
  const mobileScreenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
  fs.writeFileSync(path.join(temp, 'editor-mobile.png'), Buffer.from(mobileScreenshot.data, 'base64'))
  await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 800, deviceScaleFactor: 1, mobile: false }, sessionId)
  await send('Page.navigate', { url: 'http://127.0.0.1:5189/tests/placement-regression.html' }, sessionId)
  const until = async (expression) => {
    for (let i = 0; i < 150; i++) { if (await evaluate(expression)) return; await wait(200) }
    throw new Error(`Timed out: ${expression}; camera=${JSON.stringify(await evaluate('window.placementCamera?.()'))}`)
  }
  await until("!!document.querySelector('.viewer-edit-toggle') && !!window.placementCamera && !!window.setTestViewMode")
  await evaluate("window.setTestViewMode('walkthrough')")
  let walkthroughCamera
  for (let i = 0; i < 30; i++) {
    walkthroughCamera = await evaluate('window.placementCamera()')
    if (walkthroughCamera[0] < 1) break
    await wait(50)
  }
  assert.ok(walkthroughCamera[0] > 0.5 && walkthroughCamera[0] < 3.5
    && walkthroughCamera[1] > 1.4 && walkthroughCamera[1] < 2
    && walkthroughCamera[2] < -0.5 && walkthroughCamera[2] > -3.5
    && Math.hypot(walkthroughCamera[0] - 2, walkthroughCamera[2] + 2) > 1,
  `walkthrough starts at a clear interior viewpoint instead of inside center furniture: ${JSON.stringify(walkthroughCamera)}`)
  await evaluate("document.querySelector('.viewer-edit-toggle').click()")
  await until("!!document.querySelector('.viewer-add-assets')")
  const cameraBeforeLibrary = await evaluate('window.placementCamera()')
  await evaluate("document.querySelector('.viewer-add-assets').click()")
  await until("!!document.querySelector('.interior-editor-drawer select') && !document.querySelector('.placement-room-transition')")
  assert.deepEqual(await evaluate('window.placementCamera()'), cameraBeforeLibrary, 'opening Add assets preserves the current view')
  const selectDestination = async (id) => {
    await evaluate(`(() => { const s = document.querySelector('select'); s.value = '${id}'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`)
    await until(`document.querySelector('select')?.value === '${id}' && !document.querySelector('.placement-room-transition')`)
  }
  await selectDestination('kitchen')
  const kitchenCamera = await evaluate('window.placementCamera()')
  assert.deepEqual(kitchenCamera, cameraBeforeLibrary, 'choosing the current room preserves the current view')
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
  await selectDestination('bedroom')
  const choosePlacementOption = async (label, value) => {
    await evaluate(`(() => { const s = Array.from(document.querySelectorAll('.editor-library-field')).find(l => l.firstChild.textContent.trim() === '${label}').querySelector('select'); s.value = '${value}'; s.dispatchEvent(new Event('change', { bubbles: true })); })()`)
    await wait(100)
  }
  await choosePlacementOption('Place on', 'tabletop')
  await choosePlacementOption('Table or desk', 'bedroom_table')
  await evaluate("document.querySelector('button[title=\"Clock 01\"]').click()")
  await until("Array.from(document.querySelectorAll('button')).some(b => b.textContent === 'Place here' && !b.disabled)")
  await choosePlacementOption('Place on', 'floor')
  assert.ok(!(await evaluate("!!document.querySelector('.editor-placement-confirm')")), 'surface change cancels clock preview')
  assert.deepEqual(await evaluate('window.placementDesign()'), committed)
  await choosePlacementOption('Place on', 'tabletop')
  await choosePlacementOption('Table or desk', 'bedroom_table')
  await evaluate("document.querySelector('button[title=\"Clock 01\"]').click()")
  await until("Array.from(document.querySelectorAll('button')).some(b => b.textContent === 'Place here' && !b.disabled)")
  await evaluate("Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Place here').click()")
  await until("window.placementDesign().furniture.some(item => item.model_id === 'clock_01')")
  const clock = (await evaluate('window.placementDesign()')).furniture.find(item => item.model_id === 'clock_01')
  assert.equal(clock.support_id, 'bedroom_table')
  assert.ok(Math.abs(clock.position.z - 0.702) < 1e-8)
  await evaluate("window.setTestViewMode('dollhouse')")
  await until("!document.querySelector('.interior-editor-drawer') && document.querySelector('.viewer-edit-toggle')?.textContent.includes('Edit 3D')")
  await until('window.placementCamera()[1] > 8')
  const overviewCamera = await evaluate('window.placementCamera()')
  assert.ok(overviewCamera[1] > 8, `dollhouse switch escapes the interior: ${JSON.stringify(overviewCamera)}`)
  await evaluate("window.setTestViewMode('walkthrough')")
  await until('window.placementCamera()[0] > 6 && window.placementCamera()[0] < 10 && window.placementCamera()[1] < 2')
  const returningCamera = await evaluate('window.placementCamera()')
  assert.ok(returningCamera[0] > 6 && returningCamera[0] < 10 && returningCamera[1] < 2,
    `returning to walkthrough restores the selected bedroom: ${JSON.stringify(returningCamera)}`)
  assert.ok(!(await evaluate("!!document.querySelector('.editor-placement-confirm')")), 'switching view mode closes editing and clears pending placement')
  await send('Page.navigate', { url: 'http://127.0.0.1:5189/tests/exterior-regression.html' }, sessionId)
  await until("!!document.querySelector('.viewer-edit-toggle') && !!window.selectExteriorTestSurface")
  await evaluate("document.querySelector('.viewer-edit-toggle').click()")
  await until("window.selectExteriorTestSurface('Lush_Garden_Ground')")
  await until("!!document.querySelector('button[title=\"Outdoor urn\"]')")
  await evaluate("document.querySelector('button[title=\"Outdoor urn\"]').click()")
  await until("window.exteriorDesign().exterior.assets.length === 1 && !!document.querySelector('button[title=\"Move right\"]')")
  await wait(600)
  await evaluate("document.querySelector('button[title=\"Move right\"]').click()")
  await wait(100)
  let outdoor = (await evaluate('window.exteriorDesign()')).exterior.assets[0]
  assert.ok(Math.abs(outdoor.position.x + 4.9) < 1e-5, JSON.stringify(outdoor.position))
  assert.ok(Math.abs(outdoor.position.y + 4) < 1e-5)
  assert.ok(Math.abs(outdoor.position.z + 0.22) < 1e-5)
  await evaluate("Array.from(document.querySelectorAll('.editor-inline-actions button')).find(b => b.textContent === '90?').click()")
  await wait(100)
  outdoor = (await evaluate('window.exteriorDesign()')).exterior.assets[0]
  assert.ok(outdoor.position.x < 0 && outdoor.position.y < 0, 'rotation does not snap outdoor objects inside plot')
  assert.ok(await evaluate("window.selectExteriorTestSurface('Exterior_Boundary_Wall_1')"))
  await until("document.querySelector('.interior-editor-drawer')?.textContent.includes('Boundary wall')")
  await evaluate('window.setPlacementCamera([-2, 3, -4])')
  await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
  await evaluate('window.setPlacementCamera([-2, 1, -4])')
  await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
  await evaluate('window.setPlacementCamera([2, 1, -4])')
  await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
  const boundaryCamera = await evaluate('window.placementCamera()')
  assert.ok(boundaryCamera[0] < -0.1, `dollhouse camera cannot scroll through the boundary wall: ${JSON.stringify(boundaryCamera)}`)
  assert.ok(!(await evaluate("Array.from(document.querySelectorAll('.editor-surface-tabs button')).some(b => b.textContent === 'Curtains')")))
  await evaluate("document.querySelector('button[title=\"Plaster finish\"]').click()")
  await until("!!window.exteriorDesign().wall_face_overrides?.Exterior_Boundary_Wall_1?.nx")
  await evaluate("Array.from(document.querySelectorAll('.editor-surface-tabs button')).find(b => b.textContent === 'Panels').click()")
  await until("!!document.querySelector('button[title=\"Boundary panel\"]')")
  await evaluate("document.querySelector('button[title=\"Boundary panel\"]').click()")
  await until("window.exteriorDesign().exterior.assets.length === 2 && !!document.querySelector('button[title=\"Move toward front\"]')")
  await wait(600)
  await evaluate("document.querySelector('button[title=\"Move toward front\"]').click()")
  await wait(100)
  const panel = (await evaluate('window.exteriorDesign()')).exterior.assets[1]
  assert.ok(panel.wall_mounted && panel.position.x < -0.075)
  assert.ok(Math.abs(panel.position.y - 3.1) < 1e-5, JSON.stringify(panel.position))
  for (const suffix of ['', '?legacy=1']) {
  await send('Page.navigate', { url: `http://127.0.0.1:5189/tests/opening-regression.html${suffix}` }, sessionId)
  await until('window.openingSnapshot && window.openingSnapshot().originals.length === 3')
  for (const index of [0, 1, 2, 3]) {
    await evaluate(`window.setOpeningAsset(${index})`)
    await until(`window.openingSnapshot().replacements.length === 1 && window.openingSnapshot().originals.filter(o => !o.visible).length === ${index === 2 ? 1 : 2}`)
    const opening = await evaluate('window.openingSnapshot()')
    if (index === 1) assert.ok(!opening.replacements[0].names.some((name) => /^Wall|^(Wing[ _]\d{2}|Frame)[._]?001$/.test(name)), 'standard window excludes demonstration geometry')
    if (index === 3) assert.ok(opening.replacements[0].names.includes('Arch_wall_infill'))
    if (!suffix && [1, 3].includes(index)) {
      const shot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
      fs.writeFileSync(path.join(temp, `window-${index}.png`), Buffer.from(shot.data, 'base64'))
    }
    const expected = index === 2 ? [0.22, 2.1, 0.9] : [1.4, 1.1, 0.22]
    opening.replacements[0].size.forEach((value, axis) => assert.ok(Math.abs(value - expected[axis]) < 1e-5, JSON.stringify(opening)))
    assert.ok(Math.abs(opening.replacements[0].min[1] - (index === 2 ? 0 : 1)) < 1e-5)
    await evaluate('window.setOpeningFloor(1)')
    await wait(100)
    assert.ok((await evaluate('window.openingSnapshot()')).replacements[0].visible, 'lower floor openings remain visible in upper-floor cutaway')
    await evaluate('window.setOpeningAsset(null)')
    await until('window.openingSnapshot().replacements.length === 0 && window.openingSnapshot().originals.every(o => o.visible)')
  }
  }
  const roofCases = [
    { shape: 'flat', width: 1200, height: 800 },
    { shape: 'sloped', width: 1200, height: 800 },
    { shape: 'large', width: 1200, height: 800 },
    { shape: 'sloped', width: 390, height: 844 },
    { shape: 'flat', width: 1200, height: 800, ceiling: true },
    { shape: 'shared', width: 1200, height: 800, ceiling: true },
    { shape: 'shared', width: 390, height: 844, ceiling: true },
  ]
  for (const entry of roofCases) {
    await send('Emulation.setDeviceMetricsOverride', { width: entry.width, height: entry.height, deviceScaleFactor: 1, mobile: false }, sessionId)
    await send('Page.navigate', { url: `http://127.0.0.1:5189/tests/roof-regression.html?shape=${entry.shape}` }, sessionId)
    await until("!!document.querySelector('.viewer-edit-toggle') && !!window.roofPrepare")
    await evaluate("document.querySelector('.viewer-edit-toggle').click()")
    await until("document.querySelector('.viewer-edit-toggle')?.textContent.includes('Done editing')")
    if (entry.ceiling) {
      await evaluate("window.setTestViewMode('walkthrough')")
      await until("window.roofWalkthroughReady() && document.querySelector('.viewer-edit-toggle')?.textContent.includes('Edit 3D')")
      await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
      await evaluate("document.querySelector('.viewer-edit-toggle').click()")
      await until("document.querySelector('.viewer-edit-toggle')?.textContent.includes('Done editing')")
    }
    assert.ok(await evaluate(`window.roofPrepare(${!!entry.ceiling})`))
    await evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    const click = await evaluate('window.roofClickPoint()')
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', buttons: 1, clickCount: 1, ...click }, sessionId)
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', buttons: 0, clickCount: 1, ...click }, sessionId)
    await until(`window.roofSnapshot()?.selectionType === '${entry.ceiling ? 'ceiling' : 'roof'}'`)
    await until('window.roofSnapshot().target.every((v,i) => Math.abs(v-window.roofSnapshot().reference.target[i]) < 0.02)')
    await until(`(() => {
      const frames = window.roofTrack;
      if (frames.length < 12) return false;
      const last = frames.at(-1);
      return (${!!entry.ceiling} || frames.some(p => p.some((v,i) => Math.abs(v-frames[0][i]) > 0.01)))
        && frames.slice(-6).every(p => p.every((v,i) => Math.abs(v-last[i]) < 0.0001));
    })()`)
    const focused = await evaluate('window.roofSnapshot()')
    assert.ok(focused.selectedPrimitive, 'real selection retains the clicked mesh and world face')
    const facing = focused.position.reduce((sum,v,i) => sum+(v-focused.reference.target[i])*focused.reference.normal[i],0)
    assert.ok(facing > 0, JSON.stringify({entry,focused}))
    assert.ok(focused.direction.reduce((sum,v,i) => sum+v*focused.reference.normal[i],0) < 0, 'camera faces the selected side')
    if (entry.ceiling) {
      assert.deepEqual(focused.position, await evaluate('window.roofInitialPosition'), 'interior ceiling focus never moves the viewer to another room')
      if (entry.shape === 'shared') {
        assert.equal(focused.roomId,'living')
        assert.ok(focused.target[0] < focused.reference.bounds.min[0] + 4, 'ceiling target remains in the living room')
        assert.ok((await evaluate('window.roofTrack')).every(p => p.every((v,i) => Math.abs(v-focused.position[i]) < 1e-6)), 'no transition frame crosses the divider wall')
      }
    }
    if (!entry.ceiling) {
      assert.ok(focused.position[1] > focused.reference.bounds.max[1])
      const drawer = await evaluate("(() => { const r=document.querySelector('.interior-editor-drawer').getBoundingClientRect(); return {left:r.left,top:r.top,width:r.width}; })()")
      for (const point of focused.points) {
        assert.ok(point.x > 0 && point.x < entry.width && point.y > 0 && point.y < entry.height, JSON.stringify({entry,point}))
        assert.ok(drawer.width > entry.width*.85 ? point.y < drawer.top : point.x < drawer.left, JSON.stringify({entry,point,drawer}))
      }
    }
    const track = await evaluate('window.roofTrack')
    assert.ok(track.length > 2, 'focus renders intermediate frames')
    assert.ok(track.every(p => p.reduce((sum,v,i)=>sum+(v-focused.reference.target[i])*focused.reference.normal[i],0)>0), 'transition never crosses through the selected face')
    const roofScreenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
    fs.writeFileSync(path.join(temp, `roof-${entry.shape}-${entry.width}${entry.ceiling ? '-ceiling' : ''}.png`), Buffer.from(roofScreenshot.data, 'base64'))
    if (entry.ceiling) {
      await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 100, y: entry.height * .35,
        deltaX: 0, deltaY: -120 }, sessionId)
      await until(`window.roofSnapshot().fov < ${focused.fov - 5}`)
      await wait(500)
      const zoomed = await evaluate('window.roofSnapshot()')
      assert.deepEqual(zoomed.position, focused.position, 'ceiling edit zoom stays in the room')
      assert.deepEqual(zoomed.target, focused.target, 'ceiling edit zoom preserves the selected target')
    }
  }
  assert.equal(errors.length, 0, JSON.stringify(errors))
  console.log(JSON.stringify({ ...report, heightButtons: 'passed', surfaceMenus: 'passed',
    windowAndCoveringTabs: 'passed', openingFitReplacementRestoreAndFloorVisibility: 'passed',
    legacyOpeningsWithoutGlbMetadata: 'passed', roofAndCeilingCamera: '7 real-selection cases passed, including shared living-room/bedroom ceilings',
    dragAngleDegrees: dragAngle * 180 / Math.PI, dragPosition: cameraAfter.position,
    gizmoDragDoesNotTurnCamera: true, mobileSelectionVisible: mobile.selectionVisible,
    placementRoomCameraPreviewCancelConfirmAndUpperFloor: 'passed', screenshotPath }, null, 2))
} finally {
  socket?.close()
  browser?.kill()
  await server.close()
}
