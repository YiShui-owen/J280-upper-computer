const WINDOW_MS = 10000
const PLOT_LEFT = 54
const PLOT_RIGHT = 18
const NUMBER_FONT = 'Consolas, "Courier New", monospace'
const CHANNELS = [
  { field: 'angle_deg', name: '摆杆偏角', unit: '°', color: '#38BDF8', minimum: 2, digits: 3 },
  { field: 'angle_velocity_deg_s', name: '摆杆角速度', unit: '°/s', color: '#A9D4E8', minimum: 5, digits: 1 },
  { field: 'duty_actual_percent', name: 'PWM', unit: '%', color: '#E4B86A', minimum: 65, digits: 1 },
]

function localTime(timestamp) {
  const date = new Date(timestamp)
  const pad = (value, length = 2) => String(value).padStart(length, '0')
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${pad(date.getMilliseconds(), 3)}`
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character])
}

function yExtent(data, channel) {
  if (channel.field === 'duty_actual_percent') return channel.minimum
  const magnitude = data.reduce((maximum, point) => Math.max(maximum, Math.abs(point[1] ?? 0)), 0)
  return Math.max(channel.minimum, Math.ceil(magnitude * 1.12 * 10) / 10)
}

/** Keep tooltip/cursor models alive; graphic components are snapshots so expired overlays disappear. */
export function updateWaveformChart(chart, option) {
  chart.setOption(option, { replaceMerge: ['graphic'], silent: true })
}

/** Pure rendering option: telemetry received_at is seconds; now and event.at are epoch milliseconds. */
export function createWaveformOption(samples, now, height = 500, events = [], width = 600, windowMs = WINDOW_MS) {
  if (!Number.isFinite(now)) throw new TypeError('now must be a finite epoch millisecond timestamp')
  if (![10000, 30000].includes(windowMs)) throw new RangeError('waveform window must be 10000 or 30000 ms')
  const chartHeight = Number.isFinite(height) && height > 0 ? height : 500
  const chartWidth = Number.isFinite(width) && width > 0 ? width : 600
  const start = now - windowMs
  const tickInterval = windowMs === 30000 ? 5000 : 2000
  const tickCount = windowMs / tickInterval
  const plotWidth = Math.max(1, chartWidth - PLOT_LEFT - PLOT_RIGHT)
  const gridHeight = Math.max(1, (chartHeight - 28 - 28 - 2 * 38) / 3)
  const grid = CHANNELS.map((_, index) => ({
    left: PLOT_LEFT, right: PLOT_RIGHT,
    top: 28 + index * (gridHeight + 38), height: gridHeight,
  }))
  const inWindow = (Array.isArray(samples) ? samples : [])
    .filter(sample => sample && Number.isFinite(sample.received_at))
    .map(sample => ({ sample, at: sample.received_at * 1000 }))
    .filter(({ at }) => Number.isFinite(at) && at >= start && at <= now)
    .sort((a, b) => a.at - b.at)
  const series = CHANNELS.map((channel, index) => ({
    id: channel.field,
    name: channel.name,
    type: 'line', xAxisIndex: index, yAxisIndex: index,
    data: inWindow.map(({ sample, at }) => [at, Number.isFinite(sample[channel.field]) ? sample[channel.field] : null]),
    showSymbol: false, smooth: false, connectNulls: false, animation: false,
    lineStyle: { color: channel.color, width: 1.5 },
    itemStyle: { color: channel.color },
    emphasis: { disabled: true },
  }))
  const visibleEvents = (Array.isArray(events) ? events : [])
    .filter(event => event && Number.isFinite(event.at) && event.at >= start && event.at <= now)
  const eventChildren = visibleEvents.flatMap((event, index) => {
    const x = PLOT_LEFT + ((event.at - start) / windowMs) * plotWidth
    const label = String(event.label ?? '')
    const labelWidth = Math.min(plotWidth, Math.max(32, Array.from(label).length * 11 + 12))
    return [
      {
        id: `event-line-${index}`, type: 'line', silent: true, z: 8,
        shape: { x1: x, y1: grid[0].top, x2: x, y2: grid[2].top + gridHeight },
        style: { stroke: '#E4B86A', lineWidth: 1, opacity: 0.65, lineDash: [4, 4] },
      },
      {
        id: `event-label-${index}`, type: 'text', silent: true, z: 9,
        x: Math.max(PLOT_LEFT, Math.min(x + 4, chartWidth - PLOT_RIGHT - labelWidth)),
        y: grid[0].top + 5,
        style: {
          text: label, fill: '#E4B86A', font: '11px sans-serif',
          width: labelWidth, overflow: 'truncate', padding: [2, 4], backgroundColor: '#102032',
        },
      },
    ]
  })

  return {
    animation: false,
    backgroundColor: 'transparent',
    grid,
    title: CHANNELS.map((channel, index) => ({
      text: `${channel.name} · ${channel.unit}`, left: PLOT_LEFT, top: grid[index].top - 24,
      padding: 0, textStyle: { color: channel.color, fontSize: 12, fontWeight: 500 },
    })),
    axisPointer: { link: [{ xAxisIndex: 'all' }], lineStyle: { color: '#7C93A9', width: 1 } },
    tooltip: {
      trigger: 'axis', confine: true, transitionDuration: 0,
      backgroundColor: '#102032', borderColor: '#344A60', textStyle: { color: '#D8E4EF', fontSize: 12, fontFamily: NUMBER_FONT },
      axisPointer: { type: 'line' },
      formatter(params) {
        const points = (Array.isArray(params) ? params : [params]).filter(point => Array.isArray(point?.data))
        if (!points.length) return ''
        return [localTime(points[0].data[0]), ...points.map(point => {
          const channel = CHANNELS.find(item => item.name === point.seriesName)
          const value = Number.isFinite(point.data[1]) ? point.data[1].toFixed(channel?.digits ?? 3) : '—'
          return `${escapeHtml(point.seriesName ?? '')}：${value}${escapeHtml(channel?.unit ?? '')}`
        })].join('<br/>')
      },
    },
    xAxis: CHANNELS.map((_, index) => ({
      type: 'value', gridIndex: index, min: start, max: now, interval: tickInterval,
      axisLabel: { show: false }, axisTick: { show: false },
      axisLine: { show: index === 2, lineStyle: { color: '#344A60' } },
      splitLine: { show: true, lineStyle: { color: 'rgba(132, 161, 184, 0.10)' } },
      axisPointer: { label: { show: index === 2, fontFamily: NUMBER_FONT, formatter: params => localTime(params.value) } },
    })),
    yAxis: CHANNELS.map((channel, index) => {
      const extent = yExtent(series[index].data, channel)
      return {
        type: 'value', gridIndex: index, min: -extent, max: extent, splitNumber: 2,
        ...(channel.field === 'duty_actual_percent' ? { interval: 65 } : {}),
        axisLabel: { color: '#8FA4B8', fontFamily: NUMBER_FONT, fontSize: 10, margin: 8, hideOverlap: true },
        axisTick: { show: false }, axisLine: { show: false },
        splitLine: { show: true, lineStyle: { color: 'rgba(132, 161, 184, 0.12)' } },
        axisPointer: { show: false },
      }
    }),
    series,
    graphic: [
      { id: 'waveform-events', type: 'group', silent: true, children: eventChildren },
      {
        id: 'waveform-time-labels', type: 'group', silent: true,
        children: Array.from({ length: tickCount + 1 }, (_, index) => ({
          type: 'text', x: PLOT_LEFT + index / tickCount * plotWidth, y: grid[2].top + gridHeight + 10,
          style: {
            text: index === tickCount ? '0 s' : `−${(windowMs - index * tickInterval) / 1000} s`,
            fill: '#8FA4B8', font: `10px ${NUMBER_FONT}`,
            align: index === 0 ? 'left' : index === tickCount ? 'right' : 'center',
          },
        })),
      },
    ],
  }
}
