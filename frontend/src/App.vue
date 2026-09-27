<template>
  <main class="dashboard-shell">
    <header class="topbar panel">
      <div class="brand-block">
        <div class="logo-mark"><span></span></div>
        <div>
          <div class="eyebrow">FPGA REAL-TIME CONTROL · J280</div>
          <h1>旋转倒立摆实时姿态控制系统</h1>
        </div>
      </div>

      <div class="mode-beacon" :class="modeClass">
        <i></i>
        <div>
          <span>SYSTEM STATE</span>
          <strong>{{ state.mode_name || 'WAITING' }}</strong>
        </div>
      </div>

      <div class="status-cluster">
        <span class="status-pill" :class="online ? 'ok' : 'bad'"><i></i>{{ online ? '系统在线' : '数据断开' }}</span>
        <span class="status-pill">V5.12</span>
        <span class="status-pill">50 MHz</span>
        <span class="status-pill accent">TRUE CASCADE</span>
        <button class="settings-ghost" @click="settingsOpen = true">工程设置</button>
      </div>
    </header>

    <section class="main-grid">
      <aside class="instrument-column left-column">
        <div class="column-title"><span>CONTROLLED VARIABLES</span><b>被控量</b></div>

        <article class="readout-card panel featured">
          <div class="readout-top"><span class="symbol">α</span><em>摆杆偏角</em></div>
          <strong class="readout-value">{{ fmt(state.angle_deg, 3) }}<small>°</small></strong>
          <div class="readout-foot"><span>目标 0.000°</span><span :class="angleStateClass">{{ angleStateText }}</span></div>
          <div class="spark-line"><i :style="{ width: angleBar + '%' }"></i></div>
        </article>

        <article class="readout-card panel">
          <div class="readout-top"><span class="symbol">ω</span><em>摆杆角速度</em></div>
          <strong class="readout-value">{{ fmt(state.angle_velocity_deg_s, 1) }}<small>°/s</small></strong>
          <div class="readout-foot"><span>实时角速度</span><span>α̇</span></div>
        </article>

        <article class="readout-card panel">
          <div class="readout-top"><span class="symbol">θ</span><em>旋臂角度</em></div>
          <strong class="readout-value">{{ fmt(state.arm_angle_deg, 1) }}<small>°</small></strong>
          <div class="readout-foot"><span>ENC {{ state.encoder ?? 0 }}</span><span>{{ fmt(state.arm_velocity_deg_s, 1) }}°/s</span></div>
        </article>

        <div class="aux-strip panel">
          <div><span>位置误差</span><b>{{ state.position_error ?? 0 }}</b></div>
          <div><span>参考角</span><b>{{ fmt(state.alpha_ref_deg, 2) }}°</b></div>
          <div><span>故障码</span><b :class="state.fault ? 'fault-text' : ''">0x{{ hex2(state.fault || 0) }}</b></div>
        </div>
      </aside>

      <article class="visual-card panel">
        <div class="visual-heading">
          <div><span>3D DIGITAL TWIN</span><b>实时机械姿态映射</b></div>
          <div class="camera-lock"><i></i> INTERACTIVE 3/4 VIEW</div>
        </div>

        <div class="digital-twin-3d">
          <DigitalTwin3D
            :arm-angle="Number(state.arm_angle_deg || 0)"
            :pendulum-angle="Number(state.angle_deg || 0)"
            :mode="state.mode_name"
            :sample-time="state.received_at"
            :sample-tick="state.fpga_time_ms ?? null"
            :arm-velocity="state.arm_velocity_deg_s"
            :pendulum-velocity="state.angle_velocity_deg_s"
          />
        </div>

        <div class="control-strip">
          <button class="btn primary" @click="send('START')">自动启动</button>
          <button class="btn probe" @click="probe('+')">+12 q2 扰动</button>
          <button class="btn probe" @click="probe('-')">−12 q2 扰动</button>
          <button class="btn danger" @click="send('STOP')">停止</button>
        </div>
        <p class="safety-note">命令复用 V5.12 tuner 的 HOME-M29 / mailbox 流程；现场演示请保持旋臂运动区域净空。</p>
      </article>

      <aside class="instrument-column right-column">
        <div class="column-title"><span>CONTROL & ARCHITECTURE</span><b>控制侧</b></div>

        <article class="readout-card panel pwm-card">
          <div class="readout-top"><span class="symbol wide">PWM</span><em>电机输出</em></div>
          <strong class="readout-value">{{ fmtSigned(state.duty_actual_percent, 1) }}<small>%</small></strong>
          <div class="pwm-scale"><span class="zero"></span><i :class="pwmPositive ? 'positive' : 'negative'" :style="pwmFillStyle"></i></div>
          <div class="readout-foot"><span>−60%</span><span>LIMIT ±60%</span><span>+60%</span></div>
        </article>

        <article class="readout-card panel rms-card">
          <div class="readout-top"><span class="symbol wide">RMS</span><em>近 3 s 角度 RMS</em></div>
          <strong class="readout-value">{{ rmsAngle === null ? '--' : rmsAngle.toFixed(3) }}<small>°</small></strong>
          <div class="rms-state" :class="rmsStateClass"><i></i>{{ rmsStateText }}</div>
        </article>

        <article class="architecture-card panel">
          <div class="arch-heading"><span>CONTROL ARCHITECTURE</span><b>只读</b></div>
          <div class="arch-row"><span>控制模式</span><b>TRUE CASCADE</b></div>
          <div class="arch-row"><span>角度内环</span><b>1 ms · 1 kHz</b></div>
          <div class="arch-row"><span>位置外环</span><b>10 ms · 100 Hz</b></div>
          <div class="arch-row"><span>Angle PID</span><b>{{ state.akp || 38 }} / {{ state.akd || 120 }}</b></div>
          <div class="arch-row"><span>Position PID</span><b>{{ state.pkp || 28 }} / {{ state.pki ?? 0 }} / {{ state.pkd || 160 }}</b></div>
          <div class="arch-row"><span>D Filter</span><b>{{ fmt(state.d_filter || 0.1848, 4) }}</b></div>
        </article>
      </aside>
    </section>

    <section class="bottom-grid">
      <article class="chart-card panel angle-chart-card">
        <div class="chart-heading">
          <div><span>STABILITY RESPONSE</span><b>摆杆角度实时响应</b></div>
          <div class="legend"><span><i class="cyan"></i>α 实测</span><span><i class="purple"></i>α 目标</span></div>
        </div>
        <div ref="angleChartRef" class="chart"></div>
      </article>

      <article class="recovery-card panel" :class="disturbanceClass">
        <div class="recovery-heading">
          <div><span>DISTURBANCE RECOVERY</span><b>最近一次扰动</b></div>
          <button v-if="disturbance.startedAt" @click="resetDisturbance">清除</button>
        </div>

        <div class="event-chip">
          <i></i>
          <div>
            <span>{{ disturbancePhaseLabel }}</span>
            <strong>{{ disturbanceDirectionLabel }}</strong>
          </div>
        </div>

        <div class="recovery-metrics">
          <div><span>峰值偏角</span><b>{{ disturbance.startedAt ? `${disturbance.peak.toFixed(2)}°` : '--' }}</b></div>
          <div><span>恢复时间</span><b>{{ disturbance.recoveryTime === null ? '--' : `${disturbance.recoveryTime.toFixed(2)} s` }}</b></div>
          <div><span>恢复后 RMS</span><b>{{ recoveryRms === null ? '--' : `${recoveryRms.toFixed(3)}°` }}</b></div>
        </div>
        <p class="recovery-rule">恢复判定：BALANCE 且 |α| &lt; 0.5°、|α̇| &lt; 5°/s 持续 0.35 s</p>
      </article>

      <article class="chart-card panel pwm-chart-card">
        <div class="chart-heading">
          <div><span>CONTROL EFFORT</span><b>PWM 控制输出</b></div>
        </div>
        <div ref="controlChartRef" class="chart"></div>
      </article>
    </section>

    <div v-if="settingsOpen" class="settings-backdrop" @click.self="settingsOpen = false">
      <section class="settings-panel panel">
        <button class="settings-close" @click="settingsOpen = false">×</button>
        <div class="settings-copy">
          <span>ENGINEERING SETTINGS</span>
          <h3>工程参数</h3>
          <p>比赛展示时保持关闭；这里只保留原有 PID 下发能力。</p>
        </div>
        <label>AKP <input v-model.number="params.akp" type="number" /></label>
        <label>AKD <input v-model.number="params.akd" type="number" /></label>
        <label>PKP <input v-model.number="params.pkp" type="number" /></label>
        <label>PKD <input v-model.number="params.pkd" type="number" /></label>
        <button class="btn primary" @click="applyPid">下发 PID</button>
      </section>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import * as echarts from 'echarts'
import DigitalTwin3D from './DigitalTwin3D.vue'

const API = 'http://127.0.0.1:8000'
const WS = 'ws://127.0.0.1:8000/ws'
const WINDOW_MS = 12000

const state = reactive({
  mode_name: 'WAITING', angle_deg: 0, angle_velocity_deg_s: 0,
  encoder: 0, arm_angle_deg: 0, arm_velocity_deg_s: 0,
  duty_actual_percent: 0, position_error: 0, alpha_ref_deg: 0,
  fault: 0, akp: 38, akd: 120, pkp: 28, pki: 0, pkd: 160,
  d_filter: 0.1848, received_at: 0,
})
const params = reactive({ akp: 38, akd: 120, pkp: 28, pkd: 160 })
const samples = ref([])
const settingsOpen = ref(false)
const toast = ref('')
const clock = ref(Date.now())
const angleChartRef = ref(null)
const controlChartRef = ref(null)

const disturbance = reactive({
  direction: '', phase: 'idle', startedAt: 0,
  peak: 0, peakTime: 0, peakValue: 0,
  stableSince: 0, recoveredAt: 0, recoveryTime: null,
})

let angleChart = null
let controlChart = null
let ws = null
let onlineTimer = null
let chartRenderTimer = null
let reconnectTimer = null
let destroyed = false

const online = computed(() => Boolean(state.received_at) && clock.value / 1000 - Number(state.received_at) < 2)
const modeClass = computed(() => ({ BALANCE:'balance', SWING:'swing', FAULT:'fault', ZERO:'zero' }[state.mode_name] || 'idle'))
const angleBar = computed(() => Math.min(100, Math.abs(Number(state.angle_deg || 0)) / 5 * 100))
const angleStateClass = computed(() => Math.abs(Number(state.angle_deg || 0)) < 0.5 ? 'state-good' : 'state-warn')
const angleStateText = computed(() => Math.abs(Number(state.angle_deg || 0)) < 0.5 ? '稳定区间' : '恢复中')
const pwmPositive = computed(() => Number(state.duty_actual_percent || 0) >= 0)
const pwmWidth = computed(() => Math.min(50, Math.abs(Number(state.duty_actual_percent || 0)) / 60 * 50))
const pwmFillStyle = computed(() => pwmPositive.value
  ? { left:'50%', width:`${pwmWidth.value}%` }
  : { left:`${50 - pwmWidth.value}%`, width:`${pwmWidth.value}%` })

const rmsAngle = computed(() => {
  const nowSec = clock.value / 1000
  const vals = samples.value
    .filter(s => nowSec - Number(s.received_at || 0) <= 3)
    .map(s => Number(s.angle_deg || 0))
    .filter(Number.isFinite)
  if (!vals.length) return null
  return Math.sqrt(vals.reduce((sum, v) => sum + v * v, 0) / vals.length)
})
const rmsStateClass = computed(() => {
  if (rmsAngle.value === null) return 'idle'
  if (rmsAngle.value < 0.20) return 'stable'
  if (rmsAngle.value < 1.00) return 'critical'
  return 'dispersed'
})
const rmsStateText = computed(() => ({ stable:'稳定', critical:'偏高', dispersed:'波动', idle:'等待数据' }[rmsStateClass.value]))

const disturbanceDirectionLabel = computed(() => disturbance.direction ? `${disturbance.direction}12 q2` : '等待触发')
const disturbancePhaseLabel = computed(() => ({
  idle:'READY', triggered:'DISTURBANCE APPLIED', recovering:'RECOVERING', recovered:'RECOVERED', fault:'FAULT'
}[disturbance.phase] || 'READY'))
const disturbanceClass = computed(() => `phase-${disturbance.phase}`)
const recoveryRms = computed(() => {
  if (!disturbance.recoveredAt) return null
  const from = Math.max(disturbance.recoveredAt, clock.value - 3000)
  const vals = samples.value
    .filter(s => sampleTimeMs(s) >= from)
    .map(s => Number(s.angle_deg || 0))
    .filter(Number.isFinite)
  if (!vals.length) return null
  return Math.sqrt(vals.reduce((sum, v) => sum + v * v, 0) / vals.length)
})

function fmt(v, digits = 2){ return Number.isFinite(Number(v)) ? Number(v).toFixed(digits) : '--' }
function fmtSigned(v, digits = 1){
  if (!Number.isFinite(Number(v))) return '--'
  const n = Number(v)
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}`
}
function hex2(v){ return Number(v || 0).toString(16).toUpperCase().padStart(2, '0') }
function delay(ms){ return new Promise(resolve => setTimeout(resolve, ms)) }
function sampleTimeMs(s){ return Number(s?.received_at || 0) * 1000 || Date.now() }
function showToast(message){
  toast.value = message
  const current = message
  setTimeout(() => { if (toast.value === current) toast.value = '' }, 2200)
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

function startDisturbance(direction){
  Object.assign(disturbance, {
    direction, phase:'triggered', startedAt:Date.now(),
    peak:0, peakTime:0, peakValue:0,
    stableSince:0, recoveredAt:0, recoveryTime:null,
  })
  scheduleCharts()
}
async function probe(direction){
  const ampOk = await send('PROBEAMP=12', { quiet:true })
  if (!ampOk) return
  await delay(120)
  const probeOk = await send(`PROBE=${direction}`, { quiet:true })
  if (!probeOk) return
  startDisturbance(direction)
  showToast(`已施加 ${direction}12 q2 扰动`)
}
function resetDisturbance(){
  Object.assign(disturbance, {
    direction:'', phase:'idle', startedAt:0,
    peak:0, peakTime:0, peakValue:0,
    stableSince:0, recoveredAt:0, recoveryTime:null,
  })
  scheduleCharts()
}
async function applyPid(){
  for (const [key, value] of Object.entries(params)){
    const ok = await send(`${key.toUpperCase()}=${Math.max(0, Number(value) || 0)}`, { quiet:true })
    if (!ok) return
  }
  showToast('PID 参数已下发')
}

function updateDisturbance(sample){
  if (!disturbance.startedAt || disturbance.recoveredAt || disturbance.phase === 'fault') return
  const time = sampleTimeMs(sample)
  if (time < disturbance.startedAt) return

  const angle = Number(sample.angle_deg || 0)
  const speed = Number(sample.angle_velocity_deg_s || 0)
  const elapsed = time - disturbance.startedAt
  const absAngle = Math.abs(angle)

  if (absAngle >= disturbance.peak){
    disturbance.peak = absAngle
    disturbance.peakValue = angle
    disturbance.peakTime = time
  }
  if (sample.mode_name === 'FAULT' || Number(sample.fault || 0) !== 0){
    disturbance.phase = 'fault'
    disturbance.stableSince = 0
    return
  }
  if (disturbance.phase === 'triggered' && (disturbance.peak >= 0.55 || Math.abs(speed) >= 8 || elapsed >= 350)){
    disturbance.phase = 'recovering'
  }
  if (elapsed < 250) return

  const stable = sample.mode_name === 'BALANCE' && absAngle < 0.5 && Math.abs(speed) < 5
  if (stable){
    if (!disturbance.stableSince) disturbance.stableSince = time
    if (time - disturbance.stableSince >= 350){
      disturbance.recoveredAt = time
      disturbance.recoveryTime = (time - disturbance.startedAt) / 1000
      disturbance.phase = 'recovered'
    }
  }else{
    disturbance.stableSince = 0
  }
}

function axisTheme(){
  return {
    axisLine:{ lineStyle:{ color:'#1E3A56' } },
    axisLabel:{ color:'#7A93AC', fontSize:10 },
    splitLine:{ lineStyle:{ color:'rgba(70,104,135,.16)' } },
    axisTick:{ show:false },
  }
}
function timeLabel(value){
  const d = new Date(value)
  return `${String(d.getMinutes()).padStart(2,'0')}:${String(d.getSeconds()).padStart(2,'0')}`
}
function initCharts(){
  angleChart = echarts.init(angleChartRef.value)
  controlChart = echarts.init(controlChartRef.value)
  renderCharts()
}
function renderCharts(){
  if (!angleChart || !controlChart) return
  const now = Date.now()
  const data = samples.value.filter(s => sampleTimeMs(s) >= now - WINDOW_MS)
  const angleData = data.map(s => [sampleTimeMs(s), Number(s.angle_deg || 0)])
  const refData = data.map(s => [sampleTimeMs(s), Number(s.alpha_ref_deg || 0)])
  const pwmData = data.map(s => [sampleTimeMs(s), Number(s.duty_actual_percent || 0)])
  const eventVisible = disturbance.startedAt && disturbance.startedAt >= now - WINDOW_MS
  const eventEnd = disturbance.recoveredAt || now

  const markLine = eventVisible ? {
    symbol:['none','none'], silent:true,
    lineStyle:{ color:'#FBBF24', width:1.3, type:'dashed', opacity:.9 },
    label:{ show:true, formatter:`⚡ ${disturbance.direction}12 q2`, color:'#FBBF24', fontSize:10, position:'insideEndTop' },
    data:[{ xAxis:disturbance.startedAt }],
  } : undefined
  const markArea = eventVisible ? {
    silent:true,
    itemStyle:{ color:'rgba(251,191,36,.055)' },
    data:[[{ xAxis:disturbance.startedAt }, { xAxis:eventEnd }]],
  } : undefined
  const markPoint = eventVisible && disturbance.peakTime ? {
    symbol:'circle', symbolSize:8,
    itemStyle:{ color:'#FBBF24' },
    label:{ show:true, formatter:`α max ${disturbance.peak.toFixed(2)}°`, color:'#FBBF24', fontSize:10, position:'top' },
    data:[{ coord:[disturbance.peakTime, disturbance.peakValue], value:disturbance.peak }],
  } : undefined

  angleChart.setOption({
    animation:false,
    grid:{ left:44, right:16, top:12, bottom:28 },
    tooltip:{ trigger:'axis', backgroundColor:'#0B1724', borderColor:'#1E3A56', textStyle:{ color:'#DCE9F5', fontSize:11 } },
    xAxis:{ type:'time', min:now-WINDOW_MS, max:now, boundaryGap:false, ...axisTheme(), axisLabel:{ color:'#7A93AC', fontSize:9, formatter:timeLabel } },
    yAxis:{ type:'value', name:'deg', nameGap:8, nameTextStyle:{ color:'#6F879C', fontSize:9 },
      min:value => Math.min(-2, Math.floor(value.min - 1)), max:value => Math.max(2, Math.ceil(value.max + 1)), splitNumber:4, ...axisTheme() },
    series:[
      { name:'α 实测', type:'line', data:angleData, showSymbol:false, smooth:.16, connectNulls:true,
        lineStyle:{ width:2.1, color:'#38BDF8' }, areaStyle:{ color:'rgba(56,189,248,.045)' }, markLine, markArea, markPoint },
      { name:'α 目标', type:'line', data:refData, showSymbol:false, smooth:true,
        lineStyle:{ width:1.2, color:'#A78BFA', type:'dashed', opacity:.9 } },
    ],
  }, true)

  controlChart.setOption({
    animation:false,
    grid:{ left:40, right:14, top:12, bottom:28 },
    tooltip:{ trigger:'axis', backgroundColor:'#0B1724', borderColor:'#1E3A56', textStyle:{ color:'#DCE9F5', fontSize:11 } },
    xAxis:{ type:'time', min:now-WINDOW_MS, max:now, boundaryGap:false, ...axisTheme(), axisLabel:{ color:'#7A93AC', fontSize:9, formatter:timeLabel } },
    yAxis:{ type:'value', min:-65, max:65, interval:30, ...axisTheme() },
    series:[{
      name:'PWM', type:'line', data:pwmData, showSymbol:false, smooth:.12, connectNulls:true,
      lineStyle:{ width:1.8, color:'#A78BFA' }, areaStyle:{ color:'rgba(167,139,250,.045)' }, markLine,
    }],
  }, true)
}
function scheduleCharts(){
  if (chartRenderTimer) return
  chartRenderTimer = setTimeout(() => {
    chartRenderTimer = null
    renderCharts()
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
    if (samples.value.length > 1000) samples.value.splice(0, samples.value.length - 1000)
  }
  updateDisturbance(data)
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
function onResize(){ angleChart?.resize(); controlChart?.resize() }

onMounted(async () => {
  await nextTick()
  initCharts()
  await loadSnapshot()
  connectWs()
  window.addEventListener('resize', onResize)
  onlineTimer = setInterval(() => { clock.value = Date.now(); scheduleCharts() }, 500)
})
onBeforeUnmount(() => {
  destroyed = true
  window.removeEventListener('resize', onResize)
  if (onlineTimer) clearInterval(onlineTimer)
  if (chartRenderTimer) clearTimeout(chartRenderTimer)
  if (reconnectTimer) clearTimeout(reconnectTimer)
  try{ ws?.close() }catch(_error){}
  angleChart?.dispose()
  controlChart?.dispose()
})
</script>
