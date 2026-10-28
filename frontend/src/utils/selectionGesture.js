const gestures = new WeakMap()
const CLICK_DISTANCE = 5
const CLICK_DURATION = 350

export function trackSelectionGestures(canvas, eventTarget, now = () => performance.now()) {
  let gesture = null
  const down = (event) => {
    gesture = { pointerId: event.pointerId, x: event.clientX, y: event.clientY,
      startedAt: now(), completed: false, cancelled: event.button !== 0, now }
    gestures.set(canvas, gesture)
  }
  const move = (event) => {
    if (!gesture || event.pointerId !== gesture.pointerId || gesture.completed) return
    if (Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y) >= CLICK_DISTANCE) gesture.cancelled = true
  }
  const up = (event) => {
    if (!gesture || event.pointerId !== gesture.pointerId) return
    move(event)
    gesture.completed = true
    gesture.endedAt = now()
    if (gesture.endedAt - gesture.startedAt > CLICK_DURATION) gesture.cancelled = true
  }
  const cancel = () => { if (gesture) gesture.cancelled = true }
  canvas.addEventListener('pointerdown', down, true)
  eventTarget.addEventListener('pointermove', move, true)
  eventTarget.addEventListener('pointerup', up, true)
  eventTarget.addEventListener('pointercancel', cancel, true)
  eventTarget.addEventListener('blur', cancel)
  return {
    cancel,
    dispose() {
      canvas.removeEventListener('pointerdown', down, true)
      eventTarget.removeEventListener('pointermove', move, true)
      eventTarget.removeEventListener('pointerup', up, true)
      eventTarget.removeEventListener('pointercancel', cancel, true)
      eventTarget.removeEventListener('blur', cancel)
      gestures.delete(canvas)
    },
  }
}

export function isSelectionClick(event) {
  const source = event.sourceEvent || event.nativeEvent || event
  const gesture = gestures.get(source.target)
  return source.button === 0 && Boolean(gesture?.completed && !gesture.cancelled
    && gesture.now() - gesture.endedAt < 150)
}
