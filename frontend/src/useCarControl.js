import {computed, onBeforeUnmount, onMounted, reactive} from 'vue'
import {createCarInput, keyAction} from './carInput.js'
const API = 'http://127.0.0.1:8000/car'

export function useCarControl() {
  const input = createCarInput()
  let session = null, sequence = 0, generation = 0, intentBusy = false, stopping = null, destroyed = false
  let heartbeatTimer, pollTimer
  const model = reactive({status:{connected:false,identified:false,feedback_fresh:false,telemetry:null,received_at:0,session:null,phase:'未连接'},
    devices:[],selected:'',enabled:false,held:[],busy:false,error:'',notice:'',apiOnline:false,apiError:'',
    feedback:computed(() => model.apiOnline && model.status.feedback_fresh && model.status.telemetry &&
      Date.now()/1000-model.status.received_at>=0 && Date.now()/1000-model.status.received_at<1 ? model.status.telemetry : null),
    canEnable:computed(() => model.apiOnline && model.status.connected && model.status.identified && Boolean(model.status.session) && !model.busy),
  })
  function syncHeld() { model.held = input.held() }
  function clearInput() { input.cancel(); syncHeld(); model.enabled = false; generation++ }
  async function request(path, body, timeout = 5000, keepalive = false) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), timeout)
    try {
      const response = await fetch(API+path, {signal:controller.signal,keepalive,
        ...(body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})})
      const result = await response.json()
      if (!response.ok) throw new Error(response.status === 404
        ? '当前后台未加载小车接口（404）。请关闭旧的 J280 Showcase Backend / Frontend 窗口后重新运行 START_SHOWCASE.bat。'
        : typeof result.detail === 'string' ? result.detail : result.detail?.message || `小车请求被拒绝（${response.status}）`)
      return result
    } finally { clearTimeout(timer) }
  }
  async function stop(reason = '遥控已取消', keepEnabled = false) {
    clearInput()
    const stopGeneration = generation
    if (stopping) return stopping
    const token = session || model.status.session
    session = null
    model.notice = `${reason}，等待停车读回`
    if (!token) { model.notice = '遥控未启用'; return }
    let parkingConfirmed = false
    stopping = (async () => {
      try {
        const result = await request('/stop', {session:token}, 5000, true)
        if (!destroyed) {
          model.status = result; session = result.session; sequence = 0
          parkingConfirmed = true
          const resume = keepEnabled && generation === stopGeneration
          generation++
          if (resume) {
            const resumeGeneration = generation, resumeToken = session
            await request('/intent', {session:resumeToken,sequence:++sequence,direction:null,steering:'CENTER'}, 800)
            if (!destroyed && generation === resumeGeneration && session === resumeToken) model.enabled = true
          }
          model.notice = model.enabled ? '行驶输入已释放，停车并回正；再次按住可操作' : '停车结果以车辆新反馈为准；重新操作前启用遥控'
        }
      } catch (error) { model.error = parkingConfirmed ? `停车已确认，遥控未恢复：${error.message}` : `停车结果未知：${error.message}；遥控已取消` }
      finally { stopping = null }
    })()
    return stopping
  }
  async function sendIntent(neutral = false) {
    if ((!model.enabled && !neutral) || !session || intentBusy || stopping) return false
    const token = session, currentGeneration = generation
    intentBusy = true
    try {
      await request('/intent', {session:token,sequence:++sequence,...(neutral ? {direction:null,steering:'CENTER'} : input.intent())}, 800)
      return currentGeneration === generation && session === token
    } catch (error) {
      if (currentGeneration === generation && session === token) { model.error = `遥控输入中断：${error.message}`; void stop('输入中断') }
      return false
    } finally { intentBusy = false }
  }
  async function enable() {
    if (!model.canEnable || stopping) return
    clearInput(); model.error = ''; model.busy = true
    const currentGeneration = generation
    try {
      // 刷新页面只观察已有连接；用户显式启用时先确认停车并取得新 token。
      if (!session || session !== model.status.session) {
        const result = await request('/stop', {session:model.status.session})
        if (destroyed) return
        const cancelled = currentGeneration !== generation
        model.status = result; session = result.session; sequence = 0; generation++
        if (cancelled) return
      }
      if (await sendIntent(true)) { model.enabled = true; model.notice = '遥控已启用，先打方向，再前进／后退' }
    }
    catch (error) { session = null; model.error = `遥控接管结果未知：${error.message}；尚未启用` }
    finally { model.busy = false }
  }
  function press(token, action) {
    if (model.enabled && model.canEnable && !stopping && input.press(token, action)) { syncHeld(); void sendIntent() }
  }
  function release(token) {
    const action = input.release(token)
    syncHeld()
    if (action === 'forward' || action === 'reverse') void stop('行驶输入已释放', true)
    else if (action) void sendIntent()
  }
  async function scan() {
    if (!model.apiOnline || model.busy || model.status.connected) return
    model.busy = true; model.error = ''; model.devices = []; model.selected = ''
    try { const result = await request('/scan', {}, 12000); model.devices = result.devices; model.notice = result.devices.length ? '请手动选择小车' : '未找到设备，请确认供电与电脑蓝牙' }
    catch (error) { model.error = error.message }
    finally { model.busy = false }
  }
  async function connect() {
    if (!model.apiOnline || model.busy || !model.selected || model.status.connected) return
    clearInput(); model.busy = true; model.error = ''; model.notice = '正在核对车辆身份与停车状态'
    const currentGeneration = generation
    try {
      const result = await request('/connect', {device_id:model.selected}, 20000)
      if (!destroyed) {
        const cancelled = currentGeneration !== generation
        model.status = result; model.apiOnline = true; session = result.session; sequence = 0; generation++; model.notice = '连接已验证，遥控尚未启用'
        if (cancelled) void stop('连接期间页面状态已变化')
      }
    } catch (error) { model.error = error.message; session = null }
    finally { model.busy = false }
  }
  async function disconnect() {
    clearInput()
    if (stopping) await stopping
    if ((!session && !model.status.session) || model.busy) return
    const token = session || model.status.session
    session = null; model.busy = true; model.error = ''
    try { model.status = await request('/disconnect', {session:token}, 5000); model.notice = '已断开，重新连接需手动选择' }
    catch (error) { model.error = `断开结果未知：${error.message}` }
    finally { model.busy = false }
  }
  async function poll() {
    if (destroyed) return
    const currentGeneration = generation
    try {
      const result = await request('/status', undefined, 1500)
      if (!destroyed) {
        model.apiOnline = true; model.apiError = ''
        if (!stopping && !model.busy && generation === currentGeneration) {
          model.status = result
          if (!result.connected || (session && result.session !== session)) { clearInput(); session = null }
        }
      }
    } catch (error) {
      if (!destroyed) {
        model.apiOnline = false
        model.apiError = error.message.includes('404') ? error.message : '无法连接小车后台（127.0.0.1:8000）。请检查后台窗口，并使用 http://localhost:5173 打开网页。'
        if (model.enabled) void stop('后端连接中断')
      }
    } finally { if (!destroyed) pollTimer = setTimeout(poll, 150) }
  }
  function keydown(event) {
    if (!model.enabled) return
    if (event.code === 'Space' || event.code === 'Escape') { event.preventDefault(); void stop('键盘停止'); return }
    if (event.target.closest?.('input,select,textarea,[contenteditable="true"]')) return
    const action = keyAction(event.code)
    if (action) { event.preventDefault(); if (!event.repeat) press(`key:${event.code}`, action) }
  }
  function keyup(event) { if (keyAction(event.code)) release(`key:${event.code}`) }
  function deactivate(reason) { if (session) return stop(reason); clearInput() }
  function loseFocus() { void deactivate('页面已失去焦点') }
  function visibility() { if (document.hidden) loseFocus() }
  onMounted(() => {
    void poll(); heartbeatTimer = setInterval(() => { if (model.enabled) void sendIntent() }, 70)
    window.addEventListener('keydown', keydown); window.addEventListener('keyup', keyup)
    window.addEventListener('blur', loseFocus); window.addEventListener('pagehide', loseFocus)
    document.addEventListener('visibilitychange', visibility)
  })
  onBeforeUnmount(() => {
    void deactivate('页面已关闭'); destroyed = true; clearInterval(heartbeatTimer); clearTimeout(pollTimer)
    window.removeEventListener('keydown', keydown); window.removeEventListener('keyup', keyup)
    window.removeEventListener('blur', loseFocus); window.removeEventListener('pagehide', loseFocus)
    document.removeEventListener('visibilitychange', visibility)
  })
  return Object.assign(model, {scan,connect,disconnect,enable,stop,deactivate,press,release})
}
