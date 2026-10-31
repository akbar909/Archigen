import { createServer } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';
const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'archigen-cad-browser-')),
  wait = ms => new Promise(r => setTimeout(r, ms));
let savedDesign = null;
const server = await createServer({
  root: frontend,
  configFile: false,
  plugins: [react(), {
    name: 'cad-api-fixtures',
    configureServer(instance) {
      instance.middlewares.use((req, res, next) => {
        if (!req.url.startsWith('/api/')) return next();
        res.setHeader('Content-Type', 'application/json');
        if (req.url.startsWith('/api/assets/catalog')) {
          res.end(JSON.stringify({
            assets: []
          }));
          return;
        }
        if (req.method === 'PATCH') {
          let body = '';
          req.on('data', chunk => body += chunk);
          req.on('end', () => {
            savedDesign = JSON.parse(body).design;
            res.end(JSON.stringify({
              success: true,
              design: savedDesign,
              version: {
                id: '507f191e810c19729de860ea',
                version_num: 1
              }
            }));
          });
          return;
        }
        if (req.url.endsWith('/layout/refine')) {
          let body = '';
          req.on('data', chunk => body += chunk);
          req.on('end', () => {
            const payload=JSON.parse(body),d = payload.design;
            assert.deepEqual(payload.selection,{type:'furniture',id:'sofa',floor_id:'floor_0'});
            d.floors[0].furniture.find(i=>i.id===payload.selection.id).rotation = 90;
            res.end(JSON.stringify({
              success: true,
              design: d
            }));
          });
          return;
        }
        if(req.url.endsWith('/approve-layout')){
          res.statusCode=422;
          res.end(JSON.stringify({error:'Layout cannot be approved until critical conflicts are resolved.',validation:{critical_errors:["Door 'bed_door' intends to connect ['living', 'bedroom'] but its wall 'wall_l0_part_012' connects ['living']."]}}));return;
        }
        if (req.url.endsWith('/projects')) {
          res.end(JSON.stringify({
            projects: []
          }));
          return;
        }
        res.end(JSON.stringify({
          success: true
        }));
      });
    }
  }],
  server: {
    host: '127.0.0.1',
    port: 5193,
    strictPort: true
  }
});
let browser, socket;
try {
  await server.listen();
  browser = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', ['--headless=new', '--remote-debugging-port=0', `--user-data-dir=${temp}`, '--no-first-run', '--no-default-browser-check', 'about:blank'], {
    windowsHide: true,
    stdio: 'ignore'
  });
  const portFile = path.join(temp, 'DevToolsActivePort');
  for (let i = 0; i < 150 && !fs.existsSync(portFile); i++) await wait(100);
  const [port, endpoint] = fs.readFileSync(portFile, 'utf8').trim().split(/\r?\n/);
  socket = new WebSocket(`ws://127.0.0.1:${port}${endpoint}`);
  await new Promise((resolve, reject) => {
    socket.onopen = resolve;
    socket.onerror = reject;
  });
  let seq = 0;
  const pending = new Map(),
    errors = [];
  socket.onmessage = ({
    data
  }) => {
    const m = JSON.parse(data);
    if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push(m.params.args.map(a => a.description || a.value).join(' '));
    if (pending.has(m.id)) {
      const {
        resolve,
        reject
      } = pending.get(m.id);
      pending.delete(m.id);
      m.error ? reject(m.error) : resolve(m.result);
    }
  };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, {
      resolve,
      reject
    });
    socket.send(JSON.stringify({
      id,
      method,
      params,
      ...(sessionId ? {
        sessionId
      } : {})
    }));
  });
  const {
      targetId
    } = await send('Target.createTarget', {
      url: 'about:blank'
    }),
    {
      sessionId
    } = await send('Target.attachToTarget', {
      targetId,
      flatten: true
    });
  const evaluate = async expression => {
    const r = await send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true
    }, sessionId);
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  const until = async expression => {
    for (let i = 0; i < 120; i++) {
      if (await evaluate(`Boolean(${expression})`)) return;
      await wait(100);
    }
    throw new Error(`Timed out: ${expression}`);
  };
  const click = async selector => {
    if (!(await evaluate(`!!document.querySelector(${JSON.stringify(selector)})`))) {
      await capture('failure');
      console.log(JSON.stringify({
        errors,
        body: await evaluate('document.body.innerText')
      }));
      throw new Error('Missing button: ' + selector);
    }
    await evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    await wait(120);
  };
  const capture = async name => {
    const shot = await send('Page.captureScreenshot', {
      format: 'png'
    }, sessionId);
    fs.writeFileSync(path.join(temp, `${name}.png`), Buffer.from(shot.data, 'base64'));
  };
  const rect = async selector => evaluate(`(()=>{const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return{x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}})()`);
  const metrics = async (w, h) => {
    await send('Emulation.setDeviceMetricsOverride', {
      width: w,
      height: h,
      deviceScaleFactor: 1,
      mobile: w < 600
    }, sessionId);
    await send('Emulation.setTouchEmulationEnabled', {
      enabled: w < 600,
      maxTouchPoints: 5
    }, sessionId);
    await wait(250);
  };
  const mouse = async (type, x, y, buttons = 0, modifiers = 0) => send('Input.dispatchMouseEvent', {
    type,
    x,
    y,
    button: 'left',
    buttons,
    clickCount: 1,
    modifiers
  }, sessionId);
  const point = async (x, y) => evaluate(`(()=>{const svg=document.querySelector('.cad-canvas'),p=new DOMPoint(${(x + 2) * 40},${(18 - y) * 40}).matrixTransform(svg.getScreenCTM());return{x:p.x,y:p.y}})()`);
  const drag = async (from, to) => {
    await mouse('mousePressed', from.x, from.y, 1);
    await wait(150);
    for (let i = 1; i <= 6; i++) {
      await mouse('mouseMoved', from.x + (to.x - from.x) * i / 6, from.y + (to.y - from.y) * i / 6, 1);
      await wait(30);
    }
    await mouse('mouseReleased', to.x, to.y);
    await wait(180);
  };
  const input = async (label, value) => {
    await evaluate(`(()=>{const e=document.querySelector('input[aria-label=${JSON.stringify(label)}]');const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));e.focus()})()`);
    await send('Input.dispatchKeyEvent', {
      type: 'keyDown',
      key: 'Enter',
      code: 'Enter',
      windowsVirtualKeyCode: 13
    }, sessionId);
    await send('Input.dispatchKeyEvent', {
      type: 'keyUp',
      key: 'Enter',
      code: 'Enter',
      windowsVirtualKeyCode: 13
    }, sessionId);
    await wait(150);
  };
  await send('Runtime.enable', {}, sessionId);
  await metrics(1280, 900);
  await send('Page.navigate', {
    url: 'http://127.0.0.1:5193/tests/cad-regression.html'
  }, sessionId);
  await until(`document.querySelector('.cad-canvas')`);
  assert.equal(await evaluate('cadEditor.getState().strict'),true);
  assert.equal(await evaluate("document.querySelectorAll('.version-save-trigger').length"),1);
  assert.equal(await evaluate("document.querySelectorAll('.cad-save,.cad-chat-mode,.design-chat,.mobile-chat-launcher').length"),0);
  assert.equal(await evaluate("Array.from(document.querySelectorAll('button')).some(b=>b.textContent.includes('Design Wizard'))"),false);
  assert.ok((await rect('.cad-editor')).height>650,'editor should use the former chat area');
  await evaluate("cadEditor.getState().setOption('strict',false)");
  await evaluate(`{const style=document.createElement('style');style.textContent='*{transition:none!important;animation:none!important}';document.head.append(style)}`);
  // A first drag must work before opening the inspector, without moving the
  // viewport underneath the pointer partway through the gesture.
  const before = await evaluate('JSON.stringify(cadProject.getState().design)');
  const sofaBefore = await evaluate('cadProject.getState().design.floors[0].furniture[0].position');
  await capture('initial-desktop');
  await evaluate(`{window.cadEvents=[];for(const type of ['pointerdown','pointermove','pointerup','gotpointercapture','lostpointercapture'])document.addEventListener(type,e=>window.cadEvents.push([type,e.target.tagName,e.clientX,e.clientY]),true)}`);
  await drag(await point(3.5, 5), await point(4, 5.5));
  const sofaAfter = await evaluate('cadProject.getState().design.floors[0].furniture[0].position');
  if (!(sofaAfter.x > sofaBefore.x + .2)) {
    await capture('drag-failure');
    console.log(JSON.stringify({
      errors,
      selection: await evaluate('cadEditor.getState().selection'),
      events: await evaluate('cadEvents'),
      dirty: await evaluate('cadProject.getState().isDirty')
    }));
  }
  assert.ok(sofaAfter.x > sofaBefore.x + .2, JSON.stringify({
    sofaBefore,
    sofaAfter
  }));
  assert.equal(await evaluate('cadEditor.getState().past.length'), 1);
  await click('[aria-label="Undo"]');
  assert.equal(await evaluate('JSON.stringify(cadProject.getState().design)'), before);
  await click('[aria-label="Redo"]');
  assert.equal(await evaluate('cadProject.getState().design.floors[0].furniture[0].position.x'), sofaAfter.x);
  await click('[aria-label="Undo"]');
  // Numeric room resize accepts explicit units even when display units differ.
  const rp = await point(3, 7);
  await mouse('mousePressed', rp.x, rp.y, 1);
  await mouse('mouseReleased', rp.x, rp.y);
  await wait(120);
  await input('Width', '16 ft');
  assert.ok(Math.abs((await evaluate('cadProject.getState().design.floors[0].rooms[0].dimensions.width')) - 4.8768) < .001);
  await click('[aria-label="Undo"]');
  // Room corner resize creates exactly one history entry.
  await evaluate("cadEditor.getState().select({type:'room',id:'living'})");
  await wait(120);
  const handle = await rect('[data-handle="nw"]');
  await drag({
    x: handle.x + handle.width / 2,
    y: handle.y + handle.height / 2
  }, {
    x: handle.x + handle.width / 2 - 20,
    y: handle.y + handle.height / 2 - 20
  });
  assert.equal(await evaluate('cadEditor.getState().past.length'), 1);
  await click('[aria-label="Undo"]');
  // Wall-hosted window slide and undo.
  const winBefore = await evaluate('cadProject.getState().design.floors[0].windows[0].position.y');
  await drag(await point(1, 5), await point(1, 6));
  assert.ok((await evaluate('cadProject.getState().design.floors[0].windows[0].position.y')) > winBefore + .3);
  assert.ok(await evaluate('!!cadProject.getState().design.floors[0].windows[0].wall_id'));
  await click('[aria-label="Undo"]');
  // Split and undo inventory.
  await evaluate("cadEditor.getState().select({type:'room',id:'living'})");
  await wait(120);
  await evaluate(`Array.from(document.querySelectorAll('.cad-action-grid button')).find(b=>b.textContent.includes('Split front')).click()`);
  await wait(120);
  assert.equal(await evaluate('cadProject.getState().design.floors[0].rooms.length'), 3);
  await click('[aria-label="Undo"]');
  // Local AI response is one undoable command.
  await evaluate("cadEditor.getState().select({type:'furniture',id:'sofa'})");await wait(120);
  assert.ok(await evaluate("document.querySelector('.cad-ai-target').textContent.includes('Sofa')"));
  await evaluate(`{const e=document.querySelector('#cad-ai-prompt');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,'rotate sofa 90 degrees');e.dispatchEvent(new Event('input',{bubbles:true}))}`);
  await evaluate("document.querySelector('.cad-ai').requestSubmit()");
  await until('cadProject.getState().design.floors[0].furniture[0].rotation === 90');
  assert.equal(await evaluate('cadEditor.getState().past.length'), 1);
  await click('[aria-label="Undo"]');
  // Locks reject interaction and inspector edits are blocked.
  await evaluate("cadEditor.getState().setLayer('furniture',{locked:true})");
  await wait(100);
  const lockedBefore = await evaluate('JSON.stringify(cadProject.getState().design)');
  await drag(await point(3.5, 5), await point(4.5, 5));
  assert.equal(await evaluate('JSON.stringify(cadProject.getState().design)'), lockedBefore);
  await evaluate("cadEditor.getState().setLayer('furniture',{locked:false})");
  // Floor operations preserve one undo transaction.
  await click('[aria-label="Add floor"]');
  assert.equal(await evaluate('cadProject.getState().design.floors.length'), 2);
  await click('[aria-label="Undo"]');
  assert.equal(await evaluate('cadProject.getState().design.floors.length'), 1);
  // Stair setup creates a destination without switching away from its lower floor.
  await evaluate("cadProject.getState().setDraftDesign(d=>{d.floors[0].furniture[0].position.y=7.8;return d});cadEditor.getState().setOption('strict',true)");await wait(150);
  await click('[aria-label="Stair"]');
  await until("document.querySelector('.cad-stair-setup')");
  await evaluate("Array.from(document.querySelectorAll('.cad-stair-setup button')).find(b=>b.textContent.includes('Add upper')).click()");await wait(180);
  assert.equal(await evaluate('cadProject.getState().design.floors.length'),2);
  assert.equal(await evaluate('cadEditor.getState().activeFloorIndex'),0);
  const stairPoint=await point(3.5,4);
  await mouse('mousePressed',stairPoint.x,stairPoint.y,1);await mouse('mouseReleased',stairPoint.x,stairPoint.y);await wait(180);
  assert.equal(await evaluate('cadProject.getState().design.floors[0].stairs.length'),1);
  assert.equal(await evaluate('cadProject.getState().design.floors[1].stair_openings.length'),1);
  await click('[aria-label="Undo"]');await click('[aria-label="Undo"]');await click('[aria-label="Undo"]');
  // Responsive inspector must leave a visible, usable plan at every target size.
  // Strict mode rejects a newly introduced collision and creates no history.
  await evaluate("cadEditor.getState().setOption('strict',true);cadEditor.getState().setFloor(0)");
  await wait(120);
  const strictBefore=await evaluate('JSON.stringify(cadProject.getState().design)');
  await drag(await point(3.5,5),await point(8.5,5));
  assert.equal(await evaluate('JSON.stringify(cadProject.getState().design)'),strictBefore);
  await evaluate("cadEditor.getState().setOption('strict',false)");
  // The library contains distinct catalog variants without duplicate React keys.
  await click('[aria-label="Furniture"]');
  assert.ok(await evaluate("document.querySelectorAll('.cad-assets > button').length")>5);
  await click('[aria-label="Close panel"]');
  await click('[aria-label="Select"]');
  await evaluate("cadEditor.getState().setOption('strict',true)");
  for (const [w, h] of [[320, 568], [390, 844], [430, 932], [768, 1024], [844, 390], [1280, 900]]) {
    await metrics(w, h);
    await evaluate('dismissCadToasts()');
    await evaluate("cadEditor.getState().setOption('panel','inspector')");
    await wait(180);
    const panel = await rect('.cad-sidepanel'),
      canvas = await rect('.cad-canvas'),
      status = await rect('.cad-statusbar');
    assert.ok(panel.x >= -1 && panel.right <= w + 1 && panel.bottom <= h + 1, JSON.stringify({
      w,
      h,
      panel
    }));
    assert.ok(canvas.height > 100 && canvas.width > 150, JSON.stringify({
      w,
      h,
      canvas
    }));
    assert.ok(status.bottom <= h + 1, JSON.stringify({
      w,
      h,
      status
    }));
    assert.equal(await evaluate('document.documentElement.scrollWidth>innerWidth'), false);
    await capture(`cad-${w}-${h}`);
  }
  await metrics(390, 844);
  await evaluate("document.querySelector('#cad-ai-prompt').focus()");
  await until('cadEditor.getState().panelExpanded');
  assert.ok((await rect('.cad-sidepanel')).height>300);
  await capture('mobile-selection-ai-expanded');
  await click('[aria-label="Close panel"]');
  assert.ok((await rect('.cad-canvas')).height>400,'closing an expanded panel restores the canvas height');
  await evaluate("cadEditor.getState().setOption('panelExpanded',false)");
  // Touch move and cancellation (cancel never commits a draft).
  const touchFrom = await point(3.5, 5),
    touchTo = {
      x: touchFrom.x + 25,
      y: touchFrom.y - 15
    };
  const touch = (type, points) => send('Input.dispatchTouchEvent', {
    type,
    touchPoints: points
  }, sessionId);
  const touchInitial = await evaluate('JSON.stringify(cadProject.getState().design)');
  await touch('touchStart', [{
    ...touchFrom,
    id: 1
  }]);
  await wait(120);
  await touch('touchMove', [{
    ...touchTo,
    id: 1
  }]);
  await wait(120);
  await touch('touchCancel', []);
  await wait(120);
  assert.equal(await evaluate('JSON.stringify(cadProject.getState().design)'), touchInitial);
  // Pinch changes only the view; releasing both fingers must not create a command.
  if (await evaluate("!!document.querySelector('[aria-label=\"Close panel\"]')")) await click('[aria-label="Close panel"]');
  const pinchA=await point(10,12),pinchB=await point(12,12);
  const historyLength=await evaluate('cadEditor.getState().past.length');
  await touch('touchStart',[{...pinchA,id:3},{...pinchB,id:4}]);
  await touch('touchMove',[{x:pinchA.x-15,y:pinchA.y,id:3},{x:pinchB.x+15,y:pinchB.y,id:4}]);
  await touch('touchEnd',[]);await wait(120);
  assert.notEqual(await evaluate("document.querySelector('.cad-view-controls span').textContent"),'100%');
  assert.equal(await evaluate('cadEditor.getState().past.length'),historyLength);
  await click('[aria-label="Fit plan"]');
  const p = await point(3.5, 5);
  await touch('touchStart', [{
    ...p,
    id: 2
  }]);
  await wait(120);
  await touch('touchMove', [{
    x: p.x + 25,
    y: p.y - 15,
    id: 2
  }]);
  await wait(100);
  await touch('touchEnd', []);
  await wait(150);
  assert.notEqual(await evaluate('JSON.stringify(cadProject.getState().design)'), touchInitial);
  await click('[aria-label="Undo"]');
  assert.equal(await evaluate('JSON.stringify(cadProject.getState().design)'), touchInitial);
  fs.writeFileSync(path.join(temp, 'editor-layout.json'), await evaluate('JSON.stringify(cadProject.getState().design,null,2)'));
  // The only save entry point opens the existing version modal and persists the draft.
  await evaluate("cadProject.getState().setDraftDesign(d=>{d.floors[0].furniture[0].rotation=45;return d})");await wait(120);
  await click('.version-save-trigger');await until("document.querySelector('.save-version-modal')");
  await click('input[name="save-mode"][value="overwrite"]');await click('.save-version-submit');
  await until("!document.querySelector('.save-version-modal') && !cadProject.getState().isDirty");
  assert.equal(savedDesign.floors[0].furniture[0].rotation,45);
  // Approval failures show a concise toast and selectable diagnostics, not a wall of IDs.
  await click('[aria-label="Build 3D"]');await until("document.querySelector('.cad-diagnostics')");
  assert.equal(await evaluate('cadProject.getState().layoutValidation.report.critical_errors.length'),1);
  assert.equal(await evaluate("document.body.innerText.includes('wall_l0_part_012')"),false);
  assert.ok(await evaluate("document.querySelector('.cad-diagnostics').textContent.includes('shared wall')"));
  await capture('compact-approval-message');
  await click('.cad-diagnostics > button:not(.cad-repair-links)');
  assert.equal(await evaluate('cadEditor.getState().selection[0].id'),'bed_door');
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({
    geometryGestures: 'passed',
    transactionalUndo: 'passed',
    numericUnits: 'passed',
    hostedOpenings: 'passed',
    splitRooms: 'passed',
    aiDraftUndo: 'passed',
    layers: 'passed',
    floorManagement: 'passed',
    guidedStairPlacement:'passed in strict mode with an aligned upper opening',
    selectionContext:'passed',
    singleSaveFlow:'passed',
    approvalDiagnostics:'passed',
    responsiveSizes: 6,
    touchMoveAndCancel: 'passed',
    strictCollisions: 'passed',
    assetPalette: 'passed',
    pinchZoom: 'passed',
    artifacts: temp
  }, null, 2));
} finally {
  socket?.close();
  browser?.kill();
  await server.close();
}
