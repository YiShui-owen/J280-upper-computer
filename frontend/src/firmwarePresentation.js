export const FIRMWARE_TARGETS = ['V1', 'V2', 'V3', 'V4', 'V5']
export const initialFirmwareSelection = () => ''
export function firmwareJobTerminal(job) {return ['succeeded','failed','indeterminate'].includes(job?.state)}

export function firmwareReadiness({state = {}, config = {}, status = {}, statusKnown = false,
  loading = false, dirty = false, motorIsolated = false, unresolvedRequest = false, now = Date.now()} = {}) {
  const replay = Boolean(state.replay?.active)
  const busy = Boolean(status.busy || state.programming?.busy)
  const needsIsolation = !state.host_online && !state.connected && !replay
  const elapsed = Math.max(0, now / 1000 - Number(state.observed_at))
  const fresh = Number.isFinite(state.status_age_s) && state.status_age_s >= 0 && state.status_age_s + elapsed < .5
  const hostReady = Boolean(state.host_online && state.connected && state.synced && state.status_fresh &&
    FIRMWARE_TARGETS.includes(state.firmware) && fresh && !state.fd2?.log_error)
  const cable = config.cable
  const configured = Boolean(config.configured && config.programmer_path?.trim() && config.usb_port?.trim() &&
    cable && [0,1,5].includes(cable.cable_index) && Number.isInteger(cable.channel))
  const settingsDisabled = replay || busy || loading || unresolvedRequest || !statusKnown
  let reason = ''
  if (replay) reason = '离线回放期间禁止固件切换'
  else if (busy) reason = '固件切换正在进行'
  else if (unresolvedRequest) reason = '上次请求结果未知，请查询任务'
  else if (!statusKnown) reason = '等待任务状态'
  else if (loading) reason = '正在处理设置'
  else if (!configured || dirty) reason = '请先保存工具路径、下载器和 USB 串口'
  else if (needsIsolation && !motorIsolated) reason = '请确认本次操作的电机电源已断开'
  else if (!needsIsolation && !hostReady) reason = '等待有效 Host 身份、新鲜状态和正常会话日志'
  return {settingsDisabled, needsIsolation, canSelect:!reason, reason}
}

export function firmwareSelection({target, origin, readiness, requestId, motorIsolated = false}) {
  const submission = origin === 'user' && readiness?.canSelect && FIRMWARE_TARGETS.includes(target) && requestId
    ? {request_id:requestId, target, motor_isolated:Boolean(readiness.needsIsolation && motorIsolated)} : null
  return {selection:'', motorIsolated:submission ? false : motorIsolated, submission}
}

export function firmwareJobFailure(error, job) {
  const rejected=error.httpStatus>=400 && error.httpStatus<500
  return {...job, state:rejected ? 'rejected' : 'indeterminate',
    message:rejected ? error.message : `${error.message}；结果未知，请查询任务，未重发`}
}

export function firmwarePhaseLabel(phase) {
  return ({idle:'等待选择',submitting:'正在提交',validating:'校验设置与位流',preparing:'等待设备停止',
    checking:'校验设置与位流',stopping:'等待设备停止',closing:'释放原 Host',scanning_cables:'正在扫描下载器',
    preparing_host:'等待设备停止',closing_host:'释放原 Host',scanning:'核验下载器与芯片',
    programming:'下载并校验 SRAM',starting_host:'启动目标 Host',reconnecting:'连接目标 Host',
    verifying:'核验固件身份',verifying_host:'核验固件身份',completed:'切换完成',succeeded:'切换完成',
    failed:'切换失败',unknown:'结果未知',indeterminate:'结果未知',rejected:'请求被拒绝'})[phase] || phase || '等待选择'
}

export function firmwareUsbPort(config = {}, state = {}) {
  if (config.usb_port) return config.usb_port
  const transport = state.transport || {}
  return /^(usb|usb\+ble)$/i.test(transport.mode || '') ? transport.usb_port || transport.port || '' : ''
}
