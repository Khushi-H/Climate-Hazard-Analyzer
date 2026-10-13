const BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')

export function buildQuery(form, extra = {}) {
  const q = new URLSearchParams()
  const r = form.region
  if (r.kind === 'box') {
    q.set('south', Number(r.south).toFixed(2))
    q.set('west', Number(r.west).toFixed(2))
    q.set('north', Number(r.north).toFixed(2))
    q.set('east', Number(r.east).toFixed(2))
  } else {
    q.set('lat', Number(r.lat).toFixed(2))
    q.set('lon', Number(r.lon).toFixed(2))
  }
  if (r.name) q.set('name', r.name.slice(0, 80))
  q.set('start_year', form.startYear)
  q.set('end_year', form.endYear)
  q.set('percentile', form.percentile)
  q.set('min_days', form.minDays)
  q.set('method', form.method)
  q.set('hazard', 'heatwave')
  Object.entries(extra).forEach(([k, v]) => q.set(k, v))
  return q
}

async function getJson(url, signal) {
  const res = await fetch(url, { signal })
  if (!res.ok) {
    let msg = ''
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : j.detail?.[0]?.msg || ''
    } catch {
      /* ignore */
    }
    if (res.status === 429) msg = msg || 'Too many requests. Please wait a moment.'
    throw new Error(msg || `The server returned an error (${res.status}).`)
  }
  return res.json()
}

export const api = {
  meta: () => getJson(`${BASE}/api/meta`),
  geocode: (q, signal) => getJson(`${BASE}/api/geocode?q=${encodeURIComponent(q)}`, signal),
  analysis: (form, signal) => getJson(`${BASE}/api/analysis?${buildQuery(form)}`, signal),
  csvUrl: (form, kind) => `${BASE}/api/analysis/export.csv?${buildQuery(form, { kind })}`,
  pdfUrl: (form) => `${BASE}/api/analysis/export.pdf?${buildQuery(form)}`,
  plotUrl: (form, metric) => `${BASE}/api/analysis/plot.png?${buildQuery(form, { metric, theme: 'light' })}`,
}
