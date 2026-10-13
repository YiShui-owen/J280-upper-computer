<template>
  <main class="instrument-shell">
    <header class="topbar">
      <h1>J280 <span>车载旋转倒立摆</span></h1>
      <div class="system-tools">
        <button class="text-button" @click="settingsDialog.showModal()">设置</button>
        <button class="button primary" disabled title="连接小车后可启用遥控">启用遥控</button>
        <button class="button stop" disabled title="等待小车连接">停止小车</button>
        <button v-if="state.received_at" class="button stop hardware-stop" @click="send('STOP')">停止摆控</button>
      </div>
    </header>

    <section class="mechanical-stage" aria-label="车载旋转倒立摆一体化展示">
        <DigitalTwin3D
          ref="digitalTwin"
          :arm-angle="Number(state.arm_angle_deg || 0)"
          :pendulum-angle="Number(state.angle_deg || 0)"
          :mode="state.mode_name"
          :sample-time="state.received_at"
          :sample-tick="state.fpga_time_ms ?? null"
          :arm-velocity="state.arm_velocity_deg_s"
          :pendulum-velocity="state.angle_velocity_deg_s"
          :left-wheel-count="car.left_count"
          :right-wheel-count="car.right_count"
          :steering-request="car.servo_compare"
        />
      <aside class="pendulum-readouts" aria-label="摆控关键指标">
        <h2>倒立摆</h2>
        <strong class="system-state" :class="modeClass" role="status"><i></i>{{ modeLabel }}</strong>
        <dl class="readouts" :class="{ stale:!online }">
          <div v-for="metric in showcaseMetrics" :key="metric.key" class="readout" :class="metric.key">
            <dt>{{ metric.label }}<span v-if="metric.symbol">{{ metric.symbol }}</span></dt>
            <dd :class="metric.tone"><strong>{{ metric.value }}</strong><small>{{ metric.unit }}</small></dd>
          </div>
        </dl>
      </aside>
      <aside class="car-readouts" aria-label="移动平台反馈">
        <h2>底盘</h2>
        <strong class="car-phase" :class="{ running:carRunning }"><i></i>{{ carPhase }}</strong>
        <dl class="readouts">
          <div class="readout car-pwm">
            <dt>左右驱动 PWM</dt>
            <dd><strong>{{ fmt(car.left_pwm8400 == null ? null : car.left_pwm8400 / 84, 1) }}</strong><small>%</small><span class="readout-separator">/</span><strong>{{ fmt(car.right_pwm8400 == null ? null : car.right_pwm8400 / 84, 1) }}</strong><small>%</small></dd>
          </div>
          <div class="readout car-encoder"><dt>左右轮计数</dt><dd><strong>{{ car.left_count ?? '--' }}</strong><span class="readout-separator">/</span><strong>{{ car.right_count ?? '--' }}</strong></dd></div>
          <div class="readout car-steering"><dt>转向指令</dt><dd><strong>{{ steeringLabel }}</strong></dd></div>
        </dl>
        <section class="car-main-controls" aria-label="小车遥控">
          <CarControlPad />
        </section>
      </aside>
    </section>

    <section class="waveform-section" aria-label="摆控实时响应">
      <header class="waveform-heading"><h2>摆控波形</h2><span title="悬停显示最近 30 秒，移开恢复 10 秒">最近 {{ waveformWindowMs / 1000 }} 秒</span></header>
      <WaveformPanel layout="horizontal" :samples="chartSamples" :now="chartNow" :events="events" @window-change="waveformWindowMs = $event" />
    </section>

    <dialog ref="settingsDialog" class="engineering-dialog" @click="closeOnBackdrop">
      <header class="dialog-heading"><h2>设置</h2><button class="icon-button" aria-label="关闭设置" @click="settingsDialog.close()">×</button></header>
      <CarControlPanel />
      <section class="hardware-settings">
        <h3>实机摆控 · V5.12</h3>
        <div class="debug-actions"><button class="button primary compact" @click="send('START')">自动启动</button><button class="button stop compact" @click="send('STOP')">停止摆控</button></div>
        <p>命令由原 tuner 执行；写入成功不代表动作完成，参数生效请核对实际遥测。</p>
        <div class="control-info"><span>{{ state.control_mode_name || 'TRUE CASCADE' }}</span><span>角度环 1 ms</span><span>位置环 10 ms</span><span>50 MHz</span></div>
      </section>
      <form @submit.prevent="applyPid">
        <h3>PID 参数</h3>
        <div class="pid-fields">
          <label v-for="(_, key) in params" :key="key">{{ key.toUpperCase() }}<input v-model.number="params[key]" type="number" min="0" step="1" required /></label>
        </div>
        <button class="button primary compact" type="submit">下发 PID</button>
      </form>
      <div class="engineering-row"><span>机械姿态映射</span><button class="button compact" @click="openCalibration">姿态标定</button></div>
      <dl class="engineering-readouts">
        <div><dt>编码器</dt><dd>{{ state.encoder ?? '--' }}</dd></div>
        <div><dt>位置误差</dt><dd>{{ state.position_error ?? '--' }}</dd></div>
        <div><dt>参考角</dt><dd>{{ fmt(state.alpha_ref_deg, 3) }}°</dd></div>
        <div><dt>故障码</dt><dd :class="{ 'fault-text':state.fault }">0x{{ hex2(state.fault) }}</dd></div>
        <div><dt>旋臂角速度</dt><dd>{{ fmt(state.arm_velocity_deg_s, 1) }} °/s</dd></div>
        <div><dt>D Filter</dt><dd>{{ fmt(state.d_filter, 4) }}</dd></div>
      </dl>
      <details class="debug-tools">
        <summary>调试工具</summary>
        <div class="debug-actions"><button class="button compact" @click="probe('+')">+12 q2 扰动</button><button class="button compact" @click="probe('-')">−12 q2 扰动</button></div>
        <p>现场操作请保持旋臂运动区域净空。</p>
      </details>
    </dialog>
    <div v-if="toast" class="toast" role="status">{{ toast }}</div>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'
import DigitalTwin3D from './DigitalTwin3D.vue'
import WaveformPanel from './WaveformPanel.vue'
import CarControlPanel from './CarControlPanel.vue'
import CarControlPad from './CarControlPad.vue'

// 小车功能待实物联调；当前页面仅呈现待接入界面，不生成反馈或发送控制。
const car = Object.freeze({ left_count:null, right_count:null, left_pwm8400:null, right_pwm8400:null, servo_compare:null })
const carRunning = false
const carPhase = '未连接'
const steeringLabel = '--'

const API = 'http://127.0.0.1:8000'
const WS = 'ws://127.0.0.1:8000/ws'
const HISTORY_MS = 30000

const state = reactive({
  mode_name: 'WAITING', angle_deg: 0, angle_velocity_deg_s: 0,
  encoder: 0, arm_angle_deg: 0, arm_velocity_deg_s: 0,
  duty_actual_percent: 0, position_error: 0, alpha_ref_deg: 0,
  fault: 0, akp: 38, akd: 120, pkp: 28, pki: 0, pkd: 160,
  d_filter: 0.1848, received_at: 0,
})
const params = reactive({ akp: 38, akd: 120, pkp: 28, pkd: 160 })
const samples = ref([])
const chartSamples = shallowRef([])
const chartNow = ref(Date.now())
const waveformWindowMs = ref(10000)
const events = shallowRef([])
const settingsDialog = ref(null)
const digitalTwin = ref(null)
const toast = ref('')
const clock = ref(Date.now())
let eventId = 0
let ws = null
let onlineTimer = null
let chartRenderTimer = null
let reconnectTimer = null
let destroyed = false

const online = computed(() => Boolean(state.received_at) && clock.value / 1000 - Number(state.received_at) < 2)
const modeClass = computed(() => !online.value ? 'idle' : ({ BALANCE:'balance', SWING:'swing', FAULT:'fault', ZERO:'zero' }[state.mode_name] || 'idle'))
const modeLabel = computed(() => !online.value ? (state.received_at ? '数据中断' : '无数据') : ({ BALANCE:'平衡', SWING:'起摆', FAULT:'故障', ZERO:'归零', IDLE:'待机' }[state.mode_name] || '待机'))
const rmsAngle = computed(() => {
  // New telemetry may arrive between the 500 ms connection-status ticks.
  const nowSec = Math.max(clock.value, Date.now()) / 1000
  const vals = samples.value
    .filter(s => nowSec - Number(s.received_at || 0) <= 3 && nowSec >= Number(s.received_at || 0))
    .map(s => s.angle_deg == null ? NaN : Number(s.angle_deg))
    .filter(Number.isFinite)
  return vals.length ? Math.sqrt(vals.reduce((sum, v) => sum + v * v, 0) / vals.length) : null
})
// Field definitions keep the presentation independent of a particular mechanism.
const metrics = computed(() => [
  { key:'angle', label:'摆杆偏角', symbol:'α', value:reading(state.angle_deg, 3), unit:'°', tone:'cyan' },
  { key:'velocity', label:'摆杆角速度', symbol:'ω', value:reading(state.angle_velocity_deg_s, 2), unit:'°/s', tone:'' },
  { key:'arm', label:'旋臂角度', symbol:'θ', value:reading(state.arm_angle_deg, 2), unit:'°', tone:'' },
  { key:'pwm', label:'PWM', value:state.received_at ? fmtSigned(state.duty_actual_percent, 1) : '--', unit:'%', tone:'amber' },
  { key:'rms', label:'3 秒 RMS', value:rmsAngle.value === null ? '--' : rmsAngle.value.toFixed(3), unit:'°', tone:'' },
])
const showcaseMetrics = computed(() => ['angle', 'arm', 'rms'].map(key => metrics.value.find(metric => metric.key === key)))
const pwmFillStyle = computed(() => {
  const duty = Number(state.duty_actual_percent || 0)
  const width = Math.min(50, Math.abs(duty) / 60 * 50)
  return { left:`${duty >= 0 ? 50 : 50 - width}%`, width:`${width}%` }
})

function fmt(v, digits = 2){ return v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(digits) : '--' }
function reading(v, digits){ return state.received_at ? fmt(v, digits) : '--' }
function fmtSigned(v, digits = 1){
  if (!Number.isFinite(Number(v))) return '--'
  const n = Number(v)
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}`
}
function hex2(v){ return Number(v || 0).toString(16).toUpperCase().padStart(2, '0') }
function delay(ms){ return new Promise(resolve => setTimeout(resolve, ms)) }
function showToast(message){
  toast.value = message
  const current = message
  setTimeout(() => { if (toast.value === current) toast.value = '' }, 2200)
}
function closeOnBackdrop(event){ if (event.target === settingsDialog.value) settingsDialog.value.close() }
function openCalibration(){
  settingsDialog.value.close()
  digitalTwin.value?.openCalibration()
}
// General event interface: only record confirmed actions, never synthetic activity.
function recordEvent(label, at = Date.now()){
  events.value = [...events.value, { id:++eventId, at, label }].filter(event => event.at >= at - HISTORY_MS)
  scheduleCharts()
}

async function send(command, { quiet = false } = {}){
  try{
    const response = await fetch(`${API}/command`, {
      method:'POST', headers:{ 'Content-Type':'application/json' },
      body:JSON.stringify({ command }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || 'command failed')
    if (!quiet) showToast(`已发送：${command}`)
    return true
  }catch(error){
    showToast(`命令失败：${error.message}`)
    return false
  }
}
async function probe(direction){
  const ampOk = await send('PROBEAMP=12', { quiet:true })
  if (!ampOk) return
  await delay(120)
  const probeOk = await send(`PROBE=${direction}`, { quiet:true })
  if (!probeOk) return
  recordEvent(`扰动 ${direction}12 q2`)
  showToast(`已施加 ${direction}12 q2 扰动`)
}
async function applyPid(){
  for (const [key, value] of Object.entries(params)){
    const ok = await send(`${key.toUpperCase()}=${Math.max(0, Number(value) || 0)}`, { quiet:true })
    if (!ok) return
  }
  showToast('PID 参数已下发')
}

function scheduleCharts(){
  if (chartRenderTimer) return
  chartRenderTimer = setTimeout(() => {
    chartRenderTimer = null
    const now = Date.now()
    samples.value = samples.value.filter(sample => Number(sample.received_at) * 1000 >= now - HISTORY_MS)
    chartSamples.value = samples.value.slice()
    chartNow.value = now
    events.value = events.value.filter(event => event.at >= now - HISTORY_MS)
  }, 70)
}
function applyTelemetry(data, pushSample = true){
  if (!data || typeof data !== 'object') return
  Object.assign(state, data)
  params.akp = data.akp ?? params.akp
  params.akd = data.akd ?? params.akd
  params.pkp = data.pkp ?? params.pkp
  params.pkd = data.pkd ?? params.pkd
  if (pushSample){
    samples.value.push(data)
  }
  scheduleCharts()
}
async function loadSnapshot(){
  try{
    const response = await fetch(`${API}/snapshot`)
    const data = await response.json()
    if (Array.isArray(data.history) && data.history.length) samples.value = [...data.history]
    if (data.latest) applyTelemetry(data.latest, false)
    scheduleCharts()
  }catch(_error){}
}
function connectWs(){
  if (destroyed) return
  ws = new WebSocket(WS)
  ws.onmessage = event => {
    try{
      const message = JSON.parse(event.data)
      if (message.type === 'telemetry') applyTelemetry(message.data)
    }catch(_error){}
  }
  ws.onclose = () => {
    if (!destroyed) reconnectTimer = setTimeout(connectWs, 1000)
  }
  ws.onerror = () => { try{ ws.close() }catch(_error){} }
}
onMounted(async () => {
  await loadSnapshot()
  connectWs()
  onlineTimer = setInterval(() => { clock.value = Date.now(); scheduleCharts() }, 500)
})
onBeforeUnmount(() => {
  destroyed = true
  if (onlineTimer) clearInterval(onlineTimer)
  if (chartRenderTimer) clearTimeout(chartRenderTimer)
  if (reconnectTimer) clearTimeout(reconnectTimer)
  try{ ws?.close() }catch(_error){}
})
</script>
