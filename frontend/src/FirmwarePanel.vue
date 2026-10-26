<template>
  <section class="firmware-panel" aria-labelledby="firmware-heading">
    <header class="firmware-heading"><h3 id="firmware-heading">固件切换</h3><span>SRAM · 断电不保留</span></header>
    <form class="firmware-configuration" @submit.prevent="saveConfig">
      <fieldset :disabled="readiness.settingsDisabled">
        <label class="firmware-path">Programmer 路径
          <input v-model="draft.programmer_path" list="firmware-programmer-paths" placeholder="工具目录或 programmer_cli.exe 完整路径" @input="clearCable" />
          <datalist id="firmware-programmer-paths"><option v-for="path in detectedPaths" :key="path" :value="path" /></datalist>
        </label>
        <div class="firmware-connection-row">
          <label>下载器
            <select :value="selectedCable" @change="selectCable">
              <option value="">请选择下载器</option>
              <option v-for="(cable,index) in cables" :key="cableKey(cable)" :value="String(index)">{{ cableLabel(cable) }}</option>
            </select>
          </label>
          <button type="button" class="button compact" :disabled="!draft.programmer_path.trim()" @click="scanCables">扫描下载器</button>
          <label>USB 串口 <input v-model="draft.usb_port" placeholder="例如 COM7" autocomplete="off" /></label>
          <button class="button compact" :disabled="!canSave">保存固件设置</button>
        </div>
      </fieldset>
    </form>
    <label v-if="readiness.needsIsolation" class="firmware-isolation">
      <input v-model="motorIsolated" type="checkbox" :disabled="readiness.settingsDisabled" />本次操作：电机电源已断开
    </label>
    <div class="firmware-target-row">
      <label>切换到
        <select :value="selection" :disabled="!readiness.canSelect" @change="chooseTarget">
          <option value="">选择固件后自动下载</option>
          <option v-for="version in FIRMWARE_TARGETS" :key="version" :value="version">{{ version }}</option>
        </select>
      </label>
      <span v-if="readiness.reason" class="firmware-hint">{{ readiness.reason }}</span>
    </div>
    <p class="firmware-notice">仅切换固件并连接 USB；完成后仍需手动启动摆控。</p>
    <p v-if="notice || connectionError" class="firmware-notice" role="status">{{ connectionError || notice }}</p>
    <section v-if="job" class="firmware-task" aria-label="固件切换任务" aria-live="polite">
      <div class="firmware-job-heading"><strong>{{ job.target }} · {{ firmwarePhaseLabel(job.phase || job.state) }}</strong><button class="text-button" :disabled="querying || replay" @click="queryJob">查询任务</button></div>
      <p v-if="job.message">{{ job.message }}</p>
      <p class="firmware-task-id">任务 {{ job.request_id }}</p>
      <details v-if="job.log?.length" :open="status.busy"><summary>任务日志</summary><pre>{{ job.log.join('\n') }}</pre></details>
    </section>
  </section>
</template>

<script setup>
import {computed,onBeforeUnmount,onMounted,reactive,ref,watch} from 'vue'
import {FIRMWARE_TARGETS,initialFirmwareSelection,firmwareReadiness,firmwareSelection,firmwareJobFailure,firmwarePhaseLabel,firmwareUsbPort,firmwareJobTerminal} from './firmwarePresentation.js'

const props=defineProps({state:{type:Object,required:true}})
const emit=defineEmits(['status','started'])
const API='http://127.0.0.1:8000/firmware', STORAGE_KEY='j280-firmware-request'
const draft=reactive({programmer_path:'',cable:null,usb_port:''})
const config=ref({}),detectedPaths=ref([]),cables=ref([])
const status=ref({busy:false,phase:'idle',job:null,error:null}),statusKnown=ref(false)
const selection=ref(initialFirmwareSelection()),motorIsolated=ref(false),loading=ref(false),querying=ref(false)
const notice=ref(''),connectionError=ref(''),unresolvedRequest=ref(false),clock=ref(Date.now())
const replay=computed(()=>Boolean(props.state.replay?.active))
const controllers=new Set()
let destroyed=false,pollTimer=null,pollInFlight=false,epoch=0,trackedId=''
const job=computed(()=>status.value.job)
const cableKey=cable=>JSON.stringify(cable && {cable_index:cable.cable_index,channel:cable.channel,location:cable.location??null,uid:cable.uid??null})
const selectedCable=computed(()=>draft.cable ? String(cables.value.findIndex(cable=>cableKey(cable)===cableKey(draft.cable))) : '')
const dirty=computed(()=>draft.programmer_path.trim()!==(config.value.programmer_path || '').trim() || draft.usb_port.trim()!==(config.value.usb_port || '').trim() || cableKey(draft.cable)!==cableKey(config.value.cable))
const readiness=computed(()=>firmwareReadiness({state:props.state,config:config.value,status:status.value,statusKnown:statusKnown.value,loading:loading.value,dirty:dirty.value,motorIsolated:motorIsolated.value,unresolvedRequest:unresolvedRequest.value,now:clock.value}))
const canSave=computed(()=>Boolean(draft.programmer_path.trim() && draft.cable && draft.usb_port.trim()))

function cableLabel(cable){return `${cable.label || `下载器 ${cable.cable_index}`} · 通道 ${cable.channel}${cable.location==null?'':` · 位置 ${cable.location}`}${cable.uid?` · ${cable.uid}`:''}`}
function clearCable(){draft.cable=null}
function selectCable(event){draft.cable=event.target.value===''?null:{...cables.value[Number(event.target.value)]}}
function remember(id){trackedId=id;try{sessionStorage.setItem(STORAGE_KEY,id)}catch{/* Session storage is optional. */}}
function publish(value){if(destroyed)return;status.value=value;emit('status',value)}

async function request(path,body,timeout=6000){
  const controller=new AbortController()
  controllers.add(controller)
  const timer=setTimeout(()=>controller.abort(),timeout)
  try{
    const response=await fetch(API+path,{signal:controller.signal,headers:{'X-J280-Local':'1',...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{method:'POST',body:JSON.stringify(body)})})
    const data=await response.json()
    if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:data.detail?.message || '请求被拒绝');error.httpStatus=response.status;throw error}
    return data
  }finally{clearTimeout(timer);controllers.delete(controller)}
}

function loadConfig(value){
  config.value=value
  detectedPaths.value=Array.isArray(value.detected_paths)?value.detected_paths:[]
  draft.programmer_path=value.programmer_path || ''
  draft.usb_port=firmwareUsbPort(value,props.state)
  draft.cable=value.cable?{...value.cable}:null
  if(value.cable && !cables.value.some(c=>cableKey(c)===cableKey(value.cable)))cables.value=[{...value.cable},...cables.value]
}

async function saveConfig(){
  if(readiness.value.settingsDisabled || !canSave.value)return
  loading.value=true
  try{
    const saved=await request('/config',{programmer_path:draft.programmer_path.trim(),cable:draft.cable,usb_port:draft.usb_port.trim()})
    if(destroyed)return
    // Re-read when the server returns a save receipt rather than the full config.
    loadConfig(saved.programmer_path!==undefined?saved:await request('/config'))
    notice.value='固件设置已保存'
  }catch(error){if(!destroyed)notice.value=error.message}
  finally{loading.value=false}
}

async function scanCables(){
  if(readiness.value.settingsDisabled || !draft.programmer_path.trim())return
  loading.value=true
  draft.cable=null
  try{
    const value=await request('/scan',{programmer_path:draft.programmer_path.trim()},20000)
    if(destroyed)return
    cables.value=Array.isArray(value.cables)?value.cables:[]
    notice.value=cables.value.length?'请选择下载器并保存设置':'未发现下载器'
  }catch(error){if(!destroyed)notice.value=error.message}
  finally{loading.value=false}
}

async function chooseTarget(event){
  clock.value=Date.now()
  const result=firmwareSelection({target:event.target.value,origin:'user',readiness:readiness.value,requestId:crypto.randomUUID(),motorIsolated:motorIsolated.value})
  selection.value=result.selection
  event.target.value=result.selection
  motorIsolated.value=result.motorIsolated
  if(!result.submission)return
  const pending={request_id:result.submission.request_id,target:result.submission.target,state:'pending',phase:'submitting',log:[],message:'正在提交任务'}
  epoch++
  remember(pending.request_id)
  unresolvedRequest.value=true
  connectionError.value=''
  publish({busy:true,phase:'submitting',job:pending,error:null})
  try{
    const accepted=await request('/jobs',result.submission)
    if(destroyed)return
    unresolvedRequest.value=false
    connectionError.value=''
    publish({busy:!firmwareJobTerminal(accepted),phase:accepted.phase,job:accepted,error:null})
    emit('started',accepted)
  }catch(error){
    if(destroyed)return
    const failed=firmwareJobFailure(error,pending)
    failed.phase=failed.state
    unresolvedRequest.value=failed.state==='indeterminate'
    if(!unresolvedRequest.value){try{sessionStorage.removeItem(STORAGE_KEY)}catch{/* A rejected request has no recoverable backend job. */}}
    publish({busy:unresolvedRequest.value,phase:failed.phase,job:failed,error:null})
    notice.value=failed.message
  }
}

async function queryJob(){
  if(!trackedId || querying.value || replay.value)return
  querying.value=true
  const queryEpoch=epoch
  try{
    const value=await request('/jobs/'+encodeURIComponent(trackedId))
    if(destroyed || epoch!==queryEpoch)return
    unresolvedRequest.value=false
    connectionError.value=''
    publish({busy:!firmwareJobTerminal(value),phase:value.phase,job:value,error:null})
  }catch(error){if(!destroyed)connectionError.value=`任务 ${trackedId}：${error.message}；请继续查询，未重发`}
  finally{querying.value=false}
}

async function refresh(){
  if(pollInFlight || destroyed || replay.value)return
  pollInFlight=true
  const pollEpoch=epoch
  try{
    const value=await request('/status')
    if(destroyed || epoch!==pollEpoch)return
    statusKnown.value=true
    connectionError.value=''
    if(unresolvedRequest.value && value.job?.request_id!==trackedId){await queryJob();return}
    if(value.job?.request_id){remember(value.job.request_id);unresolvedRequest.value=false}
    publish(value)
  }catch(error){
    if(!destroyed){
      statusKnown.value=false
      connectionError.value=`任务状态暂不可用：${error.message}`
      // Preserve a busy/unknown task until an actual query confirms its outcome.
      if(status.value.busy)emit('status',{...status.value,error:connectionError.value})
    }
  }finally{pollInFlight=false}
}

watch(()=>props.state.replay?.active,active=>{
  motorIsolated.value=false
  if(active){for(const controller of controllers)controller.abort()}
  else void refresh()
})
watch(()=>readiness.value.needsIsolation,()=>{motorIsolated.value=false})
watch(()=>props.state.transport,()=>{if(!draft.usb_port && !config.value.usb_port)draft.usb_port=firmwareUsbPort(config.value,props.state)},{deep:true})

onMounted(async()=>{
  try{trackedId=sessionStorage.getItem(STORAGE_KEY) || ''}catch{/* Session storage is optional. */}
  if(trackedId){unresolvedRequest.value=true;publish({busy:true,phase:'indeterminate',job:{request_id:trackedId,state:'indeterminate',phase:'indeterminate',log:[],message:'正在查询上次任务'},error:null})}
  // Replay never scans or writes hardware; config is a filesystem-only read.
  try{const value=await request('/config');if(!destroyed)loadConfig(value)}catch(error){if(!destroyed)notice.value=error.message}
  if(!destroyed){
    await refresh()
    if(!destroyed)pollTimer=setInterval(()=>{clock.value=Date.now();void refresh()},1000)
  }
})
onBeforeUnmount(()=>{destroyed=true;clearInterval(pollTimer);for(const controller of controllers)controller.abort();controllers.clear()})
defineExpose({refresh})
</script>

<style scoped>
.firmware-panel{margin:22px 0;padding-top:20px;border-top:1px solid #55594d;color:#d7d8cd}
.firmware-heading,.firmware-job-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}
.firmware-heading h3{margin:0;font-size:16px;font-weight:600}
.firmware-heading span,.firmware-hint,.firmware-notice,.firmware-task p{font-size:13px;color:#aeb2a3;line-height:1.7}
.firmware-configuration{margin-top:14px}
fieldset{margin:0;padding:0;border:0;min-width:0}
label{display:flex;align-items:center;gap:8px;font-size:13px}
input,select{min-width:0;background:#292c28;color:#d7d8cd;border:1px solid #55594d;padding:7px;font:inherit}
.firmware-path{align-items:flex-start;flex-direction:column}
.firmware-path input{width:100%;box-sizing:border-box}
.firmware-connection-row,.firmware-target-row{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-top:14px}
.firmware-connection-row label:first-child{flex:1;min-width:240px}
.firmware-connection-row select{flex:1;width:100%;max-width:430px}
.firmware-connection-row input{width:100px}
.firmware-isolation{margin-top:16px;color:#d6b16a}
.firmware-isolation input{accent-color:#d6b16a}
.firmware-target-row select{border-color:#8d774d}
.firmware-notice{margin:10px 0 0}
.firmware-task{margin-top:16px;padding:12px;border:1px solid #55594d}
.firmware-job-heading strong{font-size:14px;font-weight:500;color:#d6b16a}
.firmware-task p{margin:6px 0}
.firmware-task-id{overflow-wrap:anywhere}
summary{cursor:pointer;font-size:13px;color:#aeb2a3}
pre{max-height:190px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:#b8bcb0;line-height:1.6}
input:disabled,select:disabled{opacity:.5}
@media(max-width:650px){.firmware-heading{align-items:flex-start}.firmware-connection-row label:first-child{min-width:100%}.firmware-connection-row select{max-width:100%}}
</style>
