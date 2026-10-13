const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))

export function makeScale(stops) {
  const rgb = stops.map(hex)
  return (t) => {
    const x = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0))
    const p = x * (rgb.length - 1)
    const i = Math.min(Math.floor(p), rgb.length - 2)
    const f = p - i
    const c = rgb[i].map((v, k) => Math.round(v + (rgb[i + 1][k] - v) * f))
    return `rgb(${c[0]},${c[1]},${c[2]})`
  }
}

// Sequential (magnitude): a single orange hue, light to dark.
export const seq = makeScale(['#fde0c8', '#f9a770', '#ec6a2c', '#c43e12', '#7d1f06'])

// Diverging (polarity): blue and red poles with a neutral grey midpoint.
export const div = makeScale(['#1d4e9e', '#5b9bd5', '#e6eaee', '#ef8a62', '#b2182b'])

// Same idea, brightened so every step stays readable on the dark hero band.
export const divDark = makeScale(['#4f9bff', '#8cc2ff', '#eef2f8', '#ff9a6b', '#ff3b4e'])

// Magnitude on a dark background: stronger events glow hotter (amber, orange, red, hot pink).
export const heatDark = makeScale(['#ffc46b', '#ff8a3d', '#ff4d3a', '#ff2a6d'])

// One hard-edged colour stop per year (cooler = blue, hotter = red, relative to the period
// average). Used to fill the big headline number with the same "warming stripes" as the band above.
export function stripeGradient(yearly) {
  const vals = yearly.map((r) => r.mean_tmax)
  const finite = vals.filter((v) => v != null)
  if (!finite.length) return 'none'
  const mean = finite.reduce((a, b) => a + b, 0) / finite.length
  const maxAbs = Math.max(0.15, ...finite.map((v) => Math.abs(v - mean)))
  const n = yearly.length
  const stops = yearly.map((r, i) => {
    const c = r.mean_tmax == null ? '#33405f' : divDark(0.5 + 0.5 * ((r.mean_tmax - mean) / maxAbs))
    return `${c} ${((i / n) * 100).toFixed(3)}% ${(((i + 1) / n) * 100).toFixed(3)}%`
  })
  return `linear-gradient(90deg, ${stops.join(', ')})`
}

export const INK = '#0a1330'
export const SLATE = '#55657f'
export const LINE = '#cbd8e4'