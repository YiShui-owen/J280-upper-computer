import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {parse,compileScript,compileTemplate} from '@vue/compiler-sfc'
import {
  FIRMWARE_TARGETS, initialFirmwareSelection, firmwareReadiness,
  firmwareSelection, firmwareJobFailure, firmwarePhaseLabel, firmwareUsbPort, firmwareJobTerminal,
} from '../src/firmwarePresentation.js'

const config = { configured:true, programmer_path:'C:\\工具 路径\\bin', cable:{cable_index:0,channel:0,location:1,uid:null}, usb_port:'COM7' }
const state = {firmware:'V2',host_online:true,connected:true,synced:true,status_fresh:true,status_age_s:.1,observed_at:10,fd2:{log_error:''}}
const ready = extra => firmwareReadiness({state,config,status:{busy:false},statusKnown:true,now:10000,...extra})

test('target starts empty and restores never submit a job', () => {
  assert.equal(initialFirmwareSelection(), '')
  assert.deepEqual(FIRMWARE_TARGETS,['V1','V2','V3','V4','V5'])
  for (const origin of ['mount','restore','poll','config',undefined]) {
    assert.equal(firmwareSelection({target:'V3',origin,readiness:ready(),requestId:'one'}).submission,null)
  }
})

test('only a ready user change creates one explicit SRAM task and consumes isolation', () => {
  const selection=firmwareSelection({target:'V3',origin:'user',readiness:ready(),requestId:'one',motorIsolated:true})
  assert.deepEqual(selection,{selection:'',motorIsolated:false,submission:{request_id:'one',target:'V3',motor_isolated:false}})
  assert.equal(firmwareSelection({target:'V3',origin:'user',readiness:ready({status:{busy:true}}),requestId:'two'}).submission,null)
  for(const target of ['', 'auto','V6'])assert.equal(firmwareSelection({target,origin:'user',readiness:ready(),requestId:'one'}).submission,null)
})

test('busy, replay, dirty or missing configuration, unqueried status and unresolved transport failure disable selection', () => {
  for (const extra of [{status:{busy:true}},{state:{...state,programming:{busy:true}}},{state:{...state,replay:{active:true}}},{dirty:true},{config:{...config,configured:false}},{statusKnown:false},{unresolvedRequest:true},{loading:true}]) {
    assert.equal(ready(extra).canSelect,false,JSON.stringify(extra))
  }
  assert.equal(ready({state:{...state,replay:{active:true}}}).settingsDisabled,true)
  assert.equal(ready({status:{busy:true}}).settingsDisabled,true)
  assert.equal(ready().canSelect,true)
})

test('motor isolation applies only to truly absent Host and is consumed once', () => {
  const absent={host_online:false,connected:false}
  assert.equal(ready({state:absent}).needsIsolation,true)
  assert.equal(ready({state:absent}).canSelect,false)
  const gate=ready({state:absent,motorIsolated:true})
  assert.equal(gate.canSelect,true)
  const selected=firmwareSelection({target:'V1',origin:'user',readiness:gate,requestId:'cold-start',motorIsolated:true})
  assert.equal(selected.submission.motor_isolated,true)
  assert.equal(selected.motorIsolated,false)
  for(const invalid of [{...state,status_fresh:false},{...state,synced:false},{...state,firmware:null},{...state,host_online:false},{...state,fd2:{log_error:'logging failed'}},{...state,observed_at:9}]) {
    assert.equal(ready({state:invalid,motorIsolated:true}).canSelect,false)
    assert.equal(ready({state:invalid,motorIsolated:true}).needsIsolation,false)
  }
})

test('transport timeout preserves request ID for querying and never supplies a retry', () => {
  const failed=firmwareJobFailure(new Error('timeout'),{request_id:'same-id',target:'V5'})
  assert.equal(failed.request_id,'same-id')
  assert.equal(failed.state,'indeterminate')
  assert.match(failed.message,/查询/)
  assert.equal(failed.retry,undefined)
  assert.equal(firmwareJobFailure(Object.assign(new Error('busy'),{httpStatus:409}),{request_id:'r'}).state,'rejected')
  assert.equal(firmwareJobFailure(Object.assign(new Error('unavailable'),{httpStatus:503}),{request_id:'r'}).state,'indeterminate')
})

test('server indeterminate is a terminal unknown outcome, never success',()=>{
  for(const state of ['succeeded','failed','indeterminate'])assert.equal(firmwareJobTerminal({state}),true)
  for(const state of ['queued','running','pending'])assert.equal(firmwareJobTerminal({state}),false)
  assert.equal(firmwarePhaseLabel('indeterminate'),'结果未知')
})

test('stages use actual phase text and USB restores without inventing a serial port', () => {
  assert.equal(firmwarePhaseLabel('programming'),'下载并校验 SRAM')
  assert.equal(firmwarePhaseLabel('driver specific phase'),'driver specific phase')
  assert.equal(firmwareUsbPort({usb_port:'COM8'},{transport:{port:'COM7',mode:'USB'}}),'COM8')
  assert.equal(firmwareUsbPort({}, {transport:{port:'COM7',mode:'USB'}}),'COM7')
  assert.equal(firmwareUsbPort({}, {transport:{port:'COM7',mode:'BLE'}}),'')
  assert.equal(firmwareUsbPort({}, {}),'')
})

// Compile the real script with a small lifecycle adapter: no DOM or hardware is used.
async function mountPanel(fetcher, remembered='', stateOverride={}) {
  const source=await readFile(new URL('../src/FirmwarePanel.vue',import.meta.url),'utf8')
  const {descriptor,errors}=parse(source)
  assert.deepEqual(errors,[])
  assert.deepEqual(compileTemplate({source:descriptor.template.content,filename:'FirmwarePanel.vue',id:'firmware-test'}).errors,[])
  const hooks={}
  const previous={fetch:globalThis.fetch,sessionStorage:globalThis.sessionStorage,hooks:globalThis.__firmwareTestHooks}
  globalThis.__firmwareTestHooks=hooks
  globalThis.fetch=fetcher
  globalThis.sessionStorage={getItem:()=>remembered,setItem:(_key,id)=>{remembered=id},removeItem:()=>{remembered=''}}
  const vue=`export const reactive=o=>o,ref=value=>({value}),computed=get=>({get value(){return get()}}),watch=()=>{},onMounted=f=>globalThis.__firmwareTestHooks.mounted=f,onBeforeUnmount=f=>globalThis.__firmwareTestHooks.unmount=f;`
  const vueUrl='data:text/javascript;base64,'+Buffer.from(vue).toString('base64')
  const helperUrl=new URL('../src/firmwarePresentation.js',import.meta.url).href
  const script=compileScript(descriptor,{id:'firmware-test'}).content.replace("from 'vue'",`from '${vueUrl}'`).replace("from './firmwarePresentation.js'",`from '${helperUrl}'`)
  const module=await import('data:text/javascript;base64,'+Buffer.from(script).toString('base64'))
  const events=[]
  const panel=module.default.setup({state:{...state,observed_at:Date.now()/1000,status_age_s:0,...stateOverride}},{expose:()=>{},emit:(name,value)=>events.push([name,value])})
  const cleanup=()=>{hooks.unmount?.();globalThis.fetch=previous.fetch;globalThis.sessionStorage=previous.sessionStorage;globalThis.__firmwareTestHooks=previous.hooks}
  try{await hooks.mounted();return {panel,events,cleanup,storedId:()=>remembered}}catch(error){cleanup();throw error}
}
const response=value=>({ok:true,json:async()=>value})

test('component mount, config save, scan and refresh never submit; user change submits once before response',async()=>{
  const calls=[]
  let finishSubmission
  const harness=await mountPanel(async(url,options={})=>{
    calls.push({url,options})
    if(url.endsWith('/jobs'))return new Promise(resolve=>{finishSubmission=resolve})
    if(url.endsWith('/status'))return response({busy:false,phase:'idle',job:null,error:null})
    if(url.endsWith('/scan'))return response({cables:[config.cable]})
    return response(config)
  })
  try{
    const {panel,events}=harness
    assert.equal(panel.selection.value,'')
    for(const suffix of ['/config','/status']){
      const call=calls.find(c=>c.url.endsWith(suffix))
      assert.equal(call.options.headers?.['X-J280-Local'],'1')
    }
    assert.equal(calls.some(c=>c.url.endsWith('/scan')),false)
    await panel.scanCables()
    assert.equal(panel.draft.cable,null)
    panel.selectCable({target:{value:'0'}})
    await panel.saveConfig()
    await panel.refresh()
    assert.equal(calls.some(c=>c.url.endsWith('/jobs')),false)
    const submit=panel.chooseTarget({target:{value:'V3'}})
    assert.equal(events.at(-1)[0],'status')
    assert.equal(events.at(-1)[1].busy,true)
    assert.equal(calls.filter(c=>c.url.endsWith('/jobs')).length,1)
    await panel.chooseTarget({target:{value:'V4'}})
    assert.equal(calls.filter(c=>c.url.endsWith('/jobs')).length,1)
    const write=calls.find(c=>c.url.endsWith('/jobs'))
    for(const call of calls.filter(c=>c.options.method==='POST'))assert.equal(call.options.headers['X-J280-Local'],'1')
    const body=JSON.parse(write.options.body)
    finishSubmission(response({request_id:body.request_id,target:'V3',state:'queued',phase:'checking',log:[]}))
    await submit
    assert.equal(events.at(-1)[0],'started')
    assert.equal(panel.selection.value,'')
  }finally{harness.cleanup()}
})

test('replay rejects all mutation handlers and target changes',async()=>{
  const calls=[]
  const harness=await mountPanel(async(url,options={})=>{calls.push({url,options});return response(config)},'',{replay:{active:true}})
  try{
    await harness.panel.saveConfig()
    await harness.panel.scanCables()
    await harness.panel.chooseTarget({target:{value:'V5'}})
    assert.equal(calls.length,1)
    assert(calls[0].url.endsWith('/config'))
    assert.equal(harness.panel.readiness.value.canSelect,false)
  }finally{harness.cleanup()}
})

test('unmount aborts outstanding requests',async()=>{
  let pendingSignal
  const harness=await mountPanel(async(url,options={})=>{
    if(url.endsWith('/pending'))return new Promise((_,reject)=>{pendingSignal=options.signal;pendingSignal.addEventListener('abort',()=>reject(new Error('aborted')),{once:true})})
    return response(url.endsWith('/status')?{busy:false,job:null,phase:'idle',error:null}:config)
  })
  const pending=harness.panel.request('/pending')
  const aborted=assert.rejects(pending,/aborted/)
  harness.cleanup()
  await aborted
  assert.equal(pendingSignal.aborted,true)
})

test('transport failure is queried by the original ID; server indeterminate unlocks without resubmission',async()=>{
  const calls=[]
  let submitted
  const harness=await mountPanel(async(url,options={})=>{
    calls.push({url,options})
    if(url.endsWith('/jobs')){submitted=JSON.parse(options.body);throw new Error('timeout')}
    if(url.includes('/jobs/'))return response({...submitted,state:'indeterminate',phase:'indeterminate',message:'interrupted',log:[]})
    if(url.endsWith('/status'))return response({busy:false,phase:'idle',job:null,error:null})
    return response(config)
  })
  try{
    await harness.panel.chooseTarget({target:{value:'V5'}})
    assert.equal(harness.panel.unresolvedRequest.value,true)
    assert.equal(harness.panel.status.value.busy,true)
    await harness.panel.chooseTarget({target:{value:'V4'}})
    await harness.panel.refresh()
    assert.equal(calls.filter(c=>c.url.endsWith('/jobs')).length,1)
    assert(calls.some(c=>c.url.endsWith('/jobs/'+submitted.request_id)))
    const query=calls.find(c=>c.url.endsWith('/jobs/'+submitted.request_id))
    assert.equal(query.options.headers?.['X-J280-Local'],'1')
    assert.equal(harness.panel.status.value.job.state,'indeterminate')
    assert.equal(harness.panel.status.value.busy,false)
    assert.equal(harness.panel.unresolvedRequest.value,false)
  }finally{harness.cleanup()}
})

test('known rejection does not persist a nonexistent request as an unknown task after reload',async()=>{
  const harness=await mountPanel(async(url)=>{
    if(url.endsWith('/jobs'))return {ok:false,status:409,json:async()=>({detail:{message:'busy'}})}
    return response(url.endsWith('/status')?{busy:false,job:null,phase:'idle',error:null}:config)
  })
  try{
    await harness.panel.chooseTarget({target:{value:'V1'}})
    assert.equal(harness.panel.status.value.job.state,'rejected')
    assert.equal(harness.panel.status.value.busy,false)
    assert.equal(harness.storedId(),'')
  }finally{harness.cleanup()}
})

test('refresh restores a remembered background task with no POST and leaves target empty',async()=>{
  const calls=[]
  const harness=await mountPanel(async(url,options={})=>{
    calls.push({url,options})
    if(url.endsWith('/status'))return response({busy:true,phase:'programming',job:{request_id:'remembered',target:'V1',state:'running',phase:'programming',log:['actual CLI output']},error:null})
    return response(config)
  },'remembered')
  try{
    assert.equal(harness.panel.selection.value,'')
    assert.equal(harness.panel.status.value.job.request_id,'remembered')
    assert.equal(harness.panel.status.value.job.log[0],'actual CLI output')
    assert(calls.every(c=>!c.options.method))
  }finally{harness.cleanup()}
})
