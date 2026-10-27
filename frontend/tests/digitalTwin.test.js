// Execute the actual SFC setup/watch logic with Vue; scene mounting and device I/O are disabled.
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as vue from 'vue'
import * as THREE from 'three'
import * as mapping from '../src/pendulumCalibration.js'

const script=fs.readFileSync(new URL('../src/DigitalTwin3D.vue',import.meta.url),'utf8')
  .match(/<script setup>([\s\S]*?)<\/script>/)[1]
  .replace(/^import .+\r?\n/gm,'').replace(/^const pendulumAssetUrl = .+\r?\n/m,'')
const setup=new Function('deps',`const {computed,onBeforeUnmount,onMounted,reactive,ref,watch,THREE,
  calibrationDefaults,calibrationStorageKey,normalizeDisplayCalibration,alphaReferencesValid,displayAlphaDeg,calibrateDownPose,
  window,defineProps,defineExpose}=deps;
  ${script}
  return {calibrationProfile,calibration,restoreCalibration,canAlignDown,
    target:()=>THREE.MathUtils.radToDeg(targetPendulum)};`)
function harness(initial={},saved={}) {
  const storage=new Map(Object.entries(saved).map(([key,value])=>[key,JSON.stringify(value)]))
  const props=vue.reactive({firmware:'',session:'',armAngle:null,pendulumAngle:null,mode:'WAITING',sampleTime:0,sampleTick:null,armVelocity:null,pendulumVelocity:null,pwmPercent:null,...initial})
  const scope=vue.effectScope()
  const component=scope.run(()=>setup({...vue,...mapping,THREE,normalizeDisplayCalibration:mapping.normalizeCalibration,
    onMounted:()=>{},onBeforeUnmount:()=>{},defineProps:()=>props,defineExpose:()=>{},
    window:{localStorage:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)}}}))
  return {...component,storage,close:()=>scope.stop(),push:async values=>{Object.assign(props,values);await vue.nextTick()}}
}
const key=mapping.calibrationStorageKey

test('async FD2 identity loads its own calibration instead of a contaminated generic profile',async()=>{
  for(const firmware of ['V1','V2','V3','V4','V5']) {
    const generic={...mapping.calibrationDefaults(''),alphaOffsetDeg:90}
    const h=harness({}, {[key('')]:generic,[key(firmware)]:mapping.calibrationDefaults(firmware)})
    try {
      await h.push({firmware,session:'new-device',pendulumAngle:-.084,sampleTick:1000,mode:'BALANCE'})
      assert.equal(h.calibrationProfile.value,firmware)
      assert(Math.abs(h.target()-.084)<1e-8)
      h.restoreCalibration();await vue.nextTick()
      assert.equal(h.storage.get(key('')),JSON.stringify(generic),'must not overwrite another profile')
      assert.deepEqual(JSON.parse(h.storage.get(key(firmware))),mapping.calibrationDefaults(firmware))
    }finally{h.close()}
  }
})
test('FD2 hot switch reloads calibration and reaccepts an equal device tick from another session',async()=>{
  const h=harness({firmware:'V2',session:'v2',pendulumAngle:0,sampleTick:1000,pendulumVelocity:0}, {
    [key('V2')]:mapping.calibrationDefaults('V2'),
    [key('V5')]:{...mapping.calibrationDefaults('V5'),alphaOffsetDeg:17},
  })
  try {
    await h.push({firmware:'V5',session:'v5',pendulumAngle:180,sampleTick:1000,mode:'FAULT',pwmPercent:0})
    assert.equal(h.calibrationProfile.value,'V5')
    assert(Math.abs(h.target()+163)<1e-8)
    await h.push({firmware:''})
    assert.equal(h.calibrationProfile.value,'V5','temporary unknown identity does not save over a profile')
  }finally{h.close()}
})
test('display-only down alignment is available after confirmed zero-output fault, and unavailable with unknown output',async()=>{
  const h=harness({firmware:'V5',pendulumAngle:180,sampleTick:1,mode:'FAULT',pwmPercent:0})
  try {
    assert.equal(h.canAlignDown.value,true)
    await h.push({pwmPercent:null});assert.equal(h.canAlignDown.value,false)
    await h.push({pwmPercent:1});assert.equal(h.canAlignDown.value,false)
    await h.push({mode:'BALANCE',pwmPercent:0});assert.equal(h.canAlignDown.value,false)
  }finally{h.close()}
})
