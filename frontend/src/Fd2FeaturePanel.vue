<template>
<aside class="gesture-panel fd2-feature">
<header class="panel-heading">
<h2>{{ state.firmware || 'FD2' }} 功能状态</h2>
<span>{{ state.replay?.active ? '离线回放' : fresh ? '实时' : '等待数据' }}</span>
</header>
<template v-if="['V1','V2','V4'].includes(state.firmware)">
<h3>起摆</h3>
<p>起摆方案：{{ statusFresh ? swingLabel(state.swing?.profile) : '—' }}</p>
<p>实际阶段：{{ statusFresh ? swingStageLabel(state.swing,state.mode_name) : '—' }}</p>
</template>
<template v-if="['V1','V2'].includes(state.firmware)">
<h3>光学手势识别</h3>
<div class="directions">
<span v-for="(arrow,code) in arrows" :key="code" :title="gestureLabels[code]" :class="{active:fresh && gestureCode===Number(code)}">{{ arrow }}</span>
</div>
<p>识别事件 #{{ read(state.gesture_event?.sequence) }} · {{ fresh ? gestureLabels[state.gesture_event?.code] ?? '—' : '—' }}</p>
<p>最近动作原因：{{ read(state.action_reason) }}</p>
</template>
<template v-if="state.firmware==='V3'">
<h3>角 P / D 自适应</h3>
<p>启用：{{ read(state.adaptive?.enabled) }} · 实际采用：{{ read(state.adaptive?.used) }}</p>
<p v-for="[key,label] in [['manual_gains','手动基值'],['active_gains','实际增益'],['target_gains','候选目标']]" :key="key">{{ label }}：{{ gains(state.adaptive?.[key]) }}</p>
<p>冻结原因：{{ read(state.adaptive?.freeze_reason) }}</p>
<p class="gain-legend"><span>P 琥珀</span> · D 银 · 各自刻度</p>
<svg viewBox="0 0 300 70" aria-label="实际 Kp 琥珀色、Kd 银色趋势">
<g v-for="(field,i) in ['angle_kp','angle_kd']" :key="field">
<polyline v-for="(points,n) in trend(field)" :key="n" :points="points" fill="none" :stroke="i?'#C7CBBE':'#DBAA64'" stroke-width="1.5"/>
</g>
</svg>
<p v-for="seconds in [1,5]" :key="seconds">{{ seconds }} 秒实际均值：{{ fmt(average(seconds).kp) }} / {{ fmt(average(seconds).kd) }} · 覆盖 {{ Math.round(average(seconds).coverage*100) }}%</p>
</template>
<template v-if="['V4','V5'].includes(state.firmware)">
<h3>运动状态</h3>
<dl>
<div v-for="[key,label] in motionFields" :key="key">
<dt>{{ label }}</dt>
<dd>{{ readMotion(key) }}</dd>
</div>
</dl>
<p>动作请求：{{ readDiagnostic(state.motion?.request_id) }} / {{ readDiagnostic(state.motion?.action) }}</p>
<p>轨迹生成完成：{{ readDiagnostic(state.motion?.trajectory_done) }}</p>
<p>实际跟踪到位：{{ readDiagnostic(state.motion?.tracking_settled) }}</p>
</template>
<p class="host-error">{{ state.fd2?.error || state.fd2?.log_error }}</p>
<p>CRC {{ state.fd2?.crc_errors ?? '—' }} · 缺序 {{ state.fd2?.sequence_gaps ?? '—' }}<br>USB {{ state.transport?.usb_connected ? '已连接' : '未连接' }} · BT10 {{ state.transport?.ble_connected ? '已连接' : '未连接' }}</p>
</aside>
</template>
<script setup>
import {computed,ref,watch} from 'vue'
import {actualGainWindow,gainPair,gestureLabels,fd2Freshness,gainSegments,swingLabel,swingStageLabel,formatMotionValue} from './fd2Presentation.js'
const props=defineProps({state:Object,samples:Array,now:Number}),fresh=computed(()=>fd2Freshness(props.state,props.state.presentation_now_ms??Date.now()).control),gestureCode=ref(null),arrows={1:'→',2:'←',3:'↑',4:'↓',5:'靠近',6:'远离',7:'↻',8:'↺',9:'挥手STOP'}
const statusFresh=computed(()=>props.state.replay?.active||fd2Freshness(props.state,props.state.presentation_now_ms??Date.now()).status)
let initial=true,previousSession,previousSequence
watch(()=>[props.state.session,props.state.gesture_event?.sequence],([session,sequence])=>{if(initial||session!==previousSession){initial=false;
gestureCode.value=null}else if(sequence!==previousSequence&&fresh.value)gestureCode.value=props.state.gesture_event?.code;
previousSession=session;
previousSequence=sequence},{immediate:true})
const motionFields=[['origin_count','动作原点计数'],['final_target_count','最终目标计数'],['actual_count','实际累计计数'],['reference_count','当前参考计数'],['planner_phase','规划阶段'],['tracking_error_deg','跟踪误差 °'],['measured_velocity_deg_s','实际速度 °/s']]
function read(v){return !fresh.value||v==null?'—':typeof v==='boolean'?v?'是':'否':v}
function readMotion(key){return ['actual_count','reference_count'].includes(key)?read(props.state.motion?.[key]):readDiagnostic(formatMotionValue(key,props.state.motion?.[key]))}
function readDiagnostic(v){return !fd2Freshness(props.state,props.state.presentation_now_ms??Date.now()).diagnostic||v==null?'—':typeof v==='boolean'?v?'是':'否':v}
function fmt(v){return fresh.value&&Number.isFinite(v)?v.toFixed(3):'—'}
function gains(g){return !fresh.value||!g?'—':gainPair(g).map(fmt).join(' / ')}
function average(s){return fresh.value?actualGainWindow(props.state.adaptive?.averages,s*1000):{kp:null,kd:null,coverage:0}}
function trend(field){const rows=(props.samples||[]).filter(r=>r.plot_at*1000>=props.now-10000&&r.plot_at*1000<=props.now);
const values=rows.map(r=>r[field]).filter(Number.isFinite);
if(!values.length||!fresh.value)return [];
const min=Math.min(...values),max=Math.max(...values);
return gainSegments(rows,field).map(segment=>segment.map(r=>`${300*(r.plot_at*1000-props.now+10000)/10000},${60-50*(r[field]-min)/(max-min||1)}`).join(' '))}
</script>
<style scoped>.fd2-feature{overflow:auto;padding:20px 24px}
h3{font-size:14px;font-weight:500;margin:20px 0 12px}
dl{margin:0}
dl div{display:flex;justify-content:space-between;gap:12px;margin:9px 0;font-size:13px}
dt,p{color:#aeb2a3}
dd{margin:0;text-align:right;overflow-wrap:anywhere}
p{font-size:12px;line-height:1.7}
.directions{display:flex;flex-wrap:wrap;gap:12px;align-items:center;font-size:26px;color:#666b60}
.directions .active{color:#dbaa64}
svg{width:100%;height:70px}
.gain-legend span{color:#DBAA64}
</style>
