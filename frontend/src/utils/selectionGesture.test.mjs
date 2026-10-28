import assert from 'node:assert/strict'
import test from 'node:test'
import { isSelectionClick, trackSelectionGestures } from './selectionGesture.js'

function setup(t) {
  const canvas = new EventTarget(), window = new EventTarget()
  let time = 0
  const tracker = trackSelectionGestures(canvas, window, () => time)
  t.after(() => tracker.dispose())
  const dispatch = (target, type, x = 10, y = 20, button = 0) => {
    const event = new Event(type)
    Object.assign(event, { clientX: x, clientY: y, pointerId: 1, button })
    target.dispatchEvent(event)
  }
  return { down: (button = 0) => dispatch(canvas, 'pointerdown', 10, 20, button),
    move: (x, y) => dispatch(window, 'pointermove', x, y),
    up: () => dispatch(window, 'pointerup'), cancel: tracker.cancel,
    elapsed: (ms) => { time += ms },
    click: () => isSelectionClick({ sourceEvent: { target: canvas, button: 0 } }),
    blur: () => dispatch(window, 'blur'),
  }
}

test('selection happens on a completed short click, never on pointer down', (t) => {
  const gesture = setup(t)
  gesture.down()
  assert.equal(gesture.click(), false)
  gesture.elapsed(80)
  gesture.up()
  assert.equal(gesture.click(), true)
  gesture.elapsed(200)
  assert.equal(gesture.click(), false)
})

test('holding the left button does not select even when released without movement', (t) => {
  const gesture = setup(t)
  gesture.down()
  gesture.elapsed(500)
  assert.equal(gesture.click(), false)
  gesture.up()
  assert.equal(gesture.click(), false)
})

test('camera drag stays cancelled even when the pointer returns to the starting point', (t) => {
  const gesture = setup(t)
  gesture.down()
  gesture.move(80, 20)
  gesture.move(10, 20)
  gesture.elapsed(80)
  gesture.up()
  assert.equal(gesture.click(), false)
})

test('right click, gizmo interaction, and losing focus never change selection', (t) => {
  const gesture = setup(t)
  gesture.down(2)
  gesture.up()
  assert.equal(gesture.click(), false)
  gesture.down()
  gesture.cancel()
  gesture.up()
  assert.equal(gesture.click(), false)
  gesture.down()
  gesture.blur()
  gesture.up()
  assert.equal(gesture.click(), false)
})
