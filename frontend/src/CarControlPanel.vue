<template>
  <section class="car-control-settings">
    <div class="car-control-heading"><span class="car-waiting-state" :class="{live:control.apiOnline && control.status.connected}" title="BLE 蓝牙 · WH-BLE102"><i></i>{{ control.apiOnline ? control.status.connected ? '小车已连接' : '小车未连接' : control.apiError ? '小车服务不可用' : '连接服务中' }}</span></div>
    <div class="car-connect-row">
      <button class="button compact" :disabled="!control.apiOnline || control.busy || control.status.connected" @click="control.scan()">{{ control.busy ? '处理中…' : '搜索小车' }}</button>
      <button class="button primary compact" :disabled="!control.apiOnline || control.busy || !control.selected || control.status.connected" @click="control.connect()">连接小车</button>
      <button v-if="control.status.connected" class="button compact" :disabled="control.busy" @click="control.disconnect()">断开</button>
    </div>
    <label class="car-device-select"><span class="sr-only">小车设备</span><select v-model="control.selected" aria-label="小车设备" :disabled="control.busy || control.status.connected"><option value="">选择小车</option><option v-for="device in control.devices" :key="device.id" :value="device.id">{{ device.name || '未命名设备' }} · {{ device.id }}</option></select></label>
  </section>
</template>
<script setup>
defineProps({control:{type:Object,required:true}})
</script>
