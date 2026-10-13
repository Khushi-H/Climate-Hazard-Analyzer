import { useEffect, useMemo, useRef, useState } from 'react'
import { seq } from '../lib/colors'
import { fmtDate } from '../lib/format'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTH_START_DOY = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
const LEFT = 40
const TOP = 22

const doyOf = (d) => Math.floor((Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - Date.UTC(d.getUTCFullYear(), 0, 0)) / 864e5)

// Year-by-day grid. Every mark is a heatwave day; darker means further above the threshold.
export default function HeatCalendar({ events, startYear, endYear }) {
  const wrap = useRef(null)
  const canvas = useRef(null)
  const [width, setWidth] = useState(900)
  const [tip, setTip] = useState(null)
  const years = endYear - startYear + 1
  const rowH = years <= 20 ? 16 : years <= 40 ? 11 : 7
  const height = TOP + years * rowH + 6

  const { cells, lo, hi } = useMemo(() => {
    const map = new Map()
    let lo = Infinity
    let hi = -Infinity
    for (const e of events) {
      lo = Math.min(lo, e.intensity)
      hi = Math.max(hi, e.intensity)
      const end = new Date(e.end + 'T00:00:00Z')
      for (let d = new Date(e.start + 'T00:00:00Z'); d <= end; d = new Date(d.getTime() + 864e5)) {
        map.set(d.getUTCFullYear() * 1000 + doyOf(d), e)
      }
    }
    return { cells: map, lo, hi }
  }, [events])

  useEffect(() => {
    const el = wrap.current
    if (!el) return undefined
    const ro = new ResizeObserver(() => setWidth(Math.max(320, el.clientWidth)))
    ro.observe(el)
    setWidth(Math.max(320, el.clientWidth))
    return () => ro.disconnect()
  }, [])

  const cellW = (width - LEFT - 6) / 366

  useEffect(() => {
    const c = canvas.current
    if (!c) return
    const dpr = window.devicePixelRatio || 1
    c.width = width * dpr
    c.height = height * dpr
    c.style.width = `${width}px`
    c.style.height = `${height}px`
    const g = c.getContext('2d')
    g.setTransform(dpr, 0, 0, dpr, 0, 0)
    g.clearRect(0, 0, width, height)
    g.font = "11px 'Public Sans', sans-serif"
    g.fillStyle = '#55657f'
    g.textBaseline = 'middle'
    MONTHS.forEach((m, i) => g.fillText(m, LEFT + (MONTH_START_DOY[i] - 1) * cellW, 8))
    for (let r = 0; r < years; r++) {
      const y = startYear + r
      const top = TOP + r * rowH
      g.fillStyle = '#dde7f0'
      g.fillRect(LEFT, top, 366 * cellW, rowH - 1.5)
      if (years <= 20 || y % 5 === 0 || r === 0 || r === years - 1) {
        g.fillStyle = '#55657f'
        g.textAlign = 'right'
        g.fillText(String(y), LEFT - 8, top + rowH / 2)
        g.textAlign = 'left'
      }
      for (let d = 1; d <= 366; d++) {
        const e = cells.get(y * 1000 + d)
        if (!e) continue
        const t = hi > lo ? (e.intensity - lo) / (hi - lo) : 0.5
        g.fillStyle = seq(0.15 + 0.85 * t)
        g.fillRect(LEFT + (d - 1) * cellW, top, Math.max(1, cellW), rowH - 1.5)
      }
    }
  }, [cells, width, height, years, startYear, rowH, cellW, lo, hi])

  const onMove = (ev) => {
    const rect = canvas.current.getBoundingClientRect()
    const x = ev.clientX - rect.left
    const y = ev.clientY - rect.top
    const day = Math.floor((x - LEFT) / cellW) + 1
    const row = Math.floor((y - TOP) / rowH)
    if (day < 1 || day > 366 || row < 0 || row >= years) return setTip(null)
    const e = cells.get((startYear + row) * 1000 + day)
    setTip(e ? { x, y, e } : null)
  }

  return (
    <section className="panel" aria-labelledby="cal-h">
      <div className="panel-head">
        <h2 id="cal-h">When heatwaves happened</h2>
        <p className="sub">Each row is a year and each mark is a heatwave day. Darker marks were further above the threshold.</p>
      </div>
      <div ref={wrap} className="cal-wrap">
        <canvas ref={canvas} onMouseMove={onMove} onMouseLeave={() => setTip(null)} role="img"
          aria-label={`Calendar of ${events.length} heatwave events between ${startYear} and ${endYear}. The events table below lists the same data.`} />
        {tip && (
          <div className="tip" style={{ left: Math.min(tip.x + 14, width - 190), top: tip.y + 14 }}>
            <strong>{fmtDate(tip.e.start)}</strong>
            <span>{tip.e.duration} days, peak {tip.e.peak_temp} {'°C'}</span>
            <span>{tip.e.intensity.toFixed(1)} {'°C'} above threshold on average</span>
          </div>
        )}
      </div>
    </section>
  )
}
