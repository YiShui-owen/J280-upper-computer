<template>
 <section class="host-control-panel fd2-controls">
  <form class="connection-form" @submit.prevent="saveConnection">
<label>Host 桥端口 <input v-model.number="connection.bridge_port" type="number" min="1024" max="65535" required>
</label>
<label>固件 <select v-model="connection.firmware_variant">
<option value="auto">自动识别 V1～V5</option>
<option v-for="v in versions" :key="v" :value="v">{{ v }}</option>
</select>
</label>
<button class="button compact" :disabled="state.replay?.active">保存连接设置</button>
</form>
  <p>串口由配套 Host 显式连接；USB 与 BT10 命令链路独立。</p>
  <p v-if="state.replay?.active" class="host-error">离线回放 · 全部硬件操作已禁用</p>
  <div class="debug-actions">
<button v-for="action in actions.filter(a=>!['position','trajectory'].includes(a))" :key="action" class="button compact" :class="{'stop':['stop','estop'].includes(action)}" :disabled="!canSend(action)" @click="send(action)">{{ labels[action] }}</button>
</div>
  <div v-if="actions.includes('position')" class="debug-actions">
<label>位置／轨迹编号 <select v-model.number="target">
<option v-for="n in 6" :value="n" :key="n">{{ n }}</option>
</select>
</label>
<button class="button compact" :disabled="!canSend('position')" @click="send('position',target)">相对定位</button>
<button v-if="actions.includes('trajectory')" class="button compact" :disabled="!canSend('trajectory')" @click="send('trajectory',target)">有限轨迹</button>
</div>
  <p>ACK 只表示请求已接受；完成与到位以独立遥测为准。超时不自动重发。</p>
  <p v-if="notice" role="status">{{ notice }}</p>
<ol class="request-list">
<li v-for="r in records" :key="r.request_id">{{ labels[r.action] || r.action }} · {{ requestLabel(r) }} <small>{{ r.request_id }}</small> <button class="text-button" @click="query(r)">查询</button>
</li>
</ol>
 </section>
</template>
<script setup>
import {computed,onMounted,reactive,ref,watch} from 'vue'
import {fd2Actions,canDispatchFd2,commandFailure,swingLabel} from './fd2Presentation.js'
import {requestLabel} from './hostPresentation.js'
const props=defineProps({state:{type:Object,required:true}})
const versions=['V1','V2','V3','V4','V5'],API='http://127.0.0.1:8000'
const connection=reactive({bridge_port:8371,firmware_variant:'auto'}),target=ref(1),notice=ref(''),records=ref([]),inflight=ref(0),busy=computed(()=>inflight.value>0)
const labels={'stop':'STOP 停止','estop':'ESTOP 急停','zero':'显式抓零','balance':'手动平衡','clear-fault':'清除故障','start-swing':'按当前方案起摆','adapt-enable':'启用自适应','adapt-disable':'关闭自适应','hold':'保持当前位置','position':'相对定位','trajectory':'有限轨迹'}
const actions=computed(()=>fd2Actions(props.state.firmware))
const runAction=computed(()=>actions.value.includes('start-swing')?'start-swing':'balance')
const canRun=computed(()=>canSend(runAction.value))
const runLabel=computed(()=>runAction.value==='start-swing'?`${swingLabel(props.state.swing?.profile)} 起摆`:'手动平衡')
function canSend(action){return canDispatchFd2(props.state,action,busy.value,props.state.presentation_now_ms??Date.now())}

async function request(path,body){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
try{const r=await fetch(API+path,{signal:controller.signal,...(body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});
const d=await r.json();
if(!r.ok){const e=new Error(typeof d.detail==='string'?d.detail:d.detail?.message||'请求被拒绝');
e.httpStatus=r.status;
e.result=d.detail;
throw e;
}return d}
finally{clearTimeout(timer)}}
async function send(action,value){if(!actions.value.includes(action)||!canSend(action))return;
const record={request_id:crypto.randomUUID(),action,state:'pending'};
records.value=[record,...records.value].slice(0,12);
inflight.value++;
try{Object.assign(record,await request('/command',{request_id:record.request_id,action,...(value===undefined?{}:{value})}))}
catch(error){Object.assign(record,commandFailure(error));
notice.value=record.message}
finally{inflight.value--;
records.value=[...records.value]}}
async function query(record){try{Object.assign(record,await request('/requests/'+encodeURIComponent(record.request_id)));
records.value=[...records.value]}
catch(e){notice.value=e.message}}
async function saveConnection(){try{await request('/config',{...connection});
notice.value='连接设置已保存'}
catch(e){notice.value=e.message}}
watch(()=>props.state.requests,requests=>{for(const r of records.value)if(requests?.[r.request_id])Object.assign(r,requests[r.request_id]);
records.value=[...records.value]})
onMounted(async()=>{try{const c=await request('/config');
connection.bridge_port=c.bridge_port;
if(['auto',...versions].includes(c.firmware_variant))connection.firmware_variant=c.firmware_variant}
catch(e){notice.value=e.message}})
function run(){return send(actions.value.includes('start-swing')?'start-swing':'balance')}
function stop(){return send('stop')}
const runRequest=computed(()=>records.value.find(r=>['start-swing','balance'].includes(r.action)))
defineExpose({run,stop,canRun,runLabel,runRequest,busy})
</script>
<style scoped>
.connection-form,.debug-actions{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:16px 0}
label{display:flex;gap:8px;align-items:center}
input,select{background:#292c28;color:#d7d8cd;border:1px solid #55594d;padding:7px}
p,li{color:#aeb2a3;line-height:1.7;font-size:13px}
small{font-size:11px;overflow-wrap:anywhere}
.request-list{padding-left:20px}

</style>
