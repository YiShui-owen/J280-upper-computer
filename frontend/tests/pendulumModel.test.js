import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import crypto from 'node:crypto'
import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

let mountPendulumModel, PENDULUM_DISPLAY
try { ({ mountPendulumModel, PENDULUM_DISPLAY } = await import('../src/pendulumModel.js')) }
catch (error) { if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error }

async function model() {
  assert.equal(typeof mountPendulumModel, 'function', '需要 STEP 摆杆显示适配')
  const bytes = await fs.readFile(new URL('../src/assets/models/l-pendulum.glb', import.meta.url))
  const gltf = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset+bytes.byteLength), '')
  return gltf.scene
}

test('网页网格保留 STEP 实物尺寸、36 个面以及源文件追溯', async () => {
  const scene = await model()
  const metadata = JSON.parse(await fs.readFile(new URL('../src/assets/models/l-pendulum.meta.json', import.meta.url),'utf8'))
  const source = await fs.readFile(new URL('../model-sources/l-arm.step',import.meta.url))
  assert.equal(crypto.createHash('sha256').update(source).digest('hex'),metadata.sourceSha256)
  assert.equal(metadata.sourceFaces,36)
  const bounds = new THREE.Box3().setFromObject(scene), size=bounds.getSize(new THREE.Vector3())
  assert.ok(Math.abs(size.x-.04)<1e-6, '原 40 mm 折边尺寸')
  assert.ok(Math.abs(size.y-.152)<1e-6, '原 152 mm 总长')
  assert.ok(Math.abs(size.z-.036)<1e-6, '原 36 mm 宽度')
  assert.ok(Math.abs(bounds.max.y-.134)<1e-6, '安装轴到远端 134 mm')
  let triangles=0
  scene.traverse(object=>{if(object.isMesh) triangles+=object.geometry.index.count/3})
  assert.equal(triangles,metadata.triangles)
})

test('等比例显示且轴端向上、向下时均完整处于地面上方', async () => {
  const part=await model()
  mountPendulumModel(part, new THREE.MeshStandardMaterial())
  assert.equal(part.scale.x,part.scale.y)
  assert.equal(part.scale.y,part.scale.z)
  const arm=new THREE.Group(), pendulum=new THREE.Group()
  arm.position.y=1.70
  pendulum.position.x=2.23
  arm.add(pendulum)
  pendulum.add(part)
  const upright=new THREE.Box3().setFromObject(arm)
  assert.ok(Math.abs(upright.max.y-(1.70+2.21))<1e-5,'保留原场景摆杆显示高度')
  pendulum.rotation.x=Math.PI
  arm.updateMatrixWorld(true)
  const down=new THREE.Box3().setFromObject(arm)
  assert.ok(down.min.y > -1, '下垂模型没有穿过地面')
})

test('摆杆始终跟随旋臂局部轴运动，正负摆角保持相反方向', async () => {
  const part=await model()
  mountPendulumModel(part,new THREE.MeshStandardMaterial())
  const arm=new THREE.Group(), pivot=new THREE.Group()
  pivot.position.set(2.23,1.70,0)
  pivot.add(part)
  arm.add(pivot)
  const point=new THREE.Vector3(0,.134,0)
  pivot.rotation.x=Math.PI/2
  arm.updateMatrixWorld(true)
  const positive=part.localToWorld(point.clone())
  assert.ok(positive.z>2,'正摆角沿局部 +Z')
  pivot.rotation.x=-Math.PI/2
  arm.updateMatrixWorld(true)
  const negative=part.localToWorld(point.clone())
  assert.ok(negative.z<-2,'负摆角沿局部 -Z')
  pivot.rotation.x=Math.PI/2
  arm.rotation.y=Math.PI/2
  arm.updateMatrixWorld(true)
  const turned=part.localToWorld(point.clone())
  assert.ok(Math.abs(turned.x-positive.z)<1e-5,'摆角跟随旋臂转到新的方向')
  assert.ok(Math.abs(turned.z+positive.x)<1e-5,'沿旋臂旋转后的铰链轴摆动')
  assert.equal(PENDULUM_DISPLAY.hingeOffset,part.position.x)
})
