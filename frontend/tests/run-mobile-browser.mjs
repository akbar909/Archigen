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
    return `import MobileProbe from '/tests/mobile-probe.jsx'; import PlacementProbe from '/tests/placement-probe.jsx';\n${code}`
      .replace('<Environment preset={isNightMode ? \'night\' : \'city\'} />', '<ambientLight intensity={0.5} />')
      .replace('<SelectionClickGuard isTransforming={isTransforming} />', '<><MobileProbe /><SelectionClickGuard isTransforming={isTransforming} /><PlacementProbe onSelect={handleSelectEntity} onModeChange={handleModeChange} /></>')
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
      if (request.url.includes('mobileSlow=1')) setTimeout(() => fs.createReadStream(file).pipe(response), 1800); else fs.createReadStream(file).pipe(response)
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
  const until = async (expression) => { for (let i = 0; i < 150; i++) { if (await evaluate(`Boolean(${expression})`)) return; await wait(100) } throw new Error(`Timed out: ${expression}`) }
  const metrics = async (width, height, touch = true) => {
    await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: true }, sessionId)
    await send('Emulation.setTouchEmulationEnabled', { enabled: touch, maxTouchPoints: 5 }, sessionId)
    await until(`!document.querySelector(".app-shell") || (innerWidth === ${width} && Math.abs(innerHeight - ${height}) < 2 && Math.abs(document.querySelector(".app-shell").getBoundingClientRect().height - ${height}) < 2)` )
    await wait(400)
  }
  const visible = (selector) => `(() => { const e = document.querySelector(${JSON.stringify(selector)}); return !!e && e.getBoundingClientRect().height > 0 && getComputedStyle(e).visibility !== 'hidden' })()`
  const click = async (selector) => { await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`); await wait(200) }
  const capture = async (name) => { const shot = await send('Page.captureScreenshot', { format: 'png' }, sessionId); fs.writeFileSync(path.join(temp, name + '.png'), Buffer.from(shot.data, 'base64')) }
  const rect = async (selector) => evaluate(`(() => { const r = document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return { x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom } })()`)
  await metrics(390, 844)
  await send('Page.navigate', { url: 'http://127.0.0.1:5189/tests/mobile-regression.html' }, sessionId)
  await until(`document.querySelector('.viewer-container[aria-busy="true"]')`)
  assert.equal(await evaluate(visible('.viewer-editor-actions')), false)
  await until("document.querySelector('.viewer-loading-card')")
  const loader = await rect('.viewer-loading-card'), loadingViewport = await rect('.viewer-container')
  assert.ok(Math.abs(loader.x + loader.width / 2 - loadingViewport.x - loadingViewport.width / 2) < 2, JSON.stringify({loader,loadingViewport}))
  assert.ok(Math.abs(loader.y + loader.height / 2 - loadingViewport.y - loadingViewport.height / 2) < 2, JSON.stringify({loader,loadingViewport}))
  await capture('mobile-centered-loader')
  await until("document.querySelector('.viewer-edit-toggle')")
  assert.deepEqual(await evaluate('window.mobileFlashes'), [])
  await evaluate('window.mobileStore.setState({ isGenerating3D: true })')
  await until("!document.querySelector('.viewer-editor-actions')")
  await evaluate('window.mobileStore.setState({ isGenerating3D: false })')
  await until("document.querySelector('.viewer-editor-actions')")
  await evaluate('window.mobileStore.setState(state => ({ design: { ...state.design, glb_url: state.design.glb_url + "&reload=2" } }))')
  await until(`document.querySelector('.viewer-container[aria-busy="true"]')`)
  assert.equal(await evaluate(visible('.viewer-editor-actions')), false)
  await until("document.querySelector('.viewer-editor-actions')")
  assert.deepEqual(await evaluate('window.mobileFlashes'), [])
  await evaluate(`{ const style = document.createElement('style'); style.textContent = '* { animation: none !important; transition: none !important; }'; document.head.append(style); }`)
  await click('.viewer-info-menu > button')
  const info = await rect('.viewer-info-menu > div')
  assert.ok(info.x >= 0 && info.right <= 390, JSON.stringify(info))
  assert.equal(await evaluate(visible('.viewer-rebuild-model')),true)
  assert.equal((await rect('.viewer-details-toggle')).width,44)
  assert.equal((await rect('.viewer-details-toggle > svg')).width,20)
  assert.equal(await evaluate(`(() => { const button = document.querySelector('.viewer-details-close'); const r = button.getBoundingClientRect(); return !!document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)?.closest('.viewer-details-close'); })()`),true, 'room navigator cannot cover the details close button')
  await capture('architectural-details')
  await click('[aria-label="Close architectural details"]')
  assert.equal(await evaluate("document.querySelector('.viewer-details-toggle').getAttribute('aria-expanded')"),'false')
  await click('.viewer-edit-toggle')
  await click('.viewer-add-assets')
  await until("document.querySelector('.interior-editor-drawer')")
  for (const [width,height] of [[320,568],[390,844],[430,932],[844,390],[768,1024]]) {
    await metrics(width,height)
    const sheet = await rect('.interior-editor-drawer'), viewport = await rect('.viewer-container')
    assert.ok(sheet.right <= width + 1 && sheet.bottom <= height + 1, JSON.stringify({sheet,viewport}))
    if (width < height) assert.ok(sheet.height <= viewport.height * .45, JSON.stringify({sheet,viewport}))
    else assert.ok(sheet.width <= viewport.width * .44, JSON.stringify({sheet,viewport}))
    assert.equal(await evaluate('document.documentElement.scrollWidth > innerWidth'), false)
    const overlaps = await evaluate(`(() => {
      const overlap = (a,b) => a.width > 0 && b.width > 0 && Math.max(a.left,b.left) < Math.min(a.right,b.right) - 1 && Math.max(a.top,b.top) < Math.min(a.bottom,b.bottom) - 1;
      const chat = document.querySelector('.mobile-chat-launcher')?.getBoundingClientRect();
      const floor = document.querySelector('.viewer-floor-mobile').getBoundingClientRect();
      return {
        chat: !!chat && Array.from(document.querySelectorAll('.viewer-editor-actions button, .interior-editor-drawer')).some(e => overlap(chat,e.getBoundingClientRect())),
        floor: Array.from(document.querySelectorAll('.viewer-toolbar-right button')).some(e => overlap(floor,e.getBoundingClientRect())),
        room: getComputedStyle(document.querySelector('.room-navigator')).display !== 'none'
      };
    })()`)
    assert.deepEqual(overlaps,{chat:false,floor:false,room:false},JSON.stringify({width,height,overlaps}))
    await capture(`editor-${width}-${height}`)
  }
  await metrics(390,844)
  const expanded = await rect('.interior-editor-drawer')
  await click('.editor-sheet-handle')
  assert.ok((await rect('.interior-editor-drawer')).height < expanded.height)
  await click('.editor-sheet-handle')
  await click('[aria-label="Close editor"]')
  await click('.viewer-edit-toggle')
  await evaluate("window.setTestViewMode('walkthrough')")
  await until(visible('.walkthrough-joystick'))
  await capture('walkthrough-portrait')
  const before = await evaluate('window.mobileCamera()')
  assert.equal(before.fov,78)
  assert.equal(before.near,.03)
  const joystick = await rect('.walkthrough-joystick'), canvas = await rect('.viewer-container canvas')
  const stick = { x:joystick.x+joystick.width/2,y:joystick.y+joystick.height/2-28,id:1 }
  const look = { x:canvas.x+canvas.width*.7,y:canvas.y+canvas.height*.45,id:2 }
  const touch = (type, points) => send('Input.dispatchTouchEvent', { type, touchPoints:points }, sessionId)
  await touch('touchStart',[stick]); await wait(150)
  await touch('touchStart',[stick,look])
  await touch('touchMove',[stick,{...look,x:look.x+55,y:look.y+25}]); await wait(350)
  const moving = await evaluate('window.mobileCamera()')
  assert.ok(Math.hypot(...moving.position.map((v,i)=>v-before.position[i]))>.05,JSON.stringify({before,moving}))
  assert.ok(Math.hypot(...moving.direction.map((v,i)=>v-before.direction[i]))>.05,JSON.stringify({before,moving}))
  const rightwardLook = moving.direction[0] * -before.direction[2] + moving.direction[2] * before.direction[0]
  assert.ok(rightwardLook > 0, 'swiping right looks right')
  assert.ok(moving.direction[1] < before.direction[1], 'swiping down looks down')
  await touch('touchEnd',[stick]); await wait(150)
  await touch('touchEnd',[]); await wait(200)
  const stopped = await evaluate('window.mobileCamera()'); await wait(200)
  assert.deepEqual((await evaluate('window.mobileCamera()')).position,stopped.position)
  assert.equal(stopped.fov, 78, 'joystick plus look must not trigger pinch zoom')
  const fingerA = { x: canvas.x + canvas.width * .35, y: canvas.y + canvas.height * .4, id: 3 }
  const fingerB = { x: canvas.x + canvas.width * .65, y: fingerA.y, id: 4 }
  await touch('touchStart', [fingerA, fingerB])
  await touch('touchMove', [{ ...fingerA, x: fingerA.x - 30 }, { ...fingerB, x: fingerB.x + 30 }])
  await touch('touchEnd', [])
  await until('window.mobileCamera().fov < 65')
  await wait(500)
  const pinched = await evaluate('window.mobileCamera()')
  assert.deepEqual(pinched.position, stopped.position, 'pinch cannot move into another room')
  assert.deepEqual(pinched.direction, stopped.direction, 'pinch cannot rotate the camera')
  await touch('touchStart', [fingerA, fingerB])
  await touch('touchMove', [{ ...fingerA, x: fingerA.x + 40 }, { ...fingerB, x: fingerB.x - 40 }])
  await touch('touchEnd', [])
  await until('window.mobileCamera().fov === 90')
  assert.equal(await evaluate(visible('.design-chat')),false)
  assert.equal(await evaluate(visible('.mobile-chat-launcher')),false)
  await capture('loaded-design-without-chat')
  assert.equal(await evaluate(visible('.walkthrough-joystick')),true)
  await metrics(390,844)
  await click('.topbar .mobile-only')
  const account = await rect('.sidebar-footer')
  assert.ok(account.bottom <= 844 && account.y > 0,JSON.stringify(account))
  assert.equal(await evaluate("document.querySelector('.sidebar-user-email').textContent"),'architect.long.email@example.com')
  assert.equal(await evaluate("document.querySelector('.sidebar-user-role').textContent.trim()"),'24 projects')
  assert.equal(await evaluate(visible('[aria-label="Sign out"]')),true)
  await evaluate("window.mobileAuth.setState({ user: { name: 'jamaliakbar909@gmail.com', email: 'jamaliakbar909@gmail.com' } })")
  await until("document.querySelector('.sidebar-user-name').textContent === 'jamaliakbar909'")
  for (const width of [320,390]) {
    await metrics(width,844)
    const rename = await rect('.sidebar-project-rename'), remove = await rect('.sidebar-project-delete')
    assert.ok(rename.width === 36 && remove.width === 36 && rename.height === 36 && remove.height === 36)
    assert.ok(rename.right + 5 <= remove.x, JSON.stringify({rename,remove}))
    assert.equal(await evaluate("document.querySelectorAll('.project-action-label').length"),0)
    const icon = await rect('.sidebar-project-rename > svg')
    assert.equal(icon.width,16)
    assert.equal(rename.width,rename.height)
    const email = await rect('.sidebar-user-email'), name = await rect('.sidebar-user-name')
    assert.ok(email.y > name.bottom && email.width > name.width)
    assert.equal(await evaluate("document.querySelector('.sidebar-user-email').textContent"),'jamaliakbar909@gmail.com')
    assert.ok(email.height < 34, JSON.stringify(email))
    assert.ok(Math.abs(icon.x + icon.width / 2 - rename.x - rename.width / 2) < 1)
    assert.ok(Math.abs(icon.y + icon.height / 2 - rename.y - rename.height / 2) < 1)
    assert.equal(await evaluate("document.querySelector('.sidebar-history').scrollWidth > document.querySelector('.sidebar-history').clientWidth"),false)
  }
  await capture('navigation-project-actions')
  await click('[aria-label="Close navigation"]')
  await metrics(844,390)
  assert.equal((await evaluate('window.mobileCamera()')).fov,64)
  await metrics(1200,800,false)
  assert.equal((await evaluate('window.mobileCamera()')).fov,64)
  const desktopCamera = await evaluate('window.mobileCamera()')
  const desktopCanvas = await rect('.viewer-container canvas')
  const wheel = (deltaY) => send('Input.dispatchMouseEvent', { type: 'mouseWheel',
    x: desktopCanvas.x + desktopCanvas.width / 2, y: desktopCanvas.y + desktopCanvas.height / 2,
    deltaX: 0, deltaY }, sessionId)
  await wheel(200)
  await until('window.mobileCamera().fov > 85')
  await wheel(200)
  await until('window.mobileCamera().fov === 90')
  for (let i = 0; i < 4; i++) await wheel(-200)
  await until('window.mobileCamera().fov === 40')
  const zoomed = await evaluate('window.mobileCamera()')
  assert.deepEqual(zoomed.position, desktopCamera.position)
  assert.deepEqual(zoomed.direction, desktopCamera.direction)
  assert.equal(await evaluate(visible('.design-chat')),false)
  assert.equal(await evaluate(visible('.walkthrough-joystick')),false)
  assert.equal((await rect('.sidebar-project-rename')).width,20)
  assert.equal(await evaluate("document.querySelectorAll('.project-action-label').length"),0)
  await evaluate("window.setTestViewMode('dollhouse')")
  await until('window.mobileCamera().fov === 44')
  assert.deepEqual(await evaluate('window.mobileFlashes'),[])
  assert.equal(errors.length,0,JSON.stringify(errors))
  console.log(JSON.stringify({ loading:'passed', responsiveSheets:'5 sizes passed', multitouchMovementAndLook:'passed', stopOnRelease:'passed', mobileFov:'passed', pinchAndWheelZoom:'passed with limits and unchanged camera position', loadedDesignChatHidden:'passed', navigationFooter:'passed', desktopLens:'passed', artifacts:temp },null,2))
} finally { socket?.close(); browser?.kill(); await server.close() }
