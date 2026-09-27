<template>
  <div ref="host" class="twin3d-host">
    <div class="twin3d-corner-label">
      <span>MECHANICAL TWIN</span>
      <b>左键旋转 · 滚轮缩放 · 右键平移</b>
    </div>
    <div class="twin3d-tools">
      <button type="button" @click="resetView">重置视角</button>
      <button v-if="isDev" type="button" :aria-expanded="calibrationOpen" @click="calibrationOpen = !calibrationOpen">
        {{ calibrationOpen ? '隐藏标定' : 'Calibration' }}
      </button>
    </div>
    <section v-if="isDev && calibrationOpen" class="twin3d-calibration" aria-label="3D Calibration" @change="normalizeCalibration">
      <div class="calibration-heading"><b>Calibration</b><span>仅调整 3D 映射</span></div>
      <label>θ direction
        <select v-model.number="calibration.thetaDirection"><option :value="1">+1</option><option :value="-1">−1</option></select>
      </label>
      <label>θ offset (°)<input v-model.number="calibration.thetaOffsetDeg" type="number" step="0.1" /></label>
      <label>α direction
        <select v-model.number="calibration.alphaDirection"><option :value="1">+1</option><option :value="-1">−1</option></select>
      </label>
      <label>α offset (°)<input v-model.number="calibration.alphaOffsetDeg" type="number" step="0.1" /></label>
      <label class="calibration-toggle">α 两点显示标定<input v-model="calibration.alphaTwoPointEnabled" type="checkbox" /></label>
      <template v-if="calibration.alphaTwoPointEnabled">
        <label>竖直向上读数 (°)<input v-model.number="calibration.alphaUprightDeg" type="number" step="0.001" /></label>
        <label>自然下垂读数 (°)<input v-model.number="calibration.alphaDownDeg" type="number" step="0.001" /></label>
        <p v-if="!alphaReferencesValid(calibration)" role="status">两参考点的最短夹角须至少为 90°；当前暂用原始角度映射。</p>
        <p>两点校正后再应用 α direction / offset。参考读数可微调；关闭后恢复原始角度映射。</p>
      </template>
      <label>smoothing (s)<input v-model.number="calibration.smoothing" type="number" min="0" max="0.05" step="0.005" /></label>
      <p>0 = 关闭插值；两轴异常样本检查仍开启。参数自动保存在当前浏览器。</p>
      <p>BALANCE 微动轻量平滑。没有角速度支持的突跳需连续样本确认，不因等待超时而放行。</p>
      <p>模型零点：θ 沿 +X，α 竖直向上。</p>
      <button type="button" @click="restoreCalibration">恢复默认标定</button>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'

const props = defineProps({
  armAngle: { type:Number, default:0 },
  pendulumAngle: { type:Number, default:0 },
  mode: { type:String, default:'WAITING' },
  sampleTime: { type:Number, default:0 }, // Existing received_at; repeated equal samples can confirm real motion.
  sampleTick: { type:Number, default:null }, // Existing FPGA timestamp (ms), independent of arrival bursts.
  armVelocity: { type:Number, default:null }, // Degrees/s, only used to validate the displayed pose.
  pendulumVelocity: { type:Number, default:null },
})

const host = ref(null)
const isDev = import.meta.env.DEV
const calibrationOpen = ref(false)
// Angles are degrees at the telemetry boundary. Persisted values override these
// defaults in this browser; copy the final hardware calibration here for deployment.
const calibrationDefaults = Object.freeze({
  thetaDirection: 1,
  thetaOffsetDeg: 0,
  alphaDirection: -1,
  alphaOffsetDeg: 0,
  // Display references supplied from the same physical setup, 2026-09-26.
  // The hand-held upright sample is approximate; refine both in Calibration.
  alphaTwoPointEnabled: true,
  alphaUprightDeg: -.396,
  alphaDownDeg: -169.937,
  smoothing: 0.02, // Time constant in seconds, 0 disables interpolation; capped at 50 ms.
})
const calibrationStorageKey = 'j280:twin3d:calibration:v1'
const calibration = reactive(loadCalibration())
// Display-only sample conditioning, before calibration; never modifies telemetry.
const displayTuning = Object.freeze({
  jumpToleranceDeg: 2,
  velocityAllowance: 2,
  confirmationSamples: 4,
  confirmationSpanMs: 100,
  balanceSmoothing: .06,
  microMotionDeg: .25,
  fullSpeedDeg: 1,
})
const displayFloorY = -1
let renderer, scene, camera, controls, base, armPivot, pendulumPivot, motorHalo, stabilityHalo, stabilityMaterial, resizeObserver
let environmentTarget
let raf = 0
let lastFrameTime = null
let currentArm = 0
let currentPendulum = 0
let targetArm = 0
let targetPendulum = 0
const armSamples = createAngleSamples()
const pendulumSamples = createAngleSamples()
let lastSampleTick = null

function finiteNumber(value, fallback){
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}
function normalizedCalibration(value = {}){
  return {
    thetaDirection: [1, -1].includes(value.thetaDirection) ? value.thetaDirection : calibrationDefaults.thetaDirection,
    thetaOffsetDeg: finiteNumber(value.thetaOffsetDeg, calibrationDefaults.thetaOffsetDeg),
    alphaDirection: [1, -1].includes(value.alphaDirection) ? value.alphaDirection : calibrationDefaults.alphaDirection,
    alphaOffsetDeg: finiteNumber(value.alphaOffsetDeg, calibrationDefaults.alphaOffsetDeg),
    alphaTwoPointEnabled: typeof value.alphaTwoPointEnabled === 'boolean' ? value.alphaTwoPointEnabled : calibrationDefaults.alphaTwoPointEnabled,
    alphaUprightDeg: finiteNumber(value.alphaUprightDeg, calibrationDefaults.alphaUprightDeg),
    alphaDownDeg: finiteNumber(value.alphaDownDeg, calibrationDefaults.alphaDownDeg),
    smoothing: THREE.MathUtils.clamp(finiteNumber(value.smoothing, calibrationDefaults.smoothing), 0, .05),
  }
}
function loadCalibration(){
  try {
    return normalizedCalibration(JSON.parse(window.localStorage.getItem(calibrationStorageKey)) || {})
  } catch {
    return { ...calibrationDefaults }
  }
}
function restoreCalibration(){
  Object.assign(calibration, calibrationDefaults)
}
function normalizeCalibration(){
  // Commit validation on change, allowing intermediate input such as '-' or '0.'.
  Object.assign(calibration, normalizedCalibration(calibration))
}
// Validate the two telemetry axes before applying calibration. Raw readouts,
// charts and control data remain untouched. A repeated packet is not new evidence.
watch(
  () => [props.armAngle, props.pendulumAngle, props.armVelocity, props.pendulumVelocity, props.sampleTime, props.sampleTick],
  () => {
    const tick = Number.isFinite(props.sampleTick) ? props.sampleTick
      : props.sampleTime > 0 ? props.sampleTime * 1000 : null
    if (tick !== null && tick === lastSampleTick) return
    const firstTimedSample = tick !== null && lastSampleTick === null
    const sampleClock = tick ?? performance.now()
    if (tick !== null && lastSampleTick !== null && tick < lastSampleTick){
      // A reboot OR a truncated timestamp can move the clock backward. Reset
      // timing only: neither case is evidence that both mechanical angles are zero.
      for (const samples of [armSamples, pendulumSamples]){
        samples.acceptedAt = sampleClock
        samples.candidate = null
        samples.confirmations = 0
      }
    }
    lastSampleTick = tick
    acceptAngleSample(armSamples, props.armAngle, props.armVelocity, sampleClock, firstTimedSample)
    acceptAngleSample(pendulumSamples, props.pendulumAngle, props.pendulumVelocity, sampleClock, firstTimedSample)
    mapPoseTargets()
  },
  { immediate:true },
)
watch(calibration, () => {
  const config = normalizedCalibration(calibration)
  mapPoseTargets()
  try {
    window.localStorage.setItem(calibrationStorageKey, JSON.stringify(config))
  } catch { /* Rendering still works when browser storage is unavailable. */ }
})

function createAngleSamples(){
  return { initialized:false, value:0, acceptedAt:0, candidate:null, candidateSince:0, confirmations:0 }
}
function acceptAngleSample(samples, value, velocity, sampleClock, initialize){
  if (!Number.isFinite(value)) return
  const delta = THREE.MathUtils.radToDeg(angleDelta(
    THREE.MathUtils.degToRad(samples.value), THREE.MathUtils.degToRad(value),
  ))
  const tolerance = displayTuning.jumpToleranceDeg
  // Pair displacement with the time since THAT accepted position. Using only
  // the latest packet interval would freeze real motion after dropped samples.
  const dt = Math.max(.001, (sampleClock - samples.acceptedAt) / 1000)
  // Use the CURRENT velocity, not a stale or possibly truncated previous value.
  // Missing velocity props preserve compatibility for standalone angle-only use.
  const movingInDirection = Number.isFinite(velocity) && Math.sign(velocity) === Math.sign(delta)
  const allowed = tolerance + (movingInDirection ? Math.abs(velocity) * dt * displayTuning.velocityAllowance : 0)
  if (initialize || !samples.initialized || !Number.isFinite(velocity) || Math.abs(delta) <= allowed){
    samples.initialized = true
    samples.value = value
    samples.acceptedAt = sampleClock
    samples.candidate = null
    samples.confirmations = 0
    return
  }
  const candidateDelta = samples.candidate === null ? Infinity : Math.abs(THREE.MathUtils.radToDeg(angleDelta(
    THREE.MathUtils.degToRad(samples.candidate), THREE.MathUtils.degToRad(value),
  )))
  if (candidateDelta > tolerance){
    samples.candidateSince = sampleClock
    samples.confirmations = 0
  }
  samples.candidate = value
  samples.confirmations += 1
  // Reacquire a genuine new steady pose even when its velocity sample was missed.
  // Only fresh consistent samples can confirm it; animation time cannot do so.
  if (samples.confirmations >= displayTuning.confirmationSamples &&
      sampleClock - samples.candidateSince >= displayTuning.confirmationSpanMs){
    samples.value = value
    samples.acceptedAt = sampleClock
    samples.candidate = null
    samples.confirmations = 0
  }
}
function alphaReferencesValid(config){
  if (!Number.isFinite(config.alphaUprightDeg) || !Number.isFinite(config.alphaDownDeg)) return false
  const span = THREE.MathUtils.euclideanModulo(config.alphaDownDeg - config.alphaUprightDeg, 360)
  // Prevent nearly coincident references from creating extreme angular gains.
  return span >= 90 && span <= 270
}
function correctAlphaTelemetry(value, config){
  if (!config.alphaTwoPointEnabled || !alphaReferencesValid(config)) return value
  const down = THREE.MathUtils.euclideanModulo(config.alphaDownDeg - config.alphaUprightDeg, 360)
  const phase = THREE.MathUtils.euclideanModulo(value - config.alphaUprightDeg, 360)
  // Map the two measured arcs separately to two physical half-turns. A single
  // gain of 180/169.541 would break continuity when raw telemetry wraps at +/-180.
  const corrected = phase <= down ? 180 * phase / down
    : 180 + 180 * (phase - down) / (360 - down)
  return corrected > 180 ? corrected - 360 : corrected
}
function mapPoseTargets(){
  const config = normalizedCalibration(calibration)
  if (armSamples.initialized && Number.isFinite(calibration.thetaOffsetDeg)){
    targetArm = THREE.MathUtils.degToRad(config.thetaDirection * armSamples.value + config.thetaOffsetDeg)
  }
  if (pendulumSamples.initialized && Number.isFinite(calibration.alphaOffsetDeg)){
    const alpha = config.alphaTwoPointEnabled && !alphaReferencesValid(calibration)
      ? pendulumSamples.value : correctAlphaTelemetry(pendulumSamples.value, config)
    targetPendulum = THREE.MathUtils.degToRad(config.alphaDirection * alpha + config.alphaOffsetDeg)
  }
}

function metal(color, roughness=.3, metalness=.85){
  return new THREE.MeshStandardMaterial({ color, roughness, metalness })
}
function addBox(parent, size, pos, material){
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size), material)
  mesh.position.set(...pos)
  mesh.castShadow = true
  mesh.receiveShadow = true
  parent.add(mesh)
  return mesh
}
function addCylinder(parent, radiusTop, radiusBottom, height, pos, material, radial=48){
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radiusTop, radiusBottom, height, radial), material)
  mesh.position.set(...pos)
  mesh.castShadow = true
  mesh.receiveShadow = true
  parent.add(mesh)
  return mesh
}
function addHingeCylinder(parent, radius, depth, pos, material){
  const mesh = addCylinder(parent, radius, radius, depth, pos, material, 48)
  // CylinderGeometry starts along +Y. The real J280 hinge is radial, along +X.
  mesh.rotation.z = -Math.PI / 2
  return mesh
}
function addScrew(parent, x, z, y=.47){
  const screw = addCylinder(parent, .045, .045, .035, [x, y, z], metal(0x98a8b4,.22,.9), 24)
  return screw
}

function initScene(){
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x0d2030)
  scene.fog = new THREE.FogExp2(0x0d2030, .028)

  // Preserve the original 3/4 position/target; leave headroom for the upright rod.
  camera = new THREE.PerspectiveCamera(44, 1, .1, 100)
  camera.position.set(5.45, 3.75, 6.55)
  camera.lookAt(.30, 1.26, 0)

  renderer = new THREE.WebGLRenderer({ antialias:true, alpha:true, powerPreference:'high-performance' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  renderer.setClearColor(0x000000, 0)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.outputColorSpace = THREE.SRGBColorSpace
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.18
  host.value.prepend(renderer.domElement)

  // Broad reflections make metal readable on its shaded faces. Generate once
  // locally, without an HDR download or a visible room in the dark-blue scene.
  const environment = new RoomEnvironment()
  const pmrem = new THREE.PMREMGenerator(renderer)
  environmentTarget = pmrem.fromScene(environment, .03)
  scene.environment = environmentTarget.texture
  scene.environmentIntensity = .65
  environment.dispose()
  pmrem.dispose()

  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(.30, 1.26, 0)
  controls.enableDamping = true
  controls.dampingFactor = .08
  controls.enableRotate = true
  controls.enableZoom = true
  controls.enablePan = true
  controls.mouseButtons = { LEFT:THREE.MOUSE.ROTATE, MIDDLE:THREE.MOUSE.DOLLY, RIGHT:THREE.MOUSE.PAN }
  controls.minDistance = 2.5
  controls.maxDistance = 18
  controls.maxPolarAngle = Math.PI / 2 - .06
  controls.cursor.copy(controls.target)
  controls.maxTargetRadius = 6
  controls.update()
  controls.saveState()

  scene.add(new THREE.HemisphereLight(0xe5f3ff, 0x334b61, 1.75))
  const key = new THREE.DirectionalLight(0xf0f7ff, 2.8)
  key.position.set(4.3, 7.5, 4.2)
  key.castShadow = true
  key.shadow.mapSize.set(2048, 2048)
  key.shadow.camera.left = -6
  key.shadow.camera.right = 6
  key.shadow.camera.top = 6
  key.shadow.camera.bottom = -6
  scene.add(key)

  const rim = new THREE.PointLight(0x8bcff5, 12, 10, 2)
  rim.position.set(-3.6, 3.0, -3.6)
  scene.add(rim)
  const fill = new THREE.PointLight(0xc9dcf0, 10, 9, 2)
  fill.position.set(3.6, 2.0, 2.8)
  scene.add(fill)

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(200, 200),
    new THREE.MeshStandardMaterial({ color:0x040b13, roughness:.98, metalness:0, envMapIntensity:.05 })
  )
  floor.rotation.x = -Math.PI / 2
  floor.name = 'displayFloor'
  // Lowest swept point is 1.70 - 2.21 - .13 = -.64, leaving .36 clearance.
  floor.position.y = displayFloorY
  floor.receiveShadow = true
  scene.add(floor)

  const grid = new THREE.GridHelper(32, 80, 0x226789, 0x173147)
  grid.name = 'displayGrid'
  grid.position.y = displayFloorY + .006
  grid.material.transparent = true
  grid.material.opacity = .18
  grid.material.depthWrite = false
  grid.material.onBeforeCompile = shader => {
    // Interpolate coordinates, not endpoint distances: each grid line spans the
    // whole floor and would disappear if both endpoint fade values were zero.
    shader.vertexShader = 'varying vec2 vGridPosition;\n' + shader.vertexShader
    shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>',
      '#include <begin_vertex>\nvGridPosition = position.xz;')
    shader.fragmentShader = 'varying vec2 vGridPosition;\n' + shader.fragmentShader
    shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>',
      '#include <color_fragment>\ndiffuseColor.a *= 1.0 - smoothstep(3.0, 12.0, length(vGridPosition));')
  }
  scene.add(grid)

  const baseSteel = metal(0x6b7b89,.45,.55)
  const darkSteel = metal(0x2b3947,.40,.68)
  const silver = metal(0xc3cdd6,.28,.80)
  const armSilver = metal(0xc8d4df,.32,.72)
  const armEdge = metal(0xa4bac8,.28,.70)
  const counterSteel = metal(0x60707e,.40,.65)
  const rodSteel = metal(0xe3eaf0,.28,.70)
  const accent = new THREE.MeshStandardMaterial({
    color:0x38bdf8, emissive:0x083a50, emissiveIntensity:.75,
    metalness:.68, roughness:.18,
  })

  // Fixed frame: base -> armPivot (local Y / world vertical) -> pendulumPivot (local X).
  base = new THREE.Group()
  base.name = 'base'
  scene.add(base)

  // Fixed display support under the existing instrument. Keep the original
  // hinge height, arm and rod dimensions; the pendulum swings beside this stand.
  const support = new THREE.Group()
  support.name = 'displaySupport'
  base.add(support)
  const supportMaterial = metal(0x334858, .65, .30)
  addBox(support, [2.16,.12,1.58], [0,displayFloorY+.06,0], supportMaterial)
  addBox(support, [1.38,.80,1.06], [0,-.48,0], supportMaterial)
  addBox(support, [1.92,.08,1.38], [0,-.04,0], darkSteel)

  // Square instrument base with mounting details.
  addBox(base, [2.05,.38,1.48], [0,.19,0], baseSteel)
  addBox(base, [1.76,.09,1.22], [0,.425,0], darkSteel)
  addScrew(base,-.73,-.47)
  addScrew(base,.73,-.47)
  addScrew(base,-.73,.47)
  addScrew(base,.73,.47)

  // Motor / encoder stack.
  addCylinder(base,.43,.43,.42,[0,.69,0],darkSteel)
  addCylinder(base,.31,.31,.14,[0,.98,0],silver)
  addCylinder(base,.25,.25,.24,[0,1.17,0],baseSteel)
  addCylinder(base,.105,.105,.43,[0,1.48,0],silver)
  addCylinder(base,.29,.29,.10,[0,1.69,0],darkSteel)

  motorHalo = new THREE.Mesh(
    new THREE.TorusGeometry(.37,.012,12,80),
    new THREE.MeshBasicMaterial({ color:0x38bdf8, transparent:true, opacity:.45 })
  )
  motorHalo.rotation.x = Math.PI / 2
  motorHalo.position.y = .49
  base.add(motorHalo)

  // Furuta arm: active side + short counterweight side.
  armPivot = new THREE.Group()
  armPivot.name = 'armPivot'
  armPivot.position.set(0,1.70,0)
  base.add(armPivot)

  addBox(armPivot,[2.30,.105,.17],[1.09,0,0],armSilver)
  addBox(armPivot,[.75,.11,.17],[-.38,0,0],armSilver)
  addBox(armPivot,[.34,.30,.32],[-.78,.02,0],counterSteel)
  addBox(armPivot,[.06,.14,.21],[2.20,0,0],armEdge)

  // End encoder / hinge ring: both coaxial with the real local X hinge.
  addHingeCylinder(armPivot,.19,.30,[2.23,0,0],darkSteel)
  addHingeCylinder(armPivot,.135,.32,[2.23,0,0],silver)
  const encoderRing = new THREE.Mesh(new THREE.TorusGeometry(.205,.022,12,64), accent)
  encoderRing.position.set(2.23,0,0)
  encoderRing.rotation.y = Math.PI / 2
  armPivot.add(encoderRing)

  pendulumPivot = new THREE.Group()
  pendulumPivot.name = 'pendulumPivot'
  pendulumPivot.position.set(2.23,0,0)
  armPivot.add(pendulumPivot)

  // α=0: rod along +Y. Positive α rotates toward local +Z about local +X.
  // This entire frame follows θ; never rotate the rod about a world axis.
  addCylinder(pendulumPivot,.047,.047,2.18,[0,1.09,0],rodSteel,32)
  const topMass = new THREE.Mesh(new THREE.SphereGeometry(.13,28,20), counterSteel)
  topMass.position.set(0,2.21,0)
  topMass.castShadow = true
  pendulumPivot.add(topMass)

  // Vertical target reference attached to the rotating hinge.
  const guideGeometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(2.23,.12,0),
    new THREE.Vector3(2.23,2.42,0),
  ])
  const guide = new THREE.Line(
    guideGeometry,
    new THREE.LineDashedMaterial({ color:0x34d399, dashSize:.075, gapSize:.065, transparent:true, opacity:.28 })
  )
  guide.computeLineDistances()
  armPivot.add(guide)

  stabilityMaterial = new THREE.MeshBasicMaterial({ color:0x34d399, transparent:true, opacity:.35 })
  stabilityHalo = new THREE.Mesh(new THREE.TorusGeometry(.23,.010,10,64), stabilityMaterial)
  stabilityHalo.position.set(2.23,2.28,0)
  stabilityHalo.rotation.x = Math.PI / 2
  armPivot.add(stabilityHalo)

  resizeObserver = new ResizeObserver(resize)
  resizeObserver.observe(host.value)
  resize()
  currentArm = targetArm
  currentPendulum = targetPendulum
  animate(performance.now())
}

function resetView(){
  if (!controls) return
  // Flush residual orbit/pan damping before reset, so an immediate reset cannot drift.
  const damping = controls.enableDamping
  controls.enableDamping = false
  controls.update()
  controls.reset()
  controls.enableDamping = damping
}
function resize(){
  if (!renderer || !host.value) return
  const width = Math.max(10, host.value.clientWidth)
  const height = Math.max(10, host.value.clientHeight)
  renderer.setSize(width, height, false)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
}
function angleDelta(a, b){
  return THREE.MathUtils.euclideanModulo(b - a + Math.PI, Math.PI * 2) - Math.PI
}
function angleLerp(a, b, t){
  // Keep a continuous local angle across +/-180, including multi-turn telemetry.
  return a + angleDelta(a, b) * t
}
function pendulumSmoothing(smoothing){
  if (smoothing === 0 || props.mode !== 'BALANCE') return smoothing
  const errorDeg = Math.abs(THREE.MathUtils.radToDeg(angleDelta(currentPendulum, targetPendulum)))
  const motion = THREE.MathUtils.smoothstep(errorDeg, displayTuning.microMotionDeg, displayTuning.fullSpeedDeg)
  // Filter tiny rapid fluctuations without a dead zone, zero clamp, or angle gain.
  // Genuine motion uses the original fast response and steady angles remain exact.
  return THREE.MathUtils.lerp(Math.max(smoothing, displayTuning.balanceSmoothing), smoothing, motion)
}
function modeColor(){
  if (props.mode === 'BALANCE') return 0x34d399
  if (props.mode === 'SWING') return 0xfbbf24
  if (props.mode === 'FAULT') return 0xf87171
  return 0x38bdf8
}
function animate(now){
  raf = requestAnimationFrame(animate)
  const previousFrameTime = lastFrameTime ?? now
  const dt = Math.max(0, (now - previousFrameTime) / 1000)
  lastFrameTime = now
  const smoothing = normalizedCalibration(calibration).smoothing
  const blend = smoothing === 0 ? 1 : -Math.expm1(-dt / smoothing)
  const alphaSmoothing = pendulumSmoothing(smoothing)
  const alphaBlend = alphaSmoothing === 0 ? 1 : -Math.expm1(-dt / alphaSmoothing)
  currentArm = angleLerp(currentArm, targetArm, blend)
  currentPendulum = angleLerp(currentPendulum, targetPendulum, alphaBlend)
  if (armPivot) armPivot.rotation.y = currentArm
  if (pendulumPivot) pendulumPivot.rotation.x = currentPendulum

  const color = modeColor()
  if (motorHalo){
    motorHalo.material.color.setHex(color)
    motorHalo.material.opacity = .35 + Math.sin(performance.now() * .0022) * .06
    motorHalo.rotation.z += .0015
  }
  if (stabilityMaterial){
    stabilityMaterial.color.setHex(color)
    stabilityMaterial.opacity = props.mode === 'BALANCE' ? .46 : .23
  }
  if (stabilityHalo) stabilityHalo.scale.setScalar(1 + Math.sin(performance.now()*.0017)*.025)

  controls.update()
  // Orbit remains above the floor even after a downward right-button pan.
  const lift = Math.max(0, displayFloorY + .2 - controls.target.y)
  controls.target.y += lift
  camera.position.y += lift
  renderer.render(scene, camera)
}

onMounted(initScene)
onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  resizeObserver?.disconnect()
  controls?.dispose()
  environmentTarget?.dispose()
  if (renderer){ renderer.dispose(); renderer.domElement.remove() }
  scene?.traverse(object => {
    object.geometry?.dispose?.()
    if (object.material){
      const materials = Array.isArray(object.material) ? object.material : [object.material]
      materials.forEach(material => material.dispose?.())
    }
  })
})
</script>

<style scoped>
.twin3d-tools{position:absolute;z-index:4;right:12px;top:11px;display:flex;gap:6px}
.twin3d-tools button,.twin3d-calibration button{border:1px solid #31546b;border-radius:5px;background:rgba(9,26,40,.94);color:#b7d2e2;padding:6px 9px;font-size:10px;cursor:pointer}
.twin3d-tools button:hover,.twin3d-calibration button:hover{border-color:#38bdf8;color:#edf8ff}
.twin3d-calibration{position:absolute;z-index:4;right:12px;top:48px;width:min(256px,calc(100% - 24px));max-height:calc(100% - 60px);overflow:auto;box-sizing:border-box;padding:12px;border:1px solid #31546b;border-radius:8px;background:rgba(7,20,32,.96);color:#a9c1d1;box-shadow:0 8px 24px #0005;font-size:11px}
.calibration-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.calibration-heading b{color:#d3e7f3}.calibration-heading span{font-size:9px;color:#829eaf}
.twin3d-calibration label{display:grid;grid-template-columns:1fr 90px;gap:10px;align-items:center;margin:8px 0}
.twin3d-calibration input,.twin3d-calibration select{min-width:0;width:100%;box-sizing:border-box;border:1px solid #31546b;border-radius:4px;background:#0b1c2b;color:#d9edf9;padding:5px;font:inherit;color-scheme:dark}
.twin3d-calibration .calibration-toggle{border-top:1px solid #234153;padding-top:10px;margin-top:12px}
.twin3d-calibration input[type=checkbox]{width:16px;height:16px;justify-self:end;accent-color:#38bdf8}
.twin3d-calibration p{color:#829eaf;font-size:10px;line-height:1.6;margin:9px 0}
.twin3d-tools button:focus-visible,.twin3d-calibration :is(input,select,button):focus-visible{outline:2px solid #38bdf8;outline-offset:2px}
</style>
