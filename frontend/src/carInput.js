const actions = new Set(['forward','reverse','left','right'])
export function keyAction(code) {
  return {KeyW:'forward',ArrowUp:'forward',KeyS:'reverse',ArrowDown:'reverse',
    KeyA:'left',ArrowLeft:'left',KeyD:'right',ArrowRight:'right'}[code] ?? null
}

export function createCarInput() {
  const held = new Map(), suppressed = new Set()
  return {
    press(token, action) {
      if (!actions.has(action) || suppressed.has(token) || held.has(token)) return false
      held.set(token, action)
      return true
    },
    release(token) { const action = held.get(token); held.delete(token); suppressed.delete(token); return action },
    cancel() { for (const token of held.keys()) suppressed.add(token); held.clear() },
    held() { return [...held.values()] },
    intent() {
      const values = new Set(held.values())
      return {
        direction:values.has('forward') === values.has('reverse') ? null : values.has('forward') ? 'FWD' : 'REV',
        steering:values.has('left') === values.has('right') ? 'CENTER' : values.has('left') ? 'LEFT' : 'RIGHT',
      }
    },
  }
}
