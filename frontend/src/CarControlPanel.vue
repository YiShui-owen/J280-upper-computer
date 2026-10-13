<template>
  <section class="car-control-settings">
    <div class="car-control-heading"><h3>小车连接</h3><span class="car-waiting-state"><i></i>未连接</span></div>
    <div class="car-connect-row">
      <div class="car-connection-type"><strong>BLE 蓝牙（WH-BLE102）</strong></div>
      <button class="button compact" disabled>搜索小车</button>
      <button class="button primary compact" disabled>连接小车</button>
    </div>
    <label class="car-device-select">设备<select disabled><option>未选择设备</option></select></label>
  </section>
</template>
