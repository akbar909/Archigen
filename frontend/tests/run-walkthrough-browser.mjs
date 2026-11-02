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
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'archigen-walk-browser-'))
const wait = ms => new Promise(resolve => setTimeout(resolve, ms))
const server = await createServer({ root: frontend, configFile: false, plugins: [react(), {
  name: 'walk-fixture', enforce: 'pre',
  transform(code, id) {
    if (!id.replaceAll('\\', '/').endsWith('/components/viewer3d/ViewerStage.jsx')) return null
    return `import WalkProbe from '/tests/walkthrough-probe.jsx';\n${code}`
      .replace('<Environment preset={isNightMode ? \'night\' : \'city\'} />', '<ambientLight intensity={0.5} />')
      .replace('<SelectionClickGuard isTransforming={isTransforming} />', '<><SelectionClickGuard isTransforming={isTransforming} /><WalkProbe controlsRef={controlsRef} targetPos={targetPos} targetCamPos={targetCamPos} touchMoveRef={touchMoveRef} onSelectRoom={handleSelectRoom} onModeChange={handleModeChange} level={charFloorLevel} selection={selectedEntity} /></>')
  },
  configureServer(instance) {
    instance.middlewares.use((request, response, next) => {
      if (request.url.startsWith('/api/assets/catalog')) {
        const metadata = JSON.parse(fs.readFileSync(path.resolve(frontend, '../blender/metadata/wall_panel_01.json')))
        response.setHeader('Content-Type', 'application/json')
        response.end(JSON.stringify({ assets: [{ ...metadata, id: 'wall_panel_01', name: 'Wall panel', kind: 'model', group: 'wall_panel', category: 'wall_panel',
          s3_key: 'assets/architecture/walls/designs/wall_panel_01.glb', model_path: '/asset-test/architecture/walls/designs/wall_panel_01.glb',
          dimensions: { width: .8, depth: .1, height: 1 } }] }))
        return
      }
      if (!request.url.startsWith('/asset-test/')) return next()
      const file = path.resolve(assets, decodeURIComponent(request.url.slice('/asset-test/'.length).split('?')[0]))
      if (!file.startsWith(assets + path.sep) || !fs.existsSync(file)) { response.statusCode = 404; response.end(); return }
      response.setHeader('Content-Type', 'model/gltf-binary'); fs.createReadStream(file).pipe(response)
    })
  },
}], server: { host: '127.0.0.1', port: 5191, strictPort: true, hmr: false } })
let browser, socket
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
  const pending = new Map(), errors = []
  socket.onmessage = ({ data }) => {
    const result = JSON.parse(data)
    if (result.method === 'Runtime.exceptionThrown') errors.push(result.params.exceptionDetails.exception?.description || result.params.exceptionDetails.text)
    if (pending.has(result.id)) { const { resolve, reject } = pending.get(result.id); pending.delete(result.id); result.error ? reject(result.error) : resolve(result.result) }
  }
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++sequence; pending.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }))
  })
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' })
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true })
  const evaluate = async expression => {
    const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }, sessionId)
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text)
    return result.result.value
  }
  const until = async expression => {
    for (let i = 0; i < 200; i++) { if (await evaluate(`Boolean(${expression})`)) return; await wait(100) }
    throw new Error(`Timeout: ${expression}; ${JSON.stringify(await evaluate('window.walkState?.()'))}; ${errors.join('\n')}`)
  }
  await send('Runtime.enable', {}, sessionId)
  await send('Emulation.setDeviceMetricsOverride', { width: 1200, height: 800, deviceScaleFactor: 1, mobile: false }, sessionId)
  await send('Page.navigate', { url: 'http://127.0.0.1:5191/tests/walkthrough-regression.html' }, sessionId)
  await until('window.walkMode && document.querySelector(".viewer-edit-toggle")')
  await evaluate('window.walkMode("walkthrough")')
  await wait(500)
  const selectRoom = async name => {
    await evaluate('document.querySelector(".room-navigator > button").click()')
    await until('Array.from(document.querySelectorAll(".room-navigator button")).some(b => b.textContent === ' + JSON.stringify(name) + ')')
    await evaluate('Array.from(document.querySelectorAll(".room-navigator button")).find(b => b.textContent === ' + JSON.stringify(name) + ').click()')
    await wait(200)
  }
  await selectRoom('Bathroom 0')
  assert.ok((await evaluate('window.walkState()')).position[0] > 4.6)
  await selectRoom('Stair Lobby 0')
  let selectedLobby = await evaluate('window.walkState()')
  assert.ok(selectedLobby.position[0] < 4.6, 'Selecting Stair Lobby must leave the bathroom')
  assert.ok(selectedLobby.direction[0] * (1.775 - selectedLobby.position[0]) + selectedLobby.direction[2] * (-1.3 - selectedLobby.position[2]) > 0,
    `Lobby camera must look toward the stairs, not through the bathroom wall: ${JSON.stringify(selectedLobby)}`)
  const route = [[4.05, -.71], [.65, -.71], [.65, -1.89], [4.05, -1.89]]
  const travel = async points => {
    for (const point of points) {
      await evaluate(`window.walkToward(${point.join(',')})`)
      await until('window.walkArrived')
      console.log(JSON.stringify(await evaluate('window.walkState()')))
    }
  }
  await travel(route)
  let state = await evaluate('window.walkState()')
  assert.equal(state.level, 1); assert.ok(Math.abs(state.position[1] - 4.65) < .05)
  await travel(route.slice().reverse())
  state = await evaluate('window.walkState()')
  assert.equal(state.level, 0); assert.ok(Math.abs(state.position[1] - 1.65) < .05)
  await selectRoom('Bathroom 1')
  assert.ok((await evaluate('window.walkState()')).position[0] > 4.6)
  await selectRoom('Stair Lobby 1')
  await wait(500)
  state = await evaluate('window.walkState()')
  assert.ok(state.position[0] > 3.4 && state.position[0] < 4.6, `Room selection must use upper landing: ${JSON.stringify(state)}`)
  assert.ok(state.direction[0] < 0, `Upper landing camera must face the stairs: ${JSON.stringify(state)}`)
  const lobbyScreenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
  fs.writeFileSync(path.join(temp, 'stair-lobby-selection.png'), Buffer.from(lobbyScreenshot.data, 'base64'))

  await evaluate('window.walkMode("front")')
  await wait(500)
  await evaluate('document.querySelector(".viewer-edit-toggle").click()')
  await wait(300)
  const point = await evaluate('window.walkFacade()')
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', clickCount: 1, ...point }, sessionId)
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', clickCount: 1, ...point }, sessionId)
  await until('window.walkState().selection?.type === "wall"')
  assert.equal((await evaluate('window.walkState()')).selection.wallFace, 'exterior')
  await evaluate('Array.from(document.querySelectorAll("button")).find(b => b.textContent === "Panels").click()')
  await until('document.querySelector(\'button[title="Wall panel"]\')')
  await evaluate('document.querySelector(\'button[title="Wall panel"]\').click()')
  await until('window.walkPanelBounds()')
  const bounds = await evaluate('window.walkPanelBounds()')
  assert.ok(bounds.min[2] > .1, `Panel must sit outside south facade: ${JSON.stringify(bounds)}`)
  const screenshot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
  fs.writeFileSync(path.join(temp, 'exterior-panel.png'), Buffer.from(screenshot.data, 'base64'))
  assert.equal(errors.length, 0, errors.join('\n'))
  console.log(JSON.stringify({ ascent: 'passed', descent: 'passed', landingSelection: 'passed', exteriorPanel: bounds, artifacts: temp }))
} finally {
  socket?.close(); browser?.kill(); await server.close()
}
